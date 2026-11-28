"""Controlled patch mutation checks; real validator runs in Docker CI."""
import unittest
from test_e14_runtime import ROOT,load_module

gate=load_module(ROOT/'labs/e13e14/pair_c5_gate.py','pair_c5_gate_test')


class WrongPatch(unittest.TestCase):
    def test_replaces_only_one_dependency(self):
        good=b'--- a/Makefile\n+++ b/Makefile\n@@ -1 +1 @@\n-main.o: main.c unused.h\n+main.o: main.c unused.h config.h extra.h\n'
        self.assertEqual(good.replace(b'extra.h',b'unused.h'),gate.derive_bad_patch(good))

    def test_rejects_unrecognized_patch(self):
        for value in (b'+main.o: main.c extra.h\n',b'+other.o: config.h extra.h\n',
                      b'+main.o: config.h extra.h\n+main.o: config.h extra.h\n'):
            with self.subTest(value=value),self.assertRaises(gate.GateError):
                gate.derive_bad_patch(value)


if __name__=='__main__':
    unittest.main()
