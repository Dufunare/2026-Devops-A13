"""Member C (241830217) repeatable E13 *teaching-fixture* checks.

C4 timeout/cleanup + recovery; C7 failed-to-successful task isolation;
C8 isolated single-worker HTTP API, replay, 409 and downloaded artifact hashes.

This does not implement C1-C3, C5, B13 cross-machine acceptance, or E14 release.
It uses new evidence directories and never stops other people's Docker resources.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data/integration-sample"
SCANNER = ROOT / "labs/e13e14/scan_runtime_logs.py"


class GateError(RuntimeError):
    pass


def require(test: bool, message: str) -> None:
    if not test:
        raise GateError(message)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_bytes())
    require(isinstance(data, dict), f"Expected JSON object: {path}")
    return data


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def command(args: list[str], *, timeout: int = 40) -> str:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    require(result.returncode == 0, f"Command failed: {args[0]} {args[1:3]}: {result.stderr[-500:]}")
    return result.stdout.strip()


def artifact_bytes_check(root: Path, result: dict) -> int:
    job = result["job_id"]
    prefix = f"artifact://{job}/"
    items = result.get("artifacts")
    require(isinstance(items, list) and items, "No artifact list")
    seen = set()
    for item in items:
        uri = item.get("uri")
        require(isinstance(uri, str) and uri.startswith(prefix), "Wrong artifact job")
        relative = uri[len(prefix):]
        require(relative not in seen and relative != "", f"Duplicate/empty URI: {relative}")
        require(all(x not in ("", ".", "..", ".git") for x in relative.split("/"))
                and "\\" not in relative, "Unsafe artifact path")
        path = (root / relative).resolve()
        require(path.is_relative_to(root.resolve()) and path.is_file(), f"Artifact missing: {relative}")
        raw = path.read_bytes()
        require(sha_bytes(raw) == item["sha256"] and len(raw) == item["bytes"],
                f"Artifact bytes/hash mismatch: {relative}")
        seen.add(relative)
    return len(seen)


def run_local(request: Path, out: Path, label: str, evidence: Path, timeout: int = 1200) -> tuple[int, dict]:
    require(request.is_file() and not out.exists(), f"Missing request / existing OUT: {request} {out}")
    log = evidence / f"{label}.console.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    args = [sys.executable, "run_e11e12.py", "run", "--request",
            request.relative_to(ROOT).as_posix(), "--out", out.relative_to(ROOT).as_posix()]
    with log.open("wb") as stream:
        try:
            completed = subprocess.run(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise GateError(f"Runner timeout for {label}; see {log}") from exc
    result_path = out / "result.json"
    require(result_path.is_file(), f"No result.json for {label}; see {log}")
    return completed.returncode, load_json(result_path)


def file_snapshot(root: Path) -> dict:
    data = {}
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_file():
                raw = path.read_bytes()
                data[path.relative_to(root).as_posix()] = {"bytes": len(raw), "sha256": sha_bytes(raw)}
    return data


def c4(evidence: Path) -> dict:
    src = load_json(SAMPLE / "e12.json")
    src["build_timeout"] = 0.01
    request = evidence / "inputs/c4-timeout.json"
    write_json(request, src)
    bad_out = evidence / "c4-timeout"
    rc, bad = run_local(request, bad_out, "c4-timeout", evidence)
    inner = load_json(bad_out / "draft-build/result.json")
    require(rc != 0 and bad.get("status") == "FAILED", "C4 timeout reported success")
    require(bad.get("error", {}).get("code") == "DRAFT_FAILED", "C4 outer error mismatch")
    require(inner.get("status") == "TIMED_OUT", "C4 DRAFT did not time out")
    before = file_snapshot(bad_out / "draft-build")
    write_json(evidence / "c4-files-before.json", before)
    time.sleep(3)
    after = file_snapshot(bad_out / "draft-build")
    write_json(evidence / "c4-files-after.json", after)
    require(before == after, "C4 timed-out DRAFT files changed after terminal result")
    # Observe only processes identifiable with this task's unique OUT path.
    # Unrelated students may be building at the same time: do not kill or
    # misclassify their Docker work.
    process = subprocess.run(["ps", "-eo", "pid=,ppid=,args="], cwd=ROOT,
                             capture_output=True, text=True, timeout=15)
    require(process.returncode == 0, "Unable to inspect process list for C4")
    build_processes = [line for line in process.stdout.splitlines()
                       if "docker build" in line and str(bad_out) in line]
    (evidence / "c4-build-process-check.txt").write_text(
        "\n".join(build_processes) + "\n", encoding="utf-8")
    require(not build_processes, "C4 task-specific Docker build process remains")

    # A normal task proves the failed run did not poison subsequent work.
    good_request = SAMPLE / "e11-a.json"
    good_out = evidence / "c4-recovery"
    good_rc, good = run_local(good_request, good_out, "c4-recovery", evidence)
    require(good_rc == 0 and good["status"] == "SUCCEEDED", "C4 recovery failed")
    require(good["job_id"] != bad["job_id"] and good["trace_id"] != bad["trace_id"],
            "C4 recovery reused failed task identity")
    count = artifact_bytes_check(good_out, good)
    result = {"status": "PASS", "timeout_rc": rc, "timeout_error": bad["error"],
              "draft_status": inner["status"], "timeout_job": bad["job_id"],
              "recovery_job": good["job_id"], "recovery_trace": good["trace_id"],
              "recovery_artifacts_verified": count, "late_file_writes_observed": False,
              "task_specific_build_processes_observed": len(build_processes),
              "note": "3-second file stability and task-path process sample; not full daemon attestation"}
    write_json(evidence / "c4-summary.json", result)
    print("C4_TIMEOUT_AND_RECOVERY=PASS", flush=True)
    return result


def c7(evidence: Path) -> dict:
    src = load_json(SAMPLE / "e11-a.json")
    src["base"] = "0" * 40
    request = evidence / "inputs/c7-invalid-base.json"
    write_json(request, src)
    bad_out = evidence / "c7-failed"
    bad_rc, bad = run_local(request, bad_out, "c7-failed", evidence)
    require(bad_rc != 0 and bad.get("status") == "FAILED", "C7 negative task did not fail")
    good_out = evidence / "c7-success"
    good_rc, good = run_local(SAMPLE / "e11-a.json", good_out, "c7-success", evidence)
    require(good_rc == 0 and good["status"] == "SUCCEEDED", "C7 success task failed")
    require(bad["job_id"] != good["job_id"] and bad["trace_id"] != good["trace_id"],
            "C7 identities not isolated")
    count = artifact_bytes_check(good_out, good)
    result = {"status": "PASS", "negative_exit": bad_rc,
              "negative_error": bad.get("error"), "negative_job": bad["job_id"],
              "positive_job": good["job_id"], "positive_trace": good["trace_id"],
              "positive_artifacts_verified": count,
              "scope": "Sequential invalid-base-to-success fixture, not concurrent build-crash isolation"}
    write_json(evidence / "c7-summary.json", result)
    print("C7_FAILURE_ISOLATION=PASS", flush=True)
    return result


def http_call(base: str, method: str, path: str, payload: dict | None = None,
              timeout: int = 30) -> tuple[int, dict | bytes, dict]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = Request(base + path, data=data, method=method, headers=headers)
    try:
        response = urlopen(req, timeout=timeout)
    except HTTPError as err:
        response = err
    with response:
        status = response.status
        raw = response.read()
        response_headers = {k.lower(): v for k, v in response.headers.items()}
    if path.find("/files/") >= 0:
        return status, raw, response_headers
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as ex:
        raise GateError(f"Invalid HTTP JSON at {path}: {raw[:100]!r}") from ex
    require(isinstance(body, dict), "HTTP JSON not object")
    return status, body, response_headers


def c8(evidence: Path, image: str, port: int, wait_seconds: int) -> dict:
    # Use a distinct host port and a *separate* /course/work mount to ensure this
    # server cannot share the Store database with another student's API process.
    server_work = evidence / "c8-api-private-work"
    server_work.mkdir(parents=True, exist_ok=False)
    require(not any(server_work.iterdir()), "C8 private work is not empty")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", port))
    ident = "e13c8-" + uuid.uuid4().hex[:15]
    base = f"http://127.0.0.1:{port}"
    docker_gid = str(Path("/var/run/docker.sock").stat().st_gid)
    args = ["docker", "run", "-d", "--rm", "--name", ident,
            "--network", "bridge", "--group-add", docker_gid,
            "--cap-add", "SYS_PTRACE", "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-p", f"127.0.0.1:{port}:8080", "-e", "HOME=/tmp",
            "-e", "PYTHONPATH=/course/labs/e11e12:/course/labs/e8e10:/course/labs/e11e12/vendor:/app",
            "-v", f"{ROOT}:/course", "-v", f"{server_work.resolve()}:/course/work",
            "-w", "/course", image, "python3", "labs/e11e12/server.py",
            "--host", "0.0.0.0"]
    created = False
    try:
        output = command(args, timeout=40)
        created = True
        (evidence / "c8-api-container-id.txt").write_text(output + "\n", encoding="utf-8")
        end = time.monotonic() + 45
        while time.monotonic() < end:
            try:
                status, health, _ = http_call(base, "GET", "/health", timeout=3)
                if status == 200 and health.get("schema_version") == "e11e12-1":
                    break
            except (URLError, TimeoutError, OSError):
                pass
            time.sleep(1)
        else:
            raise GateError("C8 isolated API did not become healthy")
        original = load_json(SAMPLE / "e11-a.json")
        key = "e13-c-241830217-" + uuid.uuid4().hex
        payload = {"input": original, "idempotency_key": key}
        write_json(evidence / "c8-request.json", payload)
        first_code, first, _ = http_call(base, "POST", "/v1/jobs", payload)
        write_json(evidence / "c8-first.json", first)
        require(first_code == 202 and first.get("job_id", "").startswith("job-"), "C8 first POST invalid")
        job = first["job_id"]
        duplicate_code, dup, _ = http_call(base, "POST", "/v1/jobs", payload)
        write_json(evidence / "c8-duplicate.json", dup)
        require(duplicate_code == 202 and dup.get("job_id") == job, "C8 duplicate created job")
        conflict = copy.deepcopy(payload)
        conflict["input"]["target"] = "0" * 40
        write_json(evidence / "c8-conflict-request.json", conflict)
        conflict_code, refused, _ = http_call(base, "POST", "/v1/jobs", conflict)
        write_json(evidence / "c8-conflict-response.json", refused)
        require(conflict_code == 409 and refused.get("error") == "IDEMPOTENCY_CONFLICT",
                "C8 same key with different input was not rejected")
        deadline = time.monotonic() + wait_seconds
        polls = []
        while time.monotonic() < deadline:
            poll_code, state, _ = http_call(base, "GET", f"/v1/jobs/{job}")
            require(poll_code == 200 and state.get("job_id") == job, "C8 status/job mismatch")
            polls.append(state)
            if state["status"] in ("SUCCEEDED", "FAILED", "TIMED_OUT"):
                break
            time.sleep(2)
        else:
            write_json(evidence / "c8-polls.json", polls)
            raise GateError("C8 API polling deadline exceeded")
        write_json(evidence / "c8-polls.json", polls)
        write_json(evidence / "c8-terminal-state.json", state)
        require(state["status"] == "SUCCEEDED", f"C8 API job did not succeed: {state}")
        code, result, _ = http_call(base, "GET", f"/v1/jobs/{job}/artifacts")
        require(code == 200 and result.get("job_id") == job, "C8 artifact manifest failed")
        write_json(evidence / "c8-artifact-index.json", result)
        prefix = f"artifact://{job}/"
        names = set()
        for entry in result["artifacts"]:
            uri = entry["uri"]
            require(uri.startswith(prefix), "C8 wrong artifact URI")
            name = uri[len(prefix):]
            require(name not in names and name != "" and
                    all(p not in ("", ".", "..", ".git") for p in name.split("/")),
                    "C8 duplicate/unsafe artifact")
            names.add(name)
            status, raw, headers = http_call(base, "GET", f"/v1/jobs/{job}/files/{quote(name, safe='/')}")
            require(status == 200 and isinstance(raw, bytes), f"C8 HTTP file error: {name}")
            require(sha_bytes(raw) == entry["sha256"] == headers.get("x-content-sha256")
                    and len(raw) == entry["bytes"], f"C8 HTTP file hash mismatch: {name}")
        after_code, after, _ = http_call(base, "POST", "/v1/jobs", payload)
        require(after_code == 202 and after.get("job_id") == job and after.get("status") == "SUCCEEDED",
                "C8 repeat after completion failed")
        write_json(evidence / "c8-completed-replay.json", after)
        jobs = list((server_work / "api-jobs").glob("job-*/state.json"))
        require(len(jobs) == 1 and jobs[0].parent.name == job,
                "C8 duplicate/409 created extra job in private store")
        result_summary = {"status": "PASS", "job_id": job, "trace_id": state.get("trace_id"),
                          "first_http": first_code, "duplicate_http": duplicate_code,
                          "conflict_http": conflict_code, "completed_replay_http": after_code,
                          "new_jobs": len(jobs), "http_artifacts_verified": len(names),
                          "api_container_name": ident, "api_private_store": str(server_work),
                          "scope": "Single local API; not cross-machine B13 formal receipt"}
        write_json(evidence / "c8-summary.json", result_summary)
        print("C8_LOCAL_API_IDEMPOTENCY=PASS", flush=True)
        return result_summary
    finally:
        if created:
            # Capture this container's own logs/inspect before removing it.
            # Never stop an existing project or unrelated student container.
            try:
                observed = subprocess.run(["docker", "logs", "--timestamps", ident], cwd=ROOT,
                                          capture_output=True, text=True, timeout=20)
                (evidence / "c8-api-service.log").write_text(
                    observed.stdout + observed.stderr, encoding="utf-8")
                inspection = subprocess.run(["docker", "inspect", ident], cwd=ROOT,
                                            capture_output=True, text=True, timeout=20)
                (evidence / "c8-api-inspect.json").write_text(
                    inspection.stdout if inspection.returncode == 0 else "[]\n", encoding="utf-8")
            finally:
                cleanup = subprocess.run(["docker", "rm", "-f", ident], cwd=ROOT,
                                         capture_output=True, text=True, timeout=30)
                (evidence / "c8-api-cleanup.log").write_text(
                    f"container={ident}\nexit={cleanup.returncode}\n{cleanup.stdout}{cleanup.stderr}",
                    encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, help="New directory below work/")
    p.add_argument("--image", required=True, help="Built course-e11e12:<numeric-id> tag")
    p.add_argument("--api-port", type=int, default=18095)
    p.add_argument("--max-wait", type=int, default=600)
    args = p.parse_args()
    out = (ROOT / args.out).resolve()
    work = (ROOT / "work").resolve()
    require(out.is_relative_to(work) and out != work, "Evidence must be below work/")
    require(not out.exists(), f"Output already exists: {out}")
    require(1024 <= args.api_port <= 65535, "API port out of range")
    sid = command(["git", "config", "--local", "user.name"])
    require(sid.isdigit() and args.image == f"course-e11e12:{sid}",
            f"Image must match git config user.name: {sid}")
    for name in ("e11-a.json", "e12.json"):
        require((SAMPLE / name).is_file(), f"Missing prepared request: {name}; run prepare first")
    image_id = command(["docker", "image", "inspect", args.image, "--format", "{{.Id}}"])
    out.mkdir(parents=True)
    write_json(out / "environment.json", {
        "student": sid, "source_commit": command(["git", "rev-parse", "HEAD"]),
        "working_tree_status": command(["git", "status", "--porcelain"]),
        "image_tag": args.image, "image_id": image_id,
        "input_sha256": {name: sha_bytes((SAMPLE / name).read_bytes())
                         for name in ("e11-a.json", "e12.json")},
        "scope": "Fixed teaching fixture gate (not final pair E13 acceptance)"
    })
    sections = {}
    try:
        sections["C4"] = c4(out)
        sections["C7"] = c7(out)
        sections["C8"] = c8(out, args.image, args.api_port, args.max_wait)
        scan = subprocess.run([sys.executable, str(SCANNER), str(out)], cwd=ROOT,
                              capture_output=True, text=True, timeout=120)
        (out / "runtime-log-scan.txt").write_text(scan.stdout + scan.stderr, encoding="utf-8")
        require(scan.returncode == 0, f"C6 log scan failed: {scan.returncode}")
        sections["C6_LOGS"] = {"status": "PASS", "exit_code": scan.returncode,
                               "note": "This covers generated work logs only; source/history/image audited separately"}
        write_json(out / "summary.json", {"passed": True, "sections": sections})
        print("E13_MEMBER_C_FIXTURE_GATE=PASS", flush=True)
        return 0
    except (GateError, OSError, ValueError, subprocess.TimeoutExpired, AssertionError) as error:
        write_json(out / "summary.json", {"passed": False, "sections": sections,
                                          "error_type": type(error).__name__, "error": str(error)})
        print("E13_MEMBER_C_FIXTURE_GATE=FAIL", type(error).__name__, str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
