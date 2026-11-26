"""Artifact coverage tests for the independent variable-size E14 gate."""
import tempfile
import unittest
from pathlib import Path
from test_e14_runtime import ROOT, load_module

GATE = load_module(ROOT / 'labs/e13e14/real_job_gate.py', 'e14_real_job_gate_test')


class ManifestTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / 'a.json'
        self.path.write_text('{}')
        self.entry = {'uri': 'a.json', 'bytes': 2, 'sha256': GATE.sha(self.path)}

    def test_accepts_nonempty_exact_manifest_without_fixed_count(self):
        self.assertEqual(1, GATE.verify_manifest(self.root, {'artifacts': [self.entry]}))

    def test_rejects_empty_duplicate_traversal_and_wrong_size(self):
        for entries in ([], [self.entry, self.entry], [dict(self.entry, uri='../a.json')],
                        [dict(self.entry, bytes=3)], [dict(self.entry, bytes=True)]):
            with self.subTest(entries=entries), self.assertRaises(GATE.GateError):
                GATE.verify_manifest(self.root, {'artifacts': entries})

    def test_rejects_omitted_original_and_changed_content(self):
        extra = self.root / 'extra.json'
        extra.write_text('{}')
        with self.assertRaisesRegex(GATE.GateError, 'COVERAGE'):
            GATE.verify_manifest(self.root, {'artifacts': [self.entry]})
        extra.unlink()
        self.path.write_text('[]')
        with self.assertRaisesRegex(GATE.GateError, 'HASH_OR_SIZE'):
            GATE.verify_manifest(self.root, {'artifacts': [self.entry]})

    def test_rejects_symlink_even_if_not_in_manifest(self):
        (self.root / 'alias').symlink_to(self.path)
        with self.assertRaisesRegex(GATE.GateError, 'SYMLINK'):
            GATE.verify_manifest(self.root, {'artifacts': [self.entry]})
