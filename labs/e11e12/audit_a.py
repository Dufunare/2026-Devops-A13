"""241830088: audit complete E11-A evidence without importing scan or Docker.

Checks consistency of the complete run directory. Integrity hashes do not prove
who produced the directory; exchange the outer archive hash separately.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

TARGETS = ("main.o", "helper.o")
SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY " + key)
        result[key] = value
    return result


def load(path):
    def invalid(value):
        raise AuditError("NONFINITE_JSON " + value)
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=_pairs, parse_constant=invalid)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError("INVALID_JSON " + str(path)) from exc


def equal(left, right):
    # bool and number are distinct JSON values, unlike Python's True == 1.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def local_file(root, relative):
    require(isinstance(relative, str) and bool(relative), "INVALID_PATH")
    path = PurePosixPath(relative)
    require(not path.is_absolute() and all(part not in (".", "..") for part in relative.split("/"))
            and "\\" not in relative, "INVALID_PATH " + relative)
    resolved = root.joinpath(*path.parts)
    require(resolved.resolve().is_relative_to(root.resolve()) and not resolved.is_symlink()
            and resolved.is_file(), "MISSING_OR_UNSAFE_FILE " + relative)
    return resolved


def references(root, values, job):
    require(isinstance(values, list), "INVALID_ARTIFACT_LIST")
    result = {}
    prefix = "artifact://" + job + "/"
    for item in values:
        require(isinstance(item, dict), "INVALID_ARTIFACT")
        uri = item.get("uri")
        require(isinstance(uri, str) and uri.startswith(prefix), "ARTIFACT_JOB_MISMATCH")
        relative = uri[len(prefix):]
        require(relative not in result, "DUPLICATE_ARTIFACT " + relative)
        path = local_file(root, relative)
        raw = path.read_bytes()
        require(type(item.get("bytes")) is int and item["bytes"] == len(raw), "ARTIFACT_BYTES_MISMATCH " + relative)
        require(isinstance(item.get("sha256"), str) and HASH.fullmatch(item["sha256"])
                and item["sha256"] == hashlib.sha256(raw).hexdigest(), "ARTIFACT_HASH_MISMATCH " + relative)
        result[relative] = item
    return result


def graph_projection(graph):
    require(isinstance(graph, list), "INVALID_GRAPH")
    result = {target: set() for target in TARGETS}
    for edge in graph:
        require(isinstance(edge, dict), "INVALID_EDGE")
        if edge.get("target") in result:
            dependency = edge.get("dependency")
            require(isinstance(dependency, str) and bool(dependency), "INVALID_DEPENDENCY")
            result[edge["target"]].add(dependency)
    return result


def report_graph(value):
    require(isinstance(value, dict), "INVALID_REPORT_GRAPH")
    result = {}
    for target in TARGETS:
        deps = value.get(target)
        require(isinstance(deps, list) and all(isinstance(d, str) and bool(d) for d in deps), "INVALID_REPORT_DEPENDENCIES " + target)
        require(len(set(deps)) == len(deps), "DUPLICATE_REPORT_DEPENDENCY")
        result[target] = set(deps)
    return result


def finding_projection(values):
    require(isinstance(values, list), "INVALID_FINDINGS")
    result = set()
    for finding in values:
        require(isinstance(finding, dict), "INVALID_FINDING")
        if finding.get("target") in TARGETS:
            require(finding.get("type") in ("MISSING", "REDUNDANT")
                    and isinstance(finding.get("dependency"), str) and finding["dependency"], "INVALID_FINDING")
            item = (finding["type"], finding["target"], finding["dependency"])
            require(item not in result, "DUPLICATE_FINDING")
            result.add(item)
    return result


def graph_findings(actual, declared):
    result = set()
    for target in TARGETS:
        result.update(("MISSING", target, dep) for dep in actual[target] - declared[target])
        result.update(("REDUNDANT", target, dep) for dep in declared[target] - actual[target])
    return result


def snapshot_evidence(root, folder, source):
    directory = root / folder
    report = load(directory / "findings.json")
    require(isinstance(report, dict) and report.get("status") == "SUCCEEDED", "FULL_CHECK_FAILED " + folder)
    require(report.get("clean_exit_code") == 0 and report.get("build_exit_code") == 0,
            "FULL_BUILD_NOT_SUCCESSFUL " + folder)
    input_hashes = report.get("input_sha256")
    require(isinstance(input_hashes, dict) and {"main.c", "helper.c", "config.h", "Makefile"} <= input_hashes.keys(),
            "INCOMPLETE_INPUT_HASHES " + folder)
    for name, expected in input_hashes.items():
        require(isinstance(expected, str) and HASH.fullmatch(expected), "INVALID_INPUT_HASH")
        saved = local_file(directory / "project", name).read_bytes()
        original = local_file(root / source, name).read_bytes()
        require(hashlib.sha256(saved).hexdigest() == expected and saved == original,
                "INPUT_HASH_MISMATCH " + folder + "/" + name)
    db = local_file(directory, "make-db.txt")
    require(bool(db.read_bytes()), "EMPTY_MAKE_DATABASE")
    processes = load(directory / "processes.json")
    require(isinstance(processes, list) and bool(processes) and all(isinstance(p, dict) for p in processes), "INVALID_PROCESSES")
    traces = sorted((directory / "trace").glob("t.*"))
    require(bool(traces) and all(p.is_file() and not p.is_symlink() and p.stat().st_size > 0 for p in traces), "MISSING_RAW_TRACE")
    actual = graph_projection(load(directory / "actual-graph.json"))
    declared = graph_projection(load(directory / "declared-graph.json"))
    findings = finding_projection(report.get("findings"))
    require(findings == graph_findings(actual, declared), "FULL_FINDINGS_GRAPH_MISMATCH " + folder)
    return report, actual, declared, findings, len(traces)


def cache_report(report, commit):
    require(isinstance(report, dict) and report.get("schema_version") == "e8e10-1", "PAYLOAD_SCHEMA_MISMATCH")
    require(report.get("commit") == commit, "PAYLOAD_STALE_REPORT")
    require(isinstance(report.get("key"), dict) and bool(report["key"]), "MISSING_CACHE_KEY")


def changes(value):
    require(isinstance(value, list), "INVALID_DELTA")
    result = set()
    for item in value:
        require(isinstance(item, list) and len(item) == 3 and item[0] in ("MISSING", "REDUNDANT")
                and item[1] in TARGETS and isinstance(item[2], str) and bool(item[2]), "INVALID_DELTA")
        edge = tuple(item)
        require(edge not in result, "DUPLICATE_DELTA")
        result.add(edge)
    return result


def audit_run(run_dir):
    root = Path(run_dir).resolve()
    result = load(root / "result.json")
    request = load(root / "request.json")
    require(isinstance(result, dict) and result.get("schema_version") == "e11e12-1"
            and result.get("status") == "SUCCEEDED", "RUN_NOT_SUCCEEDED")
    require(isinstance(request, dict) and request.get("mode") == "e11-a", "EXPECTED_E11_A_RUN")
    job, trace = result.get("job_id"), result.get("trace_id")
    require(isinstance(job, str) and IDENTIFIER.fullmatch(job) and isinstance(trace, str) and IDENTIFIER.fullmatch(trace), "INVALID_TASK_IDS")
    base, target = result.get("base_commit"), result.get("target_commit")
    require(isinstance(base, str) and SHA.fullmatch(base) and isinstance(target, str) and SHA.fullmatch(target), "INVALID_COMMIT")
    require(request.get("base") == base and request.get("target") == target, "REQUEST_COMMIT_MISMATCH")
    manifest = references(root, result.get("artifacts"), job)
    required = {"request.json", "full-check.json", "incremental-check.json", "incremental-report.json", "baseline-cache.json"}
    for folder in ("baseline-full", "target-full"):
        required.update(folder + "/" + name for name in ("actual-graph.json", "declared-graph.json", "findings.json", "make-db.txt", "processes.json"))
        required.update(str(p.relative_to(root)) for p in (root / folder / "trace").glob("t.*"))
    require(required <= manifest.keys(), "INCOMPLETE_ARTIFACT_MANIFEST")
    stages = result.get("stages")
    require(isinstance(stages, list) and len(stages) == 2
            and [s.get("name") for s in stages] == ["full-check", "incremental-check"], "INVALID_E11_A_STAGES")
    envelopes = {}
    stage_references = {}
    for stage, commit in zip(stages, (base, target)):
        name = stage["name"]
        entry = stage.get("artifact")
        checked = references(root, [entry], job)
        require(list(checked) == [name + ".json"] and equal(entry, manifest[name + ".json"]), "STAGE_ARTIFACT_BINDING")
        envelope = load(root / (name + ".json"))
        require(isinstance(envelope, dict) and envelope.get("schema_version") == "e11e12-1"
                and envelope.get("status") == "SUCCEEDED" and envelope.get("kind") == name, "ENVELOPE_SCHEMA_OR_KIND")
        require(envelope.get("commit") == commit, "ENVELOPE_STALE_REPORT")
        require(envelope.get("job_id") == job and envelope.get("trace_id") == trace, "TASK_BINDING_MISMATCH")
        refs = references(root, envelope.get("artifacts"), job)
        require(all(path in manifest and equal(item, manifest[path]) for path, item in refs.items()), "ENVELOPE_ARTIFACT_BINDING")
        envelopes[name] = envelope
        stage_references[name] = refs
    require({"baseline-full/actual-graph.json", "baseline-full/findings.json", "baseline-cache.json"} <= stage_references["full-check"].keys(), "MISSING_BASELINE_REFERENCE")
    require({"incremental-report.json", "target-full/findings.json"} <= stage_references["incremental-check"].keys(), "MISSING_PAYLOAD_REFERENCE")
    baseline, base_actual, base_declared, base_findings, base_traces = snapshot_evidence(root, "baseline-full", "base-project")
    full, actual, declared, full_findings, target_traces = snapshot_evidence(root, "target-full", "target-project")
    require(equal(envelopes["full-check"].get("data"), baseline), "BASELINE_ENVELOPE_PAYLOAD_MISMATCH")
    old = load(root / "baseline-cache.json")
    current = load(root / "incremental-report.json")
    cache_report(old, base)
    cache_report(current, target)
    require(equal(envelopes["incremental-check"].get("data"), current), "ENVELOPE_PAYLOAD_MISMATCH")
    require(report_graph(old.get("actual")) == base_actual, "BASELINE_CACHE_GRAPH_MISMATCH")
    require(report_graph(old.get("declared")) == base_declared, "BASELINE_DECLARED_GRAPH_MISMATCH")
    require(finding_projection(old.get("findings")) == base_findings, "BASELINE_FINDINGS_MISMATCH")
    require(report_graph(current.get("actual")) == actual, "TARGET_ACTUAL_GRAPH_MISMATCH")
    require(report_graph(current.get("declared")) == declared, "TARGET_DECLARED_GRAPH_MISMATCH")
    require(finding_projection(current.get("findings")) == full_findings, "TARGET_FINDINGS_MISMATCH")
    require(changes(current.get("added")) == full_findings - base_findings, "ADDED_FINDINGS_MISMATCH")
    require(changes(current.get("resolved")) == base_findings - full_findings, "RESOLVED_FINDINGS_MISMATCH")
    same_key = equal(old["key"], current["key"])
    for key, expected in (("reused", set(TARGETS) if same_key else set()),
                          ("refreshed", set() if same_key else set(TARGETS))):
        values = current.get(key)
        require(isinstance(values, list) and len(values) == len(expected) and set(values) == expected, "CACHE_BEHAVIOR_MISMATCH " + key)
    require(not same_key or base_actual == actual, "REUSED_GRAPH_CHANGED")
    return {"schema_version": "a13-e11-a-audit-1", "passed": True,
            "job_id": job, "trace_id": trace, "base_commit": base, "target_commit": target,
            "artifact_count": len(manifest), "baseline_trace_files": base_traces,
            "target_trace_files": target_traces, "cache_key_equal": same_key,
            "reused": current["reused"], "refreshed": current["refreshed"],
            "findings": [list(edge) for edge in sorted(full_findings)],
            "scope": "complete E11-A directory; two object targets; integrity and consistency, not source authentication"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        if args.out is not None:
            require(not args.out.exists(), "OUTPUT_EXISTS")
        verdict = audit_run(args.run_dir)
        text = json.dumps(verdict, ensure_ascii=False, indent=2) + "\n"
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(text)
        print(text, end="")
    except (AuditError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
