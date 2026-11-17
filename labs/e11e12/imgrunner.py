"""在 DRAFT 镜像内执行下游阶段，并留下容器级证据。

设计：编排容器（course-e11e12）已把仓库挂成 /course、并挂了宿主 docker socket。
这里在编排容器内再起容器，用 `--volumes-from <自身容器>` 共享同一批挂载，
路径（/course/...）在两层完全一致。

证据（B13 五项补齐第 2 条要求）：
  - 每次执行写 <tag>.exec.json：image、完整 argv、cwd、容器 ID、退出码
  - <tag>.inspect.json：docker inspect 原文（Image / Mounts / State.ExitCode）
  - <tag>.stdout.log / <tag>.stderr.log：原始输出
  - 执行后先 inspect 再 docker rm -f 清理容器
"""
import json
import os
import socket
import subprocess
from pathlib import Path

DRIVERS = {
    'full': (
        "import json,sys;from pathlib import Path;"
        "sys.path[:0]=['/course/labs/e11e12/environment/services/buildchecker'];"
        "from buildchecker.fullcheck import full_check;"
        "r=full_check(Path(sys.argv[1]),Path(sys.argv[2]),clean_command=sys.argv[3],build_command=sys.argv[4]);"
        "print(json.dumps({'status':r.get('status'),'error':r.get('error')}))"
    ),
    'scan': (
        "import json,sys;from pathlib import Path;"
        "sys.path[:0]=['/course/labs/e8e10'];"
        "from lab import scan;"
        "old=None if sys.argv[2]=='-' else json.loads(Path(sys.argv[2]).read_text());"
        "prof=json.loads(Path(sys.argv[3]).read_text());"
        "r=scan(Path(sys.argv[1]),old,prof);"
        "Path(sys.argv[4]).write_text(json.dumps(r,ensure_ascii=False,indent=2));"
        "print('SCAN_OK')"
    ),
}


def self_container():
    """当前容器 ID：docker 会把容器 ID 写进 /etc/hostname。"""
    try:
        name = Path('/etc/hostname').read_text().strip()
        if name:
            return name
    except OSError:
        pass
    return socket.gethostname()


def run(image, argv, cwd=None, timeout=900, ptrace=True, evidence=None, tag='step'):
    """在指定镜像内执行命令，返回 (exit_code, 合并输出)；evidence 非空时记录容器级原件。"""
    cmd = ['docker', 'run', '--network', 'none',
           '--volumes-from', self_container(),
           '-u', '%d:%d' % (os.getuid(), os.getgid()),
           '-e', 'HOME=/tmp']
    if ptrace:
        cmd += ['--cap-add', 'SYS_PTRACE']

    ev = Path(evidence) if evidence else None
    cidfile = None
    if ev:
        ev.mkdir(parents=True, exist_ok=True)
        cidfile = ev / ('%s.cid' % tag)
        if cidfile.exists():
            cidfile.unlink()
        cmd += ['--cidfile', str(cidfile)]
    else:
        cmd += ['--rm']

    if cwd:
        cmd += ['-w', str(cwd)]
    cmd += [image] + [str(x) for x in argv]

    try:
        p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        code, out, err = p.returncode, (p.stdout or ''), (p.stderr or '')
    except subprocess.TimeoutExpired:
        code, out = 124, ''
        err = 'TIMEOUT after %ss: %s' % (timeout, ' '.join(cmd))

    if ev:
        record = {'tag': tag, 'image': image, 'argv': [str(x) for x in argv],
                  'cwd': str(cwd) if cwd else None, 'exit': code}
        cid = None
        if cidfile and cidfile.exists():
            cid = cidfile.read_text().strip() or None
        record['container_id'] = cid
        if cid:
            insp = subprocess.run(['docker', 'inspect', cid], text=True, capture_output=True)
            if insp.returncode == 0:
                (ev / ('%s.inspect.json' % tag)).write_text(insp.stdout, encoding='utf-8')
                try:
                    data = json.loads(insp.stdout)[0]
                    record['inspect_image'] = data.get('Image')
                    record['inspect_mounts'] = [m.get('Destination') for m in (data.get('Mounts') or [])]
                    record['inspect_exit_code'] = (data.get('State') or {}).get('ExitCode')
                except (ValueError, IndexError, KeyError):
                    pass
            subprocess.run(['docker', 'rm', '-f', cid], capture_output=True)
        (ev / ('%s.stdout.log' % tag)).write_text(out, encoding='utf-8')
        (ev / ('%s.stderr.log' % tag)).write_text(err, encoding='utf-8')
        (ev / ('%s.exec.json' % tag)).write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    return code, (out + err)


def run_py(image, driver, args, cwd=None, timeout=900, evidence=None, tag='step'):
    code = DRIVERS[driver] if driver in DRIVERS else driver
    return run(image, ['python3', '-c', code] + [str(x) for x in args],
               cwd=cwd, timeout=timeout, evidence=evidence, tag=tag)


def full_in_image(image, project, folder, clean_command, build_command, timeout=900,
                  evidence=None, tag='full'):
    code, out = run_py(image, 'full', [project, folder, clean_command, build_command],
                       timeout=timeout, evidence=evidence, tag=tag)
    if code:
        raise ValueError('IMAGE_FULL_CHECK_FAILED ' + out[-800:])
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise ValueError('IMAGE_FULL_CHECK_BAD_OUTPUT ' + out[-800:])


def scan_in_image(image, project, out_json, profile, old_json=None, timeout=600,
                  evidence=None, tag='scan'):
    profile_path = Path(str(out_json) + '.profile.json')
    profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding='utf-8')
    code, out = run_py(image, 'scan', [project, old_json or '-', profile_path, out_json],
                       timeout=timeout, evidence=evidence, tag=tag)
    if code:
        raise ValueError('IMAGE_SCAN_FAILED ' + out[-800:])
    return json.loads(Path(out_json).read_text())
