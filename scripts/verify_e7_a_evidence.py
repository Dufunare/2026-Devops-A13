#!/usr/bin/env python3
"""Offline, read-only verification of a real E7-A gate's saved evidence.

This checks provenance and internal consistency; it does not execute Docker
or replace the real E7 gate. Reference teaching logs are not accepted as
evidence of an A13 run.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

CASES = (
    "unit-tests", "original-1", "original-2", "original-3",
    "fixed", "build-failed", "unsupported", "timeout",
)
ORIGINAL = {
    ("MISSING", "main.o", "config.h"),
    ("REDUNDANT", "main.o", "unused.h"),
}
HEX = re.compile(r"^[0-9a-f]{64}$")
TRACE_FILE = re.compile(r"^t\.[0-9]+$")


class EvidenceError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise EvidenceError(message)


def load_json(path):
    need(path.is_file(), f"Missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def source_line(path, number):
    need(isinstance(number, int) and not isinstance(number, bool) and number > 0,
         f"Invalid source line: {path} [{number}]")
    need(path.is_file(), f"Evidence source missing: {path}")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    need(number <= len(lines), f"Evidence line out of range: {path}:{number}")
    return lines[number - 1]


def findings_set(report):
    items = report.get("findings")
    need(isinstance(items, list), "Missing findings array")
    found = [(x["type"], x["target"], x["dependency"]) for x in items]
    need(len(found) == len(set(found)), "Duplicate finding")
    return set(found)


def graph_edges(path, observed=None):
    items = load_json(path)
    need(isinstance(items, list), f"Graph is not a list: {path}")
    result = set()
    for row in items:
        edge = (row["target"], row["dependency"])
        need(all(isinstance(x, str) and x for x in edge), f"Invalid graph edge: {path}")
        if observed is None or row["target"] in observed:
            need(edge not in result, f"Duplicate graph edge: {edge}")
            result.add(edge)
    return result


def verify_input(case_dir, report):
    inputs = report.get("input_sha256")
    need(isinstance(inputs, dict) and inputs, "Missing input_sha256")
    source = case_dir / "fixture"
    need(source.is_dir(), f"Missing fixture: {source}")
    actual_files = {p.relative_to(source).as_posix(): p for p in source.rglob("*") if p.is_file()}
    need(set(inputs) == set(actual_files),
         f"Input file names differ in {case_dir.name}")
    for name, file in actual_files.items():
        need(not file.is_symlink(), f"Unexpected input symlink: {name}")
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        need(HEX.fullmatch(inputs[name]) is not None and inputs[name] == digest,
             f"Input SHA256 mismatch in {case_dir.name}: {name}")
    return inputs


def verify_raw_anchors(case_dir, report):
    evidence_dir = case_dir / "evidence"
    for finding in report["findings"]:
        kind, target, dependency = finding["type"], finding["target"], finding["dependency"]
        anchors = finding.get("evidence")
        need(isinstance(anchors, list) and anchors,
             f"Missing evidence anchors: {kind}/{target}/{dependency}")
        matched = False
        for anchor in anchors:
            need(isinstance(anchor, dict), "Malformed evidence anchor")
            if anchor.get("source") == "system_call":
                name = anchor.get("trace_file")
                need(isinstance(name, str) and TRACE_FILE.fullmatch(name),
                     f"Unsafe trace path: {name}")
                line = source_line(evidence_dir / "trace" / name, anchor.get("line"))
                op = anchor.get("operation")
                need(isinstance(op, str) and line.startswith(op + "("),
                     f"Trace operation mismatch: {name}:{anchor.get('line')}")
                need(isinstance(anchor.get("pid"), int), "Trace PID missing")
                if kind == "MISSING" and f'"{dependency}"' in line and "O_RDONLY" in line:
                    need("= -" not in line, "A failed open is not a dependency")
                    matched = True
            elif anchor.get("source") == "make_database":
                need(anchor.get("artifact") == "make-db.txt",
                     "Make anchor must point to the saved Make database")
                line = source_line(evidence_dir / "make-db.txt", anchor.get("line"))
                need(line == anchor.get("declaration"), "Make declaration text mismatch")
                if kind == "REDUNDANT" and line.startswith(target + ":") and dependency in line.split():
                    matched = True
            else:
                raise EvidenceError("Unknown evidence source")
        need(matched, f"Missing raw proof for {kind} {target} -> {dependency}")


def verify_success(case_dir, name, report):
    need(report.get("status") == "SUCCEEDED", f"{name}: detector status")
    need(report.get("clean_exit_code") == 0 and report.get("build_exit_code") == 0,
         f"{name}: clean/build exit code")
    expected = ORIGINAL if name.startswith("original-") else set()
    need(findings_set(report) == expected, f"{name}: wrong MD/RD set")
    need(len(report["findings"]) == len(expected), f"{name}: finding count")
    observed = set(report.get("observed_targets", []))
    need({"main.o", "app"}.issubset(observed), f"{name}: observed targets missing")
    evidence = case_dir / "evidence"
    actual = graph_edges(evidence / "actual-graph.json", observed)
    declared = graph_edges(evidence / "declared-graph.json", observed)
    missing = {("MISSING", t, d) for t, d in actual - declared}
    redundant = {("REDUNDANT", t, d) for t, d in declared - actual}
    need(missing | redundant == expected, f"{name}: graphs disagree with findings")
    need((evidence / "make-db.txt").is_file(), f"{name}: missing Make database")
    need(any((evidence / "trace").glob("t.*")), f"{name}: no raw traces")
    verify_raw_anchors(case_dir, report)
    return verify_input(case_dir, report)


def verify(gate_dir):
    gate_dir = Path(gate_dir).resolve()
    summary = load_json(gate_dir / "gate-result.json")
    need(summary.get("passed") is True, "The E7 gate did not pass")
    rows = summary.get("cases")
    need(isinstance(rows, list) and [r.get("case") for r in rows] == list(CASES),
         "Gate cases/order differ from the A track's 8-item matrix")
    need(all(r.get("passed") is True for r in rows), "Some scenarios did not pass")
    csv_path = gate_dir / "results.csv"
    need(csv_path.is_file(), "results.csv missing")
    with csv_path.open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    need(len(csv_rows) == len(rows), "JSON/CSV case counts differ")
    for row, csv_row in zip(rows, csv_rows):
        need(csv_row["case"] == row["case"], "JSON/CSV case mismatch")
        need(csv_row["passed"].lower() == "true", "CSV does not mark scenario as passing")
        need(csv_row["exit_code"] == ("" if row.get("exit_code") is None else str(row["exit_code"])),
             f"JSON/CSV exit mismatch: {row['case']}")
        need(row.get("exit_code") == (0 if row["case"] in {"unit-tests", "fixed"} else 1),
             f"Unexpected tool exit: {row['case']}")
    need((gate_dir / "unit-tests" / "stdout.log").is_file(), "Unit test log missing")
    hashes, trace_ids = {}, set()
    for name in CASES[1:]:
        case_dir = gate_dir / name
        report = load_json(case_dir / "evidence" / "findings.json")
        trace_id = report.get("trace_id")
        need(isinstance(trace_id, str) and trace_id and trace_id not in trace_ids,
             f"Missing or repeated trace_id: {name}")
        trace_ids.add(trace_id)
        row = next(r for r in rows if r["case"] == name)
        need(row.get("trace_id") == trace_id and row.get("detector_status") == report.get("status"),
             f"Case summary does not match report: {name}")
        if name.startswith("original-") or name == "fixed":
            hashes[name] = verify_success(case_dir, name, report)
        elif name == "build-failed":
            need(report.get("status") == "FAILED" and report.get("error_code") == "CHECK_FAILED"
                 and isinstance(report.get("build_exit_code"), int)
                 and report["build_exit_code"] != 0, "Build failure not proved")
            need((case_dir / "evidence" / "build-stderr.log").is_file(),
                 "Missing raw failed build log")
        elif name == "unsupported":
            need(report.get("status") == "FAILED" and report.get("error_code") == "UNSUPPORTED"
                 and report.get("build_exit_code") == 0,
                 "Unsupported multi-output case not proved")
        else:
            need(report.get("status") == "TIMED_OUT" and report.get("error_code") == "TIMEOUT",
                 "Timeout not proved")
    original = hashes["original-1"]
    need(hashes["original-2"] == original and hashes["original-3"] == original,
         "Three original runs did not use identical inputs")
    fixed = hashes["fixed"]
    need(set(original) == set(fixed), "Fixed input file list changed")
    changed = sorted(name for name in original if original[name] != fixed[name])
    need(changed == ["Makefile"], f"Fix must change only Makefile, got: {changed}")
    return {"passed": True, "cases": len(rows), "unique_trace_ids": len(trace_ids),
            "original_runs": 3, "fixed_changed_files": changed,
            "scope": "Offline audit of an actual gate's saved reports and raw evidence"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.gate_dir)
    except (EvidenceError, ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
