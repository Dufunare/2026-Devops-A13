"""Offline HTTP concurrency and timeout contract tests; no Docker required."""
import importlib.util
import json
import os
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mocked_service():
    lab = ModuleType('lab')
    for name in ('scan', 'patch', 'validate'):
        setattr(lab, name, lambda *a, **k: None)
    lab.resolve_profile = lambda raw=None: raw or {'exec_image': 'orchestrator'}
    draft = ModuleType('draft')
    draft.__path__ = []
    autobuild = ModuleType('draft.autobuild')
    autobuild.auto_build = lambda *a, **k: None
    checker = ModuleType('buildchecker')
    checker.__path__ = []
    fullcheck = ModuleType('buildchecker.fullcheck')
    fullcheck.full_check = lambda *a, **k: None
    modules = {'lab': lab, 'draft': draft, 'draft.autobuild': autobuild,
               'buildchecker': checker, 'buildchecker.fullcheck': fullcheck}
    with patch.dict(sys.modules, modules), patch.dict(os.environ, {'E14_ROLE': 'draft'}):
        return load_module(ROOT / 'labs/e13e14/service.py', 'e14_isolated_service_test')


class Concurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = mocked_service()

    def setUp(self):
        base = self.service

        class Handler(base.Handler):
            def log_message(self, *args):
                pass

        self.httpd = base.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.root = f'http://127.0.0.1:{self.httpd.server_port}'

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)

    def post(self, body):
        req = urllib.request.Request(self.root + '/v1/run', data=body,
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    def test_long_run_keeps_health_live_and_rejects_parallel_post(self):
        entered = threading.Event()
        release = threading.Event()

        def long_run(_):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('Test lock release timed out')
            return {'status': 'SUCCEEDED'}

        with patch.object(self.service, 'run', side_effect=long_run):
            with ThreadPoolExecutor(max_workers=1) as pool:
                task = pool.submit(self.post, b'{"job_id":"x","trace_id":"t"}')
                try:
                    self.assertTrue(entered.wait(2), 'First POST never began')
                    with urllib.request.urlopen(self.root + '/health', timeout=1) as resp:
                        self.assertEqual(200, resp.status)
                        self.assertEqual({'status': 'ok', 'role': 'draft'}, json.load(resp))
                    status, busy = self.post(b'{"job_id":"y","trace_id":"t"}')
                    self.assertEqual(409, status)
                    self.assertEqual('BUSY', busy['error_code'])
                finally:
                    release.set()
                status, data = task.result(timeout=3)
                self.assertEqual(200, status)
                self.assertEqual('SUCCEEDED', data['status'])

    def test_lock_is_released_after_exception(self):
        with patch.object(self.service, 'run', side_effect=[ValueError('synthetic failure'),
                                                            {'status': 'SUCCEEDED'}]):
            status, error = self.post(b'{"job_id":"bad","trace_id":"t"}')
            self.assertEqual(422, status)
            self.assertEqual('VALUEERROR', error['error_code'])
            # The client can receive HTTP 422 before the server executes
            # finally: RUN_LOCK.release(). A brief BUSY response is valid.
            deadline = time.monotonic() + 2
            while True:
                status, good = self.post(b'{"job_id":"good","trace_id":"t"}')
                if status != 409 or time.monotonic() >= deadline:
                    break
                time.sleep(0.01)
            self.assertEqual(200, status)
            self.assertEqual('SUCCEEDED', good['status'])


class HttpTimeoutContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orchestrator = load_module(ROOT / 'labs/e13e14/orchestrate.py', 'e14_orchestrator_test')

    def test_draft_covers_both_build_attempts(self):
        self.assertGreaterEqual(self.orchestrator.http_timeout('draft', {'build_timeout': 600}), 1320)
        self.assertEqual(720, self.orchestrator.http_timeout('draft', {'build_timeout': 0.01}))
        self.assertEqual(720, self.orchestrator.http_timeout('echecker', {}))

    def test_invalid_draft_timeout_rejected(self):
        for bad in (0, -1, 3601):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.orchestrator.http_timeout('draft', {'build_timeout': bad})

    def test_configurable_ports_match_gate_and_orchestrator(self):
        settings = {'E14_PORT_BUILDCHECKER': '18181', 'E14_PORT_ECHECKER': '18182',
                    'E14_PORT_DRAFT': '18183', 'E14_PORT_MDFIXER': '18184'}
        with patch.dict(os.environ, settings):
            orch = load_module(ROOT / 'labs/e13e14/orchestrate.py',
                               'e14_configurable_ports_orchestrator')
            gate = load_module(ROOT / 'labs/e13e14/e14_gate.py',
                               'e14_configurable_ports_gate')
        expected = dict(buildchecker=18181, echecker=18182,
                        draft=18183, mdfixer=18184)
        self.assertEqual(expected, orch.PORTS)
        self.assertEqual(expected, gate.PORTS)

    def test_default_ports_preserved(self):
        self.assertEqual({'buildchecker': 18081, 'echecker': 18082,
                          'draft': 18083, 'mdfixer': 18084}, self.orchestrator.PORTS)


if __name__ == '__main__':
    unittest.main()
