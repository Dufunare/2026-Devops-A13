"""Offline negative contracts for the E14 real-project evidence wire."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "labs/e13e14"), str(ROOT / "labs/e11e12")]
from contract import (checked_incremental, digest, findings_by_scope, profile_sha256,
                      successful_draft_image, verify_request_identity)
import real_preflight

IMAGE = "sha256:" + "a" * 64
COMMIT = "b" * 40
PROFILE = {"units": [["toml.o", "toml.c"]], "exec_image": "draft"}


def report_bytes(**overrides):
    obj = {"schema_version": "e11e12-1", "kind": "incremental-check",
           "status": "SUCCEEDED", "job_id": "job-1", "trace_id": "trace-1",
           "commit": COMMIT, "profile_sha256": profile_sha256(PROFILE),
           "draft_image_id": IMAGE,
           "data": {"commit": COMMIT, "findings": [
               {"type": "MISSING", "target": "toml.o", "dependency": "toml.h"}]}}
    obj.update(overrides)
    return json.dumps(obj).encode()


class WireContract(unittest.TestCase):
    def verify(self, raw, **kwargs):
        return checked_incremental(raw, digest(raw), "job-1", "trace-1", COMMIT,
                                   profile_sha256(PROFILE), IMAGE, **kwargs)

    def test_valid_incremental_original_bytes(self):
        raw = report_bytes()
        self.assertEqual("incremental-check", self.verify(raw)["kind"])

    def test_report_tampering_stale_job_and_target_rejected(self):
        raw = report_bytes()
        with self.assertRaisesRegex(ValueError, "REPORT_HASH_MISMATCH"):
            checked_incremental(raw + b" ", digest(raw), "job-1", "trace-1", COMMIT)
        for fields in ({"job_id": "other"}, {"trace_id": "other"},
                       {"commit": "c" * 40}, {"kind": "fixed-md"},
                       {"profile_sha256": "0" * 64},
                       {"draft_image_id": "sha256:" + "c" * 64}):
            with self.subTest(fields=fields), self.assertRaisesRegex(
                ValueError, "MISMATCH"
            ):
                self.verify(report_bytes(**fields))

    def test_data_commit_and_findings_shape_fail_closed(self):
        for payload in ({"commit": "a" * 40, "findings": []},
                        {"commit": COMMIT, "findings": "oops"}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.verify(report_bytes(data=payload))

    def test_duplicate_json_key_rejected(self):
        raw = report_bytes()[:-1] + b', "kind": "incremental-check"}'
        with self.assertRaisesRegex(ValueError, "Duplicate key"):
            self.verify(raw)

    def test_draft_id_must_be_a_successful_build_sha_not_tag(self):
        valid = {"status": "SUCCEEDED", "result": {"status": "SUCCEEDED",
                 "attempts": [{"iteration": 1, "build_exit_code": 1},
                              {"iteration": 2, "build_exit_code": 0, "image_id": IMAGE}]}}
        self.assertEqual(IMAGE, successful_draft_image(valid))
        for bad in ({"status": "SUCCEEDED", "result": {"status": "SUCCEEDED", "attempts": []}},
                    {"status": "SUCCEEDED", "result": {"status": "SUCCEEDED",
                     "attempts": [{"build_exit_code": 0, "image_id": "tag:latest"}]}},
                    {**valid, "draft_image_id": "sha256:" + "c" * 64}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                successful_draft_image(bad)

    def test_profile_binding_rejected_if_mutated(self):
        with self.assertRaisesRegex(ValueError, "PROFILE_HASH_MISMATCH"):
            verify_request_identity({"profile_sha256": "a" * 64}, PROFILE)
        self.assertEqual(IMAGE, verify_request_identity(
            {"profile_sha256": profile_sha256(PROFILE), "draft_image_id": IMAGE}, PROFILE))

    def test_scope_requires_full_project_missing_zero(self):
        fs = [{"type": "MISSING", "target": "toml_json", "dependency": "toml.h"},
              {"type": "REDUNDANT", "target": "toml.o", "dependency": "unused.h"}]
        scope = findings_by_scope(fs, PROFILE)
        self.assertEqual(1, scope["remaining_missing_full"])
        self.assertEqual(0, scope["remaining_missing_profile"])
        self.assertEqual(2, len(scope["full_findings"]))

    def test_real_preflight_stops_before_docker_and_requires_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "data" / "real-project"
            repo.mkdir(parents=True)
            candidate = root / "data" / "candidate.Dockerfile"
            candidate.write_text("FROM scratch\n")
            req = {"mode": "e12", "base": "a" * 40, "target": COMMIT,
                   "repo": "/course/data/real-project",
                   "candidate": "/course/data/candidate.Dockerfile",
                   "profile": PROFILE}
            request_path = root / "request.json"
            request_path.write_text(json.dumps(req))
            with patch.object(real_preflight, "git", side_effect=[
                COMMIT, "", ""]), patch.object(real_preflight, "shape_ok",
                                                 return_value=(True, {"toml.c"}, {"toml.c"})):
                result = real_preflight.verify(
                    request_path, root, expected_request_sha=digest(request_path.read_bytes()),
                    expected_candidate_sha=digest(candidate.read_bytes()))
            self.assertEqual("INPUT_VERIFIED_EXECUTION_NOT_STARTED", result["status"])
            self.assertIsNone(result["draft_image_id"])
            self.assertFalse(result["downstream_container_attested"])


if __name__ == "__main__":
    unittest.main()
