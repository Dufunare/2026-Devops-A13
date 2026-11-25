"""Client-side C8 wire originals through a prearranged loopback SSH tunnel.

A PASS is a client receipt only. Server-side private Store job count and
independent source/image/profile verification are still required.
"""
import argparse
import getpass
import http.client
import json
import platform
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from pair_session import (JOB, TRACE, STAGES, HASH, COMMIT, MAX_RESPONSE, artifact_index,
                          canonical, digest, need, strict_json)


def save(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw)


class Recorder:
    def __init__(self, port, credential, out):
        need(1 <= port <= 65535, 'PORT_INVALID')
        self.port, self.credential, self.out, self.index = port, credential, out, 0

    def call(self, method, path, raw=None, authorized=True):
        self.index += 1
        folder = self.out / 'wire' / ('%05d' % self.index)
        folder.mkdir(parents=True, exist_ok=False)
        # Never persist Authorization, even on failure. No proxy or redirects.
        save(folder / 'request.json', canonical({'method': method, 'path': path,
             'body_sha256': digest(raw) if raw is not None else None,
             'authorization_present': authorized}))
        if raw is not None:
            save(folder / 'request.body', raw)
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        started = time.time()
        try:
            headers = {'Authorization': 'Bearer ' + self.credential.decode('ascii')} if authorized else {}
            if raw is not None:
                headers['Content-Type'] = 'application/json'
            conn.request(method, path, body=raw, headers=headers)
            response = conn.getresponse()
            data = response.read(MAX_RESPONSE + 1)
            need(len(data) <= MAX_RESPONSE, 'RESPONSE_TOO_LARGE')
            kept = {k.lower(): v for k,v in response.getheaders()
                    if k.lower() in ('content-type','content-length','x-content-sha256','date','cache-control')}
            save(folder / 'response.body', data)
            save(folder / 'response.json', canonical({'http': response.status,
                 'headers': kept, 'bytes': len(data), 'sha256': digest(data),
                 'start_epoch': started, 'end_epoch': time.time()}))
            return response.status, data, kept
        finally:
            conn.close()


