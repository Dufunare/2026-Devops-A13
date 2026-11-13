"""E8-E10 teaching profile: explicit C/Make rules, GCC dependency observation.

新增：可选 project profile。默认行为与课程原版完全一致；
传入 profile 后可支持不同的目标名、源目录、配置头文件、构建目标与输出断言。
"""
import argparse, csv, difflib, json, re, shutil, subprocess, time
from pathlib import Path

# ---------------------------------------------------------------------------
# Project profile
# ---------------------------------------------------------------------------
DEFAULT_PROFILE = {
    'units': [['main.o', 'main.c'], ['helper.o', 'helper.c']],
    'config_file': 'config.h',
    'config_after': '#define VALUE 2\n',
    'config_mode': 'overwrite',
    'header_check': 'output',
    'expected_output': '1',
    'expected_output_after': '2',
    'build_target': 'app',
    'clean_target': 'clean',
    'flags_allowed': ['-O0', '-O1', '-O0 -DMODE=1'],
    'recursive_scan': False,
    'strict_sources': True,
}

PROFILE_KEYS = set(DEFAULT_PROFILE)


def resolve_profile(raw=None):
    """把调用方传入的 profile 合并到默认值上，并做形状校验。

    未传（None）时返回默认 profile，保证课程原版行为不变。
    """
    prof = {k: (v[:] if isinstance(v, list) else v) for k, v in DEFAULT_PROFILE.items()}
    if raw is None:
        return prof
    if not isinstance(raw, dict):
        raise ValueError('UNSUPPORTED_PROFILE not an object')
    unknown = set(raw) - PROFILE_KEYS
    if unknown:
        raise ValueError('UNSUPPORTED_PROFILE unknown keys ' + ','.join(sorted(unknown)))
    for key, value in raw.items():
        prof[key] = value
    units = prof['units']
    if not units or not all(isinstance(u, list) and len(u) == 2 and all(isinstance(x, str) and x for x in u)
                            for u in units):
        raise ValueError('UNSUPPORTED_PROFILE units must be [[target, source], ...]')
    for key in ('config_file', 'config_after', 'expected_output', 'expected_output_after',
                'build_target', 'clean_target'):
        if not isinstance(prof[key], str) or not prof[key]:
            raise ValueError('UNSUPPORTED_PROFILE ' + key)
    if not isinstance(prof['flags_allowed'], list) or not prof['flags_allowed']:
        raise ValueError('UNSUPPORTED_PROFILE flags_allowed')
    if not isinstance(prof['recursive_scan'], bool):
        raise ValueError('UNSUPPORTED_PROFILE recursive_scan')
    if not isinstance(prof['strict_sources'], bool):
        raise ValueError('UNSUPPORTED_PROFILE strict_sources')
    if prof['config_mode'] not in ('overwrite', 'append'):
        raise ValueError('UNSUPPORTED_PROFILE config_mode')
    if prof['header_check'] not in ('output', 'rebuild'):
        raise ValueError('UNSUPPORTED_PROFILE header_check')
    return prof


def default_profile():
    return resolve_profile(None)


def _source_files(p, prof):
    """收集参与变化指纹的 C/H 源文件。

    默认只看项目根目录（与课程原版一致）；recursive_scan=True 时递归，
    用于源文件放在 src/ 等子目录的真实项目。
    """
    if prof['recursive_scan']:
        items = [x for pat in ('*.c', '*.h') for x in p.rglob(pat)]
        items = [x for x in items if '.git' not in x.parts and '__pycache__' not in x.parts]
        return {x.relative_to(p).as_posix(): x.read_text() for x in sorted(items)}
    return {x.name: x.read_text() for x in sorted(p.glob('*')) if x.suffix in ['.c', '.h']}


# ---------------------------------------------------------------------------
# 原课程实现
# ---------------------------------------------------------------------------
def save(p, data):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=30)
    if p.returncode: raise ValueError('COMMAND_FAILED ' + repr(cmd) + '\n' + p.stdout + p.stderr)
    return p.stdout


