"""生成教学样例。

环境适配点（默认值与课程原版逐字一致，CI 不受影响）：
  E11E12_SAMPLE_BASE    基础镜像入口，例如 m.daocloud.io/docker.io/library/python:3.13-slim
  E11E12_SAMPLE_DIGEST  候选 Dockerfile 使用的固定 digest
  E11E12_APT_MIRROR     Debian APT 源替换域名，例如 mirrors.tuna.tsinghua.edu.cn
本机无法直连 Docker Hub 时，用这三个变量重新生成样例，镜像与源都走国内镜像站。
"""
import json, os
from pathlib import Path
from pipeline import ROOT, save
from lab import fixture,commit,scan

BASE=os.environ.get('E11E12_SAMPLE_BASE','python:3.13-slim')
DIGEST=os.environ.get('E11E12_SAMPLE_DIGEST',
    'sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f')
MIRROR=os.environ.get('E11E12_APT_MIRROR','')

def apt_install():
    if not MIRROR:
        # 与课程原版完全一致
        return ('apt-get update && apt-get install -y --no-install-recommends '
                'build-essential && rm -rf /var/lib/apt/lists/*')
    return ('sed -i -e "s|deb.debian.org|%s|g" -e "s|security.debian.org|%s|g" '
            '/etc/apt/sources.list.d/debian.sources && '
            'apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 update && '
            'apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 install '
            '-y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*') % (MIRROR,MIRROR)

def main():
    root=ROOT/'data/integration-sample'
    if root.exists():raise SystemExit('data/integration-sample already exists; preserve it and choose a new workspace')
    project=root/'repo';fixture(project)
    broken='FROM %s\nWORKDIR /work\nCOPY main.c helper.c config.h extra.h unused.h Makefile ./\nRUN make app\nCMD ["./app"]\n' % BASE
    (project/'Dockerfile.broken').write_text(broken,encoding='utf-8')
    base=commit(project,'integration C0')
    (project/'main.c').write_text('#include "extra.h"\n'+(project/'main.c').read_text(),encoding='utf-8')
    target=commit(project,'integration C1 add project include')
    pin='FROM %s@%s' % (BASE,DIGEST)
    candidate=broken.replace('FROM %s' % BASE,pin).replace('RUN make app','RUN %s\nRUN make app' % apt_install())
    (root/'candidate.Dockerfile').write_text(candidate,encoding='utf-8')
    fixed=scan(project)
    save(root/'fixed-md.json',{'schema_version':'e11e12-1','kind':'fixed-md','status':'SUCCEEDED','commit':target,'data':fixed})
    for mode in ('e11-a','e11-b','e12'):
        save(root/(mode+'.json'),{'mode':mode,'repo':str(project),'base':base,'target':target,'candidate':str(root/'candidate.Dockerfile'),'fixed_report':str(root/'fixed-md.json'),'expected_output':'1','build_timeout':600})
    save(root/'dataset.json',{'source':'course-generated controlled C/Make project','base_commit':base,'target_commit':target,'candidate_source':'recorded dependency-install pattern adapted to the two-source-file project','expected_output':'1','purpose':'classroom baseline; replace request paths with your own project for real-data integration'})
    print(root)
    print('BASE=%s' % BASE)
    print('DIGEST=%s' % DIGEST)
    print('APT_MIRROR=%s' % (MIRROR or '(default)'))

if __name__=='__main__':main()
