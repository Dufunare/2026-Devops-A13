"""Export verified A originals and a separately labelled classroom fixed-md adapter."""
import argparse
import hashlib
import json
import sys
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e11e12'))
from handoff import export_handoff, validate_run
from handoff_a_to_b import make_handoff


def export_project(run_dir, repo, source_sha, image_id, toolchain, out):
    shallow = subprocess.check_output(['git', 'rev-parse', '--is-shallow-repository'],
                                      cwd=repo, text=True).strip() == 'true'
    if not shallow:
        return export_handoff(run_dir, repo, source_sha, image_id, toolchain, out)
    # A Git bundle cannot represent the shallow boundary. Preserve an explicit
    # bare Git archive instead, retaining exact C0/C1 and .git/shallow metadata.
    run_dir, repo, toolchain, result, originals = validate_run(
        run_dir, repo, source_sha, image_id, toolchain)
    if out.exists() or out.resolve().is_relative_to(repo) or out.resolve().is_relative_to(run_dir):
        raise ValueError('Use a fresh output outside the inputs')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        bare = root / 'project.git'
        subprocess.run(['git', 'clone', '--quiet', '--bare', '--no-hardlinks', str(repo), str(bare)], check=True)
        # No hooks, remote credentials, absolute paths, alternates or symlinks.
        if (bare / 'objects/info/alternates').exists():
            raise ValueError('External object store cannot be exported')
        (bare / 'config').write_text('[core]\nrepositoryformatversion = 0\nbare = true\n')
        stage = root / 'export'; stage.mkdir()
        archive = stage / 'project.git.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(bare / 'refs', arcname='project.git/refs', recursive=False)
            for child in sorted(bare.rglob('*')):
                rel = child.relative_to(bare)
                if child.is_symlink():
                    raise ValueError('Unexpected Git symlink')
                if child.is_file() and (rel.parts[0] in ('objects', 'refs') or str(rel) in ('HEAD', 'config', 'shallow', 'packed-refs')):
                    tar.add(child, arcname='project.git/' + rel.as_posix(), recursive=False)
        restored = root / 'restored'; restored.mkdir()
        with tarfile.open(archive) as tar:
            for item in tar:
                dest = restored / item.name
                if item.isdir() and dest.resolve().is_relative_to(restored.resolve()):
                    dest.mkdir(parents=True, exist_ok=True)
                    continue
                if not item.isfile() or not dest.resolve().is_relative_to(restored.resolve()):
                    raise ValueError('Unsafe archive member')
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(tar.extractfile(item).read())
        project = root / 'checkout'
        subprocess.run(['git', 'clone', '--quiet', '--no-hardlinks', str(restored / 'project.git'), str(project)], check=True)
        subprocess.run(['git', 'fsck', '--no-reflogs'], cwd=project, check=True, capture_output=True)
        for revision in (result['base_commit'], result['target_commit']):
            actual = subprocess.check_output(['git', 'rev-parse', revision + '^{commit}'], cwd=project, text=True).strip()
            if actual != revision:
                raise ValueError('Project commit changed during restore')
            subprocess.run(['git', 'checkout', '--quiet', '--detach', revision], cwd=project, check=True)
        for name, raw in originals.items():
            p = stage / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
        manifest = {'job_id': result['job_id'], 'trace_id': result['trace_id'],
                    'target_commit': result['target_commit'], 'base_commit': result['base_commit'],
                    'producer_source_sha': source_sha, 'source_restore_format': 'bare-git-tar-with-shallow-boundary',
                    'shallow_history': True, 'fresh_restore_and_exact_commits_verified': True}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (stage / 'README.md').write_text(
            '# Exact project recovery\n\nThis source has a declared shallow boundary. '
            'It is a bare Git archive, NOT a standalone Git bundle.\n\n'
            'In a fresh directory: `tar -xzf project.git.tar.gz`, then '
            '`git clone --no-hardlinks project.git project`, then '
            '`git -C project checkout --detach ' + result['target_commit'] + '`.\n'
            'Keep the shallow metadata; history above that boundary is not included. '
            'Both exact C0/C1 checkouts and git fsck passed independently.\n')
        shutil.copytree(stage, out)
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--source-sha', required=True)
    p.add_argument('--image-id', required=True)
    p.add_argument('--toolchain', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        p.error('Use a fresh output directory')
    # Both checks finish before publishing any output. The strict exporter also
    # verifies payload/envelope equality, all refs and recoverable project SHAs.
    result = json.loads((a.run_dir / 'result.json').read_text())
    fixed = make_handoff(a.run_dir / 'result.json', result['target_commit'])
    original = export_project(a.run_dir, a.repo, a.source_sha, a.image_id,
                              a.toolchain, a.out / 'originals')
    fixed_path = a.out / 'fixed-md.json'
    fixed_path.write_text(json.dumps(fixed, ensure_ascii=False, indent=2) + '\n')
    manifest = {'status': 'READY_FOR_RECEIVER_PREFLIGHT_NOT_B13_ACCEPTED',
                'original_contract': 'incremental-check', 'adapter_contract': 'fixed-md',
                'source_job_id': original['job_id'], 'source_trace_id': original['trace_id'],
                'target_commit': original['target_commit'], 'producer_source_sha': a.source_sha,
                'fixed_report_sha256': hashlib.sha256(fixed_path.read_bytes()).hexdigest(),
                'note': 'Receiver must choose its agreed contract; original bytes stay in originals.'}
    (a.out / 'handoff.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    rows = {x.relative_to(a.out).as_posix(): {'bytes': x.stat().st_size,
            'sha256': hashlib.sha256(x.read_bytes()).hexdigest()}
            for x in sorted(a.out.rglob('*')) if x.is_file()}
    (a.out / 'SHA256.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
