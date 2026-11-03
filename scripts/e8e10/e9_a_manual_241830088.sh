#!/usr/bin/env bash
set -eu
cd /root/devops-students/241830088/buildchecker
E8_PACK=/root/devops-materials/DevOps_E8_E10/03_实验包
source "$E8_PACK/classroom_helpers.sh"
lab_ready
lab_new_run e9 A
printf "\nMANUAL_BLOCK=1\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import sys
from lab import fixture
out=Path(sys.argv[1]); fixture(out/'project')
print('CREATED',out/'project')
PY

printf "\nMANUAL_BLOCK=2\n"
pwd
cat "$OUT/student-source-commit.txt"
cat "$OUT/project/Makefile"
cat "$OUT/project/main.c"
cat "$OUT/project/config.h"
cat "$OUT/project/helper.c"
git -C "$OUT/project" log -1 --oneline

printf "\nMANUAL_BLOCK=3\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import sys
from lab import scan,save,run
out=Path(sys.argv[1]);p=out/'project'
(out/'C0-build.log').write_text(run(['make','app'],p))
save(out/'baseline.json',scan(p))
assert run(['./app'],p).strip()=='1'
print('C0_BUILD_AND_BASELINE_PASS')
PY

printf "\nMANUAL_BLOCK=4\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import sys,time
from lab import commit,run
out=Path(sys.argv[1]);p=out/'project';time.sleep(1.05)
f=p/'main.c';f.write_text(f.read_text().replace('VALUE+helper()','VALUE+helper()+0'))
print('C1',commit(p,'C1 body change'))
(out/'C1-build.log').write_text(run(['make','app'],p))
print((out/'C1-build.log').read_text())
PY

printf "\nMANUAL_BLOCK=5\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import json,sys
from lab import scan,save
out=Path(sys.argv[1]);old=json.loads((out/'baseline.json').read_text())
r=scan(out/'project',old);save(out/'C1.json',r)
assert r['reused']==['main.o','helper.o'] and r['refreshed']==[]
assert r['findings']==old['findings'] and r['added']==[] and r['resolved']==[]
print('C1_REUSE_PASS',r['reused'])
PY

printf "\nMANUAL_BLOCK=6\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import sys,time
from lab import commit,run
out=Path(sys.argv[1]);p=out/'project';time.sleep(1.05)
f=p/'main.c';f.write_text('#include "extra.h"\n'+f.read_text())
print('C2',commit(p,'C2 include change'))
(out/'C2-build.log').write_text(run(['make','app'],p))
print((out/'C2-build.log').read_text())
PY

printf "\nMANUAL_BLOCK=7\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import json,sys
from lab import scan,save
out=Path(sys.argv[1]);old=json.loads((out/'C1.json').read_text())
r=scan(out/'project',old);save(out/'C2.json',r)
assert set(r['refreshed'])=={'main.o','helper.o'}
assert ['MISSING','main.o','extra.h'] in r['added']
assert 'extra.h' in r['actual']['main.o']
print('C2_REFRESH_PASS',r['added'])
PY

printf "\nMANUAL_BLOCK=8\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import sys
from lab import commit
out=Path(sys.argv[1]);p=out/'project';f=p/'Makefile'
f.write_text(f.read_text().replace('main.c unused.h','main.c unused.h config.h extra.h'))
print('C3',commit(p,'C3 repair declarations'))
print(f.read_text())
PY

printf "\nMANUAL_BLOCK=9\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import json,sys
from lab import scan,save
out=Path(sys.argv[1]);old=json.loads((out/'C2.json').read_text())
r=scan(out/'project',old);save(out/'C3.json',r)
assert r['reused']==['main.o','helper.o']
assert sorted(r['resolved'])==[['MISSING','main.o','config.h'],['MISSING','main.o','extra.h']]
assert r['findings']==[{'type':'REDUNDANT','target':'main.o','dependency':'unused.h'}]
print('C3_RESOLVED_PASS',r['resolved'])
PY

printf "\nMANUAL_BLOCK=10\n"
git -C "$OUT/project" log --oneline --reverse
python3 - "$OUT" <<'PY'
from pathlib import Path
import sys,json
out=Path(sys.argv[1])
for name in ['baseline','C1','C2','C3']:
 r=json.loads((out/(name+'.json')).read_text())
 print(name,r['commit'],r['reused'],r['refreshed'],r['added'],r['resolved'])
PY

printf "STAGE_COMPLETE=%s OUT=%s\n" e9 "$OUT"
