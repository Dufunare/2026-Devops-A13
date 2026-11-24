"""Mock Docker boundaries for the evidence-backed child lifecycle."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_e14_runtime import ROOT, load_module

runner = load_module(ROOT / 'labs/e11e12/imgrunner.py', 'e14_child_runner_test')
CID = 'a' * 64
IMAGE = 'sha256:' + 'b' * 64


class ChildCleanup(unittest.TestCase):
    def scenario(self, folder, *, create_timeout=False, start_timeout=True, remove_exit=0,
                 remaining=''):
        calls = []
        def docker(argv, **kwargs):
            calls.append(argv)
            command = argv[1]
            if command == 'create':
                if create_timeout:
                    raise subprocess.TimeoutExpired(argv, kwargs['timeout'])
                return subprocess.CompletedProcess(argv, 0, stdout=CID + '\n', stderr='')
            if command == 'start':
                self.assertEqual(['docker', 'start', '-a', CID], argv)
                if start_timeout:
                    raise subprocess.TimeoutExpired(argv, kwargs['timeout'],
                                                    output=b'partial stdout', stderr=b'partial stderr')
                return subprocess.CompletedProcess(argv, 0, stdout='ok', stderr='')
            if command == 'inspect':
                self.assertEqual(CID, argv[-1])
                return subprocess.CompletedProcess(argv, 0, stdout=json.dumps([{
                    'Id': CID, 'Image': IMAGE, 'Mounts': [{'Destination': '/course'}],
                    'State': {'ExitCode': 0, 'Running': start_timeout}}]), stderr='')
            if command == 'rm':
                self.assertEqual(['docker', 'rm', '-f', CID], argv)
                return subprocess.CompletedProcess(argv, remove_exit, stdout='', stderr='')
            if command == 'ps':
                self.assertTrue(argv[-1].startswith('name=^/course-exec-'))
                self.assertTrue(argv[-1].endswith('$'))
                return subprocess.CompletedProcess(argv, 0, stdout=remaining, stderr='')
            self.fail('Unexpected Docker command: ' + repr(argv))
        with patch.object(runner, 'child_mount_args', return_value=['--mount', 'type=bind,src=/srv/course,dst=/course']), \
                patch.object(runner.subprocess, 'run', side_effect=docker):
            code, output = runner.run(IMAGE, ['true'], timeout=20, evidence=folder)
        record = json.loads((folder / 'step.exec.json').read_text())
        return code, output, record, calls

    def test_started_timeout_preserves_output_and_cleans_exact_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            code, output, record, calls = self.scenario(folder)
            self.assertEqual(124, code)
            self.assertIn('partial stdout', output)
            self.assertIn('partial stderr', output)
            self.assertEqual(CID, record['container_id'])
            self.assertTrue(record['timed_out'])
            self.assertTrue(record['cleanup_verified'])
            self.assertEqual([], record['cleanup_remaining'])
            self.assertEqual(['create', 'start', 'inspect', 'rm', 'ps'], [x[1] for x in calls])
            self.assertTrue((folder / 'step.inspect.json').is_file())
            self.assertEqual(CID, (folder / 'step.cid').read_text().strip())

    def test_create_timeout_never_starts_or_claims_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, record, calls = self.scenario(Path(tmp), create_timeout=True)
            self.assertEqual(125, code)
            self.assertTrue(record['create_timed_out'])
            self.assertFalse(record['cleanup_verified'])
            self.assertNotIn('start', [x[1] for x in calls])

    def test_successful_process_cannot_pass_with_failed_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, record, _ = self.scenario(Path(tmp), start_timeout=False, remove_exit=1,
                                               remaining=CID + '\n')
            self.assertEqual(125, code)
            self.assertEqual(0, record['command_exit'])
            self.assertFalse(record['cleanup_verified'])


if __name__ == '__main__':
    unittest.main()
