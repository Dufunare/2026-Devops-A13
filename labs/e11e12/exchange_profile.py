"""Closed profile binding for the scoped E13 A producer."""

import hashlib
import json
from pathlib import Path


PROFILE_ID = 'a13-tomlc99-release-1'
PROFILE_SHA256 = '0f2bc52c0e791b97a833c1c4a22c70d6cd72a97befc3959c578ccf5c85d40ee1'
BASE = '592fc6f3d2463a58fe7f60b8d255ed242740bec0'
TARGET = 'b2dda5513fe4a7d250493528800fe425cae459a5'


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
    require(request.get('mode') == 'e11-a' and request.get('exchange_profile_id') == PROFILE_ID,
            'This profile binding supports the scoped tomlc99 E11-A producer')
    require(request.get('profile_sha256') == PROFILE_SHA256, 'Expected the pinned profile SHA-256')
    require(request.get('base') == BASE and request.get('target') == TARGET, 'Expected the pinned C0 and C1')
    require('profile' not in request, 'The pinned exchange profile defines the runtime configuration')
    raw = (Path(__file__).with_name('exchange_profiles') / (PROFILE_ID + '.json')).read_bytes()
    require(digest(raw) == PROFILE_SHA256, 'Pinned profile bytes changed')
    shared = json.loads(raw)
    flags = ' '.join(shared['effective_flags'])
    stdout = bytes.fromhex(shared['stdout_hex']).decode().removesuffix('\n')
    require(request.get('expected_output', stdout) == stdout, 'Expected output differs from the exchange profile')
    runtime = {
        'units': shared['units'],
        'config_file': shared['header_probe']['path'],
        'config_after': bytes.fromhex(shared['header_probe']['append_hex']).decode(),
        'config_mode': 'append',
        'header_check': 'rebuild',
        'expected_output': stdout,
        'expected_output_after': stdout,
        'clean_target': shared['clean_argv'][1],
        'build_target': shared['build_argv'][1],
        'flags_allowed': [flags],
        'require_make_flags': True,
        'recursive_scan': shared['recursive_scan'],
        'strict_sources': shared['strict_sources'],
        'exec_image': 'orchestrator',
    }
    return raw, runtime, shared


def check_snapshot(project, shared):
    require(digest((project / 'Makefile').read_bytes()) == shared['makefile_template_sha256'],
            'Snapshot Makefile differs from the exchange profile')


def check_scan_flags(report, shared):
    require(report.get('flags_source') == 'make' and report.get('flags') == ' '.join(shared['effective_flags']),
            'Effective Make flags differ from the exchange profile')
