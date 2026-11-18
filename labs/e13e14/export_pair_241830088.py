"""Export verified A originals and a separately labelled classroom fixed-md adapter."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e11e12'))
from handoff import export_handoff
from handoff_a_to_b import make_handoff


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
    original = export_handoff(a.run_dir, a.repo, a.source_sha, a.image_id,
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
