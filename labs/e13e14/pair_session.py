"""Proposed scoped loopback access layer for a single approved course session.

Never forward raw role execution or the DRAFT broker. A separate, fresh local
async Store is required for C8. This does not authenticate SSH identities.
Only the operator may start/stop this process; no credential is logged.
"""
import argparse
import hashlib
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import stat
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote

ROLES = ('buildchecker', 'echecker', 'draft', 'mdfixer')
STAGES = ['draft', 'full-check', 'incremental-check', 'repair', 'recheck']
HASH = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')
JOB = re.compile(r'job-[0-9a-f]{32}\Z')
TRACE = re.compile(r'trace-[0-9a-f]{32}\Z')
KEY = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')
MAX_BODY = 65536
MAX_RESPONSE = 64 * 1024 * 1024


def need(ok, code):
    if not ok:
        raise ValueError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    def bad_constant(_):
        raise ValueError('NONFINITE_JSON')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)
    need(isinstance(value, dict), 'JSON_OBJECT_REQUIRED')
    return value


def expiry(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(dt.tzinfo is not None, 'TIMEZONE_REQUIRED')
    return dt.timestamp()


def private_credential(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), 'CREDENTIAL_FILE_REQUIRED')
    need(not (stat.S_IMODE(path.stat().st_mode) & 0o077), 'PRIVATE_FILE_MODE_REQUIRED')
    raw = path.read_bytes().strip()
    need(re.fullmatch(rb'[A-Za-z0-9_-]{32,128}', raw), 'CREDENTIAL_FORMAT_INVALID')
    return raw


def verify_deployment(root, request_raw, candidate_sha, source):
    """Check local source, approved candidate and complete commit objects."""
    root = Path(root).resolve()
    def git(repo, *args):
        proc = subprocess.run(['git','-C',str(repo),*args], capture_output=True,
                              text=True, timeout=30)
        need(proc.returncode == 0, 'DEPLOYMENT_GIT_CHECK_FAILED')
        return proc.stdout.strip()
    need(git(root,'rev-parse','HEAD') == source and
         not git(root,'status','--porcelain','--untracked-files=no'),
         'DEPLOYMENT_SOURCE_MISMATCH')
    request = strict_json(request_raw)
    def local(value):
        need(isinstance(value,str) and value.startswith('/course/data/'),
             'DEPLOYMENT_PATH_INVALID')
        path = root / value[len('/course/'):]
        need(path.resolve() == path and path.is_relative_to(root/'data'),
             'DEPLOYMENT_PATH_ESCAPE')
        return path
    candidate = local(request.get('candidate'))
    repo = local(request.get('repo'))
    need(candidate.is_file() and digest(candidate.read_bytes()) == candidate_sha
         and repo.is_dir(), 'DEPLOYMENT_INPUT_MISMATCH')
    for field in ('base','target'):
        revision = request.get(field)
        need(isinstance(revision,str) and COMMIT.fullmatch(revision),'DEPLOYMENT_COMMIT_INVALID')
        need(git(repo,'rev-parse','--verify',revision+'^{commit}') == revision,
             'DEPLOYMENT_COMMIT_MISSING')
    return True


def artifact_index(result, job):
    need(result.get('job_id') == job and result.get('status') == 'SUCCEEDED',
         'ARTIFACT_JOB_NOT_SUCCEEDED')
    entries = result.get('artifacts')
    need(isinstance(entries, list) and bool(entries), 'EMPTY_MANIFEST')
    prefix = 'artifact://' + job + '/'
    found, folded = {}, set()
    for item in entries:
        need(isinstance(item, dict), 'ARTIFACT_RECORD_INVALID')
        uri = item.get('uri')
        need(isinstance(uri, str) and uri.startswith(prefix), 'ARTIFACT_URI_INVALID')
        name = uri[len(prefix):]
        # Portable paths: no traversal, hidden Git objects, alternate streams,
        # Windows device names, URL ambiguity or case-fold collisions.
        components = name.split('/')
        need(all(re.fullmatch(r'[A-Za-z0-9_.-]+', part) and
                 part not in ('.', '..', '.git') and not part.endswith('.') and
                 part.split('.')[0].upper() not in
                 {'CON','PRN','AUX','NUL', *('COM'+str(i) for i in range(1,10)),
                  *('LPT'+str(i) for i in range(1,10))}
                 for part in components), 'UNSAFE_ARTIFACT_PATH')
        need(name != 'result.json' and name.casefold() not in folded, 'DUPLICATE_ARTIFACT')
        folded.add(name.casefold())
        need(type(item.get('bytes')) is int and 0 <= item['bytes'] <= MAX_RESPONSE
             and isinstance(item.get('sha256'), str) and HASH.fullmatch(item['sha256']),
             'ARTIFACT_DIGEST_INVALID')
        found[name] = item
    return found


