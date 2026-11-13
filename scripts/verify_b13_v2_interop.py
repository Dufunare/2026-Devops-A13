"""Recheck the immutable B13 fixtures with A13's v2 validator."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from validate_e2_v2 import validate_report

ROOT = Path(__file__).resolve().parents[1]


def verify():
    manifest = json.loads((ROOT / 'evidence/coordination/20261113/v2-interop.json').read_bytes())
    validator_hash = hashlib.sha256((ROOT / 'scripts/validate_e2_v2.py').read_bytes()).hexdigest()
    if validator_hash != manifest['A13_fixed_validator_sha256']:
        raise ValueError('Validator changed: update the candidate and rerun mutual reading')
    results = []
    for entry in manifest['cases']:
        relative = entry['path'].split('contracts/examples/v2/', 1)[1]
        path = ROOT / 'contracts/interop/b13-1d7f4839/v2' / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry['sha256']:
            raise ValueError('Fixture changed: ' + relative)
        errors = validate_report(json.loads(path.read_bytes()))
        actual = 'REJECT' if errors else 'ACCEPT'
        if actual != entry['expected']:
            raise ValueError(relative + ': expected ' + entry['expected'] + ', got ' + actual)
        results.append({'path': entry['path'], 'sha256': digest, 'expected': entry['expected'],
                        'actual': actual, 'rejection_reasons': errors})
    assert len(results) == 19
    return {'passed': True, 'total': 19, 'accepted_valid': 2, 'rejected_invalid': 17,
            'A13_execution_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'A13_validator_sha256': validator_hash,
            'B13_fixed_commit': manifest['B13_fixed_commit'], 'files': results,
            'freeze_status': 'A13_CANDIDATE_VERIFIED_PENDING_B13_ACK'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = verify()
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    print(text, end='')
