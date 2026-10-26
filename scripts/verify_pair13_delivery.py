"""Read-only verification of the real E6 Pair13 candidate handoff."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from validate_e2_v2 import safe, validate_report

ROOT = Path(__file__).resolve().parents[1]


def verify():
    folder = ROOT / "contracts/artifacts/e6-241870063"
    hashes = json.loads((folder / "SHA256SUMS.json").read_text())
    for name, expected in hashes.items():
        if not safe(name) or hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Candidate handoff SHA256 mismatch: " + name)
    checked = 0
    reports = []
    for stage in ("before", "after"):
        report = json.loads((folder / stage / "report-v2.json").read_text())
        registry = json.loads((folder / stage / "producer-registration.json").read_text())
        errors = validate_report(report)
        if errors:
            raise ValueError("; ".join(errors))
        if report["producer_job_id"] != registry["producer_job_id"] or registry["http_job_api_deployed"]:
            raise ValueError("CLI producer registration mismatch")
        uris = set()
        for locator in registry["artifacts"].values():
            commit, path = locator["repository_commit"], locator["repository_path"]
            if not re.fullmatch(r"[0-9a-f]{40}", commit) or not safe(path):
                raise ValueError("Unsafe immutable source locator")
            raw = subprocess.check_output(["git", "show", commit + ":" + path], cwd=ROOT)
            if hashlib.sha256(raw).hexdigest() != locator["sha256"]:
                raise ValueError("Immutable Git blob SHA256 mismatch: " + path)
            uris.add(locator["uri"])
            checked += 1
        for finding in report["findings"]:
            for anchor in finding["evidence"]:
                if "uri" in anchor and anchor["uri"] not in uris:
                    raise ValueError("Evidence URI has no registered locator")
        if report["artifact_locator"] != registry["source_report"]:
            raise ValueError("Source report locator mismatch")
        reports.append(report)
    if reports[0]["configuration_id"] != reports[1]["configuration_id"]:
        raise ValueError("Before/after configurations differ")
    findings = {(f["type"], f["target"], f["dependency"]) for f in reports[0]["findings"]}
    if findings != {("MISSING", "main.o", "config.h"), ("REDUNDANT", "main.o", "unused.h")}:
        raise ValueError("Unexpected real E6 findings")
    if reports[1]["findings"]:
        raise ValueError("Fixed result is not empty")
    return {"passed": True, "reports": 2, "hashed_files": len(hashes),
            "immutable_source_locators": checked,
            "contract_status": "PROPOSED_PENDING_B13_REVIEW"}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
