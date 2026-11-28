"""Restricted, serial DRAFT execution broker for the trusted course workspace.

Only DRAFT owns the Docker socket. All execution paths derive from the active
job. No caller-supplied argv, image override, host mount, or arbitrary URL.
"""
import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from contract import checked_incremental, profile_sha256, require_image_id
from execution_attestation import verify_job

OPERATIONS = ('full-check-baseline', 'full-check-target', 'scan-baseline',
              'scan-target', 'validate', 'full-check-recheck')
IDENTITY = ('job_id', 'trace_id', 'base_commit', 'target_commit',
            'profile_sha256', 'draft_image_id', 'request_sha256', 'candidate_sha256')
HASH = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')
SAFE_TARGET = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\Z')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load(path):
    need(path.is_file() and not path.is_symlink(), 'EXEC_INPUT_MISSING: ' + path.name)
    return json.loads(path.read_bytes())


class DraftJobBusy(ValueError):
    """A different DRAFT job cannot start until the active job exits."""


class DownstreamTimeout(TimeoutError):
    """A bound execution timed out, with cleanup confirmed."""


def full_timeout(request, profile):
    """Optional full-check child timeout, not the DRAFT build timeout."""
    if 'downstream_full_timeout' not in request:
        return 900
    value = request['downstream_full_timeout']
    need(profile['exec_image'] == 'draft' and type(value) in (int, float)
         and 1 <= value <= 900, 'EXEC_FULL_TIMEOUT_INVALID')
    return value


def operation_failure(root, op, profile):
    """Classify from this operation's own originals, never exception text."""
    folder = root / ('repair-work/validation/inimage' if op == 'validate' else 'inimage')
    timed_out = []
    for tag in operation_tags(profile)[op]:
        path = folder / (tag + '.exec.json')
        if not path.exists():
            continue
        record = load(path)
        if record.get('cleanup_verified') is False:
            raise ValueError('EXEC_CLEANUP_UNCONFIRMED: ' + tag)
        if record.get('timed_out') is True:
            need(record.get('command_exit') == 124 and record.get('exit') == 124
                 and record.get('cleanup_verified') is True
                 and record.get('cleanup_exit') == 0
                 and record.get('cleanup_lookup_exit') == 0
                 and record.get('cleanup_remaining') == [],
                 'EXEC_TIMEOUT_CLEANUP_UNCONFIRMED: ' + tag)
            timed_out.append(tag)
    if timed_out:
        raise DownstreamTimeout('DOWNSTREAM_TIMED_OUT: ' + ','.join(timed_out))


def safe_relative(value):
    return (isinstance(value, str) and bool(value)
            and all(re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', p)
                    for p in value.split('/')))


def check_profile(profile):
    """Keep B's current executable-target convention; never infer ./all."""
    for field in ('build_target', 'clean_target'):
        need(SAFE_TARGET.fullmatch(profile[field]), 'EXEC_INVALID_MAKE_TARGET: ' + field)
    need(profile['build_target'] not in ('all', 'clean', profile['clean_target']),
         'EXEC_RUN_TARGET_REQUIRED: independent build/run target contract needed')
    need(safe_relative(profile['config_file']), 'EXEC_INVALID_PROFILE_PATH')
    for target, source in profile['units']:
        need(safe_relative(target) and safe_relative(source), 'EXEC_INVALID_PROFILE_PATH')
    return profile


def operation_tags(profile):
    binary = re.sub(r'[^a-zA-Z0-9]+', '-', './' + profile['build_target']).strip('-').lower()[:12]
    validation = ['validate-01-make', 'validate-02-make',
                  'validate-03-' + binary, 'validate-04-make']
    if profile['header_check'] == 'output':
        validation.append('validate-05-' + binary)
    validation.append('validate-recheck-scan')
    return {op: [op] for op in OPERATIONS if op != 'validate'} | {'validate': validation}


