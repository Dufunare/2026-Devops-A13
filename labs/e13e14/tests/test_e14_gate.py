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


class ServiceContainers(unittest.TestCase):
    ROLES = ('buildchecker', 'echecker', 'draft', 'mdfixer')

    @staticmethod
    def identities():
        return {role: {'container_id': char * 64,
                       'started_at': '2026-11-22T07:00:00.123456789Z'}
                for role, char in zip(ServiceContainers.ROLES, 'abcd')}

    def test_same_id_and_startedat_remain_stable(self):
        initial = self.identities()
        self.assertEqual('PASS',
                         GATE.verify_continuity(initial, self.identities(),
                                                'before-fault', 'after-recovery')['status'])

    def test_replacement_container_rejected(self):
        before, after = self.identities(), self.identities()
        after['draft']['container_id'] = 'e' * 64
        with self.assertRaisesRegex(GATE.GateError, 'draft container was replaced'):
            GATE.verify_continuity(before, after, 'before-fault', 'after-recovery')

    def test_restart_same_container_id_rejected(self):
        before, after = self.identities(), self.identities()
        after['mdfixer']['started_at'] = '2026-11-22T07:01:00.123456789Z'
        with self.assertRaisesRegex(GATE.GateError, 'mdfixer container restarted'):
            GATE.verify_continuity(before, after, 'before-fault', 'after-recovery')

    def test_incomplete_snapshot_rejected(self):
        before, after = self.identities(), self.identities()
        del after['echecker']
        with self.assertRaisesRegex(GATE.GateError, 'missing Compose service'):
            GATE.verify_continuity(before, after, 'before-fault', 'after-recovery')

    def test_snapshot_inspects_only_expected_four_project_services(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        ids = {role: letter * 64 for role, letter in zip(self.ROLES, 'abcd')}
        seen = []
        project = 'e14-241830217-ci-test'

        def fake_run(argv, **kwargs):
            seen.append(list(argv))
            if argv[1] == 'compose':
                role = argv[-1]
                self.assertIn(role, ids)
                self.assertEqual(project, argv[argv.index('-p') + 1])
                self.assertEqual(kwargs['env']['E14_ROOT'], str(GATE.ROOT))
                return SimpleNamespace(returncode=0, stdout=ids[role] + '\n', stderr='')
            self.assertEqual(argv[1:4], ['inspect', '--type', 'container'])
            ident = argv[4]
            role = next(key for key, value in ids.items() if value == ident)
            data = [{'Id': ident,
                     'Config': {'Labels': {'com.docker.compose.project': project,
                                           'com.docker.compose.service': role}},
                     'State': {'Running': True, 'StartedAt': '2026-11-22T07:00:00.123456789Z'}}]
            return SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr='')

        with tempfile.TemporaryDirectory() as dirname, \
                patch.object(GATE.subprocess, 'run', side_effect=fake_run):
            out = Path(dirname)
            captured = GATE.service_containers(out, project, 'course-e11e12:999', 'before-fault')
            saved = json.loads((out / 'containers-before-fault.json').read_text())
        self.assertEqual(ids, {role: item['container_id'] for role, item in captured.items()})
        self.assertEqual(captured, saved['services'])
        self.assertEqual(8, len(seen))
        self.assertFalse(any('restart' in str(argv) or 'up' in str(argv)
                             or 'down' in str(argv) for argv in seen))

    def test_wrong_compose_project_rejected(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        def fake_run(argv, **_kwargs):
            if argv[1] == 'compose':
                return SimpleNamespace(returncode=0, stdout='a' * 64 + '\n', stderr='')
            data = [{'Id': 'a' * 64,
                     'Config': {'Labels': {'com.docker.compose.project': 'another-student',
                                           'com.docker.compose.service': 'buildchecker'}},
                     'State': {'Running': True, 'StartedAt': '2026-11-22T07:00:00Z'}}]
            return SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr='')
        with tempfile.TemporaryDirectory() as dirname, \
                patch.object(GATE.subprocess, 'run', side_effect=fake_run), \
                self.assertRaisesRegex(GATE.GateError, 'project / role mismatch'):
            GATE.service_containers(Path(dirname), 'ours', 'course-e11e12:999', 'before-fault')

    def test_missing_or_nonrunning_container_rejected(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as dirname:
            with patch.object(GATE.subprocess, 'run',
                              return_value=SimpleNamespace(returncode=0, stdout='', stderr='')):
                with self.assertRaisesRegex(GATE.GateError, 'exactly one container ID'):
                    GATE.service_containers(Path(dirname), 'ours', 'course-e11e12:999', 'before-fault')


if __name__ == '__main__':
    unittest.main()
