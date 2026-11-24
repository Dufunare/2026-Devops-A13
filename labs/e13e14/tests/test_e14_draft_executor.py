"""Offline broker contracts: synthetic evidence, not a Docker runtime result."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_e14_runtime import ROOT, load_module
ORCH = load_module(ROOT / 'labs/e13e14/orchestrate.py', 'e14_broker_orchestrator')
from draft_executor import (DraftExecutor, OPERATIONS, check_profile,
                            operation_tags, sha, save, verify_receipts, evidence_files)
from contract import profile_sha256
from lab import resolve_profile

IMAGE = 'sha256:' + 'a' * 64
SOURCE = '/root/isolated'
BASE = 'b' * 40
TARGET = 'c' * 40


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.job = self.root / 'work' / 'test'
        self.job.mkdir(parents=True)
        self.profile = resolve_profile({'exec_image': 'draft'})
        save(self.job / 'request.json', {})
        self.meta = {'job_id': 'job-' + '1' * 32, 'trace_id': 'trace-' + '2' * 32,
                     'base_commit': BASE, 'target_commit': TARGET,
                     'request_sha256': sha(self.job / 'request.json'),
                     'candidate_sha256': 'd' * 64,
                     'profile_sha256': profile_sha256(self.profile),
                     'draft_image_id': IMAGE}
        self.broker = DraftExecutor(self.root, SOURCE)
        self.broker.activate((self.job, {k: v for k, v in self.meta.items() if k != 'draft_image_id'}),
                             self.profile, IMAGE)

    def request(self, operation, **extra):
        return {**self.meta, 'operation': operation, 'job_root': str(self.job), **extra}

    def test_rejects_wrong_job_image_profile_root_and_arbitrary_command(self):
        for field, value in [('job_id', 'job-' + '3' * 32),
                             ('draft_image_id', 'sha256:' + 'f' * 64),
                             ('profile_sha256', 'f' * 64), ('job_root', '/course/work/other'),
                             ('argv', ['sh', '-c', 'true'])]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.broker.execute(self.request('full-check-baseline', **{field: value}))
        self.assertEqual(0, self.broker.active['next'])

    def test_rejects_out_of_order_and_replay(self):
        with self.assertRaisesRegex(ValueError, 'EXEC_OPERATION_ORDER'):
            self.broker.execute(self.request('scan-target'))
        self.broker.active['next'] = 1
        with self.assertRaisesRegex(ValueError, 'EXEC_OPERATION_ORDER'):
            self.broker.execute(self.request('full-check-baseline'))

    def test_rejects_changed_original_request_and_closes_job(self):
        save(self.job / 'request.json', {'changed': True})
        with self.assertRaisesRegex(ValueError, 'EXEC_REQUEST_CHANGED'):
            self.broker.execute(self.request('full-check-baseline'))
        self.assertTrue(self.broker.active['failed'])
        with self.assertRaisesRegex(ValueError, 'EXEC_NO_ACTIVE_JOB'):
            self.broker.execute(self.request('full-check-baseline'))

    def test_default_validation_tag_set_includes_second_program_run(self):
        self.assertEqual(['validate-01-make', 'validate-02-make', 'validate-03-app',
                          'validate-04-make', 'validate-05-app', 'validate-recheck-scan'],
                         operation_tags(self.profile)['validate'])
        profile = dict(self.profile, build_target='toml_json', header_check='rebuild')
        self.assertEqual(['validate-01-make', 'validate-02-make', 'validate-03-toml-json',
                          'validate-04-make', 'validate-recheck-scan'], operation_tags(profile)['validate'])

    def test_rejects_unresolved_make_all_and_unsafe_profile(self):
        for raw in ({'build_target': 'all'}, {'build_target': '-f'},
                    {'config_file': '../outside'}, {'units': [['main.o', '/tmp/x.c']]}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                check_profile(dict(self.profile, **raw))

    def originals(self, op, index):
        folder = self.job / ('repair-work/validation/inimage' if op == 'validate' else 'inimage')
        for offset, tag in enumerate(operation_tags(self.profile)[op]):
            cid = '%064x' % (index * 16 + offset + 1)
            save(folder / (tag + '.exec.json'),
                 {'tag': tag, 'image': IMAGE, 'inspect_image': IMAGE, 'exit': 0,
                  'inspect_exit_code': 0, 'cleanup_exit': 0, 'container_id': cid,
                  'inspect_mounts': ['/course']})
            save(folder / (tag + '.inspect.json'), [{'Id': cid, 'Image': IMAGE,
                  'State': {'ExitCode': 0},
                  'Mounts': [{'Destination': '/course', 'Source': SOURCE, 'Type': 'bind'}]}])

    def test_full_operation_requires_raw_inspect_and_writes_bound_receipt(self):
        def full(_image, _project, folder, *_args, **_kwargs):
            save(folder / 'findings.json', {'status': 'SUCCEEDED', 'findings': []})
            self.originals('full-check-baseline', 0)
        with patch('imgrunner.full_in_image', side_effect=full):
            response = self.broker.execute(self.request('full-check-baseline'))
        self.assertEqual('SUCCEEDED', response['status'])
        self.assertEqual(1, self.broker.active['next'])
        receipt = json.loads((self.job / 'execution-receipts/full-check-baseline.json').read_bytes())
        self.assertEqual(self.meta, receipt['identity'])
        self.assertEqual(2, len(receipt['originals']))

    def test_missing_original_blocks_broker(self):
        def full(_image, _project, folder, *_args, **_kwargs):
            save(folder / 'findings.json', {'status': 'SUCCEEDED', 'findings': []})
        with patch('imgrunner.full_in_image', side_effect=full), \
                self.assertRaisesRegex(ValueError, 'EXEC_RECORDS_MISSING'):
            self.broker.execute(self.request('full-check-baseline'))
        self.assertTrue(self.broker.active['failed'])
        self.assertFalse((self.job / 'execution-receipts').exists())

    def test_final_receipts_bind_all_steps_to_same_job_and_originals(self):
        report_sha = 'e' * 64
        for index, op in enumerate(OPERATIONS):
            self.originals(op, index)
            save(self.job / 'execution-receipts' / (op + '.json'),
                 {'operation': op, 'identity': self.meta,
                  'report_sha256': report_sha if op == 'validate' else None,
                  'originals': evidence_files(self.job, op, self.profile)})
        result = verify_receipts(self.job, self.meta, self.profile, SOURCE, report_sha)
        self.assertTrue(result['downstream_container_attested'])
        self.assertEqual(11, len(result['verified_tags']))
        receipt = self.job / 'execution-receipts/validate.json'
        body = json.loads(receipt.read_bytes())
        body['report_sha256'] = 'f' * 64
        save(receipt, body)
        with self.assertRaisesRegex(ValueError, 'EXEC_RECEIPT_MISMATCH'):
            verify_receipts(self.job, self.meta, self.profile, SOURCE, report_sha)


if __name__ == '__main__':
    unittest.main()
