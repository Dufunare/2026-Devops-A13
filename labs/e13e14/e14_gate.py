"""Member C E14 teaching-fixture gate: success -> timeout -> recovery.

This gate consumes an already running four-service Compose project. It does not
start or destroy containers and never touches another project's Docker state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / 'labs/e13e14/compose.yaml'
PORTS = {role: int(os.environ.get('E14_PORT_' + role.upper(), default))
         for role, default in (('buildchecker', 18081), ('echecker', 18082),
                               ('draft', 18083), ('mdfixer', 18084))}
STAGES = ['draft', 'full-check', 'incremental-check', 'repair', 'recheck']
EXPECTED_ROLES = Counter({'buildchecker': 3, 'echecker': 1, 'draft': 1, 'mdfixer': 1})


class GateError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise GateError(message)


def save(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def course_file(value: str, out: Path):
    require(isinstance(value, str) and value.startswith('/course/'), 'Expected /course file URI')
    source = ROOT / value[len('/course/'): ]
    path = source.resolve()
    require(not source.is_symlink() and path.is_relative_to(out) and path.is_file(), 'Unsafe course artifact')
    return path


def verify_artifacts(out: Path, result: dict, expected_count=162):
    seen = set()
    for item in result.get('artifacts', []):
        rel = item['uri']
        require(isinstance(rel, str) and not Path(rel).is_absolute(), 'Absolute artifact URI')
        require(rel not in seen and all(part not in ('', '.', '..', '.git') for part in rel.split('/')),
                'Duplicate or unsafe artifact URI')
        seen.add(rel)
        source = out / rel
        path = source.resolve()
        require(not source.is_symlink() and path.is_relative_to(out) and path.is_file(), 'Artifact missing or unsafe')
        require(sha(path) == item['sha256'] and path.stat().st_size == item['bytes'],
                f'Artifact content mismatch: {rel}')
    require(len(seen) == expected_count, f'Expected {expected_count} artifacts; found {len(seen)}')
    return len(seen)


def verify_success(out: Path):
    r = load(out / 'result.json')
    require(r.get('schema_version') == 'e14-compose-1' and r.get('status') == 'SUCCEEDED',
            'E14 result was not successful')
    require([s['name'] for s in r['stages']] == STAGES, 'Five-stage order mismatch')
    envelope = {}
    for item in r['stages']:
        name = item['name']
        path = (out / item['artifact']['uri']).resolve()
        require(path.is_relative_to(out) and path.is_file(), f'Missing stage {name}')
        require(sha(path) == item['artifact']['sha256'], f'Stage SHA mismatch {name}')
        stage = load(path)
        require((stage['name'], stage['status'], stage['job_id'], stage['trace_id']) ==
                (name, 'SUCCEEDED', r['job_id'], r['trace_id']), f'Stage identity mismatch {name}')
        require(stage['commit'] == (r['base_commit'] if name == 'full-check' else r['target_commit']),
                f'Stage commit mismatch {name}')
        envelope[name] = stage
    draft = load(out / 'draft-build/result.json')
    attempts = draft['attempts']
    require(draft['status'] == 'SUCCEEDED' and len(attempts) == 2, 'DRAFT two attempts failed')
    require(attempts[0].get('failure_class') == 'MISSING_MAKE' and attempts[1].get('build_exit_code') == 0,
            'DRAFT baseline/repair build contract failed')
    require(draft['verification']['output_matches'] is True and draft['verification']['exit_code'] == 0,
            'DRAFT program verification failed')
    increment = envelope['incremental-check']['data']
    require(sha(course_file(increment['report'], out)) == increment['sha256'], 'Incremental report SHA mismatch')
    repair = envelope['repair']['data']
    require(sha(course_file(repair['patch'], out)) == repair['sha256'], 'Patch SHA mismatch')
    require(repair['validation']['accepted'] is True, 'Repair was rejected')
    recheck = envelope['recheck']['data']
    require(recheck['remaining_missing'] == 0 and not any(
        item['type'] == 'MISSING' for item in recheck['result']['result']['findings']), 'Remaining missing dependencies')
    count = verify_artifacts(out, r)
    return {'status': 'PASS', 'job_id': r['job_id'], 'trace_id': r['trace_id'],
            'stages': STAGES, 'artifacts_verified': count}


def verify_fault(out: Path):
    r = load(out / 'result.json')
    inner = load(out / 'draft-build/result.json')
    require(r['status'] == 'FAILED' and r['stages'] == [], 'Fault was not isolated')
    require(inner['status'] == 'TIMED_OUT', 'DRAFT did not time out')
    prefix = 'draft HTTP 422: '
    require(r['error'].startswith(prefix), 'Fault HTTP status mismatch')
    http_error = json.loads(r['error'][len(prefix):])
    require(http_error.get('error_code') == 'TIMEOUT', 'Fault code mismatch')
    return {'status': 'PASS', 'job_id': r['job_id'], 'trace_id': r['trace_id'],
            'draft_status': inner['status'], 'error_code': http_error['error_code']}


def get_health():
    ret = {}
    for role, port in PORTS.items():
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=5) as resp:
                data = json.load(resp)
                require(resp.status == 200 and data == {'status': 'ok', 'role': role},
                        f'{role} health response mismatch')
                ret[role] = data
        except (OSError, urllib.error.URLError) as exc:
            raise GateError(f'{role} health request failed: {exc}') from exc
    return ret


def command(argv, log: Path, *, timeout=120, check=True):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w', encoding='utf-8') as stream:
        try:
            p = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise GateError(f'Command timed out: {argv[0]}; see {log}') from exc
    if check and p.returncode:
        raise GateError(f'Command returned {p.returncode}: {argv[0]}; see {log}')
    return p.returncode


def execute(request: Path, dest: Path, log: Path, *, expect_rc):
    data = load(request)
    per_build = float(data.get('build_timeout', 600))
    timeout = max(840, int(2 * per_build + 240))
    rc = command([sys.executable, str(ROOT / 'labs/e13e14/orchestrate.py'),
                  '--request', str(request), '--out', str(dest)], log, timeout=timeout, check=False)
    require(rc == expect_rc, f'Unexpected orchestrator exit {rc} (expected {expect_rc}); see {log}')
    require((dest / 'result.json').is_file(), f'Missing result.json: {dest}')


def compose_logs(out: Path, project: str, image: str):
    env = os.environ.copy()
    env.update(E14_ROOT=str(ROOT), E14_IMAGE=image)
    with (out / 'four-services.log').open('w', encoding='utf-8') as stream:
        r = subprocess.run(['docker', 'compose', '-f', str(COMPOSE), '-p', project,
                            'logs', '--timestamps', '--no-color'], cwd=ROOT,
                           env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=40)
    require(r.returncode == 0, 'Could not collect Compose logs')


def events(logpath: Path, job: str, trace: str):
    matched = []
    for line in logpath.read_text(encoding='utf-8', errors='replace').splitlines():
        pos = line.find('{"role"')
        if pos < 0:
            continue
        try:
            event = json.loads(line[pos:])
        except json.JSONDecodeError:
            continue
        if event.get('job_id') != job:
            continue
        require(event.get('trace_id') == trace, 'Cross-service trace mismatch')
        matched.append(event)
    require(matched, f'No service events for {job}')
    return matched


def check_logs(out: Path, states: dict):
    logfile = out / 'four-services.log'
    for case in ('success', 'recovery'):
        entry = states[case]
        matched = events(logfile, entry['job_id'], entry['trace_id'])
        require(all(e.get('status') == 'SUCCEEDED' for e in matched), f'{case} log reports failure')
        require(Counter(e['role'] for e in matched) == EXPECTED_ROLES, f'{case} role counts mismatch')
    fault = states['fault']
    matched = events(logfile, fault['job_id'], fault['trace_id'])
    require(len(matched) == 1 and matched[0]['role'] == 'draft' and
            matched[0]['status'] == 'FAILED' and matched[0]['error_code'] == 'TIMEOUT',
            'Fault role/timeout log mismatch')
    return {'status': 'PASS', 'success_calls': dict(EXPECTED_ROLES),
            'recovery_calls': dict(EXPECTED_ROLES), 'fault_calls': {'draft': 1}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True, help='Existing E12-style request using /course paths')
    parser.add_argument('--out', type=Path, required=True, help='Fresh work/ subdirectory for evidence')
    parser.add_argument('--project', required=True, help='Existing Compose project; never stopped by this script')
    parser.add_argument('--image', required=True, help='Exact previously-built image tag')
    args = parser.parse_args()
    out = args.out.resolve()
    request = args.request.resolve()
    require(out.is_relative_to(ROOT / 'work') and out != ROOT / 'work', 'Output must be under work/')
    require(not out.exists(), 'Gate output already exists; preserve evidence')
    require(request.is_file() and request.is_relative_to(ROOT), 'Request file is missing/outside repository')
    out.mkdir(parents=True)
    states = {}
    try:
        (out / 'source-commit.txt').write_text(subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True), encoding='utf-8')
        (out / 'image-id.txt').write_text(subprocess.check_output(
            ['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'],
            cwd=ROOT, text=True), encoding='utf-8')
        save(out / 'health-initial.json', get_health())
        (out / 'request.sha256').write_text(f'{sha(request)}  {request}\n', encoding='utf-8')

        success = out / 'success'
        execute(request, success, out / 'success.console.log', expect_rc=0)
        states['success'] = verify_success(success)
        print('E14_FIVE_STAGE_AND_ARTIFACTS=PASS', flush=True)

        faulty = load(request)
        faulty['build_timeout'] = 0.01
        fault_request = out / 'fault.request.json'
        save(fault_request, faulty)
        fault = out / 'fault'
        execute(fault_request, fault, out / 'fault.console.log', expect_rc=1)
        states['fault'] = verify_fault(fault)
        save(out / 'health-after-fault.json', get_health())
        print('E14_TIMEOUT_AND_HEALTH_RECOVERY=PASS', flush=True)

        recovery = out / 'recovery'
        execute(request, recovery, out / 'recovery.console.log', expect_rc=0)
        states['recovery'] = verify_success(recovery)
        require(states['recovery']['job_id'] != states['fault']['job_id'] and
                states['recovery']['trace_id'] != states['fault']['trace_id'],
                'Recovery reused the failed job/trace')
        print('E14_RECOVERY_AND_ARTIFACTS=PASS', flush=True)
        save(out / 'health-final.json', get_health())
        compose_logs(out, args.project, args.image)
        states['service_logs'] = check_logs(out, states)
        print('E14_SERVICE_TRACE=PASS', flush=True)

        command([sys.executable, str(ROOT / 'labs/e13e14/scan_runtime_logs.py'), str(out)],
                out / 'secret-scan.log', timeout=180)
        print('E14_RUNTIME_SECRET_SCAN=PASS', flush=True)
        save(out / 'summary.json', {'passed': True, 'source': 'teaching fixture',
                                    'project': args.project, 'states': states})
        print('E14_MEMBER_C_GATE=PASS', flush=True)
        return 0
    except (GateError, OSError, ValueError, KeyError, AssertionError, subprocess.SubprocessError) as exc:
        save(out / 'summary.json', {'passed': False, 'states': states, 'error': str(exc)})
        print('E14_MEMBER_C_GATE=FAIL:', exc, file=sys.stderr, flush=True)
        return 1
    finally:
        if not (out / 'four-services.log').exists():
            try:
                compose_logs(out, args.project, args.image)
            except Exception:
                pass


if __name__ == '__main__':
    sys.exit(main())
