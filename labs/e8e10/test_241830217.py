"""Independent E8, E9, E10 assertions for student 241830217's extension."""

import tempfile
import unittest
from pathlib import Path

from lab import commit, fixture, scan
from targetwise_241830217 import scan_targetwise


class Student241830217Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name) / "sample"
        fixture(self.project)

    def assert_equal_full(self, incremental):
        full = scan(self.project)
        for name in ("actual", "declared", "findings"):
            self.assertEqual(incremental[name], full[name], name)

    def test_e8_initial_baseline_and_unchanged_reuse(self):
        baseline = scan_targetwise(self.project)
        self.assertEqual(baseline["refreshed"], ["main.o", "helper.o"])
        self.assertEqual(baseline["actual"]["main.o"], ["config.h", "main.c"])
        self.assertEqual(
            {(f["type"], f["target"], f["dependency"]) for f in baseline["findings"]},
            {("MISSING", "main.o", "config.h"),
             ("REDUNDANT", "main.o", "unused.h")},
        )
        unchanged = scan_targetwise(self.project, baseline)
        self.assertEqual(unchanged["reused"], ["main.o", "helper.o"])
        self.assertEqual(unchanged["refreshed"], [])
        self.assert_equal_full(unchanged)

    def test_e8_unreferenced_header_change_does_not_refresh_any_target(self):
        baseline = scan_targetwise(self.project)
        (self.project / "unused.h").write_text("#define NOT_READ 55\n")
        commit(self.project, "E8 unrelated header")
        result = scan_targetwise(self.project, baseline)
        self.assertEqual(result["refreshed"], [])
        self.assertEqual(result["reused"], ["main.o", "helper.o"])
        self.assert_equal_full(result)

    def test_e9_main_include_refreshes_only_main_target(self):
        baseline = scan_targetwise(self.project)
        source = self.project / "main.c"
        source.write_text('#include "extra.h"\n' + source.read_text())
        commit(self.project, "E9 main include")
        result = scan_targetwise(self.project, baseline)
        self.assertEqual(result["refreshed"], ["main.o"])
        self.assertEqual(result["reused"], ["helper.o"])
        self.assertEqual(result["added"], [["MISSING", "main.o", "extra.h"]])
        self.assert_equal_full(result)

    def test_e9_transitive_include_refreshes_only_main_target(self):
        baseline = scan_targetwise(self.project)
        (self.project / "config.h").write_text('#include "extra.h"\n#define VALUE 1\n')
        (self.project / "extra.h").write_text('#include "leaf.h"\n')
        (self.project / "leaf.h").write_text('#define LEAF 8\n')
        commit(self.project, "E9 transitive include")
        result = scan_targetwise(self.project, baseline)
        self.assertEqual(result["refreshed"], ["main.o"])
        self.assertEqual(result["reused"], ["helper.o"])
        self.assertEqual(result["actual"]["main.o"],
                         ["config.h", "extra.h", "leaf.h", "main.c"])
        self.assert_equal_full(result)

    def test_e9_helper_include_refreshes_only_helper_target(self):
        baseline = scan_targetwise(self.project)
        source = self.project / "helper.c"
        source.write_text('#include "extra.h"\n' + source.read_text())
        commit(self.project, "E9 helper include")
        result = scan_targetwise(self.project, baseline)
        self.assertEqual(result["refreshed"], ["helper.o"])
        self.assertEqual(result["reused"], ["main.o"])
        self.assertEqual(result["added"], [["MISSING", "helper.o", "extra.h"]])
        self.assert_equal_full(result)

    def test_e9_declaration_changes_findings_without_rescanning(self):
        baseline = scan_targetwise(self.project)
        makefile = self.project / "Makefile"
        makefile.write_text(makefile.read_text().replace(
            "main.c unused.h", "main.c unused.h config.h"))
        commit(self.project, "E9 declaration-only update")
        result = scan_targetwise(self.project, baseline)
        self.assertEqual(result["reused"], ["main.o", "helper.o"])
        self.assertEqual(result["refreshed"], [])
        self.assertEqual(result["resolved"], [["MISSING", "main.o", "config.h"]])
        self.assertEqual(result["findings"], [
            {"type": "REDUNDANT", "target": "main.o", "dependency": "unused.h"}])
        self.assert_equal_full(result)

    def test_e9_recipe_change_refreshes_only_affected_target(self):
        baseline = scan_targetwise(self.project)
        makefile = self.project / "Makefile"
        makefile.write_text(makefile.read_text().replace(
            "gcc $(CFLAGS) -c helper.c -o helper.o",
            "gcc $(CFLAGS) -Wall -c helper.c -o helper.o"))
        commit(self.project, "E9 helper recipe change")
        result = scan_targetwise(self.project, baseline)
        self.assertEqual(result["refreshed"], ["helper.o"])
        self.assertEqual(result["reused"], ["main.o"])
        self.assert_equal_full(result)

    def test_e10_global_flags_refresh_both_targets(self):
        baseline = scan_targetwise(self.project)
        makefile = self.project / "Makefile"
        makefile.write_text(makefile.read_text().replace("-O0", "-O1"))
        commit(self.project, "E10 flags change")
        result = scan_targetwise(self.project, baseline)
        self.assertEqual(result["refreshed"], ["main.o", "helper.o"])
        self.assert_equal_full(result)

    def test_e10_comment_delimiter_change_cannot_reuse_stale_include(self):
        source = self.project / "main.c"
        source.write_text(source.read_text().replace(
            '#include "config.h"',
            '/*\n#include "extra.h"\n*/\n#include "config.h"'))
        commit(self.project, "E10 commented include")
        baseline = scan_targetwise(self.project)
        source.write_text(source.read_text().replace(
            '/*\n#include "extra.h"\n*/\n', '#include "extra.h"\n'))
        commit(self.project, "E10 uncomment include")
        result = scan_targetwise(self.project, baseline)
        self.assertEqual(result["refreshed"], ["main.o"])
        self.assertEqual(result["added"], [["MISSING", "main.o", "extra.h"]])
        self.assert_equal_full(result)

    def test_e10_deleted_source_fails_closed(self):
        baseline = scan_targetwise(self.project)
        (self.project / "helper.c").unlink()
        commit(self.project, "E10 delete helper source")
        with self.assertRaisesRegex(ValueError, "COMMAND_FAILED"):
            scan_targetwise(self.project, baseline)

    def test_e10_base_course_history_does_not_claim_targetwise_reuse(self):
        base_report = scan(self.project)
        result = scan_targetwise(self.project, base_report)
        self.assertEqual(result["reused"], [])
        self.assertEqual(result["refreshed"], ["main.o", "helper.o"])
        self.assert_equal_full(result)

    def test_e10_header_macro_change_refreshes_only_main(self):
        baseline = scan_targetwise(self.project)
        (self.project / "config.h").write_text("#define VALUE 2\n")
        commit(self.project, "E10 macro changes")
        result = scan_targetwise(self.project, baseline)
        self.assertEqual(result["refreshed"], ["main.o"])
        self.assertEqual(result["reused"], ["helper.o"])
        self.assert_equal_full(result)

    def test_e10_reuse_after_invalidation(self):
        old = scan_targetwise(self.project)
        source = self.project / "main.c"
        source.write_text('#include "extra.h"\n' + source.read_text())
        commit(self.project, "E10 first refresh")
        refreshed = scan_targetwise(self.project, old)
        self.assertEqual(refreshed["refreshed"], ["main.o"])
        next_pass = scan_targetwise(self.project, refreshed)
        self.assertEqual(next_pass["refreshed"], [])
        self.assertEqual(next_pass["reused"], ["main.o", "helper.o"])
        self.assert_equal_full(next_pass)
