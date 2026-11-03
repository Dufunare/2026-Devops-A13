#!/usr/bin/env bash
set -eu
cd /root/devops-students/241830088/buildchecker
E8_PACK=/root/devops-materials/DevOps_E8_E10/03_实验包
source "$E8_PACK/classroom_helpers.sh"
lab_ready
lab_new_run e10 A
printf "\nMANUAL_BLOCK=1\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import sys
from lab import fixture,scan,save
out=Path(sys.argv[1])/'matrix';out.mkdir()
fixture(out/'project');save(out/'baseline.json',scan(out/'project'))
print('MATRIX_BASELINE_READY',out)
print((out/'project/Makefile').read_text())
PY

printf "\nMANUAL_BLOCK=2\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import csv,json,sys
from lab import scan,save,commit
out=Path(sys.argv[1])/'matrix';p=out/'project'
previous=json.loads((out/'baseline.json').read_text())
print('NO_SOURCE_CHANGE')
rows=[]
for repeat in range(1,6):
 inc=scan(p,previous);full=scan(p)
 equal=all(inc[k]==full[k] for k in ['actual','declared','findings'])
 save(out/f'unchanged-r{repeat}-incremental.json',inc)
 save(out/f'unchanged-r{repeat}-full.json',full)
 assert equal,'unchanged: dependency graph or findings differ'
 row={'case':'unchanged','repeat':repeat,'equal':equal,'incremental_s':inc['elapsed_s'],'full_s':full['elapsed_s'],'reused':len(inc['reused']),'refreshed':len(inc['refreshed'])}
 rows.append(row);print(row)
with (out/'results.csv').open('a',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]))
 if f.tell()==0:writer.writeheader()
 writer.writerows(rows)
save(out/'unchanged.json',inc)
print('UNCHANGED_FIVE_REPEATS_PASS')
PY

printf "\nMANUAL_BLOCK=3\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import csv,json,sys
from lab import scan,save,commit
out=Path(sys.argv[1])/'matrix';p=out/'project'
previous=json.loads((out/'unchanged.json').read_text())
(p/'helper.c').write_text('int helper(void){return 0+0;}\n')
print('COMMIT',commit(p,'body'))
rows=[]
for repeat in range(1,6):
 inc=scan(p,previous);full=scan(p)
 equal=all(inc[k]==full[k] for k in ['actual','declared','findings'])
 save(out/f'body-r{repeat}-incremental.json',inc)
 save(out/f'body-r{repeat}-full.json',full)
 assert equal,'body: dependency graph or findings differ'
 row={'case':'body','repeat':repeat,'equal':equal,'incremental_s':inc['elapsed_s'],'full_s':full['elapsed_s'],'reused':len(inc['reused']),'refreshed':len(inc['refreshed'])}
 rows.append(row);print(row)
with (out/'results.csv').open('a',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]))
 if f.tell()==0:writer.writeheader()
 writer.writerows(rows)
save(out/'body.json',inc)
print('BODY_FIVE_REPEATS_PASS')
PY

printf "\nMANUAL_BLOCK=4\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import csv,json,sys
from lab import scan,save,commit
out=Path(sys.argv[1])/'matrix';p=out/'project'
previous=json.loads((out/'body.json').read_text())
(p/'main.c').write_text('#include "extra.h"\n'+(p/'main.c').read_text())
print('COMMIT',commit(p,'include'))
rows=[]
for repeat in range(1,6):
 inc=scan(p,previous);full=scan(p)
 equal=all(inc[k]==full[k] for k in ['actual','declared','findings'])
 save(out/f'include-r{repeat}-incremental.json',inc)
 save(out/f'include-r{repeat}-full.json',full)
 assert equal,'include: dependency graph or findings differ'
 row={'case':'include','repeat':repeat,'equal':equal,'incremental_s':inc['elapsed_s'],'full_s':full['elapsed_s'],'reused':len(inc['reused']),'refreshed':len(inc['refreshed'])}
 rows.append(row);print(row)
with (out/'results.csv').open('a',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]))
 if f.tell()==0:writer.writeheader()
 writer.writerows(rows)
save(out/'include.json',inc)
print('INCLUDE_FIVE_REPEATS_PASS')
PY

printf "\nMANUAL_BLOCK=5\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import csv,json,sys
from lab import scan,save,commit
out=Path(sys.argv[1])/'matrix';p=out/'project'
previous=json.loads((out/'include.json').read_text())
f=p/'Makefile';f.write_text(f.read_text().replace('main.c unused.h','main.c unused.h config.h extra.h'))
print('COMMIT',commit(p,'declaration'))
rows=[]
for repeat in range(1,6):
 inc=scan(p,previous);full=scan(p)
 equal=all(inc[k]==full[k] for k in ['actual','declared','findings'])
 save(out/f'declaration-r{repeat}-incremental.json',inc)
 save(out/f'declaration-r{repeat}-full.json',full)
 assert equal,'declaration: dependency graph or findings differ'
 row={'case':'declaration','repeat':repeat,'equal':equal,'incremental_s':inc['elapsed_s'],'full_s':full['elapsed_s'],'reused':len(inc['reused']),'refreshed':len(inc['refreshed'])}
 rows.append(row);print(row)
with (out/'results.csv').open('a',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]))
 if f.tell()==0:writer.writeheader()
 writer.writerows(rows)
save(out/'declaration.json',inc)
print('DECLARATION_FIVE_REPEATS_PASS')
PY

