"""Fail-closed E14 inspection of B/A DRAFT-image child-container evidence.

Verification reads one job's *actual* Docker inspect originals; a claimed
image ID or a historic exec.json alone is never accepted as attestation.
This does not implement or invoke the downstream executor.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

IMAGE_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
TAG_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}\Z")

# B's known real08 path uses these tags. Additional tags will also be checked.
REAL08_TAGS = (
    "full-check-baseline", "scan-baseline",
    "full-check-target", "scan-target",
    "validate-01-make", "validate-02-make",
    "validate-03-toml-json", "validate-04-make",
    "validate-recheck-scan", "full-check-recheck",
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def read_json(path: Path):
    require(path.is_file() and not path.is_symlink(), f"EXEC_EVIDENCE_MISSING: {path.name}")
    return json.loads(path.read_bytes())


def verify_exec(record: dict, inspect: object, expected_image: str,
                expected_course_source: str) -> dict:
    """Validate original inspect fields, not just fields echoed by the executor."""
    require(isinstance(expected_image, str) and IMAGE_RE.fullmatch(expected_image),
            "EXEC_EXPECTED_IMAGE_INVALID")
    require(isinstance(expected_course_source, str) and
            Path(expected_course_source).is_absolute() and
            str(Path(expected_course_source)) == expected_course_source,
            "EXEC_COURSE_SOURCE_INVALID")
    require(isinstance(record, dict), "EXEC_RECORD_INVALID")
    require(record.get("image") == expected_image, "EXEC_REPORTED_IMAGE_MISMATCH")
    require(record.get("inspect_image") == expected_image, "EXEC_REPORTED_INSPECT_MISMATCH")
    require(record.get("exit") == 0 and type(record.get("exit")) is int,
            "EXEC_COMMAND_FAILED")
    require(record.get("inspect_exit_code") == 0 and type(record.get("inspect_exit_code")) is int,
            "EXEC_REPORTED_EXIT_FAILED")
    require(record.get("cleanup_exit") == 0 and type(record.get("cleanup_exit")) is int,
            "EXEC_CLEANUP_FAILED")
    declared = record.get("inspect_mounts")
    require(isinstance(declared, list) and all(isinstance(x, str) for x in declared),
            "EXEC_REPORTED_MOUNTS_MISSING")
    # This check deliberately works on B's legacy handoff, even without a raw
    # inspect original, and explicitly rejects the historical socket leak.
    require("/var/run/docker.sock" not in declared, "EXEC_DOCKER_SOCKET_EXPOSED")
    require(isinstance(inspect, list) and len(inspect) == 1 and isinstance(inspect[0], dict),
            "EXEC_INSPECT_INVALID")
    actual = inspect[0]
    cid = record.get("container_id")
    require(isinstance(cid, str) and len(cid) >= 12 and actual.get("Id") == cid,
            "EXEC_CONTAINER_ID_MISMATCH")
    require(actual.get("Image") == expected_image, "EXEC_ACTUAL_IMAGE_MISMATCH")
    state = actual.get("State")
    require(isinstance(state, dict) and state.get("ExitCode") == 0
            and type(state.get("ExitCode")) is int, "EXEC_ACTUAL_EXIT_FAILED")
    mounts = actual.get("Mounts")
    require(isinstance(mounts, list) and all(isinstance(m, dict) for m in mounts),
            "EXEC_ACTUAL_MOUNTS_MISSING")
    destinations = [m.get("Destination") for m in mounts]
    require(destinations == declared, "EXEC_MOUNTS_RECORD_MISMATCH")
    require("/var/run/docker.sock" not in destinations, "EXEC_DOCKER_SOCKET_EXPOSED")
    # Allow only the shared teaching worktree. Any additional writable mount
    # requires explicit new review rather than automatic acceptance.
    require(len(destinations) == 1 and destinations[0] == "/course",
            "EXEC_UNAPPROVED_MOUNT")
    require(mounts[0].get("Type") == "bind", "EXEC_COURSE_MOUNT_NOT_BIND")
    require(mounts[0].get("Source") == expected_course_source,
            "EXEC_COURSE_SOURCE_MISMATCH")
    return {"tag": record.get("tag"), "container_id": cid,
            "image": actual["Image"], "exit_code": state["ExitCode"],
            "mount_destinations": destinations, "course_source": expected_course_source,
            "socket_exposed": False,
            "cleanup_exit": record["cleanup_exit"]}


def verify_job(evidence_dir: Path, expected_image: str,
               expected_course_source: str, required_tags=REAL08_TAGS) -> dict:
    """Require fresh per-job exec and inspect originals for EVERY declared step."""
    directory = Path(evidence_dir).resolve()
    require(directory.is_dir(), "EXEC_EVIDENCE_DIRECTORY_MISSING")
    require(isinstance(expected_image, str) and IMAGE_RE.fullmatch(expected_image),
            "EXEC_EXPECTED_IMAGE_INVALID")
    tags = tuple(required_tags)
    require(bool(tags) and len(set(tags)) == len(tags)
            and all(isinstance(t, str) and TAG_RE.fullmatch(t) for t in tags),
            "EXEC_REQUIRED_TAGS_INVALID")
    files = sorted(directory.glob("*.exec.json"))
    require(bool(files), "EXEC_RECORDS_MISSING")
    found = {}
    for path in files:
        require(not path.is_symlink(), "EXEC_SYMLINK_REJECTED")
        tag = path.name.removesuffix(".exec.json")
        require(TAG_RE.fullmatch(tag) and tag not in found, "EXEC_TAG_INVALID")
        record = read_json(path)
        require(record.get("tag") == tag, "EXEC_TAG_MISMATCH")
        # Legacy B real08 records must be rejected for the actual socket leak,
        # even though the ZIP only carries an exec summary, not inspect JSON.
        declared = record.get("inspect_mounts", [])
        require(isinstance(declared, list), "EXEC_REPORTED_MOUNTS_MISSING")
        require("/var/run/docker.sock" not in declared, "EXEC_DOCKER_SOCKET_EXPOSED")
        inspection = read_json(directory / f"{tag}.inspect.json")
        found[tag] = verify_exec(record, inspection, expected_image,
                                 expected_course_source)
    missing = set(tags) - set(found)
    require(not missing, "EXEC_REQUIRED_STEPS_MISSING: " + ",".join(sorted(missing)))
    return {"status": "EXECUTION_ATTESTED", "image": expected_image,
            "course_source": expected_course_source,
            "required_tags": list(tags), "verified_tags": sorted(found),
            "containers": found, "downstream_container_attested": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--expected-image", required=True)
    parser.add_argument("--course-source", required=True,
                        help="Exact host worktree directory expected at /course")
    parser.add_argument("--tag", action="append", dest="tags")
    args = parser.parse_args()
    try:
        result = verify_job(args.evidence_dir, args.expected_image,
                            args.course_source,
                            args.tags if args.tags else REAL08_TAGS)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "EXECUTION_ATTESTATION_FAILED",
                          "error": str(exc), "downstream_container_attested": False}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
