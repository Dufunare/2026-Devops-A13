"""Pinned exchange profiles for tomlc99 E11-A and b13-level-v1 E12."""

import hashlib
import json
from pathlib import Path


PROFILE_ID = 'a13-tomlc99-release-1'
PROFILE_SHA256 = '0f2bc52c0e791b97a833c1c4a22c70d6cd72a97befc3959c578ccf5c85d40ee1'
BASE = '592fc6f3d2463a58fe7f60b8d255ed242740bec0'
TARGET = 'b2dda5513fe4a7d250493528800fe425cae459a5'

B13_ID = 'b13-level-v1'
B13_SHA256 = 'f0367b454aff9cb0a5304e3e3330b61d4bbd01c3f19069eaf5930a1664d3733b'
B13_BASE = 'cb6545b3e8eddda5bec89b12ee390ae5e930f822'
B13_TARGET = '5cfaf2014db78635b61d88b62760481834a344d5'


class ExchangeProfileError(ValueError):
    code = 'EXCHANGE_PROFILE_MISMATCH'


def require(condition, message):
    if not condition:
        raise ExchangeProfileError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_exchange_profile(request):
    if 'exchange_profile_id' not in request and 'profile_sha256' not in request:
        return None, request.get('profile'), None
    bound_id = request.get('exchange_profile_id')
    is_b13 = bound_id == B13_ID
    if is_b13:
        require(request.get('mode') == 'e12', 'b13-level-v1 requires E12')
        expected_sha, base, target = B13_SHA256, B13_BASE, B13_TARGET
    else:
        require(bound_id == PROFILE_ID and request.get('mode') == 'e11-a',
                'Expected the scoped tomlc99 E11-A profile')
        require('profile' not in request, 'The pinned exchange profile defines the runtime configuration')
        expected_sha, base, target = PROFILE_SHA256, BASE, TARGET

    require(request.get('profile_sha256') == expected_sha, 'Expected the pinned profile SHA-256')
    require(request.get('base') == base and request.get('target') == target, 'Expected the pinned C0 and C1')
    raw = (Path(__file__).with_name('exchange_profiles') / (bound_id + '.json')).read_bytes()
    require(digest(raw) == expected_sha, 'Pinned profile bytes changed')
    shared = json.loads(raw)
    flags = ' '.join(shared['effective_flags'])
    stdout = bytes.fromhex(shared['stdout_hex']).decode().removesuffix('\n')
    require(request.get('expected_output', stdout) == stdout, 'Expected output differs from the exchange profile')
    runtime = {
        'units': shared['units'],
        'config_file': shared['header_probe']['path'],
        'expected_output': stdout,
        'clean_target': shared['clean_argv'][1],
        'build_target': shared['build_argv'][1],
        'flags_allowed': [flags],
        'require_make_flags': True,
    }
    probe = shared['header_probe']
    if is_b13:
        runtime.update(
            config_after=bytes.fromhex(probe['content_hex']).decode(),
            config_mode='overwrite', header_check='output',
            expected_output_after=bytes.fromhex(probe['stdout_hex']).decode().removesuffix('\n'),
            recursive_scan=False, strict_sources=True, exec_image='draft',
        )
        # Compare the JSON values strictly (in Python, True also compares equal to 1).
        require(json.dumps(request.get('profile'), sort_keys=True) == json.dumps(runtime, sort_keys=True),
                'Runtime configuration differs from the pinned B13 profile')
    else:
        runtime.update(
            config_after=bytes.fromhex(probe['append_hex']).decode(),
            config_mode='append', header_check='rebuild', expected_output_after=stdout,
            recursive_scan=shared['recursive_scan'], strict_sources=shared['strict_sources'],
            exec_image='orchestrator',
        )
    return raw, runtime, shared


def check_snapshot(project, shared, revision=None):
    if shared['id'] == B13_ID:
        require(revision in (B13_BASE, B13_TARGET), 'Unexpected B13 snapshot commit')
        base_hash, target_hash = shared['makefile_templates']
        expected_hash = base_hash if revision == B13_BASE else target_hash
    else:
        expected_hash = shared['makefile_template_sha256']
    require(digest((project / 'Makefile').read_bytes()) == expected_hash,
            'Snapshot Makefile differs from the exchange profile')


def check_scan_flags(report, shared):
    require(report.get('flags_source') == 'make' and report.get('flags') == ' '.join(shared['effective_flags']),
            'Effective Make flags differ from the exchange profile')
