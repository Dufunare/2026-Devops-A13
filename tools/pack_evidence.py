"""打包交付证据：MANIFEST + tar + SHA256（对应 B13 五项第 4 条）。

要点：清单里列出的每个路径都必须真实存在，否则脚本直接失败——避免"索引里有、包里没有"。
用法：
    python3 pack_evidence.py [--repo ...] [--out /root/A13_..._evidence.tar.gz]
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

CANDIDATES = [
    'work/e12-real-07',
    'work/e12-real-06',
    'work/e12-real-04',
    'work/e11b-real-02',
    'work/binding-inimage-27c7d2d0a558.txt',
    'work/binding-13f61cdec4ed.txt',
    'work/e11e12-image-record.json',
    'data/real-e12.json',
    'data/real-e11-b.json',
    'data/real-e12-tools.json',
    'data/real-e11b-tools.json',
    'data/real-e12-inimage.json',
    'data/a13-tomlc99-release-1.json',
    'data/real-candidate-tools.Dockerfile',
    'tools/pack_evidence.py',
    'tools/to_b13_profile.py',
]


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default='/root/241870063/buildchecker')
    ap.add_argument('--out', default=None)
    ap.add_argument('--extra', nargs='*', default=[], help='额外要打包的相对路径')
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    ts = time.strftime('%Y%m%d%H%M%S')
    out = Path(a.out) if a.out else Path('/root') / ('A13_241870063_evidence_%s.tar.gz' % ts)

    present, missing = [], []
    for rel in CANDIDATES + list(a.extra):
        (present if (repo / rel).exists() else missing).append(rel)
    if missing:
        sys.exit('以下路径不存在，先补齐或从清单删除：\n  ' + '\n  '.join(missing))

    files = []
    for rel in present:
        p = repo / rel
        if p.is_file():
            files.append({'path': rel, 'bytes': p.stat().st_size, 'sha256': sha(p)})
        else:
            for sub in sorted(p.rglob('*')):
                if sub.is_file():
                    files.append({'path': sub.relative_to(repo).as_posix(),
                                  'bytes': sub.stat().st_size, 'sha256': sha(sub)})

    manifest = {'schema_version': 'e11e12-evidence-manifest-1',
                'created_at': ts, 'repo_commit': subprocess.run(
                    ['git', 'rev-parse', 'HEAD'], cwd=repo, text=True,
                    capture_output=True).stdout.strip(),
                'roots': present, 'file_count': len(files), 'files': files}
    manifest_path = repo / 'work' / ('manifest-%s.json' % ts)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    subprocess.run(['tar', 'czf', str(out)] + present + [manifest_path.relative_to(repo).as_posix()],
                   cwd=repo, check=True)
    digest = sha(out)
    Path(str(out) + '.sha256').write_text('%s  %s\n' % (digest, out), encoding='utf-8')

    print('manifest : %s（%d 个文件）' % (manifest_path, len(files)))
    print('archive  : %s' % out)
    print('bytes    : %d' % out.stat().st_size)
    print('sha256   : %s' % digest)
    print('\n包含的根路径：')
    for rel in present:
        print('  -', rel)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
