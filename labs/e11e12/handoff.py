"""241830088: export immutable E11-A originals for independent B consumption.

This exporter uses only the standard library. It does not run or acknowledge
any B-side service, and it does not claim DRAFT-image reuse.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile


class HandoffError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(code + ': ' + message)


def require(condition, code, message):
    if not condition:
        raise HandoffError(code, message)


def strict_json(raw):
    def pairs(items):
        obj = {}
        for key, value in items:
            require(key not in obj, 'INVALID_JSON', 'Duplicate key: ' + key)
            obj[key] = value
        return obj

    def floating(value):
        number = float(value)
        require(math.isfinite(number), 'INVALID_JSON', 'Nonfinite number')
        return number

    def constant(value):
        raise HandoffError('INVALID_JSON', 'Non-JSON constant: ' + value)

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_float=floating,
                           parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise HandoffError('INVALID_JSON', 'Invalid UTF-8 JSON') from error
    require(isinstance(value, dict), 'INVALID_JSON', 'Expected JSON object')
    return value


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def same_json(one, two):
    canonical = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return canonical(one) == canonical(two)


def command(args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=120)
    require(result.returncode == 0, 'GIT_FAILED', result.stderr.strip())
    return result.stdout.strip()


def validate_run(run_dir, repo, source_sha, image_id, toolchain):
    run_dir, repo, toolchain = Path(run_dir).resolve(), Path(repo).resolve(), Path(toolchain).resolve()
    require(bool(re.fullmatch(r'[0-9a-f]{40}', source_sha)), 'INVALID_METADATA', 'source SHA must be complete lowercase hex')
    require(bool(re.fullmatch(r'sha256:[0-9a-f]{64}', image_id)), 'INVALID_METADATA', 'image ID must be a sha256 digest')
    require(run_dir.is_dir() and repo.is_dir(), 'INVALID_INPUT', 'Run and repository must exist')
    require(toolchain.is_file() and bool(toolchain.read_bytes()), 'INVALID_METADATA', 'Missing toolchain record')
    for filename, expected in [('student-source-commit.txt', source_sha), ('environment-image-id.txt', image_id)]:
        record = run_dir / filename
        if record.exists():
            require(record.read_text().strip() == expected, 'METADATA_MISMATCH', filename)
    result = strict_json((run_dir / 'result.json').read_bytes())
    job, trace = result.get('job_id'), result.get('trace_id')
    for identity in (job, trace):
        require(isinstance(identity, str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', identity)), 'INVALID_ID', 'Unsafe job or trace ID')
    require(result.get('schema_version') == 'e11e12-1' and result.get('status') == 'SUCCEEDED', 'UPSTREAM_FAILED', 'Expected successful integration result')
    base, target = result.get('base_commit'), result.get('target_commit')
    for revision in (base, target):
        require(isinstance(revision, str) and bool(re.fullmatch(r'[0-9a-f]{40}', revision)), 'STALE_REPORT', 'Complete project SHA required')
        require(command(['git', 'rev-parse', '--verify', revision + '^{commit}'], repo) == revision, 'STALE_REPORT', 'Project commit unavailable')
    stages = result.get('stages')
    require(isinstance(stages, list) and all(isinstance(stage, dict) for stage in stages)
            and [stage.get('name') for stage in stages] == ['full-check', 'incremental-check'],
            'INVALID_STAGES', 'Expected E11-A full-check and incremental-check')
    originals = {'result.json': (run_dir / 'result.json').read_bytes()}
    for filename in ('student-source-commit.txt', 'environment-image-id.txt', 'input-provenance.json'):
        record = run_dir / filename
        if record.exists():
            require(record.is_file() and not record.is_symlink(), 'UNSAFE_PATH', filename)
            originals[filename] = record.read_bytes()
    if 'input-provenance.json' in originals:
        provenance = strict_json(originals['input-provenance.json'])
        for field in ('data_origin', 'execution_environment'):
            if field in provenance:
                require(isinstance(provenance[field], str) and bool(provenance[field]), 'INVALID_METADATA', field)
        if 'draft_image_reused' in provenance:
            require(type(provenance['draft_image_reused']) is bool, 'INVALID_METADATA', 'draft_image_reused must be boolean')
        if 'flags' in provenance:
            require(isinstance(provenance['flags'], str), 'INVALID_METADATA', 'flags must be string')
    originals['toolchain.txt'] = toolchain.read_bytes()
    reserved = {'manifest.json', 'SHA256SUMS', 'README.md', 'project.bundle', 'toolchain.txt'}

    def reference(ref):
        require(isinstance(ref, dict), 'INVALID_ARTIFACT', 'Reference must be object')
        prefix = 'artifact://' + job + '/'
        uri = ref.get('uri')
        require(isinstance(uri, str) and uri.startswith(prefix), 'ARTIFACT_REFERENCE_MISMATCH', 'Artifact job differs')
        relative = uri[len(prefix):]
        parts = relative.split('/')
        require(relative and not any(part in ('', '.', '..', '.git') for part in parts)
                and not any(char in relative for char in ('\\', ':', '\x00'))
                and not PurePosixPath(relative).is_absolute() and relative not in reserved,
                'UNSAFE_PATH', 'Unsafe or reserved artifact path')
        path = run_dir.joinpath(*parts)
        require(path.resolve().is_relative_to(run_dir) and path.is_file()
                and not any(parent.is_symlink() for parent in [path, *path.parents] if parent != run_dir.parent),
                'UNSAFE_PATH', 'Missing, linked or escaping artifact')
        require(isinstance(ref.get('sha256'), str) and bool(re.fullmatch(r'[0-9a-f]{64}', ref['sha256'])), 'INVALID_ARTIFACT', 'Invalid SHA256')
        require(type(ref.get('bytes')) is int and ref['bytes'] >= 0, 'ARTIFACT_SIZE_MISMATCH', 'bytes must be integer')
        raw = path.read_bytes()
        require(sha(raw) == ref['sha256'], 'ARTIFACT_HASH_MISMATCH', relative)
        require(len(raw) == ref['bytes'], 'ARTIFACT_SIZE_MISMATCH', relative)
        originals[relative] = raw
        return relative

    def references(value):
        require(isinstance(value, list), 'INVALID_ARTIFACT', 'artifacts must be list')
        paths = [reference(ref) for ref in value]
        require(len(set(paths)) == len(paths), 'ARTIFACT_REFERENCE_MISMATCH', 'Duplicate reference')
        return paths

    references(result.get('artifacts'))
    envelopes = {}
    for stage, revision in zip(stages, (base, target)):
        name = stage['name']
        require(reference(stage.get('artifact')) == name + '.json', 'ARTIFACT_REFERENCE_MISMATCH', 'Wrong stage file')
        envelope = strict_json(originals[name + '.json'])
        require(envelope.get('schema_version') == 'e11e12-1', 'SCHEMA_MISMATCH', name)
        require(envelope.get('kind') == name and envelope.get('status') == 'SUCCEEDED', 'ARTIFACT_TYPE_MISMATCH', name)
        require(envelope.get('commit') == revision, 'STALE_REPORT', name)
        require(envelope.get('job_id') == job, 'JOB_ID_MISMATCH', name)
        require(envelope.get('trace_id') == trace, 'TRACE_ID_MISMATCH', name)
        references(envelope.get('artifacts'))
        envelopes[name] = envelope
    incremental = envelopes['incremental-check']
    matches = [ref for ref in incremental['artifacts'] if ref.get('uri') == f'artifact://{job}/incremental-report.json']
    require(len(matches) == 1, 'ARTIFACT_REFERENCE_MISMATCH', 'Need exactly one payload reference')
    require('incremental-report.json' in originals, 'INVALID_ARTIFACT', 'Missing payload')
    payload = strict_json(originals['incremental-report.json'])
    require(payload.get('schema_version') == 'e8e10-1', 'SCHEMA_MISMATCH', 'Payload schema')
    require(payload.get('commit') == target, 'STALE_REPORT', 'Payload commit')
    require(same_json(incremental.get('data'), payload), 'REPORT_DATA_MISMATCH', 'Envelope data and payload differ')
    findings = payload.get('findings')
    require(isinstance(findings, list) and all(isinstance(item, dict)
        and item.get('type') in ('MISSING', 'REDUNDANT')
        and isinstance(item.get('target'), str) and bool(item['target'])
        and isinstance(item.get('dependency'), str) and bool(item['dependency']) for item in findings),
        'INVALID_REPORT', 'Malformed findings')
    return run_dir, repo, toolchain, result, originals


def export_handoff(run_dir, repo, source_sha, image_id, toolchain, out):
    out = Path(out).absolute()
    require(not out.exists() and not out.is_symlink(), 'OUTPUT_EXISTS', 'Use a fresh output path')
    run_dir, repo, toolchain, result, originals = validate_run(run_dir, repo, source_sha, image_id, toolchain)
    require(not out.resolve().is_relative_to(run_dir) and not out.resolve().is_relative_to(repo), 'INVALID_OUTPUT', 'Export outside input run/repository')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='a13-handoff-', dir=out.parent) as directory:
        temporary = Path(directory)
        destination = temporary / 'export'
        destination.mkdir()
        for name, raw in originals.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        cloned = temporary / 'project.git'
        command(['git', 'clone', '--bare', '--no-hardlinks', str(repo), str(cloned)])
        for name, revision in [('base', result['base_commit']), ('target', result['target_commit'])]:
            command(['git', 'update-ref', 'refs/heads/handoff-' + name, revision], cloned)
        command(['git', 'bundle', 'create', str(destination / 'project.bundle'),
                 'refs/heads/handoff-base', 'refs/heads/handoff-target'], cloned)
        command(['git', 'bundle', 'verify', str(destination / 'project.bundle')], cloned)
        provenance = strict_json(originals['input-provenance.json']) if 'input-provenance.json' in originals else {}
        manifest = {'schema_version': 'a13-handoff-1', 'student_id': '241830088',
            'state': 'READY_FOR_DELIVERY_NOT_ACKNOWLEDGED',
            'producer_source_sha': source_sha, 'producer_environment_image_id': image_id,
            'source_run_directory': str(run_dir), 'base_commit': result['base_commit'],
            'target_commit': result['target_commit'], 'job_id': result['job_id'], 'trace_id': result['trace_id'],
            'report_contract': {'envelope': 'e11e12-1', 'payload': 'e8e10-1'},
            'data_origin': provenance.get('data_origin', 'unknown'),
            'flags': provenance.get('flags', 'unknown'),
            'execution_environment': provenance.get('execution_environment', 'unknown'),
            'draft_image_reused': provenance.get('draft_image_reused', 'unknown'),
            'original_files': {name: {'sha256': sha(raw), 'bytes': len(raw)} for name, raw in sorted(originals.items())},
            'bundle_sha256': sha((destination / 'project.bundle').read_bytes()),
            'toolchain_sha256': sha(toolchain.read_bytes()),
            'notes': ['Original report bytes and artifact identities are preserved.',
                      'Exporting does not prove B13 execution, receipt, or DRAFT image reuse.']}
        (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (destination / 'README.md').write_text(
            '# A13 independent report handoff\n\n'
            'Verify SHA256SUMS before consuming. incremental-check.json and '
            'incremental-report.json are immutable producer originals. '
            'project.bundle contains handoff-base and handoff-target; clone it '
            'into a new project directory before B-side consumption.\n\n'
            'This offline package is not a B13 acknowledgment. B-side outputs '
            'must be returned separately with their own hashes and receipt. '
            'No new API registration is implied by the preserved artifact URIs.\n', encoding='utf-8')
        entries = [sha(path.read_bytes()) + '  ' + path.relative_to(destination).as_posix()
                   for path in sorted(destination.rglob('*')) if path.is_file()]
        (destination / 'SHA256SUMS').write_text('\n'.join(entries) + '\n', encoding='utf-8')
        try:
            out.mkdir(exist_ok=False)
        except FileExistsError as error:
            raise HandoffError('OUTPUT_EXISTS', 'Output created concurrently') from error
        for child in destination.iterdir():
            shutil.move(str(child), out / child.name)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('run-dir', 'repo', 'source-sha', 'image-id', 'toolchain', 'out'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        result = export_handoff(args.run_dir, args.repo, args.source_sha, args.image_id, args.toolchain, args.out)
    except (HandoffError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'FAILED', 'error': {'code': getattr(error, 'code', 'EXPORT_FAILED'), 'message': str(error)}}))
        return 1
    print(json.dumps({'status': 'SUCCEEDED', 'job_id': result['job_id'], 'out': args.out}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
