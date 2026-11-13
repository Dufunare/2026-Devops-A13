"""241870063 新增测试：真实项目 profile 适配 + DRAFT 候选契约。

原则：每个断言里的预期值都在实现之前手写，不使用被测代码的输出反推。
覆盖：
  1) 目标名/源码目录/配置头/构建目标与教学样例不同时，scan 能按 profile 正确映射；
  2) 同一项目不带 profile 时必须被拒绝（UNSUPPORTED_RULE / UNSUPPORTED_PROJECT）；
  3) validate 使用 profile 的输出断言与头文件变化断言；
  4) DRAFT 候选 Dockerfile 的三条硬约束（同 tag+digest、只能新增 RUN、不能漏原指令）；
  5) 默认 profile 与课程原版行为一致（回归保护）。
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

import lab
import pipeline
from draft.autobuild import prepare_candidate

REAL_PROFILE = {
    'units': [['calc.o', 'src/calc.c'], ['util.o', 'src/util.c']],
    'config_file': 'src/config.h',
    'config_after': '#define VALUE 8\n',
    'expected_output': '7',
    'expected_output_after': '8',
    'build_target': 'tool',
    'clean_target': 'clean',
    'flags_allowed': ['-O0'],
    'recursive_scan': True,
}

MAKEFILE = (
    'CFLAGS = -O0\n'
    'tool: calc.o util.o\n'
    '\tgcc calc.o util.o -o tool\n'
    'calc.o: src/calc.c src/unused.h\n'
    '\tgcc $(CFLAGS) -c src/calc.c -o calc.o\n'
    'util.o: src/util.c\n'
    '\tgcc $(CFLAGS) -c src/util.c -o util.o\n'
    '.PHONY: clean\n'
    'clean:\n'
    '\trm -f calc.o util.o tool\n'
)


def build_project(root):
    """一个刻意"不像教学样例"的真实形状项目：源码在 src/，目标名与二进制名都不同。"""
    src = root / 'src'
    src.mkdir(parents=True)
    (src / 'config.h').write_text('#define VALUE 7\n')
    (src / 'unused.h').write_text('/* declared but never included */\n')
    (src / 'calc.c').write_text('#include <stdio.h>\n#include "config.h"\n'
                                'int util(void);\n'
                                'int main(void){printf("%d\\n",VALUE+util());return 0;}\n')
    (src / 'util.c').write_text('int util(void){return 0;}\n')
    (root / 'Makefile').write_text(MAKEFILE)
    (root / '.gitignore').write_text('*.o\ntool\n')
    for cmd in (['git', 'init', '-b', 'main'],
                ['git', 'config', 'user.name', 'RealFixture'],
                ['git', 'config', 'user.email', 'real@localhost']):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'C0 real shape'], cwd=root, check=True, capture_output=True)
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, text=True,
                          capture_output=True, check=True).stdout.strip()


class RealProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'real'
        self.sha = build_project(self.root)

    def test_scan_maps_profile_units(self):
        """预期手写：calc.o 漏声明 src/config.h；calc.o 多声明 src/unused.h；util.o 无变化。"""
        report = lab.scan(self.root, None, REAL_PROFILE)
        self.assertEqual(sorted(report['declared']), ['calc.o', 'util.o'])
        self.assertEqual(
            {(f['type'], f['target'], f['dependency']) for f in report['findings']},
            {('MISSING', 'calc.o', 'src/config.h'),
             ('REDUNDANT', 'calc.o', 'src/unused.h')})

    def test_unadapted_project_is_rejected(self):
        """不带 profile：目标映射解析失败；带 profile：快照检查通过。"""
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_RULE main.o'):
            lab.scan(self.root)
        okc, names, expected = pipeline.shape_ok(self.root, REAL_PROFILE)
        self.assertTrue(okc, (names, expected))
        okc_default, _names, _expected = pipeline.shape_ok(self.root)
        self.assertFalse(okc_default)
        logs = self.base / 'logs'
        with self.assertRaises(pipeline.Failure) as ctx:
            pipeline.snapshot(self.root, self.sha, self.base / 'snap', logs)
        self.assertEqual(ctx.exception.code, 'UNSUPPORTED_PROJECT')
        self.assertEqual(
            pipeline.snapshot(self.root, self.sha, self.base / 'snap-ok', logs, REAL_PROFILE),
            self.sha)

    def test_validate_uses_profile_expectations(self):
        """补丁后先输出 7，改 src/config.h 后输出 8；五项检查全过才算 accepted。"""
        diff, _edits = lab.patch(self.root, lab.scan(self.root, None, REAL_PROFILE))
        patchfile = self.base / 'candidate.patch'
        patchfile.write_text(diff)
        verdict = lab.validate(self.root, patchfile, self.base / 'ev', profile=REAL_PROFILE)
        self.assertTrue(verdict['accepted'], verdict)
        self.assertEqual(set(verdict['checks']),
                         {'patch_applies', 'build', 'test', 'header_change', 'no_missing'})
        self.assertTrue(all(verdict['checks'].values()), verdict['checks'])
        self.assertIn('src/config.h', (self.root / 'Makefile').read_text())

    def test_default_profile_unchanged(self):
        """回归保护：不传 profile 时仍是教学样例的预期结果。"""
        p = self.base / 'teaching'
        lab.fixture(p)
        report = lab.scan(p)
        self.assertEqual(
            {(f['type'], f['dependency']) for f in report['findings']},
            {('MISSING', 'config.h'), ('REDUNDANT', 'unused.h')})

    def test_non_strict_sources_allows_extra_c_files(self):
        """真实项目通常还有别的 .c 不参与依赖检查：strict_sources=False 时允许。"""
        root = self.base / 'extra'
        build_project(root)
        (root / 'tool_extra.c').write_text('/* unrelated translation unit */\n')
        strict_ok, names, expected = pipeline.shape_ok(root, dict(REAL_PROFILE, strict_sources=True))
        self.assertFalse(strict_ok, (names, expected))
        lax_ok, _n, _e = pipeline.shape_ok(root, dict(REAL_PROFILE, strict_sources=False))
        self.assertTrue(lax_ok)

    def test_normalized_ignores_non_unit_targets(self):
        """复检只对被 profile 纳入的目标负责：内联编译的可执行目标不算 MD 残留。"""
        findings = [{'type': 'MISSING', 'target': 'toml.o', 'dependency': 'toml.h'},
                    {'type': 'MISSING', 'target': 'toml_json', 'dependency': 'toml.h'},
                    {'type': 'REDUNDANT', 'target': 'toml.o', 'dependency': 'unused.h'}]
        got = pipeline.normalized(findings, {'units': [['toml.o', 'toml.c']]})
        self.assertEqual(got, [('MISSING', 'toml.o', 'toml.h'),
                               ('REDUNDANT', 'toml.o', 'unused.h')])

    def test_rebuild_mode_checks_recompilation(self):
        """header_check=rebuild：只要求改头文件后确实重新编译，不要求程序输出变化。

        对照组用 header_check=output 且期望输出 8：注释型改动不会改变输出，必须判失败。
        """
        prof = dict(REAL_PROFILE, config_mode='append',
                    config_after='\n/* e11e12 dependency probe */\n',
                    expected_output_after='7', header_check='rebuild')
        root = self.base / 'rebuild'
        build_project(root)
        diff, _ = lab.patch(root, lab.scan(root, None, prof))
        patchfile = self.base / 'rebuild.patch'
        patchfile.write_text(diff)
        verdict = lab.validate(root, patchfile, self.base / 'ev-rebuild', profile=prof)
        self.assertTrue(verdict['accepted'], verdict)
        self.assertTrue(verdict['checks']['header_change'])

        contrast = dict(prof, header_check='output', expected_output_after='8')
        root2 = self.base / 'rebuild-out'
        build_project(root2)
        diff2, _ = lab.patch(root2, lab.scan(root2, None, contrast))
        patchfile2 = self.base / 'rebuild-out.patch'
        patchfile2.write_text(diff2)
        verdict2 = lab.validate(root2, patchfile2, self.base / 'ev-rebuild-out', profile=contrast)
        self.assertFalse(verdict2['accepted'], verdict2)


class CandidateContractTests(unittest.TestCase):
    BROKEN = ('FROM python:3.13-slim\nWORKDIR /w\nCOPY a.c ./\nRUN make app\nCMD ["./app"]\n')

    def candidate(self, extra='RUN apt-get update\n', tag='python:3.13-slim', tail='CMD ["./app"]\n'):
        return ('FROM %s@sha256:%s\nWORKDIR /w\nCOPY a.c ./\n%sRUN make app\n%s'
                % (tag, '0' * 64, extra, tail))

    def test_accepts_digest_pin_with_added_run(self):
        """iter-01 = 把候选 FROM 的固定 digest 套在 broken 上；新增 RUN 只属于候选文件本身。"""
        merged = prepare_candidate(self.BROKEN, self.candidate())
        self.assertTrue(merged.startswith('FROM python:3.13-slim@sha256:0000'))
        self.assertIn('RUN make app', merged)
        self.assertIn('CMD ["./app"]', merged)
        self.assertNotIn('apt-get update', merged)

    def test_rejects_changed_base_tag(self):
        with self.assertRaisesRegex(ValueError, 'base image tag'):
            prepare_candidate(self.BROKEN, self.candidate(tag='python:3.12-slim'))

    def test_rejects_non_run_instruction(self):
        with self.assertRaisesRegex(ValueError, 'required project/build/runtime'):
            prepare_candidate(self.BROKEN, self.candidate(extra='ENV X=1\n'))

    def test_rejects_missing_instruction(self):
        with self.assertRaisesRegex(ValueError, 'omitted instructions|supplied no repair'):
            prepare_candidate(self.BROKEN, self.candidate(tail=''))


if __name__ == '__main__':
    unittest.main()
