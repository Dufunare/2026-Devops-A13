import json, tempfile, unittest
from pathlib import Path
from lab import fixture,scan,patch,commit

class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'sample';fixture(self.p)

    def test_independent_known_edges(self):
        r=scan(self.p)
        self.assertEqual(r['actual']['main.o'],['config.h','main.c'])
        self.assertEqual({(f['type'],f['dependency']) for f in r['findings']},{('MISSING','config.h'),('REDUNDANT','unused.h')})

    def test_unchanged_reuses_both_targets(self):
        r=scan(self.p,scan(self.p));self.assertEqual(r['reused'],['main.o','helper.o']);self.assertEqual(r['refreshed'],[])

    def test_include_added_invalidates_cache(self):
        old=scan(self.p)
        (self.p/'main.c').write_text('#include "extra.h"\n'+(self.p/'main.c').read_text());commit(self.p,'new include')
        r=scan(self.p,old)
        self.assertIn(['MISSING','main.o','extra.h'],r['added']);self.assertEqual(len(r['refreshed']),2)

    def test_patch_preserves_redundant_dependency(self):
        r=scan(self.p);diff,plan=patch(self.p,r)
        self.assertIn('+main.o: main.c unused.h config.h',diff)
        self.assertNotIn('-\tgcc',diff)
        self.assertNotIn('config.h',(self.p/'Makefile').read_text())

    def test_old_report_rejected(self):
        r=scan(self.p);r['commit']='0'*40
        with self.assertRaisesRegex(ValueError,'STALE_REPORT'):patch(self.p,r)

    def test_unsafe_dependency_rejected(self):
        r=scan(self.p);r['findings']=[{'type':'MISSING','target':'main.o','dependency':'../outside.h'}]
        with self.assertRaisesRegex(ValueError,'UNSAFE_PATH'):patch(self.p,r)

    def test_unsupported_configuration_rejected(self):
        (self.p/'Makefile').write_text((self.p/'Makefile').read_text().replace('-O0','-include unknown.h'))
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_FLAGS'):scan(self.p)

# Student 241830088: independent expectations, not copied course examples.
"""241830088: independent edge expectations for the restricted A profile.

These six inputs extend the seven course tests; they do not implement the
paper's full syscall-graph update algorithm.
"""
import tempfile
import unittest
from pathlib import Path

from lab import commit, fixture, scan


