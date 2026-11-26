"""在 DRAFT 镜像内执行下游阶段，并留下容器级证据。

设计：编排容器（course-e11e12）已把仓库挂成 /course、并挂了宿主 docker socket。
下游容器显式挂载课程目录和工作目录，保留 /course/... 路径。

证据（B13 五项补齐第 2 条要求）：
  - 每次执行写 <tag>.exec.json：image、完整 argv、cwd、容器 ID、退出码
  - <tag>.inspect.json：docker inspect 原文（Image / Mounts / State.ExitCode）
  - <tag>.stdout.log / <tag>.stderr.log：原始输出
  - 执行后先 inspect 再 docker rm -f 清理容器
"""
import json
import os
import re
import socket
import subprocess
import uuid
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



def child_mount_args():
    """Share only this run's writable /course worktree with the child."""
    inspection = subprocess.run(
        ['docker', 'inspect', self_container()],
        check=True, capture_output=True, text=True,
    )
    mounts = json.loads(inspection.stdout)[0]['Mounts']
    course = [m for m in mounts if m.get('Destination') == '/course']
    if len(course) != 1 or course[0].get('Type') != 'bind':
        raise ValueError('Expected one bind mount at /course')
    mount = course[0]
    source = mount.get('Source', '')
    if not mount.get('RW') or not Path(source).is_absolute():
        raise ValueError('Expected writable /course with an absolute host source')
    if any(m.get('Destination', '').startswith('/course/') for m in mounts):
        raise ValueError('Nested mounts under /course are unsupported')
    spec = f'type=bind,src={source},dst=/course,bind-recursive=disabled'
    return ['--mount', spec]


def _text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else (value or '')


def _capture(argv, timeout):
    """Bound Docker CLI calls and retain partial output on timeout."""
    try:
        p = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
        return p.returncode, _text(p.stdout), _text(p.stderr), False
    except subprocess.TimeoutExpired as exc:
        return 124, _text(exc.stdout), (_text(exc.stderr) +
            '\nTIMEOUT after %ss: %s\n' % (timeout, ' '.join(argv))), True
    except OSError as exc:
        return 125, '', str(exc), False


def run(image, argv, cwd=None, timeout=900, ptrace=True, evidence=None, tag='step'):
    """Run a command in the DRAFT image; evidence-backed runs own a named child."""
    cmd = ['docker', 'run', '--network', 'none',
           *child_mount_args(),
           '-u', '%d:%d' % (os.getuid(), os.getgid()),
           '-e', 'HOME=/tmp']
    if ptrace:
        cmd += ['--cap-add', 'SYS_PTRACE']
    if cwd:
        cmd += ['-w', str(cwd)]
    cmd += [image] + [str(x) for x in argv]

    if evidence is None:
        # Preserve the historical no-evidence interface. The E14 broker always
        # uses the evidence-backed path below.
        cmd.insert(2, '--rm')
        code, out, err, _ = _capture(cmd, timeout)
        return code, out + err

    ev = Path(evidence)
    ev.mkdir(parents=True, exist_ok=True)
    cidfile = ev / (tag + '.cid')
    if any((ev / (tag + suffix)).exists() for suffix in
           ('.cid', '.exec.json', '.inspect.json', '.stdout.log', '.stderr.log', '.cleanup.log')):
        raise ValueError('EXEC_EVIDENCE_ALREADY_EXISTS: ' + tag)

    # Do not start a process until docker create has returned its actual ID.
    # A unique name also permits bounded recovery of a stopped container if
    # create failed before reporting an ID; never search/remove by image.
    name = 'course-exec-' + uuid.uuid4().hex
    create = ['docker', 'create', '--name', name] + cmd[2:]
    record = {'tag': tag, 'image': image, 'argv': [str(x) for x in argv],
              'cwd': str(cwd) if cwd else None, 'container_name': name,
              'create_argv': create, 'timeout_s': timeout,
              'container_id': None, 'timed_out': False, 'cleanup_verified': False}
    code, out, err, create_timeout = _capture(create, 60)
    record.update(create_exit=code, create_stdout=out, create_stderr=err,
                  create_timed_out=create_timeout)
    cid = out.strip() if code == 0 else None
    valid_id = lambda x: isinstance(x, str) and re.fullmatch(r'[0-9a-f]{64}', x) is not None
    # On a successful create, stdout is the authoritative container ID.
    if not valid_id(cid):
        cid = None
        if code == 0:
            code, err = 125, err + '\nDocker create returned no valid container ID'
    else:
        cidfile.write_text(cid + '\n', encoding='utf-8')
        record['start_argv'] = ['docker', 'start', '-a', cid]
        code, out, err, timed_out = _capture(record['start_argv'], timeout)
        record['timed_out'] = timed_out

    cleanup_log = []
    lookup = ['docker', 'ps', '-aq', '--no-trunc', '--filter', 'name=^/' + name + '$']
    record['cleanup_lookup_argv'] = lookup
    if cid is None:
        rc, found, msg, _ = _capture(lookup, 30)
        cleanup_log.extend([found, msg])
        ids = found.splitlines()
        if rc == 0 and len(ids) == 1 and valid_id(ids[0]):
            cid = ids[0]
            cidfile.write_text(cid + '\n', encoding='utf-8')
    record['container_id'] = cid
    if cid is not None:
        rc, raw, msg, _ = _capture(['docker', 'inspect', '--type', 'container', cid], 30)
        cleanup_log.append(msg)
        if rc == 0:
            (ev / (tag + '.inspect.json')).write_text(raw, encoding='utf-8')
            try:
                data = json.loads(raw)[0]
                record['inspect_image'] = data.get('Image')
                record['inspect_mounts'] = [m.get('Destination') for m in (data.get('Mounts') or [])]
                record['inspect_exit_code'] = (data.get('State') or {}).get('ExitCode')
            except (ValueError, IndexError, KeyError, TypeError):
                pass
        record['cleanup_argv'] = ['docker', 'rm', '-f', cid]
        rc, removed, msg, _ = _capture(record['cleanup_argv'], 30)
        record['cleanup_exit'] = rc
        cleanup_log.extend([removed, msg])
    rc, remaining, msg, _ = _capture(lookup, 30)
    record['cleanup_lookup_exit'] = rc
    record['cleanup_remaining'] = remaining.splitlines()
    cleanup_log.extend([remaining, msg])
    # A timed-out create may still be completing in the daemon. Even if the
    # name is currently absent, do not claim that creation was fully cleaned.
    record['cleanup_verified'] = (not create_timeout and rc == 0 and not remaining.strip()
                                  and (cid is None or record.get('cleanup_exit') == 0))
    record['command_exit'] = code
    if not record['cleanup_verified']:
        code = 125
        err += '\nEXEC_CLEANUP_UNCONFIRMED: ' + name
    record['exit'] = code
    (ev / (tag + '.cleanup.log')).write_text('\n'.join(cleanup_log), encoding='utf-8')
    (ev / (tag + '.stdout.log')).write_text(out, encoding='utf-8')
    (ev / (tag + '.stderr.log')).write_text(err, encoding='utf-8')
    (ev / (tag + '.exec.json')).write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return code, out + err


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