def campaign(recorder, original, source, candidate_sha, wait=600, key=None):
    request = strict_json(original)
    out = recorder.out
    need(request.get('mode') == 'e12' and all(COMMIT.fullmatch(request[k])
         for k in ('base','target')), 'E12_REQUEST_REQUIRED')
    need(HASH.fullmatch(candidate_sha) and COMMIT.fullmatch(source), 'PIN_INVALID')
    save(out / 'approved-request.original.json', original)
    save(out / 'client-environment.json', canonical({'system': platform.platform(),
         'python': platform.python_version(), 'local_port': recorder.port,
         'scope': 'client observation; not operator identity or bilateral acceptance'}))
    def call(method,path,body=None,code=200,authorized=True):
        got, raw, headers = recorder.call(method,path,body,authorized)
        need(got == code, 'HTTP_STATUS_MISMATCH: ' + str(got) + ' expected ' + str(code))
        return strict_json(raw)
    call('GET','/v1/session',code=401,authorized=False)
    info = call('GET','/v1/session')
    for field, expected in (('declared_source_commit', source), ('request_sha256', digest(original)),
                            ('candidate_sha256',candidate_sha), ('role','api'),
                            ('base_commit',request['base']),('target_commit',request['target'])):
        need(info.get(field) == expected, 'SESSION_PIN_MISMATCH: ' + field)
    need(call('GET','/health').get('schema_version') == 'e11e12-1', 'API_HEALTH_INVALID')
    key = key or 'pair-c8-' + uuid.uuid4().hex
    payload = canonical({'input':request,'idempotency_key':key})
    changed = canonical({'input':dict(request,target='0'*40),'idempotency_key':key})
    first = call('POST','/v1/jobs',payload,202)
    job = first.get('job_id','')
    need(JOB.fullmatch(job) and first.get('idempotency_key') == key, 'JOB_INVALID')
    expected_hash = digest(json.dumps(request,sort_keys=True).encode())
    need(first.get('request_hash') == expected_hash, 'STORE_REQUEST_HASH_MISMATCH')
    dup = call('POST','/v1/jobs',payload,202)
    need(dup.get('job_id') == job and dup.get('request_hash') == expected_hash, 'DUPLICATE_JOB')
    conflict = call('POST','/v1/jobs',changed,409)
    need(conflict.get('error') == 'IDEMPOTENCY_CONFLICT', 'CONFLICT_NOT_REJECTED')
    # Different key and out-of-session artifact reads must not reach upstream.
    call('POST','/v1/jobs',canonical({'input':request,'idempotency_key':'other-'+uuid.uuid4().hex}),403)
    call('GET','/v1/jobs/job-'+'0'*32,code=403)
    prefix = '/v1/jobs/' + job
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        state = call('GET',prefix)
        need(state.get('job_id') == job and state.get('request_hash') == expected_hash,
             'POLL_IDENTITY_MISMATCH')
        if state.get('status') in ('SUCCEEDED','FAILED','TIMED_OUT'):
            break
        time.sleep(1)
    else:
        raise ValueError('POLL_DEADLINE')
    trace = state.get('trace_id','')
    need(state.get('status') == 'SUCCEEDED' and TRACE.fullmatch(trace), 'JOB_NOT_SUCCEEDED')
    result = call('GET',prefix+'/artifacts')
    files = artifact_index(result, job)
    need(result.get('trace_id') == trace and result.get('base_commit') == request['base']
         and result.get('target_commit') == request['target'] and
         [s['name'] for s in result['stages']] == STAGES, 'RESULT_IDENTITY_MISMATCH')
    for field in ('exchange_profile_id','profile_sha256'):
        if field in request:
            need(result.get(field) == request[field], 'PROFILE_BINDING_MISMATCH')
    if request.get('profile',{}).get('exec_image') == 'draft':
        image = result.get('draft_image_id','')
        need(image.startswith('sha256:') and HASH.fullmatch(image[7:]) and
             result.get('downstream_executed_in') == 'image:' + image, 'DRAFT_IMAGE_MISMATCH')
    for name, item in files.items():
        status, raw, headers = recorder.call('GET',prefix+'/files/'+quote(name,safe='/'))
        need(status == 200 and len(raw) == item['bytes'] and
             digest(raw) == item['sha256'] == headers.get('x-content-sha256'), 'DOWNLOAD_MISMATCH')
        save(out / 'downloads' / name, raw)
    need('request.json' in files and canonical(strict_json((out/'downloads/request.json').read_bytes()))
         == canonical(request), 'EXECUTED_REQUEST_MISMATCH')
    # Verify the five stage envelopes and every nested reference against the
    # downloaded originals, independently of the outer manifest.
    def reference(entry):
        name = entry['uri'].removeprefix('artifact://'+job+'/')
        need(name in files and files[name]['uri'] == entry['uri'] and
             files[name]['sha256'] == entry['sha256'] and files[name]['bytes'] == entry['bytes'],
             'STAGE_REFERENCE_MISMATCH')
        return out/'downloads'/name
    for stage in result['stages']:
        name = stage['name']
        envelope = strict_json(reference(stage['artifact']).read_bytes())
        need(envelope['kind'] == name and envelope['job_id'] == job and
             envelope['trace_id'] == trace and envelope['status'] == 'SUCCEEDED' and
             envelope['commit'] == request['base' if name == 'full-check' else 'target'],
             'STAGE_IDENTITY_MISMATCH')
        for entry in envelope.get('artifacts',[]):
            reference(entry)
    after = call('POST','/v1/jobs',payload,202)
    need(after.get('job_id') == job and after.get('status') == 'SUCCEEDED', 'COMPLETED_REPLAY_FAILED')
    summary = {'status':'PASS','job_id':job,'trace_id':trace,'request_sha256':digest(original),
               'candidate_sha256':candidate_sha,'declared_source_commit':source,
               'http_artifacts_verified':len(files),'draft_image_id':result.get('draft_image_id'),
               'http_exchanges':recorder.index,'formal_pair_acceptance':False,
               'server_store_job_count_verified':False,'operator_identity_verified':False}
    save(out/'summary.json',canonical(summary))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--request', type=Path, required=True)
    p.add_argument('--request-sha256', required=True)
    p.add_argument('--candidate-sha256', required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--wait', type=int, default=600)
    a = p.parse_args()
    raw = a.request.read_bytes()
    need(digest(raw) == a.request_sha256 and 1 <= a.wait <= 12000, 'INPUT_OR_WAIT_INVALID')
    credential = getpass.getpass('Session credential (not recorded): ').encode('ascii')
    a.out.mkdir(parents=True, exist_ok=False)
    try:
        result = campaign(Recorder(a.port,credential,a.out),raw,a.source_commit,a.candidate_sha256,a.wait)
        print('PAIR_C8_CLIENT_GATE=PASS')
        print(json.dumps(result))
    except (ValueError, OSError, KeyError, TypeError, http.client.HTTPException) as exc:
        save(a.out/'failure.json',canonical({'status':'FAIL','error_type':type(exc).__name__,
                                          'note':'Inspect preserved wire originals; do not overwrite'}))
        raise SystemExit('PAIR_C8_CLIENT_GATE=FAIL: '+type(exc).__name__)


if __name__ == '__main__':
    main()