class Session:
    def __init__(self, request_raw, request_sha, candidate_sha, source, expires, credential):
        need(HASH.fullmatch(request_sha) and digest(request_raw) == request_sha,
             'APPROVED_REQUEST_HASH_MISMATCH')
        need(HASH.fullmatch(candidate_sha) and COMMIT.fullmatch(source), 'PIN_INVALID')
        need(time.time() < expires <= time.time() + 86400, 'SESSION_WINDOW_INVALID')
        need(re.fullmatch(rb'[A-Za-z0-9_-]{32,128}', credential), 'CREDENTIAL_FORMAT_INVALID')
        request = strict_json(request_raw)
        need(request.get('mode') == 'e12' and all(
             isinstance(request.get(k), str) and COMMIT.fullmatch(request[k])
             for k in ('base', 'target')), 'E12_COMMIT_PINS_REQUIRED')
        need(request['target'] != '0' * 40, 'CONFLICT_TARGET_RESERVED')
        self.approved = canonical(request)
        self.conflict = canonical(dict(request, target='0' * 40))
        self.verifier = hashlib.sha256(credential).digest()
        self.expires = expires
        self.info = {'schema_version': 'pair-session-preflight-1',
                     'declared_source_commit': source, 'request_sha256': request_sha,
                     'candidate_sha256': candidate_sha,
                     'expires_utc': datetime.fromtimestamp(expires, timezone.utc).isoformat(),
                     'base_commit': request['base'], 'target_commit': request['target'],
                     'scope': 'single approved E12 input; not bilateral acceptance'}
        self.lock = threading.Lock()
        self.key = None
        self.job = None
        self.files = None

    def auth(self, values):
        if time.time() >= self.expires:
            return 403
        if len(values) != 1 or not values[0].startswith('Bearer '):
            return 401
        presented = values[0][7:].encode('utf-8')
        if not hmac.compare_digest(hashlib.sha256(presented).digest(), self.verifier):
            return 401
        return 200

    def submit(self, raw, upstream):
        body = strict_json(raw)
        need(set(body) == {'input', 'idempotency_key'} and isinstance(body['input'], dict),
             'POST_SHAPE_INVALID')
        key = body['idempotency_key']
        need(isinstance(key, str) and KEY.fullmatch(key), 'KEY_INVALID')
        encoded = canonical(body['input'])
        with self.lock:
            need(time.time() < self.expires, 'SESSION_EXPIRED')
            # Reserve before sending so a lost response cannot admit a second
            # key. The same approved POST may be retried to recover its job ID.
            if self.key is None:
                need(encoded == self.approved, 'REQUEST_NOT_APPROVED')
                self.key = key
            need(key == self.key, 'SESSION_KEY_MISMATCH')
            need(encoded == self.approved or
                 (self.job is not None and encoded == self.conflict), 'REQUEST_NOT_APPROVED')
            code, answer, headers = upstream('POST', '/v1/jobs', raw)
            state = strict_json(answer)
            if encoded == self.conflict:
                need(code == 409 and state.get('error') == 'IDEMPOTENCY_CONFLICT',
                     'UPSTREAM_CONFLICT_NOT_REJECTED')
            else:
                need(code == 202 and isinstance(state.get('job_id'), str)
                     and JOB.fullmatch(state['job_id']), 'UPSTREAM_SUBMIT_INVALID')
                need(self.job in (None, state['job_id']), 'UPSTREAM_JOB_CHANGED')
                self.job = state['job_id']
            return code, answer, headers

    def read(self, path, upstream):
        with self.lock:
            need(time.time() < self.expires, 'SESSION_EXPIRED')
            need(self.job is not None, 'SESSION_NO_JOB')
            prefix = '/v1/jobs/' + self.job
            if path == prefix:
                return upstream('GET', path, None)
            if path == prefix + '/artifacts':
                code, body, headers = upstream('GET', path, None)
                if code == 200:
                    self.files = artifact_index(strict_json(body), self.job)
                return code, body, headers
            need(path.startswith(prefix + '/files/') and self.files is not None,
                 'PATH_NOT_APPROVED')
            name = unquote(path[len(prefix + '/files/'):], errors='strict')
            need(name in self.files and path == prefix + '/files/' + quote(name, safe='/'),
                 'ARTIFACT_NOT_APPROVED')
            code, body, headers = upstream('GET', path, None)
            item = self.files[name]
            need(code == 200 and len(body) == item['bytes'] and
                 digest(body) == item['sha256'] == headers.get('x-content-sha256'),
                 'UPSTREAM_ARTIFACT_MISMATCH')
            return code, body, headers


