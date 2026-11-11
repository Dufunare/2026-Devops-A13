"""Independent minimal fixtures: no compiler, Docker or pipeline import."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from audit_a import AuditError, audit_run


class AuditA241830088Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job, self.trace = "job-a13-test", "trace-a13-test"
        self.base, self.target = "a" * 40, "b" * 40
        self.make_fixture()

    def save(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n")

    def read(self, name):
        return json.loads((self.root / name).read_text())

    def artifact(self, name):
        data = (self.root / name).read_bytes()
        return {"uri": f"artifact://{self.job}/{name}",
                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def sync_references(self):
        for name in ("full-check", "incremental-check"):
            report = self.read(name + ".json")
            report["artifacts"] = [self.artifact(x["uri"].split("/", 3)[-1]) for x in report["artifacts"]]
            self.save(name + ".json", report)
        result = self.read("result.json")
        result["stages"] = [{"name": n, "artifact": self.artifact(n + ".json")}
                            for n in ("full-check", "incremental-check")]
        result["artifacts"] = [self.artifact(str(p.relative_to(self.root)))
                               for p in sorted(self.root.rglob("*"))
                               if p.is_file() and p.name != "result.json"]
        self.save("result.json", result)

    def make_fixture(self):
        base_actual = {"main.o": ["main.c", "config.h"], "helper.o": ["helper.c"]}
        target_actual = {"main.o": ["main.c", "config.h", "extra.h"], "helper.o": ["helper.c"]}
        declared = {"main.o": ["main.c", "unused.h"], "helper.o": ["helper.c"]}
        def findings(extra=False):
            values = [{"type": "MISSING", "target": "main.o", "dependency": "config.h"},
                      {"type": "REDUNDANT", "target": "main.o", "dependency": "unused.h"}]
            if extra:
                values.append({"type": "MISSING", "target": "main.o", "dependency": "extra.h"})
            return values
        for folder, source, actual, extra in (("baseline-full", "base-project", base_actual, False),
                                              ("target-full", "target-project", target_actual, True)):
            hashes = {}
            for name, content in {"Makefile": "main.o: main.c unused.h\nhelper.o: helper.c\n",
                                  "main.c": ('#include "extra.h"\n' if extra else '') + '#include "config.h"\n',
                                  "helper.c": "int helper(void){return 0;}\n",
                                  "config.h": "#define VALUE 1\n", "extra.h": "#define EXTRA 0\n",
                                  "unused.h": "/* unused */\n"}.items():
                for base_dir in (self.root / source, self.root / folder / "project"):
                    base_dir.mkdir(parents=True, exist_ok=True)
                    (base_dir / name).write_text(content)
                hashes[name] = hashlib.sha256(content.encode()).hexdigest()
            for kind, graph in (("actual", actual), ("declared", declared)):
                rows = [{"target": t, "dependency": d} for t, deps in graph.items() for d in deps]
                rows.append({"target": "app", "dependency": "uncompared-object.o"})
                self.save(folder + "/" + kind + "-graph.json", rows)
            self.save(folder + "/findings.json", {"status": "SUCCEEDED", "clean_exit_code": 0,
                                                  "build_exit_code": 0, "input_sha256": hashes,
                                                  "findings": findings(extra)})
            self.save(folder + "/processes.json", [{"pid": 11, "parent": 10, "job_pid": 11}])
            (self.root / folder / "make-db.txt").write_text("main.o: main.c unused.h\n")
            (self.root / folder / "trace").mkdir()
            (self.root / folder / "trace/t.11").write_text('openat(AT_FDCWD, "config.h", O_RDONLY) = 3\n')
        old = {"schema_version": "e8e10-1", "commit": self.base, "key": {"directives": ["config.h"]},
               "actual": base_actual, "declared": declared, "findings": findings(False)}
        current = {"schema_version": "e8e10-1", "commit": self.target, "key": {"directives": ["config.h", "extra.h"]},
                   "actual": target_actual, "declared": declared, "findings": findings(True),
                   "added": [["MISSING", "main.o", "extra.h"]], "resolved": [],
                   "reused": [], "refreshed": ["main.o", "helper.o"]}
        self.save("baseline-cache.json", old)
        self.save("incremental-report.json", current)
        for name, commit, data, files in (
                ("full-check", self.base, self.read("baseline-full/findings.json"),
                 ["baseline-full/actual-graph.json", "baseline-full/findings.json", "baseline-cache.json"]),
                ("incremental-check", self.target, current,
                 ["incremental-report.json", "target-full/findings.json"])):
            self.save(name + ".json", {"schema_version": "e11e12-1", "kind": name, "commit": commit,
                                       "status": "SUCCEEDED", "job_id": self.job, "trace_id": self.trace,
                                       "data": data, "artifacts": [self.artifact(f) for f in files]})
        self.save("request.json", {"mode": "e11-a", "base": self.base, "target": self.target})
        self.save("result.json", {"schema_version": "e11e12-1", "status": "SUCCEEDED", "job_id": self.job,
                                  "trace_id": self.trace, "base_commit": self.base, "target_commit": self.target})
        self.sync_references()

    def change_payload(self, function):
        payload = self.read("incremental-report.json")
        function(payload)
        self.save("incremental-report.json", payload)
        envelope = self.read("incremental-check.json")
        envelope["data"] = copy.deepcopy(payload)
        self.save("incremental-check.json", envelope)
        self.sync_references()

    def test_valid_full_evidence_and_extra_app_edge(self):
        verdict = audit_run(self.root)
        self.assertTrue(verdict["passed"])
        self.assertEqual(verdict["target_commit"], self.target)

    def test_same_count_wrong_actual_graph_rejected_even_with_updated_hashes(self):
        self.change_payload(lambda p: p["actual"]["main.o"].__setitem__(1, "wrong.h"))
        with self.assertRaisesRegex(AuditError, "TARGET_ACTUAL_GRAPH_MISMATCH"):
            audit_run(self.root)

    def test_same_count_wrong_declared_graph_rejected(self):
        self.change_payload(lambda p: p["declared"]["main.o"].__setitem__(1, "wrong.h"))
        with self.assertRaisesRegex(AuditError, "TARGET_DECLARED_GRAPH_MISMATCH"):
            audit_run(self.root)

    def test_old_payload_commit_rejected(self):
        self.change_payload(lambda p: p.update(commit=self.base))
        with self.assertRaisesRegex(AuditError, "PAYLOAD_STALE_REPORT"):
            audit_run(self.root)

    def test_different_task_binding_rejected(self):
        envelope = self.read("incremental-check.json")
        envelope["trace_id"] = "trace-other"
        self.save("incremental-check.json", envelope)
        self.sync_references()
        with self.assertRaisesRegex(AuditError, "TASK_BINDING_MISMATCH"):
            audit_run(self.root)

    def test_changed_raw_file_rejected(self):
        path = self.root / "target-full/trace/t.11"
        path.write_bytes(path.read_bytes().replace(b'config.h', b'wrongx.h'))
        with self.assertRaisesRegex(AuditError, "ARTIFACT_HASH_MISMATCH"):
            audit_run(self.root)

    def test_baseline_cache_not_from_actual_graph_rejected(self):
        cache = self.read("baseline-cache.json")
        cache["actual"]["main.o"] = ["main.c", "invented.h"]
        self.save("baseline-cache.json", cache)
        self.sync_references()
        with self.assertRaisesRegex(AuditError, "BASELINE_CACHE_GRAPH_MISMATCH"):
            audit_run(self.root)

    def test_input_snapshot_mismatch_rejected_after_manifest_update(self):
        (self.root / "target-full/project/main.c").write_text("changed source\n")
        self.sync_references()
        with self.assertRaisesRegex(AuditError, "INPUT_HASH_MISMATCH"):
            audit_run(self.root)

    def test_wrong_added_edge_rejected(self):
        self.change_payload(lambda p: p.update(added=[["MISSING", "main.o", "wrong.h"]]))
        with self.assertRaisesRegex(AuditError, "ADDED_FINDINGS_MISMATCH"):
            audit_run(self.root)

    def test_wrong_cache_reuse_rejected(self):
        self.change_payload(lambda p: p.update(reused=["main.o", "helper.o"], refreshed=[]))
        with self.assertRaisesRegex(AuditError, "CACHE_BEHAVIOR_MISMATCH"):
            audit_run(self.root)

    def test_payload_data_type_mismatch_rejected(self):
        payload = self.read("incremental-report.json")
        payload["measurement"] = 1
        self.save("incremental-report.json", payload)
        envelope = self.read("incremental-check.json")
        envelope["data"] = dict(payload, measurement=True)
        self.save("incremental-check.json", envelope)
        self.sync_references()
        with self.assertRaisesRegex(AuditError, "ENVELOPE_PAYLOAD_MISMATCH"):
            audit_run(self.root)

    def test_missing_raw_processes_cannot_be_hidden_by_manifest(self):
        (self.root / "target-full/processes.json").unlink()
        self.sync_references()
        with self.assertRaisesRegex(AuditError, "INCOMPLETE_ARTIFACT_MANIFEST"):
            audit_run(self.root)


if __name__ == "__main__":
    unittest.main()
