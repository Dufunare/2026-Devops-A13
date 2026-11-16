"""HTTP client tests use a local protocol fixture, not claimed as course runs."""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import unquote

from handoff import HandoffError, sha
from http_evidence_241830088 import artifact_name, capture


def encode(obj):
    return (json.dumps(obj, sort_keys=True) + '\n').encode()


@contextmanager
def fixture(scenario='ok'):
    events = []
    current = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, obj, code=200):
            self.send_response(code)
            self.end_headers()
            self.wfile.write(encode(obj))

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            events.append(('POST', self.path, body))
            request = body['input']
            mode = request['mode']
            jid, trace = 'job-http-fixture', 'trace-http-fixture'
            state = {'schema_version': 'e11e12-1', 'job_id': jid, 'status': 'RUNNING',
                     'idempotency_key': body['idempotency_key'],
                     'request_hash': hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()}
            if scenario == 'request-hash':
                state['request_hash'] = '0' * 64
            files = {'request.json': encode(request), 'raw/t.1': b'read header\x00\xff\n'}
            names = {'e11-a': ['full-check', 'incremental-check'],
                     'e11-b': ['draft', 'fixed-md', 'repair', 'recheck'],
                     'e12': ['draft', 'full-check', 'incremental-check', 'repair', 'recheck']}[mode]
            def ref(name):
                return {'uri': 'artifact://' + jid + '/' + name, 'sha256': sha(files[name]), 'bytes': len(files[name])}
            stages = []
            for name in names:
                envelope = {'schema_version': 'e11e12-1', 'job_id': jid, 'trace_id': trace,
                            'status': 'SUCCEEDED', 'kind': name,
                            'commit': request['base'] if name == 'full-check' else request['target'],
                            'artifacts': [ref('raw/t.1')]}
                if scenario == 'envelope-trace' and name == names[0]:
                    envelope['trace_id'] = 'trace-another'
                files[name + '.json'] = encode(envelope)
                stages.append({'name': name, 'artifact': ref(name + '.json')})
            if mode != 'e11-a':
                files['candidate.patch'] = b'--- a/Makefile\n+++ b/Makefile\n'
            result = {'schema_version': 'e11e12-1', 'job_id': jid, 'trace_id': trace,
                      'status': 'SUCCEEDED', 'base_commit': request['base'], 'target_commit': request['target'],
                      'stages': stages, 'artifacts': [ref(n) for n in files]}
            if scenario == 'result-commit':
                result['target_commit'] = 'f' * 40
            if scenario == 'unsafe-ref':
                result['artifacts'][0]['uri'] = 'artifact://' + jid + '/../escape'
            current.update(state=state, result=result, files=files)
            self.reply(state, 202)

        def do_GET(self):
            events.append(('GET', self.path))
            if self.path == '/health':
                return self.reply({'status': 'ok', 'schema_version': 'e11e12-1'})
            if self.path.endswith('/artifacts'):
                return self.reply(current['result'])
            if '/files/' in self.path:
                name = unquote(self.path.split('/files/')[1])
                raw = current['files'][name]
                expected = sha(raw)
                if scenario == 'tamper' and name == 'raw/t.1':
                    raw = b'changed'
                self.send_response(200)
                self.send_header('X-Content-SHA256', '0' * 64 if scenario == 'header' else expected)
                self.end_headers()
                self.wfile.write(raw)
                return
            state = dict(current['state'])
            state['trace_id'] = 'trace-http-fixture'
            state['status'] = 'RUNNING' if scenario == 'timeout' else 'FAILED' if scenario == 'failed' else 'SUCCEEDED'
            self.reply(state)

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    httpd.daemon_threads = True
    worker = threading.Thread(target=httpd.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    worker.start()
    try:
        yield 'http://127.0.0.1:' + str(httpd.server_port), events
    finally:
        httpd.shutdown()
        httpd.server_close()
        worker.join()


class HttpEvidence(unittest.TestCase):
    def run_capture(self, root, url, mode='e11-a', timeout=5):
        request = root / 'input.json'
        request.write_bytes(encode({'mode': mode, 'repo': '/course/data/fixture', 'base': 'a' * 40, 'target': 'b' * 40}))
        return capture(url, request, root / 'out', timeout=timeout, poll_seconds=.001)

    def reject(self, scenario, code):
        with tempfile.TemporaryDirectory() as directory, fixture(scenario) as (url, events):
            root = Path(directory)
            with self.assertRaisesRegex(HandoffError, code):
                self.run_capture(root, url)
            result = json.loads((root / 'out/summary.json').read_text())
            self.assertEqual(result['status'], 'FAILED')
            self.assertEqual(result['error']['code'], code)
            self.assertTrue((root / 'out/SHA256SUMS').is_file())
            return events

    def test_complete_new_job_poll_download_all_three_modes(self):
        for mode in ('e11-a', 'e11-b', 'e12'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory, fixture() as (url, events):
                root = Path(directory)
                result = self.run_capture(root, url, mode)
                self.assertEqual(result['status'], 'SUCCEEDED')
                self.assertEqual(result['downloaded_count'], 4 if mode == 'e11-a' else 7 if mode == 'e11-b' else 8)
                self.assertFalse(result['formal_pair_acceptance'])
                self.assertFalse(result['server_execution_environment_verified'])
                self.assertTrue(any(e[1].endswith('/job-http-fixture') for e in events))
                post = next(e for e in events if e[0] == 'POST')
                self.assertRegex(post[2]['idempotency_key'], r'^a13-241830088-[0-9a-f]{32}$')
                self.assertEqual((root / 'out/downloads/raw/t.1').read_bytes(), b'read header\x00\xff\n')
                for row in result['downloaded']:
                    self.assertEqual(sha((root / 'out/downloads' / row['path']).read_bytes()), row['sha256'])
                self.assertTrue((root / 'out/http/0002.request.bin').is_file())
                self.assertEqual(len(json.loads((root / 'out/http-index.json').read_text())), len(events))

    def test_reject_tampered_download_and_preserve_response(self):
        self.reject('tamper', 'HASH_MISMATCH')

    def test_reject_wrong_server_hash_header(self):
        self.reject('header', 'HEADER_HASH_MISMATCH')

    def test_reject_wrong_stage_trace_with_consistent_file_hash(self):
        self.reject('envelope-trace', 'ENVELOPE_MISMATCH')

    def test_reject_wrong_request_binding(self):
        self.reject('request-hash', 'REQUEST_MISMATCH')

    def test_reject_wrong_project_commit(self):
        self.reject('result-commit', 'COMMIT_MISMATCH')

    def test_failed_job_does_not_count_as_completed_or_download(self):
        events = self.reject('failed', 'JOB_FAILED')
        self.assertFalse(any(e[1].endswith('/artifacts') for e in events))

    def test_reject_escaping_artifact_before_download(self):
        events = self.reject('unsafe-ref', 'UNSAFE_PATH')
        self.assertFalse(any('/files/' in e[1] for e in events))

    def test_reject_unsafe_reference_job_and_bool_length(self):
        ref = {'uri': 'artifact://job-1/report.json', 'sha256': 'a' * 64, 'bytes': 1}
        for suffix in ('../x', '/x', 'x//y', '.git/config', 'x%2fy', 'x?query'):
            with self.subTest(suffix=suffix), self.assertRaises(HandoffError):
                artifact_name(dict(ref, uri='artifact://job-1/' + suffix), 'job-1')
        with self.assertRaisesRegex(HandoffError, 'JOB_MISMATCH'):
            artifact_name(ref, 'job-2')
        with self.assertRaisesRegex(HandoffError, 'INVALID_ARTIFACT'):
            artifact_name(dict(ref, bytes=True), 'job-1')

    def test_do_not_overwrite_existing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'out').mkdir()
            keep = root / 'out/keep'
            keep.write_text('original')
            with self.assertRaises(FileExistsError):
                self.run_capture(root, 'http://127.0.0.1:1')
            self.assertEqual(keep.read_text(), 'original')
            self.assertEqual(list((root / 'out').iterdir()), [keep])

    def test_timeout_preserves_partial_http_records(self):
        with tempfile.TemporaryDirectory() as directory, fixture('timeout') as (url, _):
            root = Path(directory)
            with self.assertRaisesRegex(HandoffError, 'TIMED_OUT'):
                self.run_capture(root, url, timeout=.1)
            self.assertEqual(json.loads((root / 'out/summary.json').read_text())['status'], 'FAILED')
            self.assertTrue((root / 'out/http-index.json').is_file())
