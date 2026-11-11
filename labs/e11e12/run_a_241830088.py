"""Produce independent A13 E11-A runs and immutable B13 handoff packages.

Run in the course Linux image. Data are explicitly course-generated, not an
external real-project acceptance. This command never contacts B13.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from pipeline import ROOT, execute, save
from lab import commit, fixture, run


def produce(dataset, out):
    if dataset.exists() or out.exists():
        raise ValueError("OUTPUT_EXISTS: both data and evidence directories must be new")
    if not dataset.resolve().is_relative_to(ROOT / "data") or not out.resolve().is_relative_to(ROOT / "work"):
        raise ValueError("Use a data/ dataset and a work/ evidence directory")
    source = run(["git", "rev-parse", "HEAD"], ROOT).strip()
    if run(["git", "status", "--porcelain"], ROOT).strip():
        raise ValueError("Commit student code before collecting evidence")
    image = os.environ.get("A13_IMAGE_ID", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("Set A13_IMAGE_ID from docker image inspect")
    dataset.mkdir(parents=True)
    out.mkdir(parents=True)
    project = dataset / "repo"
    fixture(project)
    c0 = run(["git", "rev-parse", "HEAD"], project).strip()
    main = project / "main.c"
    main.write_text('#include "extra.h"\n' + main.read_text())
    c1 = commit(project, "A13 241830088 C1: include extra.h without declaration")
    main.write_text(main.read_text().replace("VALUE+helper()", "VALUE+helper()+0"))
    c2 = commit(project, "A13 241830088 C2: equivalent body expression")
    makefile = project / "Makefile"
    makefile.write_text(makefile.read_text().replace("main.c unused.h", "main.c unused.h config.h"))
    c3 = commit(project, "A13 241830088 C3: declare config.h only")
    toolchain = "\n".join(run(command, ROOT) for command in [
        ["gcc", "--version"], ["make", "--version"], ["strace", "--version"],
        ["python3", "--version"], ["git", "--version"],
    ])
    (out / "toolchain.txt").write_text(toolchain)
    save(dataset / "dataset.json", {
        "source": "course-generated E8-E10 fixture, independently versioned by A13 241830088",
        "real_project_acceptance": False, "student_source_sha": source,
        "C0": c0, "C1": c1, "C2": c2, "C3": c3,
        "changes": {"C1": "include extra.h", "C2": "ordinary body only", "C3": "partial Make declaration repair"},
        "flags": "-O0", "targets": ["main.o", "helper.o"],
    })
    cases = [("include", c0, c1, [], ["main.o", "helper.o"]),
             ("body", c1, c2, ["main.o", "helper.o"], []),
             ("declaration", c2, c3, ["main.o", "helper.o"], [])]
    summary = []
    for name, base, target, reused, refreshed in cases:
        request = {"mode": "e11-a", "repo": str(project), "base": base, "target": target}
        save(dataset / (name + ".json"), request)
        folder = out / name
        result = execute(request, folder)
        if result["status"] != "SUCCEEDED":
            raise ValueError("PIPELINE_FAILED " + json.dumps(result))
        report = json.loads((folder / "incremental-report.json").read_text())
        actual = {"main.o": ["config.h", "extra.h", "main.c"], "helper.o": ["helper.c"]}
        expected = {("MISSING", "main.o", "extra.h"), ("REDUNDANT", "main.o", "unused.h")}
        if name != "declaration":
            expected.add(("MISSING", "main.o", "config.h"))
        assert report["actual"] == actual
        assert {(f["type"], f["target"], f["dependency"]) for f in report["findings"]} == expected
        assert report["reused"] == reused and report["refreshed"] == refreshed
        if name == "include":
            assert report["added"] == [["MISSING", "main.o", "extra.h"]]
        elif name == "body":
            assert report["added"] == report["resolved"] == []
        else:
            assert report["resolved"] == [["MISSING", "main.o", "config.h"]]
        (folder / "student-source-commit.txt").write_text(source + "\n")
        (folder / "environment-image-id.txt").write_text(image + "\n")
        (folder / "toolchain.txt").write_text(toolchain)
        save(folder / "input-provenance.json", {
            "data_origin": "course-generated controlled C/Make fixture; A13 independent commits",
            "real_project_acceptance": False, "flags": "-O0",
            "execution_environment": "orchestrator", "draft_image_reused": False,
            "case": name, "dataset": str(dataset), "base": base, "target": target,
        })
        save(folder / "independent-expectation.json", {
            "actual": actual, "findings": [list(edge) for edge in sorted(expected)],
            "reused": reused, "refreshed": refreshed,
        })
        summary.append({"case": name, "base": base, "target": target,
                        "job_id": result["job_id"], "trace_id": result["trace_id"],
                        "status": result["status"], "reused": reused, "refreshed": refreshed})
    save(out / "producer-summary.json", {
        "student_source_sha": source, "image_id": image,
        "dataset": str(dataset), "cases": summary, "real_project_acceptance": False,
        "B13_formal_receipt": False,
    })
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    produce(args.dataset.resolve(), args.out.resolve())
