import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handoff_a_to_b import make_handoff


def artifact(path, root, job_id):
    data = path.read_bytes()
    return {
        "uri": f"artifact://{job_id}/{path.relative_to(root).as_posix()}",
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sha = "a" * 40
        self.job = "job-example"
        self.trace = "trace-example"
        self.inner = self.root / "incremental-report.json"
        self.payload = {"schema_version": "e8e10-1", "commit": self.sha, "findings": []}
        self.stage = {
            "schema_version": "e11e12-1",
            "kind": "incremental-check",
            "status": "SUCCEEDED",
            "commit": self.sha,
            "job_id": self.job,
            "trace_id": self.trace,
            "data": self.payload.copy(),
        }
        self.stage_path = self.root / "incremental-check.json"
        self.result = {
            "schema_version": "e11e12-1",
            "status": "SUCCEEDED",
            "target_commit": self.sha,
            "job_id": self.job,
            "trace_id": self.trace,
        }
        self.result_path = self.root / "result.json"
        self.bind_payload(json.dumps(self.payload, sort_keys=True) + "\n")

    def bind_payload(self, text):
        self.inner.write_text(text, encoding="utf-8")
        self.stage["artifacts"] = [artifact(self.inner, self.root, self.job)]
        self.write_envelopes()

    def write_envelopes(self):
        self.stage_path.write_text(json.dumps(self.stage) + "\n", encoding="utf-8")
        self.result["stages"] = [
            {"name": "incremental-check", "artifact": artifact(self.stage_path, self.root, self.job)}
        ]
        self.result_path.write_text(json.dumps(self.result) + "\n", encoding="utf-8")

    def test_live_a_report_becomes_b_input_with_provenance(self):
        handoff = make_handoff(self.result_path, self.sha)
        self.assertEqual(handoff["kind"], "fixed-md")
        self.assertEqual(handoff["data"], self.payload)
        self.assertEqual(handoff["source_report"]["job_id"], self.job)

    def test_changed_inner_artifact_is_rejected(self):
        (self.root / "incremental-report.json").write_text('{"findings": ["changed"]}\n')
        with self.assertRaisesRegex(ValueError, "hash or size mismatch"):
            make_handoff(self.result_path, self.sha)

    def test_other_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "another target commit"):
            make_handoff(self.result_path, "b" * 40)

    def test_payload_findings_must_match_stage_even_with_valid_hashes(self):
        changed = dict(self.payload, findings=[{"type": "MISSING", "target": "main.o", "dependency": "config.h"}])
        self.bind_payload(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "REPORT_DATA_MISMATCH"):
            make_handoff(self.result_path, self.sha)

    def test_payload_requires_expected_schema_and_commit(self):
        for field, value, error in (("schema_version", "e8e10-2", "SCHEMA_MISMATCH"), ("commit", "b" * 40, "STALE_REPORT")):
            with self.subTest(field=field):
                changed = {**self.payload, field: value}
                self.stage["data"] = changed
                self.bind_payload(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, error):
                    make_handoff(self.result_path, self.sha)

    def test_payload_reference_must_be_unique(self):
        ref = artifact(self.inner, self.root, self.job)
        for refs in ([], [ref, ref]):
            with self.subTest(count=len(refs)):
                self.stage["artifacts"] = refs
                self.write_envelopes()
                with self.assertRaisesRegex(ValueError, "exactly one incremental-report.json"):
                    make_handoff(self.result_path, self.sha)

    def test_duplicate_payload_key_is_rejected(self):
        self.bind_payload(json.dumps(self.payload)[:-1] + ', "findings": []}')
        with self.assertRaisesRegex(ValueError, "Duplicate key: findings"):
            make_handoff(self.result_path, self.sha)


if __name__ == "__main__":
    unittest.main()
