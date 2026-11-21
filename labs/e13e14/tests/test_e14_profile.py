"""E14/B profile plumbing contracts. Pure unit tests; no Docker or ECS jobs."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_e14_runtime import ROOT, load_module, mocked_service

ORCH = load_module(ROOT / 'labs/e13e14/orchestrate.py', 'e14_profile_orchestrator')
COMMIT = 'a' * 40
PROFILE = {
    'units': [['calc.o', 'src/calc.c'], ['util.o', 'src/util.c']],
    'config_file': 'src/config.h', 'recursive_scan': True,
    'build_target': 'tool', 'clean_target': 'clean',
    'expected_output': '7', 'flags_allowed': ['-O0'],
}


class ProjectProfileContract(unittest.TestCase):
    def make_shape(self, root):
        (root / 'src').mkdir(parents=True)
        for name in ('calc.c', 'util.c', 'config.h'):
            (root / 'src' / name).write_text('/* fixture */\n')

    def test_default_profile_preserves_teaching_targets(self):
        profile = ORCH.resolve_project_profile(None)
        self.assertEqual(['main.o', 'helper.o'], [unit[0] for unit in profile['units']])
        self.assertEqual('app', profile['build_target'])
        self.assertEqual('orchestrator', profile['exec_image'])

    def test_non_default_source_layout_uses_B_shape_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'snapshot'
            self.make_shape(target)
            (root / 'repo').mkdir()
            with patch.object(ORCH, 'command', side_effect=[COMMIT, '', '']):
                self.assertEqual(
                    COMMIT, ORCH.snapshot(root / 'repo', COMMIT, target,
                                          root / 'logs', PROFILE))
            with patch.object(ORCH, 'command', side_effect=[COMMIT, '', '']):
                with self.assertRaisesRegex(ValueError, 'Unsupported project profile'):
                    ORCH.snapshot(root / 'repo', COMMIT, target, root / 'logs')

    def test_draft_image_mode_fails_closed_until_B_contract(self):
        with self.assertRaisesRegex(ValueError, 'not yet supported'):
            ORCH.resolve_project_profile(dict(PROFILE, exec_image='draft'))

    def test_orchestration_passes_identical_profile_to_all_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'work').mkdir()
            (root / 'data' / 'project').mkdir()
            (root / 'data' / 'candidate.Dockerfile').write_text('FROM scratch\n')
            seen = []
            def fake_call(role, payload, evidence):
                seen.append((role, payload))
                if role == 'buildchecker':
                    return {'status': 'SUCCEEDED', 'result': {'findings': []}}
                if role == 'echecker':
                    return {'status': 'SUCCEEDED', 'report': '/course/work/report.json',
                            'sha256': '0' * 64}
                return {'status': 'SUCCEEDED'}
            request = {
                'repo': '/course/data/project', 'candidate': '/course/data/candidate.Dockerfile',
                'base': COMMIT, 'target': 'b' * 40, 'profile': PROFILE,
            }
            with patch.object(ORCH, 'ROOT', root), \
                    patch.object(ORCH, 'snapshot', side_effect=[COMMIT, 'b' * 40]), \
                    patch.object(ORCH, 'call', side_effect=fake_call):
                result = ORCH.execute(request, root / 'work' / 'profile-e14')
            self.assertEqual('SUCCEEDED', result['status'], result.get('error'))
            self.assertEqual(6, len(seen))
            self.assertEqual(['draft', 'buildchecker', 'buildchecker', 'echecker',
                              'mdfixer', 'buildchecker'], [r for r, _ in seen])
            for _, payload in seen:
                self.assertEqual('tool', payload['profile']['build_target'])
                self.assertEqual('src/config.h', payload['profile']['config_file'])
            self.assertEqual('7', seen[0][1]['expected_output'])
            self.assertEqual('orchestrator', result['downstream_execution_environment'])


class ServiceProfileContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'work' / 'project'
        self.project.mkdir(parents=True)
        self.service = mocked_service()
        self.profile = ORCH.resolve_project_profile(PROFILE)

    def context(self, role):
        return (patch.object(self.service, 'ROOT', self.root),
                patch.object(self.service, 'ROLE', role),
                patch.object(self.service, 'resolve_profile', return_value=self.profile))

    def test_buildchecker_uses_profile_make_targets(self):
        with self.context('buildchecker')[0], self.context('buildchecker')[1], \
                patch.object(self.service, 'resolve_profile', return_value=self.profile), \
                patch.object(self.service, 'full_check',
                             return_value={'status': 'SUCCEEDED', 'findings': []}) as checker:
            answer = self.service.run({
                'project': str(self.project), 'out': str(self.root / 'work' / 'full'),
                'profile': PROFILE})
        self.assertEqual('SUCCEEDED', answer['status'])
        self.assertEqual('make clean', checker.call_args.kwargs['clean_command'])
        self.assertEqual('make tool', checker.call_args.kwargs['build_command'])

    def test_echecker_projects_profile_targets_not_main_helper(self):
        full = self.root / 'work' / 'target-findings.json'
        graph = self.root / 'work' / 'baseline-graph.json'
        graph.write_text(json.dumps([{'target': 'calc.o', 'dependency': 'src/calc.c'}]))
        findings = [{'type': 'MISSING', 'target': 'calc.o', 'dependency': 'src/config.h'}]
        full.write_text(json.dumps({'status': 'SUCCEEDED', 'findings': findings}))
        baseline = {'actual': {'calc.o': ['src/calc.c'], 'util.o': []}}
        current = {'commit': COMMIT, 'findings': findings}
        with patch.object(self.service, 'ROOT', self.root), \
                patch.object(self.service, 'ROLE', 'echecker'), \
                patch.object(self.service, 'resolve_profile', return_value=self.profile), \
                patch.object(self.service, 'scan', side_effect=[baseline, current]) as scanner:
            result = self.service.run({
                'project': str(self.project), 'base': str(self.project),
                'baseline_graph': str(graph), 'target_findings': str(full),
                'out': str(self.root / 'work' / 'incremental'),
                'target_commit': COMMIT, 'job_id': 'job-test', 'trace_id': 'trace-test',
                'profile': PROFILE})
        self.assertEqual(findings, result['findings'])
        self.assertEqual(self.profile, scanner.call_args_list[0].kwargs['profile'])
        self.assertEqual(self.profile, scanner.call_args_list[1].args[2])

    def test_mdfixer_passes_profile_to_validation(self):
        report = self.root / 'work' / 'report.json'
        report.write_text(json.dumps({
            'schema_version': 'e11e12-1', 'kind': 'incremental-check',
            'status': 'SUCCEEDED', 'commit': COMMIT, 'job_id': 'job-test',
            'trace_id': 'trace-test', 'data': {'commit': COMMIT, 'findings': []}}))
        with patch.object(self.service, 'ROOT', self.root), \
                patch.object(self.service, 'ROLE', 'mdfixer'), \
                patch.object(self.service, 'resolve_profile', return_value=self.profile), \
                patch.object(self.service, 'patch', return_value=('patch text', [])), \
                patch.object(self.service, 'validate', return_value={'accepted': True}) as validate:
            result = self.service.run({
                'project': str(self.project), 'out': str(self.root / 'work' / 'repair'),
                'report': str(report),
                'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(),
                'target_commit': COMMIT, 'job_id': 'job-test', 'trace_id': 'trace-test',
                'profile': PROFILE})
        self.assertEqual('SUCCEEDED', result['status'])
        self.assertEqual(self.profile, validate.call_args.kwargs['profile'])

    def test_direct_downstream_request_rejects_unwired_draft_mode(self):
        with patch.object(self.service, 'ROOT', self.root), \
                patch.object(self.service, 'ROLE', 'buildchecker'), \
                patch.object(self.service, 'resolve_profile',
                             return_value=dict(self.profile, exec_image='draft')):
            with self.assertRaisesRegex(ValueError, 'not yet supported'):
                self.service.run({'project': str(self.project),
                                  'out': str(self.root / 'work' / 'full'),
                                  'profile': dict(PROFILE, exec_image='draft')})


if __name__ == '__main__':
    unittest.main()