def identity(data):
    result = {key: data.get(key) for key in IDENTITY}
    for key in ('job_id', 'trace_id'):
        prefix = 'job-' if key == 'job_id' else 'trace-'
        need(isinstance(result[key], str) and
             re.fullmatch(prefix + r'[0-9a-f]{32}', result[key]), 'EXEC_IDENTITY_INVALID: ' + key)
    for key in ('base_commit', 'target_commit'):
        need(isinstance(result[key], str) and COMMIT.fullmatch(result[key]), 'EXEC_COMMIT_INVALID')
    for key in ('profile_sha256', 'request_sha256', 'candidate_sha256'):
        need(isinstance(result[key], str) and HASH.fullmatch(result[key]), 'EXEC_HASH_INVALID: ' + key)
    require_image_id(result['draft_image_id'])
    return result


def evidence_files(root, op, profile):
    folder = root / ('repair-work/validation/inimage' if op == 'validate' else 'inimage')
    files = {}
    for tag in operation_tags(profile)[op]:
        for suffix in ('.exec.json', '.inspect.json'):
            p = folder / (tag + suffix)
            need(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root),
                 'EXEC_ORIGINAL_MISSING: ' + p.name)
            files[p.relative_to(root).as_posix()] = sha(p)
    return files


def verify_receipts(root, expected, profile, course_source, report_sha):
    """Re-read all originals and receipts before E14 can claim success."""
    root = Path(root).resolve()
    expected = identity(expected)
    need(sha(root / 'request.json') == expected['request_sha256'], 'EXEC_REQUEST_CHANGED')
    need(profile_sha256(profile) == expected['profile_sha256'], 'EXEC_PROFILE_MISMATCH')
    tags = [t for op in OPERATIONS for t in operation_tags(profile)[op]]
    attested = verify_job(root, expected['draft_image_id'], course_source, tags)
    need(set(attested['verified_tags']) == set(tags), 'EXEC_UNEXPECTED_STEP')
    containers = [v['container_id'] for v in attested['containers'].values()]
    need(len(set(containers)) == len(containers), 'EXEC_CONTAINER_REUSED')
    for op in OPERATIONS:
        receipt = load(root / 'execution-receipts' / (op + '.json'))
        need(receipt == {'operation': op, 'identity': expected,
                         'report_sha256': report_sha if op == 'validate' else None,
                         'originals': evidence_files(root, op, profile)},
             'EXEC_RECEIPT_MISMATCH: ' + op)
    return {**attested, **expected, 'report_sha256': report_sha,
            'operations': list(OPERATIONS)}