printf "\nMANUAL_BLOCK=6\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import csv,json,sys
from lab import scan,save,commit
out=Path(sys.argv[1])/'matrix';p=out/'project'
previous=json.loads((out/'declaration.json').read_text())
f=p/'Makefile';f.write_text(f.read_text().replace('-O0','-O1'))
print('COMMIT',commit(p,'flags'))
rows=[]
for repeat in range(1,6):
 inc=scan(p,previous);full=scan(p)
 equal=all(inc[k]==full[k] for k in ['actual','declared','findings'])
 save(out/f'flags-r{repeat}-incremental.json',inc)
 save(out/f'flags-r{repeat}-full.json',full)
 assert equal,'flags: dependency graph or findings differ'
 row={'case':'flags','repeat':repeat,'equal':equal,'incremental_s':inc['elapsed_s'],'full_s':full['elapsed_s'],'reused':len(inc['reused']),'refreshed':len(inc['refreshed'])}
 rows.append(row);print(row)
with (out/'results.csv').open('a',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]))
 if f.tell()==0:writer.writeheader()
 writer.writerows(rows)
save(out/'flags.json',inc)
print('FLAGS_FIVE_REPEATS_PASS')
PY

printf "\nMANUAL_BLOCK=7\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import csv,json,sys
from lab import scan,save,commit
out=Path(sys.argv[1])/'matrix';p=out/'project'
previous=json.loads((out/'flags.json').read_text())
(p/'config.h').write_text('#include "extra.h"\n#define VALUE 1\n')
print('COMMIT',commit(p,'header'))
rows=[]
for repeat in range(1,6):
 inc=scan(p,previous);full=scan(p)
 equal=all(inc[k]==full[k] for k in ['actual','declared','findings'])
 save(out/f'header-r{repeat}-incremental.json',inc)
 save(out/f'header-r{repeat}-full.json',full)
 assert equal,'header: dependency graph or findings differ'
 row={'case':'header','repeat':repeat,'equal':equal,'incremental_s':inc['elapsed_s'],'full_s':full['elapsed_s'],'reused':len(inc['reused']),'refreshed':len(inc['refreshed'])}
 rows.append(row);print(row)
with (out/'results.csv').open('a',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]))
 if f.tell()==0:writer.writeheader()
 writer.writerows(rows)
save(out/'header.json',inc)
print('HEADER_FIVE_REPEATS_PASS')
PY

printf "\nMANUAL_BLOCK=8\n"
lab_python "$OUT" <<'PY'
from pathlib import Path
import csv,sys
from lab import buildchecker,save
out=Path(sys.argv[1])/'matrix';rows=list(csv.DictReader((out/'results.csv').open()))
assert len(rows)==30 and all(r['equal']=='True' for r in rows)
buildchecker(out/'project',out/'final-buildchecker')
save(out/'gate.json',{'track':'A','passed':True,'rows':len(rows)})
print('DYNAMIC_CROSSCHECK_AND_MATRIX_PASS')
PY

printf "\nMANUAL_BLOCK=9\n"
cat "$OUT/matrix/gate.json"
python3 - "$OUT" <<'PY'
from pathlib import Path
from collections import Counter
import csv,json,sys
out=Path(sys.argv[1])/'matrix';rows=list(csv.DictReader((out/'results.csv').open()))
assert len(rows)==30 and all(r['equal']=='True' for r in rows)
counts=Counter(r['case'] for r in rows)
assert set(counts)=={'unchanged','body','include','declaration','flags','header'}
assert all(v==5 for v in counts.values())
assert json.loads((out/'gate.json').read_text())['passed'] is True
print('MATRIX_PASS',dict(counts))
PY

printf "\nMANUAL_BLOCK=10\n"
python3 - "$OUT" <<'PY'
from pathlib import Path
import json,sys
p=Path(sys.argv[1])/'matrix'
for name in ['unchanged','body','include','declaration','flags','header']:
 r=json.loads((p/(name+'.json')).read_text())
 print(name,'reuse=',r['reused'],'refresh=',r['refreshed'],'findings=',r['findings'])
PY

printf "\nMANUAL_BLOCK=11\n"
python3 - "$OUT" <<'PY'
from pathlib import Path
from statistics import median
import csv,sys
p=Path(sys.argv[1])/'matrix';rows=list(csv.DictReader((p/'results.csv').open()))
with (p/'performance-summary.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['case','n','inc_median_s','full_median_s','inc_min_s','inc_max_s','full_over_inc'])
 for case in ['unchanged','body','include','declaration','flags','header']:
  group=[r for r in rows if r['case']==case]
  inc=[float(r['incremental_s']) for r in group];full=[float(r['full_s']) for r in group]
  mi,mf=median(inc),median(full);ratio=mf/mi if mi>0 else None
  result=[case,len(group),mi,mf,min(inc),max(inc),ratio]
  w.writerow(result);print(result)
print('SAVED',p/'performance-summary.csv')
PY

printf "\nMANUAL_BLOCK=12\n"
cat "$OUT/matrix/final-buildchecker/findings.json"
grep -n 'main.o:' "$OUT/matrix/final-buildchecker/make-db.txt" | head -n 8
ls "$OUT/matrix/final-buildchecker/trace" | head -n 8

printf "\nMANUAL_BLOCK=13\n"
grep -nE 'for repeat|passed=all|assert passed' labs/e8e10/lab.py
cat "$OUT/matrix/performance-summary.csv"
printf 'A E10：六类各五次，完整actual/declared/findings对照；性能为本机扫描耗时，最终另做BuildChecker对象目标交叉核对。
' > "$OUT/结论.txt"

printf "STAGE_COMPLETE=%s OUT=%s\n" e10 "$OUT"
