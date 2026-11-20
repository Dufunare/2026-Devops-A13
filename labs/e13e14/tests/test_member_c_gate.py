"""Fast offline tests for member C's C6 detector and evidence safeguards."""

import importlib.util
import io
import json
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SCANNER_PATH = ROOT / "labs/e13e14/scan_runtime_logs.py"
GATE_PATH = ROOT / "labs/e13e14/member_c_gate.py"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scan = load_module(SCANNER_PATH, "e13_c6_runtime_scan")
gate = load_module(GATE_PATH, "e13_member_c_gate")


class MemberCStaticTests(unittest.TestCase):
    def test_fake_key_is_redacted_and_then_clean(self):
        with tempfile.TemporaryDirectory() as temp:
            probe = Path(temp) / "probe.log"
            # Construct the *obviously fake* value at runtime. No token-shaped
            # literal is committed to Git or copied into CI logs.
            fake = "sk-" + "DEMO" * 7
            probe.write_text('api_key = "' + fake + '"\n', encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                first = scan.main([str(probe)])
            self.assertEqual(first, 1)
            self.assertIn("hits=", buf.getvalue())
            self.assertIn("FOUND", buf.getvalue())
            self.assertNotIn(fake, buf.getvalue())
            self.assertIn("sk-D***", buf.getvalue())
            probe.write_text("clean after fake-key injection\n", encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                second = scan.main([str(probe)])
            self.assertEqual(second, 0)
            self.assertIn("hits=0 errors=0", buf.getvalue())

    def test_missing_path_is_incomplete_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                result = scan.main([str(Path(temp) / "missing.log")])
            self.assertEqual(result, 2)
            self.assertIn("SCAN_ERROR", buf.getvalue())

    def test_reject_unsafe_or_wrong_job_artifact_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "log.txt"
            path.write_bytes(b"ok")
            good = {"job_id": "job-123", "artifacts": [{
                "uri": "artifact://job-123/log.txt", "sha256": gate.sha_bytes(b"ok"), "bytes": 2
            }]}
            self.assertEqual(gate.artifact_bytes_check(root, good), 1)
            for uri in ("artifact://job-999/log.txt", "artifact://job-123/../escape.txt",
                        "artifact://job-123/a//b"):
                with self.subTest(uri=uri):
                    bad = json.loads(json.dumps(good))
                    bad["artifacts"][0]["uri"] = uri
                    with self.assertRaises(gate.GateError):
                        gate.artifact_bytes_check(root, bad)

    def test_content_tampering_rejected_even_same_size(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "patch.txt"
            path.write_bytes(b"GOOD")
            report = {"job_id": "job-aaa", "artifacts": [{
                "uri": "artifact://job-aaa/patch.txt",
                "sha256": gate.sha_bytes(b"GOOD"), "bytes": 4
            }]}
            self.assertEqual(gate.artifact_bytes_check(root, report), 1)
            path.write_bytes(b"EVIL")
            with self.assertRaisesRegex(gate.GateError, "hash mismatch"):
                gate.artifact_bytes_check(root, report)

    def test_snapshot_changes_when_content_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "draft.log"
            path.write_text("first")
            before = gate.file_snapshot(root)
            path.write_text("later")
            after = gate.file_snapshot(root)
            self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
