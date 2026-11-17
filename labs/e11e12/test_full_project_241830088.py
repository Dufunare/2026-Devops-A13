import unittest

from accept_full_project_241830088 import repair_all


class WholeProjectRepairTests(unittest.TestCase):
    def test_inline_link_rule_keeps_headers_out_of_compiler_arguments(self):
        original = ('LIB = libtoml.a\nEXEC = toml_json toml_cat toml_sample\n'
                    'toml.o: toml.c\n\t$(CC) $(CFLAGS) -c -o toml.o toml.c\n'
                    '$(EXEC): $(LIB)\n')
        findings = [{'type': 'MISSING', 'target': t, 'dependency': 'toml.h'}
                    for t in ('toml.o', 'toml_json', 'toml_cat', 'toml_sample')]
        result = repair_all(original, findings)
        self.assertIn('toml.o: toml.c toml.h\n', result)
        for target in ('toml_json', 'toml_cat', 'toml_sample'):
            self.assertIn(target + ': ' + target + '.c $(LIB) toml.h\n', result)
            self.assertIn('$(LINK.c) ' + target + '.c $(LIB) $(LOADLIBES) $(LDLIBS) -o $@', result)
        self.assertNotIn('$^', result)
        self.assertIn('$(EXEC): $(LIB)\n', result)

    def test_unknown_target_is_rejected_instead_of_silently_dropping_md(self):
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_TARGET'):
            repair_all('', [{'type': 'MISSING', 'target': 'other', 'dependency': 'toml.h'}])

    def test_unsafe_dependency_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_DEPENDENCY'):
            repair_all('', [{'type': 'MISSING', 'target': 'toml_json', 'dependency': '../outside.h'}])


if __name__ == '__main__':
    unittest.main()
