"""Run in B13's Linux experiment environment; not on a bare Windows host.
Usage: python3 B13_消费命令.py PACKAGE NEW_OUT B13_CONSUMER_PY
This never contacts a server and never modifies A13's originals.
"""
import hashlib,json,subprocess,sys
from pathlib import Path
package,out,consumer=map(lambda p:Path(p).resolve(),sys.argv[1:4])
if out.exists():raise SystemExit('OUT already exists; preserve it and choose a new path')
for line in (package/'SHA256SUMS').read_text().splitlines():
 expected,relative=line.split('  ',1)
 p=(package/relative).resolve()
 if not p.is_relative_to(package) or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise SystemExit('SHA mismatch: '+relative)
meta=json.loads((package/'manifest.json').read_text());out.mkdir(parents=True)
subprocess.run(['git','clone','--branch','handoff-target',str(package/'project.bundle'),str(out/'repo')],check=True)
cmd=[sys.executable,str(consumer),'--envelope',str(package/'incremental-check.json'),'--envelope-sha256',meta['original_files']['incremental-check.json']['sha256'],'--payload',str(package/'incremental-report.json'),'--payload-sha256',meta['original_files']['incremental-report.json']['sha256'],'--repo',str(out/'repo'),'--target',meta['target_commit'],'--job-id',meta['job_id'],'--trace-id',meta['trace_id'],'--out',str(out/'consumption'),'--source-label','A13-241830088-20261111']
(out/'command.json').write_text(json.dumps(cmd,ensure_ascii=False,indent=2)+'\n')
raise SystemExit(subprocess.call(cmd))
