import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pipeline


class E13ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sha = 'a' * 40
        self.report = self.root / 'fixed.json'
        self.report.write_text(json.dumps({'schema_version': 'e11e12-1', 'kind': 'fixed-md',
            'status': 'SUCCEEDED', 'commit': self.sha, 'data': {'commit': self.sha}}) + '\n')

    def test_fixed_report_raw_bytes_are_preserved(self):
        raw = self.report.read_bytes()
        request = {'fixed_report': str(self.report), 'fixed_report_sha256': hashlib.sha256(raw).hexdigest()}
        parsed, received = pipeline.read_fixed_report(request, self.sha)
        self.assertEqual(received, raw)
        self.assertEqual(parsed['data']['commit'], self.sha)

    def check_early_rejection(self, request, code):
        request.update(mode='e11-b', repo=str(self.root), base=self.sha, target=self.sha)
        with patch.object(pipeline, 'snapshot', return_value=self.sha), \
             patch('draft.autobuild.auto_build', side_effect=AssertionError('DRAFT must not start')) as build:
            result = pipeline.execute(request, self.root / 'out')
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['error']['code'], code)
        self.assertEqual(result['stages'], [])
        build.assert_not_called()

    def test_tampered_report_rejected_before_build(self):
        digest = hashlib.sha256(self.report.read_bytes()).hexdigest()
        self.report.write_bytes(self.report.read_bytes() + b'\n')
        self.check_early_rejection({'fixed_report': str(self.report), 'fixed_report_sha256': digest},
                                   'ARTIFACT_HASH_MISMATCH')

    def test_old_target_rejected_before_build(self):
        value = json.loads(self.report.read_text());value['commit'] = 'b' * 40
        self.report.write_text(json.dumps(value))
        self.check_early_rejection({'fixed_report': str(self.report)}, 'STALE_REPORT')

    def test_payload_commit_mismatch_rejected_before_build(self):
        value = json.loads(self.report.read_text());value['data']['commit'] = 'b' * 40
        self.report.write_text(json.dumps(value))
        self.check_early_rejection({'fixed_report': str(self.report)}, 'STALE_REPORT')

    def test_wrong_report_kind_rejected_before_build(self):
        value = json.loads(self.report.read_text());value['kind'] = 'incremental-check'
        self.report.write_text(json.dumps(value))
        self.check_early_rejection({'fixed_report': str(self.report)}, 'ARTIFACT_TYPE_MISMATCH')
