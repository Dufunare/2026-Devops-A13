"""Independent E14 draft-image job gate, without fixture-specific artifact counts.

Run only against an already-running, isolated Compose project. No container
creation or deletion here; the orchestrator invokes the restricted DRAFT broker.
Requires the expected input hashes. This verifies one successful job, not
bilateral acceptance or a real-project fault/recovery campaign.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from e14_gate import (ROOT, STAGES, GateError, require, save, load, sha,
                      get_health, service_containers, verify_continuity, compose_logs)
from orchestrate import host_path, resolve_project_profile
from contract import checked_incremental, successful_draft_image, profile_sha256
from draft_executor import identity, verify_receipts


def verify_manifest(job, result):
    job = Path(job).resolve()
    entries = result.get('artifacts')
    require(isinstance(entries, list) and bool(entries), 'ARTIFACT_MANIFEST_EMPTY')
    seen = set()
    for item in entries:
        require(isinstance(item, dict), 'ARTIFACT_RECORD_INVALID')
        rel = item.get('uri')
        require(isinstance(rel, str) and bool(rel) and
                all(p not in ('', '.', '..', '.git') for p in rel.split('/')),
                'ARTIFACT_PATH_INVALID')
        path = job / rel
        require(rel not in seen and rel != 'result.json' and path.resolve() == path
                and path.is_file(), 'ARTIFACT_DUPLICATE_OR_MISSING')
        require(type(item.get('bytes')) is int and item['bytes'] == path.stat().st_size
                and item.get('sha256') == sha(path), 'ARTIFACT_HASH_OR_SIZE_MISMATCH')
        seen.add(rel)
    actual = set()
    for path in job.rglob('*'):
        rel = path.relative_to(job)
        if '.git' in rel.parts:
            continue
        require(not path.is_symlink(), 'ARTIFACT_SYMLINK_REJECTED')
        if path.is_file() and rel.as_posix() != 'result.json':
            actual.add(rel.as_posix())
    require(seen == actual, 'ARTIFACT_MANIFEST_COVERAGE_MISMATCH')
    return len(seen)


def verify_result(job, expected_request_sha, expected_candidate_sha):
    job = Path(job).resolve()
    r = load(job / 'result.json')
    require(r.get('schema_version') == 'e14-compose-1' and r.get('status') == 'SUCCEEDED',
            'E14_REAL_JOB_FAILED')
    meta = identity(r)
    request = load(job / 'request.json')
    profile = resolve_project_profile(request.get('profile'))
    require(profile['exec_image'] == 'draft' and profile == r.get('profile')
            and profile_sha256(profile) == meta['profile_sha256'], 'PROFILE_MISMATCH')
    require(sha(job / 'request.json') == expected_request_sha == meta['request_sha256']
            and sha(host_path(request['candidate'])) == expected_candidate_sha == meta['candidate_sha256'],
            'INPUT_HASH_MISMATCH')
    require((request['base'], request['target']) == (meta['base_commit'], meta['target_commit']),
            'COMMIT_MISMATCH')
    require(r.get('downstream_container_attested') is True
            and r.get('downstream_execution_environment') == 'image:' + meta['draft_image_id'],
            'DRAFT_EXECUTION_NOT_ATTESTED')
    count = verify_manifest(job, r)
    require([s['name'] for s in r['stages']] == STAGES, 'STAGE_ORDER_MISMATCH')
    stages = {}
    for entry in r['stages']:
        name = entry['name']
        artifact = entry['artifact']
        path = job / (name + '.json')
        require(artifact['uri'] == path.name and artifact['sha256'] == sha(path),
                'STAGE_HASH_MISMATCH')
        stage = load(path)
        require(stage['name'] == name and stage['status'] == 'SUCCEEDED'
                and stage['job_id'] == meta['job_id'] and stage['trace_id'] == meta['trace_id']
                and stage['commit'] == meta['base_commit' if name == 'full-check' else 'target_commit']
                and stage['execution_identity'] == meta, 'STAGE_IDENTITY_MISMATCH')
        stages[name] = stage['data']
    responses = {}
    job_uri = '/course/' + job.relative_to(ROOT).as_posix()
    for name, project, folder in (
            ('draft', 'target-project', 'draft-build'),
            ('baseline', 'base-project', 'baseline-full'),
            ('target', 'target-project', 'target-full'),
            ('incremental', 'target-project', 'incremental'),
            ('repair', 'target-project', 'repair-work'),
            ('recheck', 'target-project', 'final-full')):
        payload = load(job / (name + '-response-request.json'))
        answer = load(job / (name + '-response.json'))
        require(payload['project'] == job_uri + '/' + project
                and payload['out'] == job_uri + '/' + folder
                and payload['profile'] == profile, 'HTTP_REQUEST_LAYOUT_MISMATCH')
        for key, value in meta.items():
            if key != 'draft_image_id' or name != 'draft':
                require(payload.get(key) == value, 'HTTP_REQUEST_IDENTITY_MISMATCH: ' + key)
        require(answer['status'] == 'SUCCEEDED'
                and all(answer.get(key) == meta[key] for key in
                        ('job_id', 'trace_id', 'profile_sha256', 'draft_image_id')),
                'HTTP_RESPONSE_IDENTITY_MISMATCH')
        responses[name] = answer
    require(stages['draft'] == responses['draft']
            and stages['full-check'] == {'base': responses['baseline'], 'target': responses['target']}
            and stages['incremental-check'] == responses['incremental']
            and stages['repair'] == responses['repair']
            and stages['recheck']['result'] == responses['recheck'],
            'STAGE_RESPONSE_MISMATCH')
    draft = load(job / 'draft-build/result.json')
    require(draft == responses['draft']['result'] and
            successful_draft_image(responses['draft']) == meta['draft_image_id']
            and draft['candidate_sha256'] == expected_candidate_sha
            and draft['verification']['exit_code'] == 0
            and draft['verification']['output_matches'] is True,
            'DRAFT_ORIGINAL_MISMATCH')
    attempt = next(x for x in draft['attempts'] if x.get('build_exit_code') == 0)
    inspected = load(job / 'draft-build' / ('iter-%02d' % attempt['iteration']) / 'image-inspect.json')
    require(isinstance(inspected, list) and len(inspected) == 1
            and inspected[0]['Id'] == meta['draft_image_id'], 'DRAFT_IMAGE_INSPECT_MISMATCH')
    report = job / 'incremental/incremental-check.json'
    report_sha = sha(report)
    inc = responses['incremental']
    require(inc['report'] == job_uri + '/incremental/incremental-check.json'
            and inc['sha256'] == report_sha
            and r['report_transfer']['sha256'] == report_sha, 'REPORT_TRANSFER_MISMATCH')
    envelope = checked_incremental(report.read_bytes(), report_sha, meta['job_id'],
                                   meta['trace_id'], meta['target_commit'],
                                   meta['profile_sha256'], meta['draft_image_id'])
    require(envelope['data'] == load(job / 'incremental/target-scan.json'),
            'REPORT_SCAN_MISMATCH')
    repair = responses['repair']
    require(repair['input_report']['sha256'] == report_sha
            and repair['input_report']['uri'] == inc['report']
            and repair['patch'] == job_uri + '/repair-work/candidate.patch'
            and repair['sha256'] == sha(job / 'repair-work/candidate.patch')
            and repair['validation'] == load(job / 'repair-work/validation/validation.json')
            and repair['validation']['accepted'] is True
            and repair['validation']['executed_in'] == 'image:' + meta['draft_image_id'],
            'REPAIR_ORIGINAL_MISMATCH')
    for name, folder in (('baseline', 'baseline-full'), ('target', 'target-full'),
                         ('recheck', 'final-full')):
        require(responses[name]['result'] == load(job / folder / 'findings.json')
                and responses[name]['result']['status'] == 'SUCCEEDED',
                'FULL_CHECK_ORIGINAL_MISMATCH')
    findings = responses['recheck']['result']['findings']
    require(isinstance(findings, list) and not any(f['type'] == 'MISSING' for f in findings)
            and r['recheck_scope']['remaining_missing_full'] == 0,
            'FULL_PROJECT_MISSING_REMAINS')
    attested = verify_receipts(job, r, profile, str(ROOT.resolve()), report_sha)
    require(attested == load(job / 'execution-attestation.json'), 'ATTESTATION_ORIGINAL_MISMATCH')
    return {'status': 'PASS', **meta, 'artifacts_verified': count,
            'stages': STAGES, 'downstream_containers_verified': len(attested['verified_tags']),
            'remaining_missing_full': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request', type=Path, required=True)
    p.add_argument('--request-sha256', required=True)
    p.add_argument('--candidate-sha256', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--project', required=True)
    p.add_argument('--image', required=True)
    a = p.parse_args()
    out = a.out.resolve()
    require(out.is_relative_to(ROOT / 'work') and out != ROOT / 'work'
            and not out.exists(), 'Use a fresh work/ output directory')
    out.mkdir(parents=True)
    try:
        require(sha(a.request) == a.request_sha256, 'ORIGINAL_REQUEST_HASH_MISMATCH')
        request = load(a.request)
        require(sha(host_path(request['candidate'])) == a.candidate_sha256,
                'ORIGINAL_CANDIDATE_HASH_MISMATCH')
        require(resolve_project_profile(request.get('profile'))['exec_image'] == 'draft',
                'DRAFT_PROFILE_REQUIRED')
        save(out / 'health-before.json', get_health())
        before = service_containers(out, a.project, a.image, 'before')
        with (out / 'orchestrator.log').open('w', encoding='utf-8') as stream:
            proc = subprocess.run([sys.executable, str(ROOT / 'labs/e13e14/orchestrate.py'),
                '--request', str(a.request.resolve()), '--out', str(out / 'job')],
                cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=12000)
        require(proc.returncode == 0, 'REAL_JOB_EXECUTION_FAILED: see job/result.json')
        result = verify_result(out / 'job', a.request_sha256, a.candidate_sha256)
        save(out / 'health-after.json', get_health())
        after = service_containers(out, a.project, a.image, 'after')
        result['service_continuity'] = verify_continuity(before, after, 'before', 'after')
        compose_logs(out, a.project, a.image)
        save(out / 'summary.json', result)
        print('E14_DRAFT_EXECUTION_GATE=PASS', flush=True)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (GateError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        save(out / 'summary.json', {'status': 'FAIL', 'error': str(exc)})
        try:
            compose_logs(out, a.project, a.image)
        except Exception as log_exc:
            print('DIAGNOSTIC_LOG_ERROR:', log_exc, file=sys.stderr)
        print('E14_DRAFT_EXECUTION_GATE=FAIL:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
