"""把我们请求里的 profile 转成 B13 的 b13-project-profile-1 结构，并给出 canonical 哈希。

背景（B13 五项第 5 条）：对方 profile 预检报 PROFILE_HASH_MISMATCH ——
两边字段名与规范化方式不同，不是"谁对谁错"。本脚本产出可对照的两份：
  1. B13 结构的 profile JSON
  2. 该 JSON 的 canonical SHA-256（sort_keys + 紧凑分隔符）
校准方式需与 B13 成员二确认；本文件把我们的规范化假设写明，便于逐字对齐。

用法：
    python3 to_b13_profile.py --request data/real-e12-inimage.json \
        --project data/real-project --out data/a13-tomlc99-release-1.json
"""
import argparse
import hashlib
import json
from pathlib import Path


def canonical_sha(obj):
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--request', default='data/real-e12-inimage.json')
    ap.add_argument('--project', default='data/real-project')
    ap.add_argument('--out', default='data/a13-tomlc99-release-1.json')
    ap.add_argument('--id', default='a13-tomlc99-release-1')
    a = ap.parse_args()

    request = json.loads(Path(a.request).read_text())
    prof = request['profile']
    units = prof['units']
    targets = [t for t, _s in units]
    build = prof['build_target']

    makefile = Path(a.project) / 'Makefile'
    makefile_sha = hashlib.sha256(makefile.read_bytes()).hexdigest() if makefile.is_file() else None

    stdout = prof.get('expected_output', '')
    b13 = {
        'schema_version': 'b13-project-profile-1',
        'id': a.id,
        'units': units,
        'repair_targets': targets,
        'clean_argv': ['make', prof['clean_target']],
        'build_argv': ['make', build],
        'run_argv': ['./' + build],
        'stdin_hex': '',
        'stdout_hex': (stdout + '\n').encode('utf-8').hex(),
        'exit_code': 0,
        'effective_flags': prof['flags_allowed'][0].split(),
        'header_probe': {
            'path': prof['config_file'],
            'append_hex': prof.get('config_after', '').encode('utf-8').hex(),
        },
        'recursive_scan': prof.get('recursive_scan', False),
        'strict_sources': prof.get('strict_sources', False),
        'makefile_template_sha256': makefile_sha,
    }

    out = Path(a.out)
    out.write_text(json.dumps(b13, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print('written      :', out)
    print('canonical sha:', canonical_sha(b13), '（sort_keys + 紧凑分隔符，需与 B13 确认）')
    print('file sha256  :', hashlib.sha256(out.read_bytes()).hexdigest(), '（按文件字节）')
    print('\n字段对照（我们的 profile → B13 字段）：')
    for left, right in (('units', 'units'), ('build_target', 'build_argv'),
                        ('clean_target', 'clean_argv'), ('expected_output', 'stdout_hex'),
                        ('flags_allowed[0]', 'effective_flags'),
                        ('config_file', 'header_probe.path'),
                        ('config_after', 'header_probe.append_hex'),
                        ('recursive_scan', 'recursive_scan'),
                        ('strict_sources', 'strict_sources')):
        print('  %-20s → %s' % (left, right))
    print('  （config_mode=append 对应 header_probe 的追加语义；exec_image 是执行环境开关，B13 无对应字段）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