def fixture(p, style='direct'):
    p.mkdir(parents=True)
    (p / 'main.c').write_text('#include <stdio.h>\n#include "config.h"\nint helper(void);\nint main(void){printf("%d\\n",VALUE+helper());return 0;}\n')
    (p / 'helper.c').write_text('int helper(void){return 0;}\n')
    (p / 'config.h').write_text('#define VALUE 1\n')
    (p / 'extra.h').write_text('#define EXTRA 0\n')
    (p / 'unused.h').write_text('/* unused */\n')
    prefix = {'direct': '', 'macro': 'DEPS = main.c unused.h\n', 'mixed': 'HEADERS = unused.h\n'}[style]
    deps = {'direct': 'main.c unused.h', 'macro': '$(DEPS)', 'mixed': 'main.c $(HEADERS)'}[style]
    (p / 'Makefile').write_text(prefix + 'CFLAGS = -O0\napp: main.o helper.o\n\tgcc main.o helper.o -o app\nmain.o: ' + deps + '\n\tgcc $(CFLAGS) -c main.c -o main.o\nhelper.o: helper.c\n\tgcc $(CFLAGS) -c helper.c -o helper.o\n.PHONY: clean\nclean:\n\trm -f main.o helper.o app\n')
    run(['git', 'init', '-b', 'main'], p)
    run(['git', 'config', 'user.name', 'TeachingFixture'], p)
    run(['git', 'config', 'user.email', 'fixture@localhost'], p)
    (p / '.gitignore').write_text('*.o\napp\n')
    commit(p, 'C0 baseline')


def commit(p, msg):
    run(['git', 'add', '.'], p); run(['git', 'commit', '-m', msg], p)
    return run(['git', 'rev-parse', 'HEAD'], p).strip()


def declarations(p, profile=None):
    prof = resolve_profile(profile)
    text = (p / 'Makefile').read_text()
    variables = dict(re.findall(r'^(\w+)\s*=\s*(.*)$', text, re.M))
    graph = {}
    for target, _source in prof['units']:
        m = re.search(r'^' + re.escape(target) + r': ([^\n]*)$', text, re.M)
        if not m: raise ValueError('UNSUPPORTED_RULE ' + target)
        dep = m[1]
        for _ in range(8):
            dep = re.sub(r'\$\((\w+)\)', lambda x: variables.get(x[1], x[0]), dep)
        if '$' in dep or '%' in dep or '|' in dep: raise ValueError('UNSUPPORTED_DECLARATION')
        graph[target] = sorted(set(dep.split()))
    return graph, variables.get('CFLAGS', '')


def scan(p, old=None, profile=None):
    prof = resolve_profile(profile)
    start = time.perf_counter(); declared, flags = declarations(p, prof)
    if flags not in prof['flags_allowed']: raise ValueError('UNSUPPORTED_FLAGS')
    # Conservative invalidation: all local preprocessor lines, source set and recipes.
    files = _source_files(p, prof)
    key = {'directives': {n: [l for l in t.splitlines() if l.lstrip().startswith('#')] for n, t in files.items()},
           'recipes': [l for l in (p / 'Makefile').read_text().splitlines() if l.startswith('\t')],
           'flags': flags, 'compiler': run(['gcc', '--version'], p).splitlines()[0]}
    actual = {}; refreshed = []; reused = []
    for target, source in prof['units']:
        if old and old['key'] == key and target in old['actual']:
            actual[target] = old['actual'][target]; reused.append(target)
        else:
            output = run(['gcc', *flags.split(), '-MM', '-MT', target, source], p)
            actual[target] = sorted(set(output.replace('\\\n', ' ').split(':', 1)[1].split()))
            refreshed.append(target)
    findings = []
    for t in actual:
        for kind, edges in [('MISSING', set(actual[t]) - set(declared[t])), ('REDUNDANT', set(declared[t]) - set(actual[t]))]:
            findings.extend({'type': kind, 'target': t, 'dependency': d} for d in sorted(edges))
    current = {(f['type'], f['target'], f['dependency']) for f in findings}
    previous = {(f['type'], f['target'], f['dependency']) for f in old['findings']} if old else set()
    return {'schema_version': 'e8e10-1', 'profile': 'GCC_LOCAL_HEADERS_EXPLICIT_MAKE',
            'commit': run(['git', 'rev-parse', 'HEAD'], p).strip(), 'key': key, 'actual': actual, 'declared': declared,
            'findings': findings, 'added': [list(x) for x in sorted(current - previous)],
            'resolved': [list(x) for x in sorted(previous - current)], 'refreshed': refreshed, 'reused': reused,
            'elapsed_s': time.perf_counter() - start}


