"""Export an audited real CLI result to the PROPOSED Pair13 v2 format.

Completed CLI producer registrations are persisted alongside the report. They
identify existing trace IDs; they do not assert that an HTTP Job API exists.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

from validate_e2_v2 import safe, validate_report
from verify_e7_a_evidence import verify_input, verify_raw_anchors


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_export(report_path, root, repository_url, source_commit,
                 evidence_commit, configuration_id, environment):
    root, report_path = Path(root).resolve(), Path(report_path).resolve()
    for value in (source_commit, evidence_commit):
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise ValueError("Use a complete 40-hex commit")
    report_path.relative_to(root)
    raw = json.loads(report_path.read_text())
    if (raw.get("status") != "SUCCEEDED" or raw.get("clean_exit_code") != 0
            or raw.get("build_exit_code") != 0):
        raise ValueError("Only successfully completed detector runs can be exported")
    trace_id = raw.get("trace_id", "")
    if not re.fullmatch(r"[A-Za-z0-9-]+", trace_id):
        raise ValueError("The source must have a safe, recorded trace_id")
    if not configuration_id or not repository_url:
        raise ValueError("Repository and configuration identity are required")
    allowed_environment = {"os", "arch", "make_version", "cc_version", "image_ref"}
    if set(environment) - allowed_environment or not all(environment.get(k) for k in ("os", "arch")):
        raise ValueError("Environment must match the proposed contract")
    case = report_path.parent.parent
    verify_input(case, raw)
    verify_raw_anchors(case, raw)
    evidence_root = report_path.parent
    job = "job-cli-" + trace_id
    uri_root = "artifact://pair13/" + job + "/"
    artifacts = {}
    for path in sorted(evidence_root.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink():
            raise ValueError("Source artifacts must not be symlinks")
        path.resolve().relative_to(evidence_root)
        name = path.relative_to(evidence_root).as_posix()
        artifacts[name] = {
            "uri": uri_root + name,
            "repository_url": repository_url,
            "repository_commit": evidence_commit,
            "repository_path": path.relative_to(root).as_posix(),
            "sha256": digest(path),
        }
    findings = []
    makefile = evidence_root / "project/Makefile"
    for index, finding in enumerate(raw["findings"], 1):
        if not safe(finding["target"]) or not safe(finding["dependency"]):
            raise ValueError("Target and dependency must be project-relative paths")
        matches = []
        if makefile.is_file():
            matches = [(number, line) for number, line in enumerate(makefile.read_text().splitlines(), 1)
                       if line.startswith(finding["target"] + ":")]
        if len(matches) == 1:
            number, declaration = matches[0]
            location = {"status": "RESOLVED", "path": "Makefile", "line": number,
                        "declaration": declaration}
        else:
            location = {"status": "UNRESOLVED", "reason": "No unique explicit Makefile declaration"}
        anchors = []
        for anchor in finding["evidence"]:
            if anchor["source"] == "system_call":
                name = "trace/" + anchor["trace_file"]
                if anchor["pid"] != int(anchor["trace_file"].split(".")[1]):
                    raise ValueError("Trace PID and file name disagree")
                line = (evidence_root / name).read_text().splitlines()[anchor["line"] - 1]
                anchors.append({"kind": "SYSTEM_CALL", "detail":
                                f"{name}:{anchor['line']} PID {anchor['pid']}: {line}",
                                "uri": artifacts[name]["uri"]})
            else:
                anchors.append({"kind": "MAKE_DATABASE", "detail":
                                f"make-db.txt:{anchor['line']}: {anchor['declaration']}",
                                "uri": artifacts["make-db.txt"]["uri"]})
        if finding["type"] == "MISSING":
            anchors.append({"kind": "DECLARATION_ABSENCE", "detail":
                            "Declared prerequisites: " + ", ".join(finding["declared_dependencies"])})
        else:
            anchors.append({"kind": "EXECUTION_ABSENCE", "detail": finding.get("scope", raw["scope"])})
        findings.append({"finding_id": f"{trace_id}-{index}", "type": finding["type"],
                         "target": finding["target"], "dependency": finding["dependency"],
                         "location": location, "evidence": anchors})
    result = {
        "schema_version": "2.0", "report_id": "pair13-cli-" + trace_id,
        "repository": {"url": repository_url, "commit": source_commit},
        "configuration_id": configuration_id, "environment": copy.deepcopy(environment),
        "detector": "BUILDCHECKER", "producer_job_id": job,
        "provenance": "Adapted from an audited real BuildChecker teaching CLI execution; "
                      "the persisted producer registration aliases its existing trace_id, not an HTTP Job API.",
        "findings": findings, "artifact_locator": artifacts[report_path.name],
        "extensions": {
            "pair13.contract_status": "PROPOSED_PENDING_B13_REVIEW",
            "a13.source_trace_id": trace_id,
            "a13.input_sha256": raw["input_sha256"],
            "a13.source_worktree": "The Git commit denotes the base revision; the isolated input "
                                   "snapshot, including any repaired Makefile, is identified by input hashes.",
        },
    }
    errors = validate_report(result)
    if errors:
        raise ValueError("; ".join(errors))
    registration = {
        "kind": "COMPLETED_CLI_PRODUCER_REGISTRATION", "producer_job_id": job,
        "recorded_source_trace_id": trace_id, "http_job_api_deployed": False,
        "source_code_commit": source_commit, "configuration_id": configuration_id,
        "source_report": artifacts[report_path.name], "artifacts": artifacts,
    }
    return result, registration


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--context", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    context = json.loads(args.context.read_text())
    report, registration = build_export(args.report, args.root, **context)
    if args.out.exists():
        raise ValueError("Use a fresh output directory")
    args.out.mkdir(parents=True)
    for name, value in [("report-v2.json", report), ("producer-registration.json", registration)]:
        (args.out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"report_id": report["report_id"], "findings": len(report["findings"]),
                      "contract_status": "PROPOSED_PENDING_B13_REVIEW"}))


if __name__ == "__main__":
    main()
