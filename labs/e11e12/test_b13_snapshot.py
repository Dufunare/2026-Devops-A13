import tempfile
import unittest
from pathlib import Path

from exchange_profile import B13_BASE, B13_ID, B13_TARGET, ExchangeProfileError, check_snapshot, digest


class B13SnapshotTests(unittest.TestCase):
    def test_makefile_is_bound_to_its_own_commit(self):
        base = b'app: main.o\n'
        target = b'app: main.o helper.o\n'
        shared = {'id': B13_ID, 'makefile_templates': [digest(base), digest(target)]}
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            for revision, expected, swapped in ((B13_BASE, base, target), (B13_TARGET, target, base)):
                with self.subTest(revision=revision):
                    makefile = project / 'Makefile'
                    makefile.write_bytes(expected)
                    check_snapshot(project, shared, revision)
                    for wrong in (swapped, expected + b'# modified\n'):
                        makefile.write_bytes(wrong)
                        with self.assertRaises(ExchangeProfileError):
                            check_snapshot(project, shared, revision)

            (project / 'Makefile').write_bytes(base)
            with self.assertRaises(ExchangeProfileError):
                check_snapshot(project, shared, '0' * 40)

    def test_tomlc99_single_template(self):
        content = b'all: toml_json\n'
        shared = {'id': 'a13-tomlc99-release-1', 'makefile_template_sha256': digest(content)}
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            makefile = project / 'Makefile'
            makefile.write_bytes(content)
            check_snapshot(project, shared)
            makefile.write_bytes(content + b'\n')
            with self.assertRaises(ExchangeProfileError):
                check_snapshot(project, shared)