def patch(p, report):
    if report['commit'] != run(['git', 'rev-parse', 'HEAD'], p).strip(): raise ValueError('STALE_REPORT')
    original = (p / 'Makefile').read_text(); changed = original; edits = []
    for f in report['findings']:
        if f['type'] != 'MISSING': continue
        t, d = f['target'], f['dependency']
        if not re.fullmatch(r'[\w./-]+', d) or '..' in Path(d).parts or Path(d).is_absolute(): raise ValueError('UNSAFE_PATH')
        if not (p / d).is_file(): raise ValueError('MISSING_INPUT')
        m = re.search(r'^' + re.escape(t) + r': (.*)$', changed, re.M)
        if not m: raise ValueError('UNSUPPORTED_TARGET')
        raw = m[1]; macros = re.findall(r'\$\((\w+)\)', raw)
        if raw.strip() == ('$(%s)' % macros[0] if macros else ''):
            name = macros[0]; vm = re.search(r'^' + name + r' = (.*)$', changed, re.M)
            if not vm: raise ValueError('UNSUPPORTED_MACRO')
            changed = changed[:vm.end()] + ' ' + d + changed[vm.end():]; style = 'macro'
        else:
            changed = changed[:m.end()] + ' ' + d + changed[m.end():]; style = 'mixed' if macros else 'direct'
        edits.append({'target': t, 'dependency': d, 'style': style})
    diff = ''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True), fromfile='a/Makefile', tofile='b/Makefile'))
    return diff, edits


def validate(p, patchfile, evidence, fail_test=False, profile=None):
    prof = resolve_profile(profile)
    evidence.mkdir(parents=True); before = (p / 'Makefile').read_bytes()
    sandbox = evidence / 'sandbox'; shutil.copytree(p, sandbox, ignore=shutil.ignore_patterns('.git', '*.o', 'app'))
    run(['git', 'init', '-b', 'main'], sandbox)
    run(['git', 'config', 'user.name', 'ValidationSandbox'], sandbox)
    run(['git', 'config', 'user.email', 'fixture@localhost'], sandbox)
    commit(sandbox, 'sandbox input')
    checks = {}; error = None
    build = ['make', prof['build_target']]; clean = ['make', prof['clean_target']]
    binary = './' + prof['build_target']
    try:
        run(['git', 'apply', '--check', str(patchfile.resolve())], sandbox); checks['patch_applies'] = True
        run(['git', 'apply', str(patchfile.resolve())], sandbox)
        log = run(clean, sandbox) + run(build, sandbox); (evidence / 'build.log').write_text(log); checks['build'] = True
        expected = '99' if fail_test else prof['expected_output']
        output = run([binary], sandbox).strip(); checks['test'] = output == expected
        # Real header-change build checks the originally broken incremental behavior.
        time.sleep(1.05)
        target_header = sandbox / prof['config_file']
        if prof['config_mode'] == 'append':
            target_header.write_text(target_header.read_text() + prof['config_after'])
        else:
            target_header.write_text(prof['config_after'])
        incremental = run(build, sandbox)
        (evidence / 'incremental.log').write_text(incremental)
        if prof['header_check'] == 'rebuild':
            # 只要求"改头文件后确实重新编译"，不要求程序输出变化（真实项目常见形态）。
            checks['header_change'] = any(('-o ' + t) in incremental for t, _s in prof['units'])
        else:
            checks['header_change'] = run([binary], sandbox).strip() == prof['expected_output_after']
        recheck = scan(sandbox, profile=prof); save(evidence / 'recheck.json', recheck)
        checks['no_missing'] = not any(f['type'] == 'MISSING' for f in recheck['findings'])
    except (ValueError, subprocess.TimeoutExpired) as ex: error = str(ex)
    accepted = bool(checks) and all(checks.values()) and error is None
    # Source remains untouched until all checks pass. Evidence sandbox is retained.
    if accepted: (p / 'Makefile').write_bytes((sandbox / 'Makefile').read_bytes())
    unchanged = (p / 'Makefile').read_bytes() == before
    result = {'accepted': accepted, 'checks': checks, 'error': error, 'source_unchanged': unchanged, 'rollback': not accepted and unchanged}
    save(evidence / 'validation.json', result); return result


def buildchecker(p, out):
    import sys
    sys.path.insert(0, '/app')
    from buildchecker.fullcheck import full_check
    full_check(p, out)
    report = json.loads((out / 'findings.json').read_text())
    if report['status'] != 'SUCCEEDED': raise ValueError('BUILDCHECKER_FAILED ' + str(report))
    projected = [f for f in report['findings'] if f['target'] in ['main.o', 'helper.o']]
    oracle = scan(p)
    norm = lambda fs: sorted((f['type'], f['target'], f['dependency']) for f in fs)
    assert norm(projected) == norm(oracle['findings']), 'BuildChecker/GCC projection mismatch'
    return report


