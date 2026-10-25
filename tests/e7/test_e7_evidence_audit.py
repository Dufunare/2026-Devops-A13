"""Adversarial offline audit tests independent of Docker or teacher evidence."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("audit", ROOT / "scripts/verify_e7_a_evidence.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class EvidenceAuditTests(unittest.TestCase):
    def test_findings_duplicates_rejected(self):
        item = {"type": "MISSING", "target": "main.o", "dependency": "config.h"}
        self.assertEqual(audit.findings_set({"findings": [item]}),
                         {("MISSING", "main.o", "config.h")})
        with self.assertRaisesRegex(audit.EvidenceError, "Duplicate"):
            audit.findings_set({"findings": [item, item]})

    def test_input_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fixture").mkdir()
            (root / "fixture" / "Makefile").write_text("app:\n\ttrue\n")
            with self.assertRaisesRegex(audit.EvidenceError, "SHA256 mismatch"):
                audit.verify_input(root, {"input_sha256": {"Makefile": "0" * 64}})

    def test_make_declaration_must_match_raw_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "evidence").mkdir()
            (root / "evidence" / "make-db.txt").write_text(
                "# Files\nmain.o: main.c unused.h\n")
            anchor = {"source": "make_database", "artifact": "make-db.txt", "line": 2,
                      "declaration": "main.o: main.c unused.h"}
            finding = {"type": "REDUNDANT", "target": "main.o", "dependency": "unused.h",
                       "evidence": [anchor]}
            audit.verify_raw_anchors(root, {"findings": [finding]})
            anchor["line"] = 1
            with self.assertRaises(audit.EvidenceError):
                audit.verify_raw_anchors(root, {"findings": [finding]})

    def test_failed_syscall_not_accepted_as_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "evidence" / "trace").mkdir(parents=True)
            (root / "evidence" / "trace" / "t.12").write_text(
                'openat(AT_FDCWD, "config.h", O_RDONLY) = -1 ENOENT\n')
            finding = {"type": "MISSING", "target": "main.o", "dependency": "config.h",
                       "evidence": [{"source": "system_call", "trace_file": "t.12",
                                     "line": 1, "pid": 12, "operation": "openat"}]}
            with self.assertRaises(audit.EvidenceError):
                audit.verify_raw_anchors(root, {"findings": [finding]})

    def test_trace_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "evidence").mkdir()
            finding = {"type": "MISSING", "target": "main.o", "dependency": "config.h",
                       "evidence": [{"source": "system_call", "trace_file": "../../secret",
                                     "line": 1, "pid": 12, "operation": "openat"}]}
            with self.assertRaisesRegex(audit.EvidenceError, "Unsafe trace path"):
                audit.verify_raw_anchors(root, {"findings": [finding]})


if __name__ == "__main__":
    unittest.main()