class DraftExecutor:
    def __init__(self, root, course_source):
        self.root = Path(root).resolve()
        self.course_source = course_source
        self.active = None

    def require_idle(self):
        active = self.active
        if active is not None and not active['failed'] and active['next'] < len(OPERATIONS):
            raise DraftJobBusy('DRAFT is still serving the active job')

    def prepare(self, data, project, out, profile, candidate):
        """Validate job inputs BEFORE starting the DRAFT build."""
        check_profile(profile)
        meta = identity({**data, 'draft_image_id': 'sha256:' + '0' * 64})
        meta.pop('draft_image_id')
        job = out.parent
        need(out.name == 'draft-build' and job.is_relative_to(self.root / 'work')
             and job != self.root / 'work' and project == job / 'target-project',
             'EXEC_JOB_LAYOUT_INVALID')
        need(profile_sha256(profile) == meta['profile_sha256'], 'EXEC_PROFILE_MISMATCH')
        need(sha(job / 'request.json') == meta['request_sha256']
             and sha(candidate) == meta['candidate_sha256'], 'EXEC_INPUT_HASH_MISMATCH')
        from lab import resolve_profile
        from handoff import strict_json
        original = strict_json((job / 'request.json').read_bytes())
        need(original.get('base') == meta['base_commit']
             and original.get('target') == meta['target_commit']
             and resolve_profile(original.get('profile')) == profile
             and original.get('candidate') == str(candidate),
             'EXEC_ORIGINAL_REQUEST_MISMATCH')
        need(data.get('expected_output', profile['expected_output']) == profile['expected_output']
             and original.get('expected_output', profile['expected_output']) == profile['expected_output']
             and data.get('build_timeout', 600) == original.get('build_timeout', 600),
             'EXEC_EXPECTED_OUTPUT_OR_TIMEOUT_MISMATCH')
        full_timeout(original, profile)
        for name, commit_key in (('base-project', 'base_commit'), ('target-project', 'target_commit')):
            path = job / name
            need(path.is_dir() and path.resolve() == path, 'EXEC_SNAPSHOT_PATH_INVALID')
            actual = subprocess.check_output(
                ['git', '-c', 'safe.directory=' + str(path), '-C', str(path),
                 'rev-parse', 'HEAD'], text=True, timeout=30).strip()
            need(actual == meta[commit_key], 'EXEC_SNAPSHOT_COMMIT_MISMATCH')
        need(not (job / 'inimage').exists() and not (job / 'execution-receipts').exists(),
             'EXEC_EVIDENCE_ALREADY_EXISTS')
        need(bool(self.course_source) and Path(self.course_source).is_absolute(),
             'EXEC_HOST_COURSE_SOURCE_REQUIRED')
        return job, meta

    def activate(self, prepared, profile, image):
        job, meta = prepared
        need(sha(job / 'request.json') == meta['request_sha256'], 'EXEC_REQUEST_CHANGED')
        self.active = {'root': job, 'identity': identity({**meta, 'draft_image_id': image}),
                       'profile': profile, 'full_timeout': full_timeout(load(job / 'request.json'), profile),
                       'next': 0, 'failed': False}

    def execute(self, request):
        need(isinstance(request, dict), 'EXEC_REQUEST_INVALID')
        op = request.get('operation')
        allowed = set(IDENTITY) | {'operation', 'job_root'} | ({'report_sha256'} if op == 'validate' else set())
        need(set(request) == allowed, 'EXEC_REQUEST_FIELDS_INVALID')
        active = self.active
        need(active is not None, 'EXEC_NO_ACTIVE_JOB')
        if op != 'abort':
            need(not active['failed'], 'EXEC_NO_ACTIVE_JOB')
        need(identity(request) == active['identity'], 'EXEC_JOB_IDENTITY_MISMATCH')
        need(request['job_root'] == str(active['root']), 'EXEC_JOB_ROOT_MISMATCH')
        # An orchestrator may fail before a downstream role reaches DRAFT.
        # Abort is identity-bound, idempotent, and performs no Docker action.
        if op == 'abort':
            active['failed'] = True
            return {'status': 'SUCCEEDED', 'operation': 'abort',
                    'identity': active['identity'], 'result': {'aborted': True}}
        index = active['next']
        need(index < len(OPERATIONS) and op == OPERATIONS[index], 'EXEC_OPERATION_ORDER')
        root, profile, meta = active['root'], active['profile'], active['identity']
        try:
            need(sha(root / 'request.json') == meta['request_sha256'], 'EXEC_REQUEST_CHANGED')
            from imgrunner import full_in_image, scan_in_image
            from lab import patch, validate
            image = meta['draft_image_id']
            base, target = root / 'base-project', root / 'target-project'
            report_sha = None
            if op.startswith('full-check-'):
                project, name = {'full-check-baseline': (base, 'baseline-full'),
                                 'full-check-target': (target, 'target-full'),
                                 'full-check-recheck': (target, 'final-full')}[op]
                folder = root / name
                need(not folder.exists(), 'EXEC_OUTPUT_EXISTS')
                full_in_image(image, project, folder, 'make ' + profile['clean_target'],
                              'make ' + profile['build_target'], timeout=active['full_timeout'],
                              evidence=root / 'inimage', tag=op)
                result = load(folder / 'findings.json')
                if result.get('status') == 'TIMED_OUT':
                    raise DownstreamTimeout('BUILDCHECKER_TIMED_OUT: ' + op)
                need(result.get('status') == 'SUCCEEDED', 'EXEC_FULL_CHECK_FAILED')
            elif op in ('scan-baseline', 'scan-target'):
                folder = root / 'incremental'
                folder.mkdir(exist_ok=True)
                output = folder / ('baseline-scan.json' if op == 'scan-baseline' else 'target-scan.json')
                need(not output.exists(), 'EXEC_OUTPUT_EXISTS')
                old = None if op == 'scan-baseline' else folder / 'baseline-cache.json'
                if old is not None:
                    need(old.is_file() and not old.is_symlink(), 'EXEC_BASELINE_CACHE_MISSING')
                result = scan_in_image(image, base if old is None else target, output, profile,
                                       old, evidence=root / 'inimage', tag=op)
                need(result.get('commit') == meta['base_commit' if old is None else 'target_commit'],
                     'EXEC_SCAN_COMMIT_MISMATCH')
            else:
                report_sha = request['report_sha256']
                report = root / 'incremental/incremental-check.json'
                envelope = checked_incremental(report.read_bytes(), report_sha,
                    meta['job_id'], meta['trace_id'], meta['target_commit'], meta['profile_sha256'], image)
                need(envelope['data'] == load(root / 'incremental/target-scan.json'),
                     'EXEC_REPORT_SCAN_MISMATCH')
                patchfile = root / 'repair-work/candidate.patch'
                need(patchfile.is_file() and not patchfile.is_symlink(), 'EXEC_PATCH_MISSING')
                diff, _ = patch(target, envelope['data'])
                need(bool(diff) and patchfile.read_bytes() == diff.encode('utf-8'), 'EXEC_PATCH_MISMATCH')
                result = validate(target, patchfile, root / 'repair-work/validation',
                                  profile=profile, exec_image=image)
                need(result.get('accepted') is True, 'EXEC_VALIDATION_REJECTED')
            tags = [t for step in OPERATIONS[:index + 1] for t in operation_tags(profile)[step]]
            attested = verify_job(root, image, self.course_source, tags)
            need(set(attested['verified_tags']) == set(tags), 'EXEC_UNEXPECTED_STEP')
            save(root / 'execution-receipts' / (op + '.json'),
                 {'operation': op, 'identity': meta, 'report_sha256': report_sha,
                  'originals': evidence_files(root, op, profile)})
            active['next'] += 1
            return {'status': 'SUCCEEDED', 'operation': op, 'identity': meta, 'result': result}
        except Exception:
            active['failed'] = True
            operation_failure(root, op, profile)
            raise


