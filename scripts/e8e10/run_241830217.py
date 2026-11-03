#!/usr/bin/env python3
"""Reproducible student extension runs; use the course Docker image.

This never reads another student's evidence. It writes to a NEW subdirectory
under /course/work, reports actual times, and cross-checks with lab.scan().
Use --dynamic-recheck for the real BuildChecker/strace check in E8/E10.
"""

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "labs/e8e10"))

from lab import buildchecker, commit, fixture, save, scan  # noqa: E402
from targetwise_241830217 import scan_targetwise  # noqa: E402

CASES = ("unchanged", "body", "include", "declaration", "flags", "header")
EXPECTED_REFRESH = {
    "unchanged": [], "body": [], "include": ["main.o"],
    "declaration": [], "flags": ["main.o", "helper.o"], "header": ["main.o"],
}


def verify_full(project, inc, context):
    """Run an independent, non-cached GCC oracle and compare *full sets*."""
    full = scan(project)
    for field in ("actual", "declared", "findings"):
        if inc[field] != full[field]:
            raise AssertionError(f"{context}: {field} mismatches full GCC scan")
    return full


def init_project(out):
    project = out / "project"
    fixture(project)
    baseline = scan_targetwise(project)
    save(out / "baseline.json", baseline)
    save(out / "baseline-full.json", verify_full(project, baseline, "C0"))
    return project, baseline


def apply_case(project, case):
    if case == "unchanged":
        return
    if case == "body":
        path = project / "helper.c"
        path.write_text("int helper(void){return 0+0;}\n")
    elif case == "include":
        path = project / "main.c"
        path.write_text('#include "extra.h"\n' + path.read_text())
    elif case == "declaration":
        path = project / "Makefile"
        old = path.read_text()
        assert "main.c unused.h" in old
        path.write_text(old.replace("main.c unused.h", "main.c unused.h config.h extra.h"))
    elif case == "flags":
        path = project / "Makefile"
        old = path.read_text()
        assert "-O0" in old
        path.write_text(old.replace("-O0", "-O1"))
    elif case == "header":
        (project / "config.h").write_text('#include "extra.h"\n#define VALUE 1\n')
    else:
        raise ValueError("UNKNOWN_CASE " + case)
    commit(project, "student 241830217 " + case)


def e8(out, dynamic):
    project, baseline = init_project(out)
    expected = {("MISSING", "main.o", "config.h"),
                ("REDUNDANT", "main.o", "unused.h")}
    edges = {(f["type"], f["target"], f["dependency"]) for f in baseline["findings"]}
    assert edges == expected, edges
    unchanged = scan_targetwise(project, baseline)
    assert unchanged["reused"] == ["main.o", "helper.o"]
    assert unchanged["refreshed"] == []
    save(out / "unchanged.json", unchanged)
    save(out / "unchanged-full.json", verify_full(project, unchanged, "E8 unchanged"))
    # Changes to an unreferenced header should not invalidate any object graph.
    (project / "unused.h").write_text("#define IRRELEVANT 42\n")
    commit(project, "student E8 unrelated header")
    unrelated = scan_targetwise(project, unchanged)
    assert unrelated["reused"] == ["main.o", "helper.o"]
    assert unrelated["refreshed"] == []
    save(out / "unrelated.json", unrelated)
    save(out / "unrelated-full.json", verify_full(project, unrelated, "E8 unrelated"))
    if dynamic:
        buildchecker(project, out / "buildchecker")
    save(out / "gate.json", {"stage": "e8", "passed": True,
                            "dynamic_recheck": "EXECUTED" if dynamic else "NOT_RUN",
                            "student": "241830217", "targetwise": True})


def e9(out, dynamic):
    project, previous = init_project(out)
    assert not dynamic, "E9 track A has no mandatory dynamic recheck; use E8/E10"
    sequence = ("body", "include", "declaration")
    for index, case in enumerate(sequence, start=1):
        apply_case(project, case)
        current = scan_targetwise(project, previous)
        full = verify_full(project, current, "E9 " + case)
        assert current["refreshed"] == EXPECTED_REFRESH[case], case
        if case == "include":
            assert current["added"] == [["MISSING", "main.o", "extra.h"]]
        if case == "declaration":
            assert current["resolved"] == [
                ["MISSING", "main.o", "config.h"],
                ["MISSING", "main.o", "extra.h"],
            ]
        save(out / f"C{index}.json", current)
        save(out / f"C{index}-full.json", full)
        previous = current
    save(out / "gate.json", {"stage": "e9", "passed": True,
                            "student": "241830217", "commits": 4,
                            "targetwise": True})


def e10(out, dynamic):
    project, previous = init_project(out)
    rows = []
    for case in CASES:
        apply_case(project, case)
        for repeat in range(1, 6):
            inc = scan_targetwise(project, previous)
            full = verify_full(project, inc, f"E10 {case}-r{repeat}")
            assert inc["refreshed"] == EXPECTED_REFRESH[case], case
            assert len(inc["refreshed"]) + len(inc["reused"]) == 2
            save(out / f"{case}-r{repeat}-incremental.json", inc)
            save(out / f"{case}-r{repeat}-full.json", full)
            rows.append({
                "case": case, "repeat": repeat, "equal": True,
                "incremental_s": inc["elapsed_s"], "full_s": full["elapsed_s"],
                "reused": len(inc["reused"]), "refreshed": len(inc["refreshed"]),
            })
        save(out / f"{case}.json", inc)
        previous = inc
    assert len(rows) == 30
    with (out / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = []
    for case in CASES:
        subset = [row for row in rows if row["case"] == case]
        inc_median = statistics.median(row["incremental_s"] for row in subset)
        full_median = statistics.median(row["full_s"] for row in subset)
        summary.append({
            "case": case, "count": len(subset),
            "incremental_median_s": inc_median,
            "full_median_s": full_median,
            "incremental_min_s": min(row["incremental_s"] for row in subset),
            "incremental_max_s": max(row["incremental_s"] for row in subset),
            "full_over_incremental": full_median / inc_median if inc_median else "undefined",
            "reused": subset[0]["reused"], "refreshed": subset[0]["refreshed"],
        })
    with (out / "performance-summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    if dynamic:
        buildchecker(project, out / "final-buildchecker")
    save(out / "gate.json", {
        "stage": "e10", "passed": True, "rows": len(rows),
        "full_graph_equal": True,
        "dynamic_recheck": "EXECUTED" if dynamic else "NOT_RUN",
        "student": "241830217", "targetwise": True,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("e8", "e9", "e10"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dynamic-recheck", action="store_true")
    options = parser.parse_args()
    out = options.out.resolve()
    if not out.is_relative_to((ROOT / "work").resolve()) or out == (ROOT / "work").resolve():
        parser.error("--out must be a fresh child of the repository work/ directory")
    if out.exists():
        parser.error("--out already exists; choose a fresh directory")
    out.mkdir(parents=True)
    if options.stage == "e8":
        e8(out, options.dynamic_recheck)
    elif options.stage == "e9":
        e9(out, options.dynamic_recheck)
    else:
        e10(out, options.dynamic_recheck)
    print("PASS", options.stage, out)


if __name__ == "__main__":
    main()
