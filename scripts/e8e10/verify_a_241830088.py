"""Audit A13 E8-E10 output against explicit edges, without calling scan()."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median


TARGETS = ["main.o", "helper.o"]
BASE = {("MISSING", "main.o", "config.h"), ("REDUNDANT", "main.o", "unused.h")}
WITH_EXTRA = BASE | {("MISSING", "main.o", "extra.h")}
RD_ONLY = {("REDUNDANT", "main.o", "unused.h")}


def read(path):
    return json.loads(path.read_text())


def findings(report):
    return {(f["type"], f["target"], f["dependency"]) for f in report["findings"]}


def check_report(report, actual_main, declared_main, expected_findings, reuse):
    assert report["actual"] == {"main.o": actual_main, "helper.o": ["helper.c"]}
    assert report["declared"] == {"main.o": declared_main, "helper.o": ["helper.c"]}
    assert findings(report) == expected_findings
    assert len(report["findings"]) == len(expected_findings), "duplicate finding"
    assert report["reused"] == (TARGETS if reuse else [])
    assert report["refreshed"] == ([] if reuse else TARGETS)


def check_dynamic(directory, actual_main, expected_findings):
    report = read(directory / "findings.json")
    assert report["status"] == "SUCCEEDED"
    projected = {e for e in findings(report) if e[1] in TARGETS}
    assert projected == expected_findings
    graph = read(directory / "actual-graph.json")
    actual = {t: sorted({e["dependency"] for e in graph if e["target"] == t}) for t in TARGETS}
    assert actual == {"main.o": actual_main, "helper.o": ["helper.c"]}
    assert "main.o:" in (directory / "make-db.txt").read_text()
    traces = list((directory / "trace").glob("t.*"))
    assert traces
    reads = []
    for trace in traces:
        for line, value in enumerate(trace.read_text().splitlines(), 1):
            if '"config.h"' in value and "O_RDONLY" in value and "= -1" not in value:
                reads.append({"file": str(trace), "line": line, "syscall": value})
    assert reads, "no successful config.h open in raw trace"
    return reads


def check_pairs(directory, case, actual, declared, edges, reuse):
    rows = [r for r in csv.DictReader((directory / "results.csv").open()) if r["case"] == case]
    assert len(rows) == 5 and {int(r["repeat"]) for r in rows} == set(range(1, 6))
    for row in rows:
        n = int(row["repeat"])
        inc = read(directory / f"{case}-r{n}-incremental.json")
        full = read(directory / f"{case}-r{n}-full.json")
        check_report(inc, actual, declared, edges, reuse)
        check_report(full, actual, declared, edges, False)
        assert all(inc[key] == full[key] for key in ("actual", "declared", "findings"))
        assert inc["commit"] == full["commit"]
        assert float(row["incremental_s"]) == inc["elapsed_s"] > 0
        assert float(row["full_s"]) == full["elapsed_s"] > 0
        assert int(row["reused"]) == len(inc["reused"])
        assert int(row["refreshed"]) == len(inc["refreshed"])
        assert row["equal"] == "True"
    inc_times = [float(r["incremental_s"]) for r in rows]
    full_times = [float(r["full_s"]) for r in rows]
    return {"case": case, "n": 5, "inc_median_s": median(inc_times),
            "full_median_s": median(full_times), "inc_min_s": min(inc_times),
            "inc_max_s": max(inc_times), "full_min_s": min(full_times),
            "full_max_s": max(full_times), "full_over_inc": median(full_times) / median(inc_times)}


def main(args):
    base_actual = ["config.h", "main.c"]
    extra_actual = ["config.h", "extra.h", "main.c"]
    base_declared = ["main.c", "unused.h"]
    repaired_declared = ["config.h", "extra.h", "main.c", "unused.h"]
    source_shas = {(p / "student-source-commit.txt").read_text().strip()
                   for p in [args.e8, args.e9, args.e10, args.extension]}
    images = {(p / "environment-image-id.txt").read_text().strip()
              for p in [args.e8, args.e9, args.e10, args.extension]}
    assert len(source_shas) == len(images) == 1
    baseline = read(args.e8 / "baseline.json")
    assert baseline["baseline_source"] == "BuildChecker actual-graph.json projected to object targets"
    check_report(baseline, base_actual, base_declared, BASE, False)
    unchanged = read(args.e8 / "incremental.json")
    check_report(unchanged, base_actual, base_declared, BASE, True)
    assert baseline["commit"] == unchanged["commit"]
    trace = {"e8": check_dynamic(args.e8 / "buildchecker", base_actual, BASE)}
    names = ["baseline", "C1", "C2", "C3"]
    reports = [read(args.e9 / (name + ".json")) for name in names]
    assert len({r["commit"] for r in reports}) == 4
    for report, actual, declared, edges, reuse in zip(
            reports, [base_actual, base_actual, extra_actual, extra_actual],
            [base_declared] * 3 + [repaired_declared], [BASE, BASE, WITH_EXTRA, RD_ONLY],
            [False, True, False, True]):
        check_report(report, actual, declared, edges, reuse)
    assert reports[1]["added"] == reports[1]["resolved"] == []
    assert reports[2]["added"] == [["MISSING", "main.o", "extra.h"]]
    assert sorted(reports[3]["resolved"]) == [["MISSING", "main.o", "config.h"], ["MISSING", "main.o", "extra.h"]]
    c1_build = (args.e9 / "C1-build.log").read_text()
    assert "-c main.c -o main.o" in c1_build
    assert "-c helper.c" not in c1_build
    matrix = args.e10 / "matrix"
    cases = ["unchanged", "body", "include", "declaration", "flags", "header"]
    rows = list(csv.DictReader((matrix / "results.csv").open()))
    assert len(rows) == 30 and Counter(r["case"] for r in rows) == {case: 5 for case in cases}
    statistics = []
    for case in cases:
        before_include = case in ("unchanged", "body")
        before_repair = case in ("unchanged", "body", "include")
        statistics.append(check_pairs(
            matrix, case, base_actual if before_include else extra_actual,
            base_declared if before_repair else repaired_declared,
            BASE if before_include else (WITH_EXTRA if case == "include" else RD_ONLY),
            case in ("unchanged", "body", "declaration")))
    original_stats = list(csv.DictReader((matrix / "performance-summary.csv").open()))
    assert len(original_stats) == 6
    for expected, actual in zip(statistics, original_stats):
        assert expected["case"] == actual["case"]
        for field in ("inc_median_s", "full_median_s", "inc_min_s", "inc_max_s", "full_over_inc"):
            assert expected[field] == float(actual[field]), field
    assert read(matrix / "gate.json") == {"track": "A", "passed": True, "rows": 30}
    trace["e10"] = check_dynamic(matrix / "final-buildchecker", extra_actual, RD_ONLY)
    extension = args.extension / "extension"
    leaf_actual = ["config.h", "extra.h", "leaf.h", "main.c"]
    leaf_edges = WITH_EXTRA | {("MISSING", "main.o", "leaf.h")}
    statistics.append(check_pairs(extension, "transitive", leaf_actual, base_declared, leaf_edges, False))
    trace["extension"] = check_dynamic(extension / "final-buildchecker", leaf_actual, leaf_edges)
    assert read(extension / "gate.json")["passed"] is True
    for directory in [args.e8, args.e9, args.e10]:
        logs = list((directory / "steps").glob("*.log"))
        assert logs and all(p.read_text().rstrip().endswith("STEP_EXIT_CODE=0") for p in logs)
    args.out.mkdir(parents=True, exist_ok=False)
    with (args.out / "performance-summary-complete.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(statistics[0]))
        writer.writeheader()
        writer.writerows(statistics)
    result = {"passed": True, "source_sha": next(iter(source_shas)), "image_id": next(iter(images)),
              "matrix_pairs": 30, "extension_pairs": 5, "dynamic_crosschecks": 3,
              "e9_commits": {name: report["commit"] for name, report in zip(names, reports)},
              "successful_header_reads": trace, "audit": "explicit expected edge sets; scan() not imported"}
    (args.out / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    hashes = []
    for directory in [args.e8, args.e9, args.e10, args.extension]:
        for path in sorted(directory.rglob("*")):
            if path.is_file() and ".git" not in path.parts:
                hashes.append(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + str(path))
    (args.out / "SHA256SUMS").write_text("\n".join(hashes) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for stage in ("e8", "e9", "e10", "extension", "out"):
        parser.add_argument("--" + stage, type=Path, required=True)
    main(parser.parse_args())