def delegate(op, data, report_sha=None):
    meta = identity(data)
    body = {**meta, 'operation': op, 'job_root': str(Path(data['out']).parent)}
    if op == 'validate':
        body['report_sha256'] = report_sha
    req = urllib.request.Request('http://draft:8080/v1/execute',
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=6000) as response:
            reply = json.load(response)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        # Keep the inner HTTP exchange separate from the outer stage response.
        folder = Path(body['job_root']) / 'broker-errors'
        folder.mkdir(exist_ok=True)
        with (folder / (op + '-request.json')).open('xb') as stream:
            stream.write(req.data)
        with (folder / (op + '-response.json')).open('xb') as stream:
            stream.write(raw)
        from handoff import strict_json
        error = strict_json(raw)
        need(exc.code == 422 and error.get('status') == 'FAILED'
             and error.get('role') == 'draft' and error.get('operation') == op
             and all(error.get(key) == meta[key] for key in
                     ('job_id', 'trace_id', 'profile_sha256', 'draft_image_id')),
             'EXEC_BROKER_ERROR_IDENTITY_MISMATCH')
        if error.get('error_code') == 'TIMEOUT':
            raise DownstreamTimeout('BROKER_TIMEOUT: ' + op) from exc
        raise ValueError('EXEC_BROKER_FAILED: ' + op + ': ' + str(error.get('error'))) from exc
    need(reply.get('status') == 'SUCCEEDED' and reply.get('operation') == op
         and reply.get('identity') == meta, 'EXEC_BROKER_RESPONSE_MISMATCH')
    return reply['result']