class Student241830088Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name) / "sample"
        fixture(self.project)

    def edges(self, report):
        return {(f["type"], f["target"], f["dependency"])
                for f in report["findings"]}

    def assert_matches_full(self, report):
        full = scan(self.project)
        for key in ("actual", "declared", "findings"):
            self.assertEqual(report[key], full[key], key)

    def test_e8_two_hop_header_addition_refreshes_history(self):
        old = scan(self.project)
        (self.project / "config.h").write_text('#include "extra.h"\n#define VALUE 1\n')
        (self.project / "extra.h").write_text('#include "leaf.h"\n')
        (self.project / "leaf.h").write_text('#define LEAF 3\n')
        commit(self.project, "student E8: two-hop headers")
        result = scan(self.project, old)
        self.assertEqual(result["actual"], {
            "main.o": ["config.h", "extra.h", "leaf.h", "main.c"],
            "helper.o": ["helper.c"],
        })
        self.assertEqual(self.edges(result), {
            ("MISSING", "main.o", "config.h"),
            ("MISSING", "main.o", "extra.h"),
            ("MISSING", "main.o", "leaf.h"),
            ("REDUNDANT", "main.o", "unused.h"),
        })
        self.assertEqual(result["refreshed"], ["main.o", "helper.o"])
        self.assert_matches_full(result)

    def test_e8_removing_include_resolves_old_missing_edge(self):
        old = scan(self.project)
        source = self.project / "main.c"
        source.write_text(source.read_text().replace('#include "config.h"\n', "").replace("VALUE", "1"))
        commit(self.project, "student E8: remove header read")
        result = scan(self.project, old)
        self.assertEqual(result["actual"]["main.o"], ["main.c"])
        self.assertEqual(result["resolved"], [["MISSING", "main.o", "config.h"]])
        self.assertEqual(self.edges(result), {("REDUNDANT", "main.o", "unused.h")})
        self.assert_matches_full(result)

    def test_e9_partial_declaration_repair_keeps_other_missing_edge(self):
        source = self.project / "main.c"
        source.write_text('#include "extra.h"\n' + source.read_text())
        commit(self.project, "student E9: add extra include")
        old = scan(self.project)
        makefile = self.project / "Makefile"
        makefile.write_text(makefile.read_text().replace(
            "main.c unused.h", "main.c unused.h config.h"))
        commit(self.project, "student E9: repair config only")
        result = scan(self.project, old)
        self.assertEqual(result["reused"], ["main.o", "helper.o"])
        self.assertEqual(result["refreshed"], [])
        self.assertEqual(result["resolved"], [["MISSING", "main.o", "config.h"]])
        self.assertEqual(self.edges(result), {
            ("MISSING", "main.o", "extra.h"),
            ("REDUNDANT", "main.o", "unused.h"),
        })
        self.assert_matches_full(result)

    def test_e9_supported_define_activates_conditional_include(self):
        source = self.project / "main.c"
        source.write_text('#ifdef MODE\n#include "extra.h"\n#endif\n' + source.read_text())
        commit(self.project, "student E9: conditional input")
        old = scan(self.project)
        self.assertNotIn("extra.h", old["actual"]["main.o"])
        makefile = self.project / "Makefile"
        makefile.write_text(makefile.read_text().replace("-O0", "-O0 -DMODE=1"))
        commit(self.project, "student E9: enable MODE")
        result = scan(self.project, old)
        self.assertEqual(result["actual"]["main.o"], ["config.h", "extra.h", "main.c"])
        self.assertEqual(result["added"], [["MISSING", "main.o", "extra.h"]])
        self.assertEqual(result["refreshed"], ["main.o", "helper.o"])
        self.assert_matches_full(result)

    def test_e10_equal_finding_counts_do_not_hide_changed_edges(self):
        old = scan(self.project)
        source = self.project / "main.c"
        source.write_text(source.read_text().replace('"config.h"', '"extra.h"').replace("VALUE", "EXTRA"))
        commit(self.project, "student E10: same counts different dependency")
        result = scan(self.project, old)
        self.assertEqual(len(result["findings"]), len(old["findings"]))
        self.assertNotEqual(result["findings"], old["findings"])
        self.assertEqual(result["actual"]["main.o"], ["extra.h", "main.c"])
        self.assertEqual(result["added"], [["MISSING", "main.o", "extra.h"]])
        self.assertEqual(result["resolved"], [["MISSING", "main.o", "config.h"]])
        self.assert_matches_full(result)

    def test_e10_deleted_source_fails_instead_of_reusing_cache(self):
        old = scan(self.project)
        (self.project / "helper.c").unlink()
        commit(self.project, "student E10: delete required source")
        for history in (old, None):
            with self.assertRaisesRegex(ValueError, "COMMAND_FAILED"):
                scan(self.project, history)



# Student 241870063: independent expectations for the restricted A profile.
class Student241870063Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'sample';fixture(self.p)

    def _edges(self,report):
        return {(f['type'],f['target'],f['dependency']) for f in report['findings']}

    def test_e8_body_change_reuses_history(self):
        old=scan(self.p)
        (self.p/'helper.c').write_text('int helper(void){return 7;}\n')
        commit(self.p,'student E8: helper body change')
        r=scan(self.p,old)
        self.assertEqual(r['actual'],old['actual'])
        self.assertEqual(r['reused'],['main.o','helper.o'])
        self.assertEqual(r['refreshed'],[])
        self.assertEqual(self._edges(r),{('MISSING','main.o','config.h'),('REDUNDANT','main.o','unused.h')})

    def test_e9_actually_using_unused_header_clears_redundant(self):
        old=scan(self.p)
        (self.p/'main.c').write_text('#include "unused.h"\n'+(self.p/'main.c').read_text())
        commit(self.p,'student E9: use unused header')
        r=scan(self.p,old)
        self.assertEqual(r['actual']['main.o'],['config.h','main.c','unused.h'])
        self.assertEqual(set(r['refreshed']),{'main.o','helper.o'})
        self.assertEqual(r['resolved'],[['REDUNDANT','main.o','unused.h']])
        self.assertEqual(self._edges(r),{('MISSING','main.o','config.h')})

    def test_e10_new_flag_signature_refreshes_and_matches_full(self):
        old=scan(self.p)
        makefile=self.p/'Makefile'
        makefile.write_text(makefile.read_text().replace('CFLAGS = -O0','CFLAGS = -O0 -DMODE=1'))
        commit(self.p,'student E10: add MODE flag')
        for _ in range(5):
            inc=scan(self.p,old); full=scan(self.p)
            for key in ('actual','declared','findings'):
                self.assertEqual(inc[key],full[key],key)
            self.assertEqual(inc['reused'],[])
            self.assertEqual(set(inc['refreshed']),{'main.o','helper.o'})

# 241830217: independent target-wise tests loaded by teaching quality gate.
from test_241830217 import Student241830217Tests

if __name__=='__main__':unittest.main()
