"""Fail-closed tests for E14 actual Docker child-container inspection."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "labs/e13e14"))
from execution_attestation import REAL08_TAGS, verify_exec, verify_job

SOURCE = "/root/e14-isolated"
IMAGE = "sha256:" + "a" * 64
CID = "b" * 64


def good(tag="scan-target"):
    record = {"tag": tag, "image": IMAGE, "inspect_image": IMAGE,
              "exit": 0, "inspect_exit_code": 0,
              "inspect_mounts": ["/course"],
              "container_id": CID, "cleanup_exit": 0}
    inspected = [{"Id": CID, "Image": IMAGE,
                  "State": {"ExitCode": 0},
                  "Mounts": [{"Destination": "/course",
                              "Source": "/root/e14-isolated", "Type": "bind"}]}]
    return record, inspected


class AttestationContract(unittest.TestCase):
    def test_genuine_identity_and_isolated_mounts_pass(self):
        record, inspect = good()
        checked = verify_exec(record, inspect, IMAGE, SOURCE)
        self.assertEqual(CID, checked["container_id"])
        self.assertEqual(["/course"], checked["mount_destinations"])

    def test_original_inspect_image_cannot_be_forged_by_reported_id(self):
        record, inspect = good()
        inspect[0]["Image"] = "sha256:" + "c" * 64
        with self.assertRaisesRegex(ValueError, "EXEC_ACTUAL_IMAGE_MISMATCH"):
            verify_exec(record, inspect, IMAGE, SOURCE)

    def test_original_inspect_mounts_cannot_be_hidden_by_reported_mounts(self):
        record, inspect = good()
        inspect[0]["Mounts"].append({"Destination": "/var/run/docker.sock",
                                      "Source": "/var/run/docker.sock", "Type": "bind"})
        with self.assertRaisesRegex(ValueError, "EXEC_MOUNTS_RECORD_MISMATCH"):
            verify_exec(record, inspect, IMAGE, SOURCE)

    def test_legacy_socket_inheritance_is_explicitly_rejected(self):
        record, inspect = good()
        record["inspect_mounts"] = ["/course", "/var/run/docker.sock"]
        inspect[0]["Mounts"].append({"Destination": "/var/run/docker.sock",
                                     "Source": "/var/run/docker.sock", "Type": "bind"})
        with self.assertRaisesRegex(ValueError, "EXEC_DOCKER_SOCKET_EXPOSED"):
            verify_exec(record, inspect, IMAGE, SOURCE)

    def test_exit_cleanup_and_container_identity_must_match(self):
        for field in ("exit", "inspect_exit_code", "cleanup_exit"):
            record, inspect = good()
            record[field] = 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_exec(record, inspect, IMAGE, SOURCE)
        record, inspect = good()
        inspect[0]["Id"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "EXEC_CONTAINER_ID_MISMATCH"):
            verify_exec(record, inspect, IMAGE, SOURCE)

    def test_course_host_source_must_match_exact_worktree(self):
        record, inspect = good()
        with self.assertRaisesRegex(ValueError, "EXEC_COURSE_SOURCE_MISMATCH"):
            verify_exec(record, inspect, IMAGE, "/root/unrelated")

    def test_extra_mounts_rejected_even_without_socket(self):
        record, inspect = good()
        record["inspect_mounts"].append("/unapproved")
        inspect[0]["Mounts"].append({"Destination": "/unapproved",
                                     "Source": "/root/other", "Type": "bind"})
        with self.assertRaisesRegex(ValueError, "EXEC_UNAPPROVED_MOUNT"):
            verify_exec(record, inspect, IMAGE, SOURCE)

    def test_directory_requires_every_step_and_inspect_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, inspected = good()
            (root / "scan-target.exec.json").write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "EXEC_EVIDENCE_MISSING"):
                verify_job(root, IMAGE, SOURCE, ["scan-target"])
            (root / "scan-target.inspect.json").write_text(json.dumps(inspected))
            self.assertTrue(verify_job(root, IMAGE, SOURCE, ["scan-target"])["downstream_container_attested"])
            with self.assertRaisesRegex(ValueError, "EXEC_REQUIRED_STEPS_MISSING"):
                verify_job(root, IMAGE, SOURCE, ["scan-target", "full-check-recheck"])

    def test_nested_validation_steps_are_counted_in_same_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for tag, folder in (("scan-target", root / "inimage"),
                                ("validate-01-make", root / "validation" / "inimage")):
                folder.mkdir(parents=True)
                rec, inspected = good(tag)
                (folder / f"{tag}.exec.json").write_text(json.dumps(rec))
                (folder / f"{tag}.inspect.json").write_text(json.dumps(inspected))
            result = verify_job(root, IMAGE, SOURCE, ["scan-target", "validate-01-make"])
            self.assertEqual(2, len(result["verified_tags"]))

    def test_duplicate_tags_from_different_subdirectories_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec, inspected = good()
            for folder in (root / "a", root / "b"):
                folder.mkdir()
                (folder / "scan-target.exec.json").write_text(json.dumps(rec))
                (folder / "scan-target.inspect.json").write_text(json.dumps(inspected))
            with self.assertRaisesRegex(ValueError, "EXEC_TAG_INVALID"):
                verify_job(root, IMAGE, SOURCE, ["scan-target"])

    def test_legacy_handoff_summary_fails_without_raw_inspect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = good()
            record["inspect_mounts"] = ["/var/run/docker.sock", "/course"]
            (root / "scan-target.exec.json").write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "EXEC_DOCKER_SOCKET_EXPOSED"):
                verify_job(root, IMAGE, SOURCE, ["scan-target"])

    def test_real08_full_required_tag_set_is_declared(self):
        self.assertIn("full-check-recheck", REAL08_TAGS)
        self.assertIn("validate-recheck-scan", REAL08_TAGS)
        self.assertEqual(len(REAL08_TAGS), len(set(REAL08_TAGS)))


if __name__ == "__main__":
    unittest.main()
