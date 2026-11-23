"""Convert a verified E11-A incremental report into B's fixed-md input.

This is a classroom interface adapter. It does not claim that the two
capabilities are already deployed as separate services.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e11e12"))
from handoff import strict_json, validate_incremental_payload


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_artifact(run_dir: Path, item: dict, job_id: str) -> tuple[Path, bytes]:
    prefix = f"artifact://{job_id}/"
    uri = item.get("uri") if isinstance(item, dict) else None
    if not isinstance(uri, str) or not uri.startswith(prefix):
        raise ValueError("Artifact belongs to another job")
    path = (run_dir / uri[len(prefix) :]).resolve()
    if not path.is_relative_to(run_dir.resolve()) or not path.is_file():
        raise ValueError("Artifact path is missing or outside the run")
    raw = path.read_bytes()
    size = item.get("bytes")
    if hashlib.sha256(raw).hexdigest() != item.get("sha256") or type(size) is not int or len(raw) != size:
        raise ValueError(f"Artifact hash or size mismatch: {path.name}")
    return path, raw


def make_handoff(result_path: Path, target_sha: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", target_sha):
        raise ValueError("Target must be a complete lowercase Git SHA")
    run_dir = result_path.resolve().parent
    result = strict_json(result_path.read_bytes())
    if result.get("schema_version") != "e11e12-1" or result.get("status") != "SUCCEEDED":
        raise ValueError("A task did not succeed with the expected schema")
    if result.get("target_commit") != target_sha:
        raise ValueError("A task belongs to another target commit")
    job_id, trace_id = result["job_id"], result["trace_id"]
    matches = [x for x in result["stages"] if x.get("name") == "incremental-check"]
    if len(matches) != 1:
        raise ValueError("Expected one incremental-check stage")
    stage_item = matches[0]["artifact"]
    _, stage_raw = checked_artifact(run_dir, stage_item, job_id)
    if stage_item["uri"] != f"artifact://{job_id}/incremental-check.json":
        raise ValueError("Unexpected stage artifact path")
    stage = strict_json(stage_raw)
    if (
        stage.get("schema_version") != "e11e12-1"
        or stage.get("kind") != "incremental-check"
        or stage.get("status") != "SUCCEEDED"
        or stage.get("commit") != target_sha
        or stage.get("job_id") != job_id
        or stage.get("trace_id") != trace_id
    ):
        raise ValueError("Incremental report identity or target mismatch")

    artifacts = stage.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Expected a list of incremental-check artifacts")
    payload_path = (run_dir / "incremental-report.json").resolve()
    payload_uri = f"artifact://{job_id}/incremental-report.json"
    payloads = []
    for item in artifacts:
        path, raw = checked_artifact(run_dir, item, job_id)
        if path == payload_path:
            if item["uri"] != payload_uri:
                raise ValueError("Unexpected incremental-report.json artifact URI")
            payloads.append(raw)
    if len(payloads) != 1:
        raise ValueError("Expected exactly one incremental-report.json artifact")
    validate_incremental_payload(strict_json(payloads[0]), stage.get("data"), target_sha)
    return {
        "schema_version": "e11e12-1",
        "kind": "fixed-md",
        "status": "SUCCEEDED",
        "commit": target_sha,
        "data": stage["data"],
        "source_report": {
            "job_id": job_id,
            "trace_id": trace_id,
            "uri": stage_item["uri"],
            "sha256": stage_item["sha256"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a-result", required=True, type=Path)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output already exists; preserve earlier evidence")
    report = make_handoff(args.a_result, args.target_sha)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("HANDOFF_READY", f"sha256={digest(args.out)}", f"source_job={report['source_report']['job_id']}")


if __name__ == "__main__":
    main()