def demo(stage, out, track):
    if out.exists(): raise ValueError('OUTPUT_MUST_BE_NEW')
    out.mkdir(parents=True); p = out / 'project'; fixture(p); baseline = scan(p); save(out / 'baseline.json', baseline)
    if stage == 'e8':
        if track == 'A':
            buildchecker(p, out / 'buildchecker')
            edges = json.loads((out / 'buildchecker/actual-graph.json').read_text())
            baseline['actual'] = {t: sorted({e['dependency'] for e in edges if e['target'] == t}) for t in ['main.o', 'helper.o']}
            baseline['baseline_source'] = 'BuildChecker actual-graph.json projected to object targets'
            save(out / 'baseline.json', baseline)
            save(out / 'incremental.json', scan(p, baseline))
        else:
            save(out / 'fixed-md-report.json', baseline)
            diff, edits = patch(p, baseline); (out / 'candidate.patch').write_text(diff); save(out / 'patch-plan.json', edits)
            stale = dict(baseline, commit='0' * 40)
            try: patch(p, stale)
            except ValueError as ex: save(out / 'expected-failure.json', {'error': str(ex)})
        return
    if stage == 'e9':
        if track == 'A':
            (out / 'C0-build.log').write_text(run(['make', 'app'], p))
            (p / 'main.c').write_text((p / 'main.c').read_text().replace('VALUE+helper()', 'VALUE+helper()+0'))
            commit(p, 'C1 body change'); (out / 'C1-build.log').write_text(run(['make', 'app'], p)); one = scan(p, baseline); save(out / 'C1.json', one)
            (p / 'main.c').write_text('#include "extra.h"\n' + (p / 'main.c').read_text()); commit(p, 'C2 include change')
            (out / 'C2-build.log').write_text(run(['make', 'app'], p)); two = scan(p, one); save(out / 'C2.json', two)
            (p / 'Makefile').write_text((p / 'Makefile').read_text().replace('main.c unused.h', 'main.c unused.h config.h extra.h'))
            commit(p, 'C3 repair declarations'); save(out / 'C3.json', scan(p, two))
        else:
            for style in ['direct', 'macro', 'mixed']:
                q = out / style; fixture(q, style); r = scan(q); diff, edits = patch(q, r)
                (out / (style + '.patch')).write_text(diff); save(out / (style + '-plan.json'), edits)
                assert (q / 'Makefile').read_text().find('config.h') < 0
        return
    rows = []
    if track == 'A':
        previous = baseline
        cases = ['unchanged', 'body', 'include', 'declaration', 'flags', 'header']
        for case in cases:
            if case == 'body': (p / 'helper.c').write_text('int helper(void){return 0+0;}\n')
            if case == 'include': (p / 'main.c').write_text('#include "extra.h"\n' + (p / 'main.c').read_text())
            if case == 'declaration': (p / 'Makefile').write_text((p / 'Makefile').read_text().replace('main.c unused.h', 'main.c unused.h config.h extra.h'))
            if case == 'flags': (p / 'Makefile').write_text((p / 'Makefile').read_text().replace('-O0', '-O1'))
            if case == 'header': (p / 'config.h').write_text('#include "extra.h"\n#define VALUE 1\n')
            if case != 'unchanged': commit(p, case)
            for repeat in range(5):
                inc = scan(p, previous); full = scan(p)
                passed = all(inc[k] == full[k] for k in ['actual', 'declared', 'findings'])
                rows.append({'case': case, 'repeat': repeat + 1, 'equal': passed, 'incremental_s': inc['elapsed_s'], 'full_s': full['elapsed_s'], 'reused': len(inc['reused']), 'refreshed': len(inc['refreshed'])})
                assert passed, case
            save(out / (case + '.json'), inc); previous = inc
        buildchecker(p, out / 'final-buildchecker')
    else:
        diff, _ = patch(p, baseline); candidate = out / 'candidate.patch'; candidate.write_text(diff)
        rejected = validate(p, candidate, out / 'reject-test', True); assert rejected['rollback']
        rows.append({'case': 'test-rejection', 'passed': rejected['rollback']})
        accepted = validate(p, candidate, out / 'accept'); assert accepted['accepted']
        rows.append({'case': 'accepted', 'passed': accepted['accepted']})
        broken = out / 'broken.patch'; broken.write_text('invalid patch\n')
        rejected2 = validate(p, broken, out / 'reject-patch'); assert rejected2['rollback']
        rows.append({'case': 'patch-rejection', 'passed': rejected2['rollback']})
        buildchecker(p, out / 'recheck-buildchecker')
    with (out / 'results.csv').open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    save(out / 'gate.json', {'track': track, 'passed': True, 'rows': len(rows)})


def main():
    a = argparse.ArgumentParser(); a.add_argument('stage', choices=['e8', 'e9', 'e10']); a.add_argument('--track', choices=['A', 'B'], required=True); a.add_argument('--out', type=Path, required=True); args = a.parse_args()
    demo(args.stage, args.out.resolve(), args.track); print('COMPLETED', args.stage, args.track, args.out)


if __name__ == '__main__': main()
