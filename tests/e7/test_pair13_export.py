"""Consumer-facing checks for real E6 output adaptation and provenance."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import shutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from export_pair13_report import build_export
from validate_e2_v2 import validate_report


class Pair13ExportTests(unittest.TestCase):
    def context(self):
        return {"repository_url": "https://github.com/Dufunare/2026-Devops-A13.git",
                "source_commit": "202555aea6092d0e54105403f4402baa9e3c40ec",
                "evidence_commit": "694d6cb2961698437cf8de581afcee515eb293b7",
                "configuration_id": "a13-e6-md-rd-linux-amd64-gcc14",
                "environment": {"os": "linux", "arch": "amd64"}}

    def source(self, stage):
        return ROOT / "evidence/E6/241870063" / stage / "evidence/findings.json"

    def test_real_before_report_preserves_findings_and_resolved_makefile(self):
        result, registration = build_export(self.source("e6-before"), ROOT, **self.context())
        self.assertEqual(validate_report(result), [])
        self.assertEqual({(x["type"], x["target"], x["dependency"]) for x in result["findings"]},
                         {("MISSING", "main.o", "config.h"), ("REDUNDANT", "main.o", "unused.h")})
        self.assertEqual(result["findings"][0]["location"]["line"], 6)
        self.assertEqual(result["producer_job_id"], "job-cli-" + registration["recorded_source_trace_id"])
        self.assertFalse(registration["http_job_api_deployed"])

    def test_real_fixed_report_is_empty_and_does_not_claim_a_fixed_git_commit(self):
        result, _ = build_export(self.source("e6-after"), ROOT, **self.context())
        self.assertEqual(result["findings"], [])
        self.assertEqual(validate_report(result), [])
        self.assertIn("isolated", result["extensions"]["a13.source_worktree"])

    def test_locator_uses_immutable_source_snapshot_and_actual_file_hash(self):
        import hashlib
        source = self.source("e6-before")
        result, registry = build_export(source, ROOT, **self.context())
        self.assertEqual(result["artifact_locator"]["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
        for finding in result["findings"]:
            for item in finding["evidence"]:
                if "uri" in item:
                    self.assertIn(item["uri"], {v["uri"] for v in registry["artifacts"].values()})

    def test_failed_detector_run_cannot_be_exported_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p = root / "findings.json"
            p.write_text(json.dumps({"status": "FAILED"}))
            with self.assertRaisesRegex(ValueError, "successfully"):
                build_export(p, root, **self.context())

    def test_tampered_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); dest = root / "case"
            shutil.copytree(self.source("e6-before").parent.parent, dest)
            (dest / "fixture/config.h").write_text("tampered\n")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                build_export(dest / "evidence/findings.json", root, **self.context())

    def test_short_commit_cannot_be_used_as_artifact_identity(self):
        context = self.context(); context["evidence_commit"] = "694d6cb"
        with self.assertRaisesRegex(ValueError, "40-hex"):
            build_export(self.source("e6-before"), ROOT, **context)
