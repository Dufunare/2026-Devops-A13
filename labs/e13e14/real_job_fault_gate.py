"""Controlled E14 draft-image timeout/replay/recovery campaign.

Consumes an already running isolated Compose project and an already verified
success from the SAME deployment. Derives a separate teaching repository with
a slow BASE clean recipe; TARGET is byte-identical to the normal target tree.
No arbitrary commands are accepted by the broker. No services are restarted.
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from e14_gate import (ROOT, PORTS, STAGES, GateError, require, save, load, sha,
                      get_health, service_containers, verify_continuity,
                      compose_logs, events)
from orchestrate import container_path, host_path
from draft_executor import identity
from real_job_gate import verify_manifest, verify_result

TIMEOUT = 20
DELAY = 50
TAG = 'full-check-baseline'
MARKER = 'e14-timeout-started'
LATE = 'e14-timeout-late'


def git(log, *args):
    cmd = ['git', *map(str, args)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    with log.open('a', encoding='utf-8') as stream:
        stream.write(repr(cmd) + '\n' + proc.stdout + proc.stderr + '\n')
    require(proc.returncode == 0, 'FAULT_FIXTURE_GIT_FAILED: ' + str(args[:3]))
    return proc.stdout.strip()


def tree_snapshot(root):
    result = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'FAULT_EVIDENCE_SYMLINK')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha(path)
    return result


def derive_fixture(request, out):
    source = host_path(request['repo'])
    require(source.is_relative_to(ROOT / 'data') and source.is_dir(),
            'FAULT_SOURCE_OUTSIDE_DATA')
    repo = ROOT / 'data' / ('e14-timeout-' + uuid.uuid4().hex)
    log = out / 'fixture-git.log'
    git(log, '-c', 'safe.directory=' + str(source), 'clone', '--no-hardlinks',
        '--no-checkout', source, repo)
    def local(*args):
        return git(log, '-C', repo, *args)
    original_base, original_target = request['base'], request['target']
    local('checkout', '-b', 'e14-timeout', original_base)
    local('config', 'user.name', 'E14 Fault Fixture')
    local('config', 'user.email', 'fixture@example.invalid')
    path = repo / 'Makefile'
    original_make = path.read_bytes()
    require(b'e14-fault-delay' not in original_make, 'FAULT_RULE_ALREADY_EXISTS')
    addition = ("\n.PHONY: e14-fault-delay\nclean: e14-fault-delay\n"
                "e14-fault-delay:\n"
                "\t@printf 'started\\n' > " + MARKER + "\n"
                "\t@sleep " + str(DELAY) + "\n"
                "\t@printf 'late\\n' > " + LATE + "\n")
    path.write_bytes(original_make + addition.encode('utf-8'))
    local('add', 'Makefile')
    local('commit', '-m', 'E14 controlled slow baseline clean')
    base = local('rev-parse', 'HEAD')
    # Preserve ancestry while restoring the entire original target tree.
    local('read-tree', '--reset', '-u', original_target)
    local('commit', '-m', 'E14 restore exact normal target tree')
    target = local('rev-parse', 'HEAD')
    tree = local('rev-parse', 'HEAD^{tree}')
    require(tree == local('rev-parse', original_target + '^{tree}'),
            'FAULT_TARGET_TREE_CHANGED')
    require(not local('status', '--porcelain'), 'FAULT_FIXTURE_DIRTY')
    local('bundle', 'create', out / 'fault-fixture.bundle', 'refs/heads/e14-timeout')
    save(out / 'fixture.json', {'original_base': original_base, 'original_target': original_target,
                                'base': base, 'target': target, 'target_tree': tree,
                                'repo': container_path(repo), 'timeout_s': TIMEOUT,
                                'delay_s': DELAY, 'bundle_sha256': sha(out / 'fault-fixture.bundle')})
    faulty = dict(request, repo=container_path(repo), base=base, target=target,
                  downstream_full_timeout=TIMEOUT)
    fault_request = out / 'fault.request.json'
    save(fault_request, faulty)
    return fault_request


def verify_timed_out_child(record, inspect, image, course_source, timeout=TIMEOUT):
    require(record.get('tag') == TAG and record.get('image') == image and
            record.get('inspect_image') == image and record.get('timeout_s') == timeout and
            record.get('create_exit') == 0 and record.get('create_timed_out') is False and
            record.get('timed_out') is True and record.get('command_exit') == 124 and
            record.get('exit') == 124, 'FAULT_NOT_ACTUAL_CHILD_TIMEOUT')
    cid, name = record.get('container_id'), record.get('container_name')
    require(isinstance(cid, str) and re.fullmatch(r'[0-9a-f]{64}', cid) and
            isinstance(name, str) and re.fullmatch(r'course-exec-[0-9a-f]{32}', name),
            'FAULT_CHILD_ID_INVALID')
    require(record.get('start_argv') == ['docker', 'start', '-a', cid] and
            record.get('cleanup_argv') == ['docker', 'rm', '-f', cid] and
            record.get('cleanup_lookup_argv') == ['docker', 'ps', '-aq', '--no-trunc',
                                                  '--filter', 'name=^/' + name + '$'] and
            record.get('cleanup_exit') == 0 and record.get('cleanup_verified') is True and
            record.get('cleanup_lookup_exit') == 0 and record.get('cleanup_remaining') == [],
            'FAULT_CHILD_CLEANUP_UNCONFIRMED')
    require(isinstance(inspect, list) and len(inspect) == 1 and isinstance(inspect[0], dict),
            'FAULT_INSPECT_INVALID')
    original = inspect[0]
    mounts = original.get('Mounts')
    require(original.get('Id') == cid and original.get('Name') == '/' + name and
            original.get('Image') == image and original.get('State', {}).get('Running') is True,
            'FAULT_CHILD_NOT_OBSERVED_RUNNING')
    require(isinstance(mounts, list) and len(mounts) == 1 and
            mounts[0].get('Destination') == '/course' and mounts[0].get('Type') == 'bind' and
            mounts[0].get('Source') == course_source and record.get('inspect_mounts') == ['/course'],
            'FAULT_CHILD_MOUNT_MISMATCH')
    return cid, name


def confirm_absent(out, cid, name, phase):
    observations = []
    for field in ('id=' + cid, 'name=^/' + name + '$'):
        argv = ['docker', 'ps', '-aq', '--no-trunc', '--filter', field]
        p = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        observations.append({'argv': argv, 'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
    save(out / ('child-absence-' + phase + '.json'), observations)
    require(all(x['exit'] == 0 and not x['stdout'].strip() for x in observations),
            'FAULT_CHILD_STILL_PRESENT')


def verify_abort(job, meta):
    result = load(job / 'result.json')
    require(result.get('broker_abort') == {'status': 'SUCCEEDED', 'operation': 'abort'},
            'FAULT_BROKER_ABORT_NOT_CONFIRMED')
    require(load(job / 'abort-request.json') ==
            {**identity(meta), 'operation': 'abort', 'job_root': container_path(job)},
            'FAULT_ABORT_REQUEST_MISMATCH')
    response = load(job / 'abort-response.json')
    require(response.get('operation') == 'abort' and response.get('status') == 'SUCCEEDED'
            and response.get('identity') == identity(meta) and response.get('result') == {'aborted': True},
            'FAULT_ABORT_RESPONSE_MISMATCH')


def verify_fault(job, request, candidate_sha):
    r = load(job / 'result.json')
    meta = identity(r)
    require(r.get('status') == 'FAILED' and r.get('error_code') == 'TIMEOUT' and
            r.get('downstream_container_attested') is False and
            [s['name'] for s in r['stages']] == ['draft'], 'FAULT_DID_NOT_STOP_AFTER_DRAFT')
    require(meta['request_sha256'] == sha(request) == sha(job / 'request.json') and
            meta['candidate_sha256'] == candidate_sha, 'FAULT_INPUT_HASH_MISMATCH')
    fault_input = load(request)
    require((meta['base_commit'], meta['target_commit']) == (fault_input['base'], fault_input['target']),
            'FAULT_COMMIT_MISMATCH')
    require(load(job / 'draft-build/result.json')['status'] == 'SUCCEEDED' and
            load(job / 'draft.json')['execution_identity'] == meta,
            'FAULT_DRAFT_NOT_SUCCESSFUL')
    require(not (job / 'execution-receipts').exists() and
            {p.relative_to(job).as_posix() for p in job.rglob('*.exec.json')} ==
            {'inimage/' + TAG + '.exec.json'}, 'FAULT_UNEXPECTED_DOWNSTREAM_EXECUTION')
    rec = load(job / 'inimage' / (TAG + '.exec.json'))
    insp = load(job / 'inimage' / (TAG + '.inspect.json'))
    cid, name = verify_timed_out_child(rec, insp, meta['draft_image_id'], str(ROOT.resolve()))
    require((job / 'inimage' / (TAG + '.cid')).read_text().strip() == cid and
            'TIMEOUT after' in (job / 'inimage' / (TAG + '.stderr.log')).read_text(),
            'FAULT_TIMEOUT_ORIGINAL_MISSING')
    body = load(job / 'broker-errors' / (TAG + '-request.json'))
    require(body == {**meta, 'operation': TAG, 'job_root': container_path(job)},
            'FAULT_BROKER_REQUEST_MISMATCH')
    outer_request = load(job / 'baseline-response-request.json')
    require(all(outer_request.get(k) == v for k, v in meta.items()),
            'FAULT_OUTER_REQUEST_IDENTITY_MISMATCH')
    for file, role in ((job / 'broker-errors' / (TAG + '-response.json'), 'draft'),
                       (job / 'baseline-response-error-body.txt', 'buildchecker')):
        answer = load(file)
        require(answer.get('status') == 'FAILED' and answer.get('error_code') == 'TIMEOUT' and
                answer.get('role') == role and all(answer.get(k) == meta[k] for k in
                    ('job_id', 'trace_id', 'profile_sha256', 'draft_image_id')),
                'FAULT_TIMEOUT_HTTP_PROPAGATION_FAILED: ' + role)
        if role == 'draft':
            require(answer.get('operation') == TAG, 'FAULT_BROKER_OPERATION_MISMATCH')
    marker = job / 'baseline-full/project' / MARKER
    require(marker.is_file() and marker.read_text().strip() == 'started' and
            not marker.with_name(LATE).exists(), 'FAULT_DELAY_NOT_INTERRUPTED')
    verify_abort(job, meta)
    count = verify_manifest(job, r)
    return {'status': 'PASS', **meta, 'container_id': cid, 'container_name': name,
            'artifacts_verified': count, 'timeout_s': TIMEOUT}


def run_job(request, job, log, expect_rc, during=None):
    argv = [sys.executable, str(ROOT / 'labs/e13e14/orchestrate.py'),
            '--request', str(request.resolve()), '--out', str(job.resolve())]
    if during is None:
        with log.open('w', encoding='utf-8') as stream:
            proc = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=12000)
        rc = proc.returncode
    else:
        # Observe the four services while the slow recipe is actually running.
        marker = job / 'baseline-full/project' / MARKER
        observed = False
        with log.open('w', encoding='utf-8') as stream:
            proc = subprocess.Popen(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 12000
            try:
                while proc.poll() is None:
                    if marker.is_file() and not observed:
                        during()
                        require(proc.poll() is None, 'FAULT_DURING_OBSERVATION_TOO_LATE')
                        observed = True
                    require(time.monotonic() < deadline, 'FAULT_ORCHESTRATOR_DEADLINE')
                    time.sleep(0.2)
                rc = proc.returncode
            finally:
                if proc.poll() is None:
                    # Only this local orchestrator, never a shared Docker daemon.
                    proc.kill()
                    proc.wait()
        require(observed, 'FAULT_RECIPE_NEVER_OBSERVED')
    require(rc == expect_rc and (job / 'result.json').is_file(),
            'FAULT_ORCHESTRATOR_UNEXPECTED_EXIT: ' + str(rc))


def replay(out, job, meta, phase, expected, operation=TAG):
    body = {**identity(meta), 'operation': operation, 'job_root': container_path(job)}
    raw = json.dumps(body).encode()
    (out / ('replay-' + phase + '-request.json')).write_bytes(raw)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 5
    attempt = 0
    while True:
        attempt += 1
        req = urllib.request.Request('http://127.0.0.1:%d/v1/execute' % PORTS['draft'],
                                     data=raw, headers={'Content-Type': 'application/json'})
        try:
            with opener.open(req, timeout=5) as response:
                status, answer = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, answer = exc.code, exc.read()
        (out / ('replay-%s-%02d-response.json' % (phase, attempt))).write_bytes(answer)
        decoded = json.loads(answer)
        if status == 409 and decoded.get('error_code') == 'BUSY' and time.monotonic() < deadline:
            time.sleep(0.05)
            continue
        require(status == 422 and decoded.get('status') == 'FAILED' and expected in decoded.get('error', '')
                and decoded.get('role') == 'draft' and decoded.get('operation') == operation
                and all(decoded.get(k) == body[k] for k in
                        ('job_id', 'trace_id', 'profile_sha256', 'draft_image_id')),
                'FAULT_OLD_JOB_REPLAY_ACCEPTED_OR_WRONG_ERROR')
        return {'status': 'PASS', 'http': status, 'attempts': attempt, 'reason': expected}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request', type=Path, required=True)
    p.add_argument('--request-sha256', required=True)
    p.add_argument('--candidate-sha256', required=True)
    p.add_argument('--success-out', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--project', required=True)
    p.add_argument('--image', required=True)
    a = p.parse_args()
    out, prior = a.out.resolve(), a.success_out.resolve()
    require(out.is_relative_to(ROOT / 'work') and not out.exists()
            and prior.is_relative_to(ROOT / 'work') and prior != ROOT / 'work'
            and not out.is_relative_to(prior), 'Use disjoint fresh work/ directories')
    out.mkdir(parents=True)
    try:
        require(sha(a.request) == a.request_sha256, 'FAULT_NORMAL_REQUEST_HASH_MISMATCH')
        normal = load(a.request)
        require('downstream_full_timeout' not in normal and
                sha(host_path(normal['candidate'])) == a.candidate_sha256,
                'FAULT_NORMAL_INPUT_MISMATCH')
        before_result = verify_result(prior / 'job', a.request_sha256, a.candidate_sha256)
        require(load(prior / 'summary.json')['status'] == 'PASS', 'FAULT_PRIOR_GATE_NOT_PASSED')
        prior_snapshot = tree_snapshot(prior)
        save(out / 'prior-snapshot.json', prior_snapshot)
        save(out / 'health-before.json', get_health())
        before = service_containers(out, a.project, a.image, 'before')
        continuity_prior = verify_continuity(load(prior / 'containers-after.json')['services'],
                                             before, 'prior-success', 'before')
        fault_request = derive_fixture(normal, out)
        job = out / 'fault'
        during = {}
        def observe():
            save(out / 'health-during.json', get_health())
            during.update(service_containers(out, a.project, a.image, 'during'))
        run_job(fault_request, job, out / 'fault.console.log', 1, during=observe)
        fault = verify_fault(job, fault_request, a.candidate_sha256)
        save(out / 'fault-summary.json', fault)
        confirm_absent(out, fault['container_id'], fault['container_name'], 'after-fault')
        save(out / 'health-after-fault.json', get_health())
        after_fault = service_containers(out, a.project, a.image, 'after-fault')
        replay_failed = replay(out, job, fault, 'failed', 'EXEC_NO_ACTIVE_JOB')
        fault_snapshot = tree_snapshot(job)
        save(out / 'fault-snapshot.json', fault_snapshot)

        recovery_job = out / 'recovery'
        run_job(a.request, recovery_job, out / 'recovery.console.log', 0)
        recovery = verify_result(recovery_job, a.request_sha256, a.candidate_sha256)
        save(out / 'recovery-summary.json', recovery)
        require(len({before_result['job_id'], fault['job_id'], recovery['job_id']}) == 3 and
                len({before_result['trace_id'], fault['trace_id'], recovery['trace_id']}) == 3,
                'FAULT_JOB_OR_TRACE_REUSED')
        replay_old = replay(out, job, fault, 'after-recovery', 'EXEC_JOB_IDENTITY_MISMATCH')

        # Wait beyond the original delayed-write point if recovery was fast.
        marker = job / 'baseline-full/project' / MARKER
        remaining = marker.stat().st_mtime + DELAY + 2 - time.time()
        require(remaining <= DELAY + 5, 'FAULT_CLOCK_INVALID')
        if remaining > 0:
            time.sleep(remaining)
        require(not marker.with_name(LATE).exists() and tree_snapshot(job) == fault_snapshot,
                'FAULT_EVIDENCE_CHANGED_AFTER_CLEANUP')
        require(tree_snapshot(prior) == prior_snapshot and
                verify_result(prior / 'job', a.request_sha256, a.candidate_sha256) == before_result,
                'FAULT_PRIOR_SUCCESS_CHANGED')
        confirm_absent(out, fault['container_id'], fault['container_name'], 'after-recovery')
        save(out / 'health-after-recovery.json', get_health())
        after_recovery = service_containers(out, a.project, a.image, 'after-recovery')
        continuity = [continuity_prior, verify_continuity(before, during, 'before', 'during'),
                      verify_continuity(during, after_fault, 'during', 'after-fault'),
                      verify_continuity(after_fault, after_recovery, 'after-fault', 'after-recovery')]
        compose_logs(out, a.project, a.image)
        fault_events = events(out / 'four-services.log', fault['job_id'], fault['trace_id'])
        require(sorted(e['role'] for e in fault_events if e.get('error_code') == 'TIMEOUT') ==
                ['buildchecker', 'draft'] and
                [(e['role'], e.get('operation')) for e in fault_events if e.get('status') == 'SUCCEEDED'] ==
                [('draft', None), ('draft', 'abort')],
                'FAULT_SERVICE_TRACE_MISMATCH')
        recovery_events = events(out / 'four-services.log', recovery['job_id'], recovery['trace_id'])
        require(all(e.get('status') == 'SUCCEEDED' for e in recovery_events) and
                sorted(e['role'] for e in recovery_events) ==
                sorted(['draft'] * 7 + ['buildchecker'] * 3 + ['echecker', 'mdfixer']),
                'FAULT_RECOVERY_TRACE_MISMATCH')
        summary = {'status': 'PASS', 'source': 'controlled teaching fixture',
                   'prior_job': before_result['job_id'], 'fault': fault, 'recovery': recovery,
                   'replay_failed': replay_failed, 'replay_after_recovery': replay_old,
                   'service_continuity': continuity, 'prior_and_fault_unchanged': True,
                   'no_late_write': True}
        save(out / 'summary.json', summary)
        print('E14_DRAFT_FAULT_RECOVERY_GATE=PASS', flush=True)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except (GateError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        save(out / 'summary.json', {'status': 'FAIL', 'error': str(exc)})
        try:
            compose_logs(out, a.project, a.image)
        except Exception as log_exc:
            print('DIAGNOSTIC_LOG_ERROR:', log_exc, file=sys.stderr)
        print('E14_DRAFT_FAULT_RECOVERY_GATE=FAIL:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
