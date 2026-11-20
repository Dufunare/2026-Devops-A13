"""Offline tests for E14 evidence integrity and cross-service event checks."""
import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('e14_gate_under_test', ROOT / 'labs/e13e14/e14_gate.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class Artifacts(unittest.TestCase):
    def test_manifest_catches_same_size_content_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            p = out / 'artifact.txt'
            p.write_text('okay', encoding='utf-8')
            item = {'uri': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                    'bytes': p.stat().st_size}
            self.assertEqual(1, GATE.verify_artifacts(out, {'artifacts': [item]}, expected_count=1))
            p.write_text('evil', encoding='utf-8')
            with self.assertRaises(GATE.GateError):
                GATE.verify_artifacts(out, {'artifacts': [item]}, expected_count=1)

    def test_manifest_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            real = out / 'real.txt'
            real.write_text('data', encoding='utf-8')
            link = out / 'link.txt'
            link.symlink_to(real)
            with self.assertRaises(GATE.GateError):
                GATE.verify_artifacts(out, {'artifacts': [
                    {'uri': link.name, 'sha256': hashlib.sha256(real.read_bytes()).hexdigest(),
                     'bytes': 4}
                ]}, expected_count=1)

    def test_manifest_rejects_relative_escape(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            for bad in ('../escape', '/etc/passwd', '.git/secret', 'a/../b'):
                with self.subTest(path=bad), self.assertRaises(GATE.GateError):
                    GATE.verify_artifacts(out, {'artifacts': [
                        {'uri': bad, 'sha256': '0' * 64, 'bytes': 0}
                    ]}, expected_count=1)


class ServiceTraces(unittest.TestCase):
    def test_good_role_counts_and_fault_code(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            log = out / 'four-services.log'
            states = {}
            items = []
            for case in ('success', 'recovery', 'fault'):
                job = 'job-' + case
                trace = 'trace-' + case
                states[case] = {'job_id': job, 'trace_id': trace}
                roles = ['draft'] if case == 'fault' else [
                    'buildchecker', 'buildchecker', 'buildchecker', 'draft', 'echecker', 'mdfixer'
                ]
                for role in roles:
                    fields = {'role': role, 'job_id': job, 'trace_id': trace,
                              'status': 'FAILED' if case == 'fault' else 'SUCCEEDED'}
                    if case == 'fault':
                        fields['error_code'] = 'TIMEOUT'
                    items.append('service-1 | ' + json.dumps(fields))
            log.write_text('\n'.join(items), encoding='utf-8')
            self.assertEqual('PASS', GATE.check_logs(out, states)['status'])
            items[-1] = items[-1].replace('TIMEOUT', 'VALUEERROR')
            log.write_text('\n'.join(items), encoding='utf-8')
            with self.assertRaises(GATE.GateError):
                GATE.check_logs(out, states)


if __name__ == '__main__':
    unittest.main()
