"""Independent producer-export tests, using real Git commits and immutable bytes."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from handoff import HandoffError, export_handoff


class Student241830088HandoffTests(unittest.TestCase):
    source = 'a' * 40
    image = 'sha256:' + 'b' * 64

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / 'project'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'main.c').write_text('int main(void){return 0;}\n')
        self.git('add', '.')
        self.git('commit', '-m', 'base')
        self.base = self.git('rev-parse', 'HEAD')
        (self.repo / 'main.c').write_text('int main(void){return 1;}\n')
        self.git('add', '.')
        self.git('commit', '-m', 'target')
        self.target = self.git('rev-parse', 'HEAD')
        self.run = self.root / 'run'
        self.run.mkdir()
        self.out = self.root / 'handoff'
        self.toolchain = self.root / 'toolchain.lock'
        self.toolchain.write_text('gcc=fixture\nmake=fixture\n')
        self.job, self.trace = 'job-a13-fixture', 'trace-a13-fixture'
        self.payload = {'schema_version': 'e8e10-1', 'commit': self.target,
                        'findings': [{'type': 'MISSING', 'target': 'main.o', 'dependency': 'config.h'}],
                        'elapsed_s': 0.25}
        self.envelope = {'schema_version': 'e11e12-1', 'kind': 'incremental-check',
                         'status': 'SUCCEEDED', 'commit': self.target,
                         'job_id': self.job, 'trace_id': self.trace, 'data': self.payload}
        self.full = {'schema_version': 'e11e12-1', 'kind': 'full-check',
                     'status': 'SUCCEEDED', 'commit': self.base,
                     'job_id': self.job, 'trace_id': self.trace,
                     'data': {'status': 'SUCCEEDED'}, 'artifacts': []}
        (self.run / 'student-source-commit.txt').write_text(self.source + '\n')
        (self.run / 'environment-image-id.txt').write_text(self.image + '\n')
        self.write()

    def git(self, *args, cwd=None):
        return subprocess.check_output(['git', *args], cwd=cwd or self.repo,
                                       text=True, stderr=subprocess.DEVNULL).strip()

    def reference(self, filename):
        raw = (self.run / filename).read_bytes()
        return {'uri': f'artifact://{self.job}/{filename}',
                'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}

    def write(self, payload_raw=None, envelope_raw=None, references=None):
        raw = payload_raw if payload_raw is not None else (json.dumps(self.payload, indent=2) + '\n').encode()
        (self.run / 'incremental-report.json').write_bytes(raw)
        self.envelope['artifacts'] = references if references is not None else [self.reference('incremental-report.json')]
        raw = envelope_raw if envelope_raw is not None else (json.dumps(self.envelope, indent=2) + '\n').encode()
        (self.run / 'incremental-check.json').write_bytes(raw)
        (self.run / 'full-check.json').write_text(json.dumps(self.full) + '\n')
        result = {'schema_version': 'e11e12-1', 'status': 'SUCCEEDED',
                  'job_id': self.job, 'trace_id': self.trace,
                  'base_commit': self.base, 'target_commit': self.target,
                  'stages': [{'name': name, 'artifact': self.reference(name + '.json')}
                             for name in ['full-check', 'incremental-check']],
                  'artifacts': [self.reference(name) for name in
                                ['full-check.json', 'incremental-check.json', 'incremental-report.json']]}
        (self.run / 'result.json').write_text(json.dumps(result) + '\n')

    def export(self, **overrides):
        values = dict(run_dir=self.run, repo=self.repo, source_sha=self.source,
                      image_id=self.image, toolchain=self.toolchain, out=self.out)
        values.update(overrides)
        return export_handoff(**values)

    def reject(self, code):
        before = {p.name: p.read_bytes() for p in self.run.iterdir() if p.is_file()}
        refs = self.git('show-ref')
        with self.assertRaises(HandoffError) as error:
            self.export()
        self.assertEqual(error.exception.code, code)
        self.assertFalse(self.out.exists())
        self.assertEqual(refs, self.git('show-ref'))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.run.iterdir() if p.is_file()})

    def test_valid_export_preserves_originals_and_contains_exact_project_commits(self):
        before = {p.name: p.read_bytes() for p in self.run.iterdir() if p.is_file()}
        refs = self.git('show-ref')
        manifest = self.export()
        for name in ['incremental-check.json', 'incremental-report.json', 'full-check.json', 'result.json']:
            self.assertEqual(before[name], (self.out / name).read_bytes())
        self.assertEqual(refs, self.git('show-ref'))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.run.iterdir() if p.is_file()})
        clone = self.root / 'received-project'
        self.git('clone', '-b', 'handoff-target', str(self.out / 'project.bundle'), str(clone))
        self.assertEqual(self.target, self.git('rev-parse', 'HEAD', cwd=clone))
        self.assertEqual(self.base, self.git('rev-parse', self.base, cwd=clone))
        self.assertEqual('READY_FOR_DELIVERY_NOT_ACKNOWLEDGED', manifest['state'])
        self.assertEqual('unknown', manifest['data_origin'])
        self.assertEqual('unknown', manifest['draft_image_reused'])
        self.assertEqual(before['student-source-commit.txt'], (self.out / 'student-source-commit.txt').read_bytes())
        self.assertEqual(self.toolchain.read_bytes(), (self.out / 'toolchain.txt').read_bytes())
        for line in (self.out / 'SHA256SUMS').read_text().splitlines():
            digest, filename = line.split('  ', 1)
            self.assertEqual(digest, hashlib.sha256((self.out / filename).read_bytes()).hexdigest())

    def test_payload_tampering_is_rejected(self):
        p = self.run / 'incremental-report.json'
        p.write_bytes(p.read_bytes() + b' ')
        self.reject('ARTIFACT_HASH_MISMATCH')

    def test_inner_commit_cannot_be_hidden_by_correct_envelope(self):
        self.payload['commit'] = self.base
        self.write()
        self.reject('STALE_REPORT')

    def test_stage_job_mismatch_is_rejected(self):
        self.envelope['job_id'] = 'job-other'
        self.write()
        self.reject('JOB_ID_MISMATCH')

    def test_stage_trace_mismatch_is_rejected(self):
        self.envelope['trace_id'] = 'trace-other'
        self.write()
        self.reject('TRACE_ID_MISMATCH')

    def test_duplicate_json_key_is_rejected_even_with_updated_hash(self):
        raw = b'{"schema_version":"e8e10-1","commit":"' + self.target.encode() + b'","commit":"' + self.base.encode() + b'"}'
        self.write(payload_raw=raw)
        self.reject('INVALID_JSON')

    def test_nan_is_rejected_even_with_updated_hash(self):
        raw = json.dumps(self.payload).replace('0.25', 'NaN').encode()
        self.write(payload_raw=raw)
        self.reject('INVALID_JSON')

    def test_float_overflow_is_rejected(self):
        raw = json.dumps(self.payload).replace('0.25', '1e999').encode()
        self.write(payload_raw=raw)
        self.reject('INVALID_JSON')

    def test_bool_cannot_impersonate_integer_byte_count(self):
        reference = self.reference('incremental-report.json')
        reference['bytes'] = True
        self.write(references=[reference])
        self.reject('ARTIFACT_SIZE_MISMATCH')

    def test_bool_and_number_data_are_distinct(self):
        self.payload['elapsed_s'] = 1
        self.envelope['data'] = dict(self.payload, elapsed_s=True)
        self.write()
        self.reject('REPORT_DATA_MISMATCH')

    def test_duplicate_payload_reference_is_rejected(self):
        reference = self.reference('incremental-report.json')
        self.write(references=[reference, reference.copy()])
        self.reject('ARTIFACT_REFERENCE_MISMATCH')

    def test_existing_output_is_preserved(self):
        self.out.mkdir()
        sentinel = self.out / 'keep.txt'
        sentinel.write_bytes(b'keep original evidence')
        with self.assertRaises(HandoffError) as error:
            self.export()
        self.assertEqual('OUTPUT_EXISTS', error.exception.code)
        self.assertEqual(b'keep original evidence', sentinel.read_bytes())

    def test_producer_metadata_cannot_disagree_with_run_record(self):
        (self.run / 'student-source-commit.txt').write_text('c' * 40)
        self.reject('METADATA_MISMATCH')

    def test_recorded_generated_data_and_environment_are_preserved(self):
        provenance = {'data_origin': 'course-generated controlled fixture; not real-project acceptance',
                      'flags': '-O0', 'execution_environment': 'orchestrator',
                      'draft_image_reused': False}
        raw = (json.dumps(provenance, indent=2) + '\n').encode()
        (self.run / 'input-provenance.json').write_bytes(raw)
        manifest = self.export()
        self.assertEqual(raw, (self.out / 'input-provenance.json').read_bytes())
        for key, value in provenance.items():
            self.assertEqual(value, manifest[key])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest['original_files']['input-provenance.json']['sha256'])

    def test_environment_reuse_metadata_rejects_bool_number_confusion(self):
        (self.run / 'input-provenance.json').write_text('{"draft_image_reused":1}')
        self.reject('INVALID_METADATA')

    def test_failed_upstream_is_rejected(self):
        p = self.run / 'result.json'
        data = json.loads(p.read_text())
        data['status'] = 'FAILED'
        p.write_text(json.dumps(data))
        self.reject('UPSTREAM_FAILED')

    def test_stage_file_is_bound_to_its_expected_name(self):
        p = self.run / 'result.json'
        data = json.loads(p.read_text())
        data['stages'][0]['artifact'] = self.reference('incremental-check.json')
        p.write_text(json.dumps(data))
        self.reject('ARTIFACT_REFERENCE_MISMATCH')

    def test_artifact_uri_cannot_escape_the_source_run(self):
        reference = self.reference('incremental-report.json')
        reference['uri'] = f'artifact://{self.job}/../incremental-report.json'
        self.write(references=[reference])
        self.reject('UNSAFE_PATH')


if __name__ == '__main__':
    unittest.main()
