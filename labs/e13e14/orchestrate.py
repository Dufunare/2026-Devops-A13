"""Run E14's four Compose services with B's optional project profile."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

# Host endpoints are configurable so an isolated pre-integration Compose project
# cannot collide with the already running member-C teaching service.
PORTS = {role: int(os.environ.get('E14_PORT_' + role.upper(), default))
         for role, default in (('buildchecker', 18081), ('echecker', 18082),
                               ('draft', 18083), ('mdfixer', 18084))}
ROOT = Path(__file__).resolve().parents[2]
# Reuse B's exact profile and project-shape contract; do not copy its rules here.
sys.path[:0] = [str(ROOT / 'labs/e11e12'), str(ROOT / 'labs/e8e10')]
from lab import resolve_profile
from pipeline import shape_ok
from contract import checked_incremental, findings_by_scope, profile_sha256, successful_draft_image
from draft_executor import check_profile, verify_receipts


def resolve_project_profile(raw):
    profile = resolve_profile(raw)
    if profile['exec_image'] == 'draft':
        check_profile(profile)
    return profile


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def container_path(path):
    return '/course/' + path.resolve().relative_to(ROOT.resolve()).as_posix()


def host_path(value):
    if not isinstance(value, str) or not value.startswith('/course/'):
        raise ValueError('Expected /course path')
    path = (ROOT / value[len('/course/'):]).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('Path escapes repository')
    return path


def command(argv, cwd, log):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(p.stdout + p.stderr, encoding='utf-8')
    if p.returncode:
        raise ValueError(f'{argv[0]} failed; inspect {log}')
    return p.stdout.strip()


def snapshot(repo, revision, target, logs, profile=None):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Use a full Git commit SHA')
    head = command(['git', 'rev-parse', '--verify', revision + '^{commit}'], repo,
                   logs / (target.name + '-resolve.log'))
    command(['git', 'clone', '--no-hardlinks', '--no-checkout', str(repo), str(target)], repo,
            logs / (target.name + '-clone.log'))
    command(['git', 'checkout', '--detach', head], target, logs / (target.name + '-checkout.log'))
    shape, actual_sources, expected_sources = shape_ok(target, profile)
    if not shape:
        raise ValueError('Unsupported project profile: expected %s, found %s' %
                         (sorted(expected_sources), sorted(actual_sources)))
    return head


def http_timeout(role, payload):
    # DRAFT runs up to two Docker builds, each with its own timeout.
    if role != 'draft':
        return 6100 if payload.get('profile', {}).get('exec_image') == 'draft' else 720
    per_build = float(payload.get('build_timeout', 600))
    if not 0 < per_build <= 3600:
        raise ValueError('DRAFT build_timeout must be in (0, 3600] seconds')
    return max(720, int(2 * per_build + 120))


def call(role, payload, evidence):
    if payload.get('profile', {}).get('exec_image') == 'draft':
        save(evidence.with_name(evidence.stem + '-request.json'), payload)
    req = urllib.request.Request(f'http://127.0.0.1:{PORTS[role]}/v1/run',
                                 data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=http_timeout(role, payload)) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors='replace')
        save(evidence, {'role': role, 'http': exc.code, 'error': body})
        raise ValueError(f'{role} HTTP {exc.code}: {body}') from exc
    save(evidence, data)
    for key in ('job_id', 'trace_id', 'profile_sha256'):
        if data.get(key) != payload.get(key):
            raise ValueError(f'{role} response {key} mismatch')
    if payload.get('draft_image_id') is not None and data.get('draft_image_id') != payload['draft_image_id']:
        raise ValueError(f'{role} response DRAFT image ID mismatch')
    if data['status'] != 'SUCCEEDED':
        raise ValueError(f'{role} did not succeed')
    return data


def execute(request, out, request_bytes=None):
    if out.exists():
        raise ValueError('Use a new output directory')
    if not out.resolve().is_relative_to((ROOT / 'work').resolve()):
        raise ValueError('Output must be inside work/')
    repo = host_path(request['repo'])
    candidate = host_path(request['candidate'])
    if not repo.resolve().is_relative_to((ROOT / 'data').resolve()) or not candidate.resolve().is_relative_to((ROOT / 'data').resolve()):
        raise ValueError('Input project and candidate must be in data/')
    profile = resolve_project_profile(request.get('profile'))
    profile_hash = profile_sha256(profile)
    candidate_hash = digest(candidate)
    out.mkdir(parents=True)
    job = 'job-' + uuid.uuid4().hex
    trace = 'trace-' + uuid.uuid4().hex
    result = {'schema_version': 'e14-compose-1', 'job_id': job, 'trace_id': trace,
              'status': 'RUNNING', 'stages': [], 'profile': profile,
              'profile_sha256': profile_hash, 'candidate_sha256': candidate_hash,
              'downstream_execution_environment': 'orchestrator',
              'downstream_container_attested': False}
    if profile['exec_image'] == 'draft' and request_bytes is not None:
        if json.loads(request_bytes) != request:
            raise ValueError('Original request bytes differ from parsed request')
        (out / 'request.json').write_bytes(request_bytes)
    else:
        save(out / 'request.json', request)
    result['request_sha256'] = digest(out / 'request.json')
    draft_image_id = None

    def payload(project, folder, **extra):
        return {'project': container_path(project), 'out': container_path(folder),
                'job_id': job, 'trace_id': trace, 'profile': profile,
                'profile_sha256': profile_hash,
                **({k: result[k] for k in ('base_commit', 'target_commit', 'request_sha256', 'candidate_sha256')}
                   if profile['exec_image'] == 'draft' else {}),
                **({'draft_image_id': draft_image_id} if draft_image_id else {}), **extra}

    def stage(name, commit, data):
        item = {'name': name, 'commit': commit, 'job_id': job, 'trace_id': trace, 'status': 'SUCCEEDED', 'data': data}
        path = out / (name + '.json')
        save(path, item)
        result['stages'].append({'name': name, 'artifact': {'uri': path.name, 'sha256': digest(path)}})

    try:
        base = out / 'base-project'
        target = out / 'target-project'
        logs = out / 'logs'
        base_sha = snapshot(repo, request['base'], base, logs, profile)
        target_sha = snapshot(repo, request['target'], target, logs, profile)
        result.update(base_commit=base_sha, target_commit=target_sha)

        drafted = call('draft', payload(target, out / 'draft-build',
                                        candidate=container_path(candidate),
                                        expected_output=request.get('expected_output', profile['expected_output']),
                                        build_timeout=request.get('build_timeout', 600)),
                       out / 'draft-response.json')
        draft_image_id = successful_draft_image(drafted)
        result['draft_image_id'] = draft_image_id
        if profile['exec_image'] == 'draft':
            result['downstream_execution_environment'] = 'image:' + draft_image_id
        stage('draft', target_sha, drafted)

        base_full = call('buildchecker', payload(base, out / 'baseline-full'), out / 'baseline-response.json')
        target_full = call('buildchecker', payload(target, out / 'target-full'), out / 'target-response.json')
        stage('full-check', base_sha, {'base': base_full, 'target': target_full})

        increment = call('echecker', payload(target, out / 'incremental', base=container_path(base),
                                            baseline_graph=container_path(out / 'baseline-full/actual-graph.json'),
                                            target_findings=container_path(out / 'target-full/findings.json'),
                                            target_commit=target_sha), out / 'incremental-response.json')
        report_path = host_path(increment['report'])
        if report_path != (out / 'incremental' / 'incremental-check.json').resolve():
            raise ValueError('Incremental report URI does not match this job output')
        checked_incremental(report_path.read_bytes(), increment['sha256'], job, trace,
                            target_sha, profile_hash, draft_image_id)
        result['report_transfer'] = {'kind': 'incremental-check',
                                     'uri': increment['report'], 'sha256': increment['sha256'],
                                     'job_id': job, 'trace_id': trace,
                                     'target_commit': target_sha,
                                     'profile_sha256': profile_hash,
                                     'draft_image_id': draft_image_id}
        stage('incremental-check', target_sha, increment)

        repair = call('mdfixer', payload(target, out / 'repair-work',
                                        report=increment['report'], report_sha256=increment['sha256'],
                                        target_commit=target_sha), out / 'repair-response.json')
        stage('repair', target_sha, repair)

        final = call('buildchecker', payload(target, out / 'final-full'), out / 'recheck-response.json')
        scope = findings_by_scope(final['result']['findings'], profile)
        result['recheck_scope'] = scope
        if scope['remaining_missing_full']:
            raise ValueError(f"Recheck has {scope['remaining_missing_full']} full-project missing dependencies")
        if profile['exec_image'] == 'draft':
            if digest(report_path) != result['report_transfer']['sha256']:
                raise ValueError('REPORT_HASH_MISMATCH: original changed after repair')
            attestation = verify_receipts(out, result, profile, str(ROOT.resolve()),
                                          result['report_transfer']['sha256'])
            save(out / 'execution-attestation.json', attestation)
            result['downstream_container_attested'] = True
        stage('recheck', target_sha, {'result': final, 'remaining_missing': 0,
                                     **scope})
        result['status'] = 'SUCCEEDED'
    except Exception as exc:
        result.update(status='FAILED', error=str(exc))
    result['artifacts'] = [{'uri': path.relative_to(out).as_posix(), 'sha256': digest(path),
                            'bytes': path.stat().st_size} for path in sorted(out.rglob('*'))
                           if path.is_file() and '.git' not in path.parts and not path.is_symlink()]
    save(out / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    from handoff import strict_json
    raw = args.request.read_bytes()
    result = execute(strict_json(raw), args.out.resolve(), request_bytes=raw)
    print(json.dumps({'status': result['status'], 'job_id': result['job_id'],
                      'stages': [x['name'] for x in result['stages']],
                      'error': result.get('error')}, ensure_ascii=False))
    return 0 if result['status'] == 'SUCCEEDED' else 1


if __name__ == '__main__':
    sys.exit(main())
