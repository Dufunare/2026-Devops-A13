"""241830088: capture a fresh HTTP job and verify every downloaded artifact.

Transport evidence proves the bytes and job identity observed by this client.
It does not attest the server's source version or DRAFT execution environment.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import uuid

from handoff import HandoffError, require, sha, same_json, strict_json


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def artifact_name(ref, job):
    require(isinstance(ref, dict), 'INVALID_ARTIFACT', 'Expected artifact object')
    uri = ref.get('uri')
    prefix = 'artifact://' + job + '/'
    require(isinstance(uri, str) and uri.startswith(prefix), 'JOB_MISMATCH', 'Artifact belongs to another job')
    name = uri[len(prefix):]
    require(name and not any(p in ('', '.', '..', '.git') for p in name.split('/'))
            and not any(c in name for c in ('\\', ':', '%', '?', '#', '\x00')),
            'UNSAFE_PATH', name)
    require(isinstance(ref.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', ref['sha256']),
            'INVALID_ARTIFACT', 'Expected SHA256')
    require(type(ref.get('bytes')) is int and ref['bytes'] >= 0,
            'INVALID_ARTIFACT', 'Expected integer bytes')
    return name


def verify_bytes(raw, headers, ref):
    require(sha(raw) == ref['sha256'], 'HASH_MISMATCH', ref['uri'])
    require(len(raw) == ref['bytes'], 'SIZE_MISMATCH', ref['uri'])
    require(headers.get('x-content-sha256') == ref['sha256'],
            'HEADER_HASH_MISMATCH', ref['uri'])


class Recorder:
    def __init__(self, base_url, out, deadline):
        parsed = urlsplit(base_url)
        require(parsed.scheme in ('http', 'https') and parsed.hostname
                and not parsed.username and not parsed.password and not parsed.query
                and not parsed.fragment and parsed.path in ('', '/'),
                'INVALID_URL', 'Use the API origin without credentials, path or query')
        self.base_url = base_url.rstrip('/')
        self.out = out
        self.deadline = deadline
        self.records = []
        self.opener = build_opener(NoRedirect)
        (out / 'http').mkdir()

    def request(self, method, path, body=None, expected=200):
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, 'TIMED_OUT', 'Client evidence deadline exceeded')
        index = len(self.records) + 1
        stem = self.out / 'http' / f'{index:04d}'
        data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode() if body is not None else None
        if data is not None:
            stem.with_suffix('.request.bin').write_bytes(data)
        request_headers = {'Content-Type': 'application/json'} if data is not None else {}
        record = {'index': index, 'time_utc': datetime.now(timezone.utc).isoformat(),
                  'method': method, 'url': self.base_url + path, 'request_headers': request_headers}
        self.records.append(record)
        save(stem.with_suffix('.request.json'), record)
        try:
            response = self.opener.open(Request(record['url'], data=data, headers=request_headers, method=method),
                                        timeout=min(30, remaining))
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            record.update(status=response.code, response_sha256=sha(raw), response_bytes=len(raw))
            headers = {k.lower(): v for k, v in response.headers.items()}
            stem.with_suffix('.headers.txt').write_text(
                f'HTTP status {response.code}\n' + str(response.headers), encoding='utf-8')
            stem.with_suffix('.body.bin').write_bytes(raw)
            save(stem.with_suffix('.response.json'), record)
        save(self.out / 'http-index.json', self.records)
        require(record['status'] == expected, 'HTTP_STATUS', f'{method} {path}: {record["status"]}, expected {expected}')
        return raw, headers

    def get_json(self, method, path, body=None, expected=200):
        raw, _ = self.request(method, path, body, expected)
        return strict_json(raw)


def capture(base_url, request_file, out, timeout=1200, poll_seconds=2, context_file=None):
    require(timeout > 0 and poll_seconds > 0, 'INVALID_ARGUMENT', 'Positive timeout and poll interval required')
    request_file, out = Path(request_file), Path(out)
    request = strict_json(request_file.read_bytes())
    require(request.get('mode') in ('e11-a', 'e11-b', 'e12'), 'INVALID_REQUEST', 'Unknown mode')
    for field in ('base', 'target'):
        require(isinstance(request.get(field), str) and re.fullmatch('[0-9a-f]{40}', request[field]),
                'INVALID_REQUEST', field + ' must be a full commit SHA')
    require(isinstance(request.get('repo'), str) and request['repo'].startswith('/course/data/'),
            'INVALID_REQUEST', 'Use the confirmed server path under /course/data/')
    out.mkdir(parents=True, exist_ok=False)
    request_hash = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    replay_tag = 'a13-241830088-' + uuid.uuid4().hex
    summary = {'schema_version': 'a13-http-evidence-1', 'status': 'RUNNING',
               'base_url': base_url, 'client_started_utc': datetime.now(timezone.utc).isoformat(),
               'request_hash': request_hash, 'idempotency_key': replay_tag,
               'mode': request['mode'], 'base_commit': request['base'], 'target_commit': request['target'],
               'server_execution_environment_verified': False,
               'formal_pair_acceptance': False, 'downloaded': []}
    (out / 'input.original.json').write_bytes(request_file.read_bytes())
    save(out / 'summary.json', summary)
    recorder = None
    try:
        if context_file:
            (out / 'operator-context.json').write_bytes(Path(context_file).read_bytes())
            strict_json((out / 'operator-context.json').read_bytes())
        recorder = Recorder(base_url, out, time.monotonic() + timeout)
        health = recorder.get_json('GET', '/health')
        require(health.get('status') == 'ok' and health.get('schema_version') == 'e11e12-1',
                'SCHEMA_MISMATCH', 'Unexpected health response')
        state = recorder.get_json('POST', '/v1/jobs', {'input': request, 'idempotency_key': replay_tag}, expected=202)
        job = state.get('job_id')
        require(isinstance(job, str) and re.fullmatch('job-[A-Za-z0-9_-]+', job), 'INVALID_JOB', 'Invalid job ID')
        summary['job_id'] = job
        while True:
            require(state.get('schema_version') == 'e11e12-1' and state.get('job_id') == job,
                    'JOB_MISMATCH', 'State identity changed')
            require(state.get('request_hash') == request_hash and state.get('idempotency_key') == replay_tag,
                    'REQUEST_MISMATCH', 'Server state does not match submitted request')
            status = state.get('status')
            require(status in ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'TIMED_OUT'),
                    'INVALID_STATE', str(status))
            if status in ('SUCCEEDED', 'FAILED', 'TIMED_OUT'):
                break
            remaining = recorder.deadline - time.monotonic()
            require(remaining > 0, 'TIMED_OUT', 'Job polling timed out')
            time.sleep(min(poll_seconds, remaining))
            state = recorder.get_json('GET', '/v1/jobs/' + job)
        save(out / 'terminal-state.json', state)
        require(status == 'SUCCEEDED', 'JOB_FAILED', str(state.get('error', status)))
        result = recorder.get_json('GET', '/v1/jobs/' + job + '/artifacts')
        save(out / 'artifact-index.json', result)
        trace = state.get('trace_id')
        require(isinstance(trace, str) and trace and result.get('schema_version') == 'e11e12-1'
                and result.get('job_id') == job and result.get('trace_id') == trace
                and result.get('status') == 'SUCCEEDED', 'RESULT_MISMATCH', 'Result identity or status differs')
        require(result.get('base_commit') == request['base'] and result.get('target_commit') == request['target'],
                'COMMIT_MISMATCH', 'Result belongs to another project revision')
        summary['trace_id'] = trace
        refs = result.get('artifacts')
        require(isinstance(refs, list) and refs, 'INVALID_ARTIFACT', 'No artifacts advertised')
        advertised = {}
        for ref in refs:
            name = artifact_name(ref, job)
            require(name not in advertised, 'INVALID_ARTIFACT', 'Duplicate artifact: ' + name)
            advertised[name] = ref
        downloads = out / 'downloads'
        downloads.mkdir()
        for name, ref in advertised.items():
            raw, headers = recorder.request('GET', '/v1/jobs/' + job + '/files/' + quote(name, safe='/'))
            verify_bytes(raw, headers, ref)
            path = downloads / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            summary['downloaded'].append({'path': name, 'sha256': sha(raw), 'bytes': len(raw)})
        stages = result.get('stages')
        expected_stages = {'e11-a': ['full-check', 'incremental-check'],
                           'e11-b': ['draft', 'fixed-md', 'repair', 'recheck'],
                           'e12': ['draft', 'full-check', 'incremental-check', 'repair', 'recheck']}[request['mode']]
        require(isinstance(stages, list) and all(isinstance(s, dict) for s in stages)
                and [s.get('name') for s in stages] == expected_stages, 'INVALID_STAGES', 'Unexpected stages')
        for stage in stages:
            ref = stage.get('artifact')
            name = artifact_name(ref, job)
            require(name == stage['name'] + '.json' and advertised.get(name) == ref,
                    'REFERENCE_MISMATCH', 'Stage reference differs from artifact index')
            envelope = strict_json((downloads / name).read_bytes())
            require(envelope.get('job_id') == job and envelope.get('trace_id') == trace
                    and envelope.get('schema_version') == 'e11e12-1' and envelope.get('status') == 'SUCCEEDED'
                    and envelope.get('kind') == stage['name'], 'ENVELOPE_MISMATCH', name)
            expected_commit = request['base'] if stage['name'] == 'full-check' else request['target']
            require(envelope.get('commit') == expected_commit, 'COMMIT_MISMATCH', name)
            require(isinstance(envelope.get('artifacts'), list), 'INVALID_ARTIFACT', 'Stage refs must be list')
            for nested in envelope['artifacts']:
                nested_name = artifact_name(nested, job)
                require(advertised.get(nested_name) == nested, 'REFERENCE_MISMATCH', nested_name)
        require((downloads / 'request.json').is_file()
                and same_json(strict_json((downloads / 'request.json').read_bytes()), request),
                'REQUEST_MISMATCH', 'Downloaded request differs')
        summary.update(status='SUCCEEDED', downloaded_count=len(summary['downloaded']),
                       stage_count=len(stages), client_finished_utc=datetime.now(timezone.utc).isoformat())
    except (HandoffError, OSError, ValueError) as error:
        summary.update(status='FAILED', error={'code': getattr(error, 'code', 'CLIENT_FAILED'), 'message': str(error)})
        raise
    finally:
        save(out / 'summary.json', summary)
        if recorder:
            save(out / 'http-index.json', recorder.records)
        checksums = [sha(p.read_bytes()) + '  ' + p.relative_to(out).as_posix()
                     for p in sorted(out.rglob('*')) if p.is_file() and p != out / 'SHA256SUMS']
        (out / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n', encoding='utf-8')
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url', required=True)
    p.add_argument('--request', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--timeout', type=float, default=1200)
    p.add_argument('--poll-seconds', type=float, default=2)
    p.add_argument('--context', help='Operator-supplied context; not a server attestation')
    a = p.parse_args()
    try:
        summary = capture(a.base_url, a.request, a.out, a.timeout, a.poll_seconds, a.context)
    except (HandoffError, OSError, ValueError) as error:
        print(json.dumps({'status': 'FAILED', 'error': {'code': getattr(error, 'code', 'CLIENT_FAILED'), 'message': str(error)}}))
        return 1
    print(json.dumps({k: summary[k] for k in ('status', 'job_id', 'trace_id', 'downloaded_count')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
