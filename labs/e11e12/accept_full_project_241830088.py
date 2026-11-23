"""Supplemental tomlc99 whole-project acceptance; never rewrites an old API job.

Runs make all before/after in a previously produced immutable DRAFT image.
Only a fresh checkout's Makefile is repaired. Original C0/C1 stay unchanged.
"""
import argparse
import difflib
import hashlib
import json
import re
import subprocess
from pathlib import Path

from imgrunner import full_in_image, run

C1 = 'b2dda5513fe4a7d250493528800fe425cae459a5'
EXECUTABLES = ('toml_json', 'toml_cat', 'toml_sample')
FLAGS = '-std=c99 -Wall -Wextra -fpic -O2 -DNDEBUG'


def repair_all(text, findings):
    """Preserve upstream inline-link semantics: headers are prerequisites, not argv."""
    edits = {}
    for finding in findings:
        if finding['type'] != 'MISSING':
            continue
        target, dep = finding['target'], finding['dependency']
        if target not in ('toml.o', *EXECUTABLES):
            raise ValueError('UNSUPPORTED_TARGET ' + target)
        if not re.fullmatch(r'[\w.-]+\.h', dep):
            raise ValueError('UNSUPPORTED_DEPENDENCY ' + dep)
        edits.setdefault(target, set()).add(dep)
    changed = text
    for target, deps in sorted(edits.items()):
        match = re.search(r'^' + re.escape(target) + r': ([^\n]*)$', changed, re.M)
        if target == 'toml.o':
            if not match:
                raise ValueError('UNSUPPORTED_OBJECT_RULE')
            missing = sorted(deps - set(match[1].split()))
            changed = changed[:match.end()] + ''.join(' ' + d for d in missing) + changed[match.end():]
        else:
            if match:
                raise ValueError('EXECUTABLE_ALREADY_EXPLICIT ' + target)
            # Same source/library inputs as GNU Make's built-in link rule. Do not
            # use $^ here: that would pass the new header prerequisites to CC.
            changed += ('\n' + target + ': ' + target + '.c $(LIB) ' + ' '.join(sorted(deps))
                        + '\n\t$(LINK.c) ' + target + '.c $(LIB) $(LOADLIBES) $(LDLIBS) -o $@\n')
    if changed == text:
        raise ValueError('NO_REPAIR')
    return changed


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', args.image):
        raise ValueError('IMMUTABLE_IMAGE_ID_REQUIRED')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[2]
    source_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=root, text=True)
    if dirty:
        raise ValueError('COMMIT_IMPLEMENTATION_BEFORE_RUNNING')
    project = out / 'project'
    subprocess.run(['git', 'clone', '--no-hardlinks', str(args.repo), str(project)], check=True)
    subprocess.run(['git', 'checkout', '--detach', C1], cwd=project, check=True)
    tracked = subprocess.check_output(['git', 'ls-files'], cwd=project, text=True).splitlines()
    before_hashes = {p: sha(project / p) for p in tracked}
    save(out / 'binding.json', {'implementation_sha': source_sha, 'dirty': False,
                              'project_c1': C1, 'draft_image_id': args.image,
                              'scope': 'all targets built by make all; supplemental local acceptance, not a new HTTP job'})

    def collect(folder, tag):
        full_in_image(args.image, project, out / folder, 'make clean', 'make all',
                      evidence=out / 'inimage', tag=tag)
        report = json.loads((out / folder / 'findings.json').read_text())
        if report['status'] != 'SUCCEEDED':
            raise ValueError('FULL_CHECK_FAILED ' + str(report))
        return report

    before = collect('before-full', 'before-full-all')
    makefile = project / 'Makefile'
    original = makefile.read_text()
    repaired = repair_all(original, before['findings'])
    makefile.write_text(repaired)
    (out / 'candidate.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), repaired.splitlines(True), fromfile='a/Makefile', tofile='b/Makefile')))
    after = collect('after-full', 'after-full-all')
    remaining = [f for f in after['findings'] if f['type'] == 'MISSING']
    if remaining:
        raise ValueError('WHOLE_PROJECT_MD_REMAINS ' + str(remaining))

    # Test the original program, then change a header without cleaning. Preserve
    # compiler exec traces and every output's nanosecond mtime, not just log text.
    probe = """import json,pathlib,subprocess,time
p=pathlib.Path('.')
names=['toml.o','libtoml.a','libtoml.so.1.0','toml_json','toml_cat','toml_sample']
def stat(): return {n:(p/n).stat().st_mtime_ns for n in names}
subprocess.run(['make','clean'],check=True)
subprocess.run(['make','all'],check=True)
program=subprocess.run(['./toml_json'],input=b'',capture_output=True)
assert program.returncode==0 and program.stdout==b'{}\\n',repr(program)
before=stat();time.sleep(1.1)
with (p/'toml.h').open('a') as f:f.write('\\n/* A13 whole-project dependency probe */\\n')
cmd=['strace','-ff','-s','4096','-e','trace=%file,%process','-o',str(pathlib.Path(__import__('sys').argv[1])/'header-trace'),'make','all']
result=subprocess.run(cmd,capture_output=True)
o=pathlib.Path(__import__('sys').argv[1]);(o/'header-build.stdout').write_bytes(result.stdout);(o/'header-build.stderr').write_bytes(result.stderr)
after=stat()
assert result.returncode==0
assert all(after[n]>before[n] for n in names),(before,after)
db=subprocess.run(['make','-p','-n'],capture_output=True,text=True,check=True).stdout
flags=[x.split('=',1)[1].strip() for x in db.splitlines() if x.startswith('CFLAGS =')][-1]
assert flags=='-std=c99 -Wall -Wextra -fpic -O2 -DNDEBUG',flags
(o/'header-probe.json').write_text(json.dumps({'before_mtime_ns':before,'after_mtime_ns':after,'program_stdout_hex':program.stdout.hex(),'program_exit':program.returncode,'make_exit':result.returncode,'flags':flags},indent=2))
"""
    code, log = run(args.image, ['python3', '-c', probe, str(out)], cwd=project,
                    evidence=out / 'inimage', tag='header-probe-all')
    (out / 'probe.log').write_text(log)
    if code:
        raise ValueError('HEADER_PROBE_FAILED')
    # Restore the probe header. Only Makefile may differ from the frozen C1.
    subprocess.run(['git', 'checkout', '--', 'toml.h'], cwd=project, check=True)
    after_hashes = {p: sha(project / p) for p in tracked}
    changed = [p for p in tracked if before_hashes[p] != after_hashes[p]]
    if changed != ['Makefile']:
        raise ValueError('UNEXPECTED_SOURCE_CHANGES ' + repr(changed))
    save(out / 'input-hashes.json', {'before': before_hashes, 'after': after_hashes, 'changed': changed})
    save(out / 'summary.json', {'passed': True, 'before_findings': before['findings'],
                              'after_findings': after['findings'], 'remaining_md': remaining,
                              'observed_targets': after['observed_targets'], 'build_target': 'all',
                              'image_id': args.image, 'implementation_sha': source_sha,
                              'project_c1': C1, 'changed_tracked_files': changed,
                              'does_not_replace_original_http_job': True})
    print((out / 'summary.json').read_text())


if __name__ == '__main__':
    main()
