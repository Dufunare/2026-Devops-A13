#!/usr/bin/env bash
set -eu
cd /root/devops-students/241830088/buildchecker
E8_PACK=/root/devops-materials/DevOps_E8_E10/03_实验包
source "$E8_PACK/classroom_helpers.sh"
lab_ready
lab_new_run e8 A
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
from lab import scan,save
out=Path(sys.argv[1]); report=scan(out/'project')
save(out/'baseline.json',report)
print('actual =',report['actual'])
print('declared =',report['declared'])
print('findings =',report['findings'])
assert report['actual']['main.o']==['config.h','main.c']
assert {(f['type'],f['target'],f['dependency']) for f in report['findings']}=={
 ('MISSING','main.o','config.h'),('REDUNDANT','main.o','unused.h')}
print('BASELINE_PASS')
PY

printf "\nMANUAL_BLOCK=4\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import json,sys
from lab import buildchecker,save
out=Path(sys.argv[1]); buildchecker(out/'project',out/'buildchecker')
r=json.loads((out/'baseline.json').read_text())
edges=json.loads((out/'buildchecker/actual-graph.json').read_text())
r['actual']={t:sorted({e['dependency'] for e in edges if e['target']==t}) for t in ['main.o','helper.o']}
r['baseline_source']='BuildChecker actual-graph.json projected to object targets'
save(out/'baseline.json',r)
print('BUILDCHECKER_BASELINE_PASS',r['actual'])
PY

printf "\nMANUAL_BLOCK=5\n"
cat "$OUT/buildchecker/findings.json"
grep -n 'main.o:' "$OUT/buildchecker/make-db.txt" | head -n 8
grep -n 'config.h' "$OUT/buildchecker/trace/"* | head -n 12
python3 -m json.tool "$OUT/baseline.json"

printf "\nMANUAL_BLOCK=6\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import json,sys
from lab import scan,save
out=Path(sys.argv[1]); old=json.loads((out/'baseline.json').read_text())
r=scan(out/'project',old);save(out/'incremental.json',r)
assert r['actual']==old['actual']
assert r['findings']==old['findings']
assert r['reused']==['main.o','helper.o'] and r['refreshed']==[]
print('REUSE_PASS',r['reused'],r['refreshed'])
PY

printf "\nMANUAL_BLOCK=7\n"
git -C "$OUT/project" status --short
printf 'A E8：main.o缺config.h，冗余unused.h；历史图来源为本次BuildChecker；未变化时两个目标复用。
' > "$OUT/结论.txt"
cat "$OUT/结论.txt"
ls "$OUT"

printf "STAGE_COMPLETE=%s OUT=%s\n" e8 "$OUT"
