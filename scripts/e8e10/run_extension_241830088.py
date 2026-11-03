"""Student A extension: a separate two-hop header case, five paired scans."""
import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "labs/e8e10"))
from lab import buildchecker, commit, fixture, save, scan


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    project = out / "project"
    fixture(project)
    baseline = scan(project)
    save(out / "baseline.json", baseline)
    (project / "config.h").write_text('#include "extra.h"\n#define VALUE 1\n')
    (project / "extra.h").write_text('#include "leaf.h"\n#define EXTRA 0\n')
    (project / "leaf.h").write_text('#define LEAF 3\n')
    commit(project, "student 241830088: config -> extra -> leaf")
    expected_actual = {
        "main.o": ["config.h", "extra.h", "leaf.h", "main.c"],
        "helper.o": ["helper.c"],
    }
    expected_findings = {
        ("MISSING", "main.o", "config.h"),
        ("MISSING", "main.o", "extra.h"),
        ("MISSING", "main.o", "leaf.h"),
        ("REDUNDANT", "main.o", "unused.h"),
    }
    save(out / "independent-expectation.json", {
        "actual": expected_actual,
        "findings": [list(edge) for edge in sorted(expected_findings)],
        "reused": [], "refreshed": ["main.o", "helper.o"],
        "repeat_history": "same C0 baseline for all five measurements",
    })
    rows = []
    for repeat in range(1, 6):
        incremental = scan(project, baseline)
        full = scan(project)
        save(out / f"transitive-r{repeat}-incremental.json", incremental)
        save(out / f"transitive-r{repeat}-full.json", full)
        for key in ("actual", "declared", "findings"):
            assert incremental[key] == full[key], key
        assert incremental["actual"] == expected_actual
        assert {(f["type"], f["target"], f["dependency"])
                for f in incremental["findings"]} == expected_findings
        assert incremental["refreshed"] == ["main.o", "helper.o"]
        assert incremental["reused"] == []
        rows.append({"case": "transitive", "repeat": repeat, "equal": True,
                     "incremental_s": incremental["elapsed_s"],
                     "full_s": full["elapsed_s"], "reused": 0, "refreshed": 2})
    with (out / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    inc = [r["incremental_s"] for r in rows]
    full = [r["full_s"] for r in rows]
    save(out / "performance-summary.json", {
        "case": "transitive", "n": 5,
        "inc_median_s": statistics.median(inc),
        "full_median_s": statistics.median(full),
        "inc_min_s": min(inc), "inc_max_s": max(inc),
        "full_min_s": min(full), "full_max_s": max(full),
        "full_over_inc": statistics.median(full) / statistics.median(inc),
        "scope": "scan includes Git/compiler identity and gcc -MM; excludes clean build",
    })
    buildchecker(project, out / "final-buildchecker")
    save(out / "gate.json", {"track": "A", "passed": True, "rows": 5,
                             "independent_edges_checked": True})
    print("TRANSITIVE_EXTENSION_PASS", out)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
