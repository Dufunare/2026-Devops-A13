import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pipeline
from exchange_profile import BASE, PROFILE_ID, PROFILE_SHA256, TARGET


class ExchangeProfileTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.request = {
            'mode': 'e11-a', 'repo': str(self.root), 'base': BASE, 'target': TARGET,
            'exchange_profile_id': PROFILE_ID, 'profile_sha256': PROFILE_SHA256,
        }

    def test_exact_profile_is_bound_before_artifact_hashes(self):
        flags = '-std=c99 -Wall -Wextra -fpic -O2 -DNDEBUG'
        current = {'schema_version': 'e8e10-1', 'commit': TARGET, 'findings': [],
                   'flags_source': 'make', 'flags': flags, 'actual': {'toml.o': ['toml.c']}}

        def snapshot(_repo, revision, project, _logs, _profile):
            project.mkdir()
            return revision

        def full(_project, out, _profile):
            report = {'status': 'SUCCEEDED', 'findings': []}
            pipeline.save(out / 'findings.json', report)
            pipeline.save(out / 'actual-graph.json', [{'target': 'toml.o', 'dependency': 'toml.c'}])
            return report

        out = self.root / 'evidence'
        with patch.object(pipeline, 'snapshot', side_effect=snapshot), \
             patch.object(pipeline, 'check_snapshot'), patch.object(pipeline, 'full', side_effect=full), \
             patch.object(pipeline, 'scan', side_effect=[dict(current), dict(current)]):
            result = pipeline.execute(self.request, out)
        self.assertEqual(result['status'], 'SUCCEEDED', result.get('error'))
        stage = pipeline.load_artifact(out / 'incremental-check.json', result['stages'][1]['artifact']['sha256'])
        payload = pipeline.load_artifact(out / 'incremental-report.json', stage['artifacts'][0]['sha256'])
        self.assertEqual(stage['data'], payload)
        self.assertEqual([d['profile_sha256'] for d in (result, stage, payload)], [PROFILE_SHA256] * 3)
        self.assertEqual(pipeline.digest((out / 'exchange-profile.json').read_bytes()), PROFILE_SHA256)

    def test_wrong_binding_is_rejected_before_loading_project(self):
        for change in ({'target': BASE}, {'profile_sha256': '0' * 64}, {'profile': {}}, {'mode': 'e12'}):
            with self.subTest(change=change), patch.object(pipeline, 'snapshot') as snapshot:
                out = Path(tempfile.mkdtemp(dir=self.root))
                result = pipeline.execute(dict(self.request, **change), out)
                self.assertEqual(result['error']['code'], 'EXCHANGE_PROFILE_MISMATCH')
                self.assertEqual(result['stages'], [])
                snapshot.assert_not_called()
