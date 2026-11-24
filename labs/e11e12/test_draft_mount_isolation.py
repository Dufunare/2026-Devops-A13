import json
import subprocess
import unittest
from unittest.mock import patch

import imgrunner


class DraftMountIsolationTests(unittest.TestCase):
    def test_child_does_not_inherit_all_parent_mounts(self):
        parent_mounts = [
            {"Type": "bind", "Source": "/srv/course",
             "Destination": "/course", "RW": True},
            {"Type": "bind", "Source": "/var/run/docker.sock",
             "Destination": "/var/run/docker.sock", "RW": True},
        ]
        child_commands = []

        def fake_docker(argv, **kwargs):
            if argv[:2] == ["docker", "inspect"]:
                output = json.dumps([{"Mounts": parent_mounts}])
            elif argv[:2] == ["docker", "run"]:
                child_commands.append(argv)
                output = ""
            else:
                self.fail(f"Unexpected Docker command: {argv}")
            return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")

        with patch.object(imgrunner.subprocess, "run", side_effect=fake_docker):
            imgrunner.run("draft-test-image", ["true"], ptrace=False)

        self.assertEqual(len(child_commands), 1)
        child = child_commands[0]
        mount_specs = [child[i + 1] for i, arg in enumerate(child) if arg == "--mount"]
        self.assertEqual(mount_specs, ["type=bind,src=/srv/course,dst=/course,bind-recursive=disabled"])
        self.assertNotIn("-v", child)
        self.assertNotIn("--volume", child)
        self.assertNotIn("--volumes-from", child,
                         "DRAFT child inherits every parent mount")
        self.assertNotIn("/var/run/docker.sock", " ".join(child),
                         "DRAFT child explicitly receives the host Docker socket")
