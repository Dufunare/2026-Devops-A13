"""A13 independently validates immutable B13 v2 fixtures and type boundaries."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_e2_v2 import validate_report


class B13V2InteropTests(unittest.TestCase):
    def valid(self):
        data = json.loads((ROOT / 'contracts/interop/b13-1d7f4839/v2/md-report.valid.json').read_bytes())
        data.setdefault('artifact_locator', {
            'uri': 'artifact://pair13/report', 'repository_url': data['repository']['url'],
            'repository_commit': data['repository']['commit'],
            'repository_path': 'reports/md.json', 'sha256': 'a' * 64,
        })
        return data

    def test_fixed_B13_files_match_hashes_and_expected_results(self):
        record = json.loads((ROOT / 'evidence/coordination/20261113/v2-interop.json').read_bytes())
        self.assertEqual(len(record['cases']), 19)
        for item in record['cases']:
            path = ROOT / 'contracts/interop/b13-1d7f4839/v2' / item['path'].split('contracts/examples/v2/', 1)[1]
            with self.subTest(path=path.name):
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item['sha256'])
                errors = validate_report(json.loads(path.read_bytes()))
                self.assertEqual(bool(errors), item['expected'] == 'REJECT')

    def test_unhashable_detector_and_finding_type_are_rejections(self):
        for value in ([], {}, ['BUILDCHECKER']):
            with self.subTest(value=value):
                data = self.valid(); data['detector'] = value
                self.assertTrue(validate_report(data))
                data = self.valid(); data['findings'][0]['type'] = value
                self.assertTrue(validate_report(data))

    def test_extensions_absent_and_namespaced_object_remain_valid(self):
        data = self.valid(); data.pop('extensions', None)
        data['findings'][0].pop('extensions', None)
        self.assertEqual(validate_report(data), [])
        data['extensions'] = {'a13.note': {'arbitrary': None}}
        data['findings'][0]['extensions'] = {'b13.note': [1, True]}
        self.assertEqual(validate_report(data), [])

    def test_explicit_null_extensions_are_rejected(self):
        for where in ('root', 'finding'):
            data = self.valid()
            (data if where == 'root' else data['findings'][0])['extensions'] = None
            self.assertTrue(validate_report(data))

    def test_locator_uri_and_path_types_are_rejected(self):
        for field, value in [('uri', None), ('uri', []), ('repository_path', 'a//b'),
                             ('repository_path', 'a/./b'), ('repository_path', 'a/'),
                             ('repository_path', '../outside')]:
            data = self.valid(); data['artifact_locator'][field] = value
            with self.subTest(field=field, value=value):
                self.assertTrue(validate_report(data))

    def test_nested_required_fields_and_unknown_fields_are_rejected(self):
        for parent, key in [('repository', 'url'), ('environment', 'arch'),
                            ('artifact_locator', 'sha256')]:
            data = self.valid(); del data[parent][key]
            self.assertTrue(validate_report(data))
            data = self.valid(); data[parent]['unknown'] = 'x'
            self.assertTrue(validate_report(data))
        data = self.valid(); del data['findings'][0]['target']
        self.assertTrue(validate_report(data))

    def test_evidence_uri_type_and_unknown_keys_are_rejected(self):
        for value in (None, [], {}, 1, 'https://invalid.example'):
            data = self.valid(); data['findings'][0]['evidence'][0]['uri'] = value
            self.assertTrue(validate_report(data))
        data = self.valid(); data['findings'][0]['evidence'][0]['unknown'] = 'x'
        self.assertTrue(validate_report(data))

    def test_producer_job_id_semantics_still_hold(self):
        for value in (None, '', [], 1):
            data = self.valid(); data['detector'] = 'ECHECKER'; data['producer_job_id'] = value
            self.assertTrue(validate_report(data))
        data = self.valid(); data['detector'] = 'A13_MANUAL_ORACLE'; data.pop('producer_job_id', None)
        self.assertEqual(validate_report(data), [])
        data['producer_job_id'] = 'job-wrong-oracle'
        self.assertTrue(validate_report(data))

    def test_bool_line_and_empty_core_strings_are_rejected(self):
        data = self.valid(); data['findings'][0]['location'] = {'status': 'RESOLVED', 'path': 'Makefile', 'line': True}
        self.assertTrue(validate_report(data))
        for field in ('report_id', 'configuration_id', 'provenance'):
            data = self.valid(); data[field] = ''
            self.assertTrue(validate_report(data))


if __name__ == '__main__':
    unittest.main()
