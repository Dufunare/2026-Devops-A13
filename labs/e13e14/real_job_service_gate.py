"""Single-service outage and recovery on an explicitly authorized isolated project.

Stops only the already verified EChecker container ID. Never stops the Docker
daemon or an unrelated project. Restore that same container in a finally block.
This is a controlled teaching preflight, not formal bilateral acceptance.
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from e14_gate import (ROOT, PORTS, GateError, require, save, load, sha,
                      get_health, service_containers, verify_continuity,
                      compose_logs, events)
from orchestrate import host_path
from draft_executor import identity
from execution_attestation import verify_job
from real_job_gate import verify_result, verify_manifest
from real_job_fault_gate import run_job, replay, tree_snapshot, verify_abort

ROLE = 'echecker'


def docker(log, argv):
    proc = subprocess.run(['docker', *argv], capture_output=True, text=True, timeout=45)
    with log.open('a', encoding='utf-8') as stream:
        stream.write(repr(['docker', *argv]) + '\n' + proc.stdout + proc.stderr + '\n')
    require(proc.returncode == 0, 'SERVICE_GATE_DOCKER_FAILED: ' + argv[0])
    return proc.stdout


def inspect_services(out, project, before, phase):
    values = {}
    for role, known in before.items():
        cid = known['container_id']
        raw = subprocess.run(['docker', 'inspect', '--type', 'container', cid],
                             capture_output=True, text=True, timeout=30)
        require(raw.returncode == 0, 'SERVICE_GATE_INSPECT_FAILED: ' + role)
        value = json.loads(raw.stdout)[0]
        labels, state = value['Config']['Labels'], value['State']
        require(value['Id'] == cid and labels['com.docker.compose.project'] == project
                and labels['com.docker.compose.service'] == role,
                'SERVICE_GATE_WRONG_CONTAINER: ' + role)
        values[role] = {'container_id': cid, 'started_at': state['StartedAt'],
                        'running': state['Running']}
    save(out / ('state-' + phase + '.json'), values)
    return values


def verify_only_stopped(before, stopped):
    require(set(before) == set(stopped) == set(PORTS), 'SERVICE_GATE_MISSING_ROLE')
    for role, known in before.items():
        current = stopped[role]
        require(current['container_id'] == known['container_id'] and
                current['started_at'] == known['started_at'] and
                current['running'] is (role != ROLE), 'SERVICE_GATE_OUTAGE_SCOPE: ' + role)


def verify_only_restarted(before, after):
    require(set(before) == set(after) == set(PORTS), 'SERVICE_GATE_MISSING_ROLE')
    for role, known in before.items():
        current = after[role]
        require(current['container_id'] == known['container_id'] and
                (current['started_at'] != known['started_at']) is (role == ROLE),
                'SERVICE_GATE_RESTART_SCOPE: ' + role)


def outage_health(out):
    result = {}
    for role, port in PORTS.items():
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=3) as resp:
                result[role] = {'http': resp.status, 'body': json.load(resp)}
        except (OSError, urllib.error.URLError) as exc:
            result[role] = {'error': str(exc)}
    save(out / 'health-during.json', result)
    require('error' in result[ROLE] and all(
        result[role] == {'http': 200, 'body': {'status': 'ok', 'role': role}}
        for role in PORTS if role != ROLE), 'SERVICE_GATE_HEALTH_ISOLATION_FAILED')


def wait_health(out):
    deadline = time.monotonic() + 60
    while True:
        try:
            value = get_health()
            save(out / 'health-restored.json', value)
            return
        except GateError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


def verify_outage_job(job, request_sha, candidate_sha):
    result = load(job / 'result.json')
    meta = identity(result)
    require(result.get('status') == 'FAILED' and result.get('error_code') == 'SERVICE_UNAVAILABLE'
            and result.get('failed_role') == ROLE and result.get('downstream_container_attested') is False
            and [s['name'] for s in result['stages']] == ['draft', 'full-check'],
            'SERVICE_GATE_WRONG_FAILURE_STAGE')
    require(meta['request_sha256'] == request_sha == sha(job / 'request.json')
            and meta['candidate_sha256'] == candidate_sha, 'SERVICE_GATE_INPUT_MISMATCH')
    failed = load(job / 'incremental-response.json')
    sent = load(job / 'incremental-response-request.json')
    require(failed.get('role') == ROLE and failed.get('error_code') == 'SERVICE_UNAVAILABLE'
            and all(sent.get(k) == v for k, v in meta.items()),
            'SERVICE_GATE_MISSING_FAILURE_EVIDENCE')
    tags = ('full-check-baseline', 'full-check-target')
    verified = verify_job(job, meta['draft_image_id'], str(ROOT.resolve()), tags)
    require(set(verified['verified_tags']) == set(tags) and
            {p.stem for p in (job / 'execution-receipts').glob('*.json')} == set(tags),
            'SERVICE_GATE_UNEXPECTED_DOWNSTREAM_EXECUTION')
    verify_abort(job, meta)
    count = verify_manifest(job, result)
    return {'status': 'PASS', **meta, 'artifacts_verified': count,
            'downstream_containers_verified': len(tags)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request', type=Path, required=True)
    p.add_argument('--request-sha256', required=True)
    p.add_argument('--candidate-sha256', required=True)
    p.add_argument('--prior-fault-out', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--project', required=True)
    p.add_argument('--image', required=True)
    p.add_argument('--allow-stop-echecker', action='store_true',
                   help='Authorize stopping exactly this isolated project EChecker')
    a = p.parse_args()
    require(a.allow_stop_echecker, 'Explicit isolated-project stop authorization required')
    out, prior = a.out.resolve(), a.prior_fault_out.resolve()
    require(out.is_relative_to(ROOT / 'work') and not out.exists()
            and prior.is_relative_to(ROOT / 'work') and prior != ROOT / 'work'
            and not out.is_relative_to(prior), 'Use disjoint fresh work/ directories')
    out.mkdir(parents=True)
    log = out / 'stop-start.log'
    stopped = False
    before = None
    try:
        require(sha(a.request) == a.request_sha256 and
                sha(host_path(load(a.request)['candidate'])) == a.candidate_sha256,
                'SERVICE_GATE_INPUT_MISMATCH')
        require(load(prior / 'summary.json')['status'] == 'PASS', 'SERVICE_GATE_PRIOR_NOT_PASSED')
        prior_result = verify_result(prior / 'recovery', a.request_sha256, a.candidate_sha256)
        prior_snapshot = tree_snapshot(prior)
        save(out / 'prior-snapshot.json', prior_snapshot)
        save(out / 'health-before.json', get_health())
        before = service_containers(out, a.project, a.image, 'before')
        verify_continuity(load(prior / 'containers-after-recovery.json')['services'],
                          before, 'prior-recovery', 'before')
        cid = before[ROLE]['container_id']
        stopped = True  # even an interrupted stop must attempt to restore this ID
        try:
            docker(log, ['stop', '--time', '10', cid])
            verify_only_stopped(before, inspect_services(out, a.project, before, 'during'))
            outage_health(out)
            failed_job = out / 'fault'
            run_job(a.request, failed_job, out / 'fault.console.log', 1)
            fault = verify_outage_job(failed_job, a.request_sha256, a.candidate_sha256)
            save(out / 'fault-summary.json', fault)
            # This was the next legal operation before abort. Reject it for
            # inactive job, not merely out-of-order replay.
            rejected = replay(out, failed_job, fault, 'outage', 'EXEC_NO_ACTIVE_JOB',
                              operation='scan-baseline')
            fault_snapshot = tree_snapshot(failed_job)
            save(out / 'fault-snapshot.json', fault_snapshot)
        finally:
            docker(log, ['start', cid])
            stopped = False
        wait_health(out)
        restored = service_containers(out, a.project, a.image, 'restored')
        verify_only_restarted(before, restored)
        recovery_job = out / 'recovery'
        run_job(a.request, recovery_job, out / 'recovery.console.log', 0)
        recovery = verify_result(recovery_job, a.request_sha256, a.candidate_sha256)
        save(out / 'recovery-summary.json', recovery)
        require(len({prior_result['job_id'], fault['job_id'], recovery['job_id']}) == 3 and
                len({prior_result['trace_id'], fault['trace_id'], recovery['trace_id']}) == 3,
                'SERVICE_GATE_JOB_REUSED')
        rejected_old = replay(out, failed_job, fault, 'restored', 'EXEC_JOB_IDENTITY_MISMATCH',
                              operation='scan-baseline')
        require(tree_snapshot(prior) == prior_snapshot and tree_snapshot(failed_job) == fault_snapshot,
                'SERVICE_GATE_EVIDENCE_CHANGED')
        save(out / 'health-after.json', get_health())
        after = service_containers(out, a.project, a.image, 'after')
        verify_continuity(restored, after, 'restored', 'after')
        compose_logs(out, a.project, a.image)
        fault_events = events(out / 'four-services.log', fault['job_id'], fault['trace_id'])
        require(sorted((e['role'], e.get('operation') or '') for e in fault_events
                       if e.get('status') == 'SUCCEEDED') ==
                sorted([('draft', ''), ('draft', 'full-check-baseline'),
                        ('draft', 'full-check-target'), ('draft', 'abort'),
                        ('buildchecker', ''), ('buildchecker', '')]),
                'SERVICE_GATE_FAULT_TRACE_MISMATCH')
        recovered = events(out / 'four-services.log', recovery['job_id'], recovery['trace_id'])
        require(all(e.get('status') == 'SUCCEEDED' for e in recovered) and
                sorted(e['role'] for e in recovered) ==
                sorted(['draft'] * 7 + ['buildchecker'] * 3 + ['echecker', 'mdfixer']),
                'SERVICE_GATE_RECOVERY_TRACE_MISMATCH')
        summary = {'status': 'PASS', 'stopped_role': ROLE, 'fault': fault, 'recovery': recovery,
                   'other_three_continuous': True, 'same_echecker_restarted': True,
                   'replay_outage': rejected, 'replay_restored': rejected_old,
                   'prior_and_fault_unchanged': True}
        save(out / 'summary.json', summary)
        print('E14_SINGLE_SERVICE_RECOVERY_GATE=PASS', flush=True)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except (GateError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        summary = {'status': 'FAIL', 'error': str(exc)}
        if stopped and before:
            try:
                docker(log, ['start', before[ROLE]['container_id']])
                wait_health(out)
                summary['restore_attempt'] = 'PASS'
            except Exception as restore:
                summary['restore_attempt'] = 'FAIL: ' + str(restore)
        save(out / 'summary.json', summary)
        try:
            compose_logs(out, a.project, a.image)
        except Exception as log_exc:
            print('DIAGNOSTIC_LOG_ERROR:', log_exc, file=sys.stderr)
        print('E14_SINGLE_SERVICE_RECOVERY_GATE=FAIL:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