def upstream_for(port):
    need(type(port) is int and 1 <= port <= 65535, 'PORT_INVALID')
    def call(method, path, body):
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
        try:
            conn.request(method, path, body=body,
                         headers={'Content-Type': 'application/json'} if body is not None else {})
            response = conn.getresponse()
            raw = response.read(MAX_RESPONSE + 1)
            need(len(raw) <= MAX_RESPONSE and not 300 <= response.status < 400,
                 'UPSTREAM_RESPONSE_REJECTED')
            return response.status, raw, {k.lower(): v for k,v in response.getheaders()}
        finally:
            conn.close()
    return call


def make_server(port, session, upstream, role='api'):
    need(role in (*ROLES, 'api'), 'ROLE_INVALID')
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_):
            # No headers, query strings, credential or uncontrolled error bodies.
            pass

        def reply(self, code, raw, headers=None):
            headers = headers or {}
            self.send_response(code)
            self.send_header('Content-Type', headers.get('content-type', 'application/json'))
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            if 'x-content-sha256' in headers:
                self.send_header('X-Content-SHA256', headers['x-content-sha256'])
            self.end_headers()
            self.wfile.write(raw)

        def dispatch(self, method):
            try:
                code = session.auth(self.headers.get_all('Authorization', []))
                if code != 200:
                    self.reply(code, canonical({'error': 'SESSION_EXPIRED' if code == 403
                                                else 'AUTH_REQUIRED'}))
                    return
                need('?' not in self.path and '#' not in self.path, 'PATH_NOT_APPROVED')
                if method == 'GET' and self.path == '/v1/session':
                    self.reply(200, canonical(dict(session.info, role=role)))
                    return
                if method == 'GET' and self.path == '/health':
                    answer = upstream('GET', '/health', None)
                elif role == 'api' and method == 'POST' and self.path == '/v1/jobs':
                    sizes = self.headers.get_all('Content-Length', [])
                    need(not self.headers.get('Transfer-Encoding') and len(sizes) == 1,
                         'BODY_LENGTH_INVALID')
                    size = int(sizes[0])
                    need(0 < size <= MAX_BODY, 'BODY_LENGTH_INVALID')
                    raw = self.rfile.read(size)
                    need(len(raw) == size, 'BODY_INCOMPLETE')
                    answer = session.submit(raw, upstream)
                elif role == 'api' and method == 'GET':
                    answer = session.read(self.path, upstream)
                else:
                    self.reply(404, canonical({'error': 'PATH_NOT_APPROVED'}))
                    return
                self.reply(*answer)
            except (ValueError, TypeError, KeyError):
                self.reply(403, canonical({'error': 'REQUEST_REJECTED'}))
            except (OSError, http.client.HTTPException):
                self.reply(502, canonical({'error': 'UPSTREAM_UNAVAILABLE'}))

        def do_GET(self):
            self.dispatch('GET')

        def do_POST(self):
            self.dispatch('POST')
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--listen-port', type=int, required=True)
    p.add_argument('--upstream-port', type=int, required=True)
    p.add_argument('--role', choices=(*ROLES, 'api'), required=True)
    p.add_argument('--approved-request', type=Path, required=True)
    p.add_argument('--request-sha256', required=True)
    p.add_argument('--candidate-sha256', required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--expires', required=True, help='ISO8601 with timezone, max 24 hours')
    p.add_argument('--credential-file', type=Path, required=True)
    p.add_argument('--course-root', type=Path, default=Path(__file__).resolve().parents[2])
    a = p.parse_args()
    need(1024 <= a.listen_port <= 65535 and a.listen_port != a.upstream_port, 'PORT_INVALID')
    need(not a.credential_file.resolve().is_relative_to(a.course_root.resolve()),
         'CREDENTIAL_MUST_BE_OUTSIDE_COURSE')
    raw = a.approved_request.read_bytes()
    session = Session(raw, a.request_sha256, a.candidate_sha256, a.source_commit,
                      expiry(a.expires), private_credential(a.credential_file))
    verify_deployment(a.course_root, raw, a.candidate_sha256, a.source_commit)
    with make_server(a.listen_port, session, upstream_for(a.upstream_port), a.role) as server:
        # Check expiry even when no clients connect. Expiry blocks access; it
        # does not cancel an already submitted job in the private backend.
        server.timeout = 0.5
        while time.time() < session.expires:
            server.handle_request()


if __name__ == '__main__':
    main()
