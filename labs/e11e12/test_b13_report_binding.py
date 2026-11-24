"""Check B13 E12 report bytes and links independently of Docker execution."""
import hashlib
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pipeline
from exchange_profile import B13_BASE, B13_ID, B13_SHA256, B13_TARGET
from lab import DEFAULT_PROFILE


class B13ReportBindingTests(unittest.TestCase):
    def test_e12_persists_one_profile_across_result_envelope_and_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / 'job'
            request = {
                'mode': 'e12', 'repo': str(root), 'candidate': str(root / 'candidate.Dockerfile'),
                'base': B13_BASE, 'target': B13_TARGET, 'expected_output': '1',
                'exchange_profile_id': B13_ID, 'profile_sha256': B13_SHA256,
                'profile': dict(DEFAULT_PROFILE, exec_image='draft', flags_allowed=['-O0'],
                                require_make_flags=True),
            }
            image = 'sha256:' + 'a' * 64
            finding = {'type': 'MISSING', 'target': 'helper.o', 'dependency': 'extra.h'}
            units = {'main.o': ['main.c'], 'helper.o': ['helper.c']}

            def snapshot(repo, revision, project, logs, profile):
                project.mkdir()
                (project / 'Makefile').write_bytes(b'helper.o: helper.c\n')
                return revision

            def draft(project, candidate, folder, expected_output, timeout):
                result = {'status': 'SUCCEEDED', 'attempts': [{'iteration': 2, 'image_id': image}]}
                pipeline.save(folder / 'result.json', result)
                return result

            def full(image_id, project, folder, clean, build, **kwargs):
                self.assertEqual(image_id, image)
                findings = [finding] if kwargs['tag'] == 'full-check-target' else []
                pipeline.save(folder / 'findings.json', {'status': 'SUCCEEDED', 'findings': findings})
                graph = [{'target': t, 'dependency': deps[0]} for t, deps in units.items()]
                pipeline.save(folder / 'actual-graph.json', graph)

            def scan(image_id, project, destination, profile, old_path, **kwargs):
                self.assertEqual(image_id, image)
                base = old_path is None
                report = {'commit': B13_BASE if base else B13_TARGET, 'actual': units,
                          'findings': [] if base else [finding], 'flags_source': 'make', 'flags': '-O0'}
                pipeline.save(destination, report)
                return report

            def validate(project, patchfile, folder, profile, exec_image):
                self.assertEqual(exec_image, image)
                verdict = {'accepted': True}
                pipeline.save(folder / 'validation.json', verdict)
                return verdict

            with ExitStack() as mocks:
                for name, impl in [('pipeline.snapshot', snapshot), ('draft.autobuild.auto_build', draft),
                                   ('imgrunner.full_in_image', full), ('imgrunner.scan_in_image', scan),
                                   ('pipeline.validate', validate)]:
                    mocks.enter_context(patch(name, side_effect=impl))
                mocks.enter_context(patch('pipeline.check_snapshot'))  # Covered by test_b13_snapshot.
                mocks.enter_context(patch('pipeline.patch', return_value=('test patch\n', [])))
                pipeline.execute(request, out)

            def read_link(ref, name):
                self.assertEqual(ref['uri'], f"artifact://{result['job_id']}/{name}")
                raw = (out / name).read_bytes()
                self.assertEqual(len(raw), ref['bytes'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), ref['sha256'])
                return json.loads(raw)

            result = json.loads((out / 'result.json').read_bytes())
            self.assertEqual(result['status'], 'SUCCEEDED', result.get('error'))
            steps = {s['name']: s['artifact'] for s in result['stages']}
            ref = steps['incremental-check']
            envelope = read_link(ref, 'incremental-check.json')
            repair = read_link(steps['repair'], 'repair.json')
            self.assertEqual(repair['data']['input_report'], ref)

            payload_uri = f"artifact://{result['job_id']}/incremental-report.json"
            refs = [entry for entry in envelope['artifacts'] if entry['uri'] == payload_uri]
            self.assertEqual(len(refs), 1)
            payload = read_link(refs[0], 'incremental-report.json')
            self.assertEqual(envelope['job_id'], result['job_id'])
            self.assertEqual(envelope['trace_id'], result['trace_id'])
            self.assertEqual(envelope['commit'], B13_TARGET)
            self.assertEqual(envelope['data'], payload)
            self.assertEqual(payload['commit'], B13_TARGET)
            for obj in (result, envelope, payload):
                self.assertEqual(obj['profile_sha256'], B13_SHA256)
            self.assertEqual(hashlib.sha256((out / 'exchange-profile.json').read_bytes()).hexdigest(),
                             B13_SHA256)
