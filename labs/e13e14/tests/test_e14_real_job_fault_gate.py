"""Fail-closed negative tests for timeout originals (offline, not Docker)."""
import copy
import unittest

from test_e14_runtime import ROOT, load_module

gate = load_module(ROOT / 'labs/e13e14/real_job_fault_gate.py', 'e14_fault_gate_test')


class FaultOriginals(unittest.TestCase):
    def setUp(self):
        self.cid = 'a' * 64
        self.image = 'sha256:' + 'b' * 64
        self.name = 'course-exec-' + 'c' * 32
        self.source = '/srv/isolated'
        self.record = {
            'tag': gate.TAG, 'container_id': self.cid, 'container_name': self.name,
            'image': self.image, 'inspect_image': self.image, 'timeout_s': gate.TIMEOUT,
            'create_exit': 0, 'create_timed_out': False, 'timed_out': True,
            'command_exit': 124, 'exit': 124, 'cleanup_exit': 0, 'cleanup_verified': True,
            'cleanup_lookup_exit': 0, 'cleanup_remaining': [],
            'start_argv': ['docker', 'start', '-a', self.cid],
            'cleanup_argv': ['docker', 'rm', '-f', self.cid],
            'cleanup_lookup_argv': ['docker', 'ps', '-aq', '--no-trunc', '--filter',
                                    'name=^/' + self.name + '$'],
            'inspect_mounts': ['/course'],
        }
        self.inspect = [{'Id': self.cid, 'Image': self.image, 'Name': '/' + self.name,
                         'State': {'Running': True}, 'Mounts': [
                            {'Type': 'bind', 'Destination': '/course', 'Source': self.source}]}]

    def test_originals_and_exact_cleanup_pass(self):
        self.assertEqual((self.cid, self.name), gate.verify_timed_out_child(
            self.record, self.inspect, self.image, self.source))

    def test_fake_timeout_or_unconfirmed_cleanup_rejected(self):
        for field, value in [('timed_out', False), ('create_timed_out', True),
                             ('timeout_s', 600), ('cleanup_verified', False),
                             ('cleanup_remaining', [self.cid]), ('cleanup_exit', 1),
                             ('cleanup_argv', ['docker', 'rm', '-f', 'other'])]:
            with self.subTest(field=field), self.assertRaises(gate.GateError):
                gate.verify_timed_out_child(dict(self.record, **{field: value}),
                                            self.inspect, self.image, self.source)

    def test_wrong_image_stopped_child_or_socket_mount_rejected(self):
        variants = []
        for field, value in [('Image', 'sha256:' + 'f' * 64),
                             ('State', {'Running': False}),
                             ('Id', 'd' * 64)]:
            raw = copy.deepcopy(self.inspect)
            raw[0][field] = value
            variants.append(raw)
        raw = copy.deepcopy(self.inspect)
        raw[0]['Mounts'].append({'Type': 'bind', 'Destination': '/var/run/docker.sock'})
        variants.append(raw)
        for raw in variants:
            with self.subTest(raw=raw), self.assertRaises(gate.GateError):
                gate.verify_timed_out_child(self.record, raw, self.image, self.source)


if __name__ == '__main__':
    unittest.main()
