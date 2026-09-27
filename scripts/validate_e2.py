"""Offline semantic checks for A13 E2 examples. Does not run the paper tools."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; EX=ROOT/"contracts"/"examples"; ART=ROOT/"contracts"/"artifacts"; SHA=re.compile(r"^[0-9a-fA-F]{40}$")
def load(p): return json.loads(p.read_text(encoding="utf-8"))
def repo_ok(r,e):
    if not isinstance(r,dict): e.append("repository required"); return
    if not r.get("url"): e.append("repository.url required")
    if not isinstance(r.get("commit"),str) or not SHA.fullmatch(r["commit"]): e.append("repository.commit must be 40-hex")
def validate_request(d):
    e=[]; k=d.get("job_type"); i=d.get("input")
    if k not in {"FULL_CHECK","INCREMENTAL_CHECK"}: return ["unsupported job_type"]
    if not isinstance(i,dict): return ["input required"]
    repo_ok(i.get("repository"),e); env=i.get("environment")
    if not isinstance(env,dict): return e+["environment required"]
    for f in ("image_ref","configuration_id","project_root"):
        if not env.get(f): e.append(f"environment.{f} required")
    if not i.get("build_command"): e.append("build_command required")
    if k=="FULL_CHECK":
        if not i.get("clean_command"): e.append("clean_command required")
    else:
        base=i.get("base_commit"); b=i.get("baseline")
        if not isinstance(base,str) or not SHA.fullmatch(base): e.append("base_commit must be 40-hex")
        if not isinstance(b,dict): e.append("baseline required")
        else:
            if b.get("commit")!=base: e.append("baseline.commit mismatch")
            if b.get("configuration_id")!=env.get("configuration_id"): e.append("baseline.configuration_id mismatch")
            if not str(b.get("actual_graph_uri","")).startswith("artifact://pair13/"): e.append("baseline actual_graph_uri invalid")
    return e
def validate_report(d):
    e=[]; r=d.get("repository"); repo_ok(r,e); cfg=d.get("configuration_id"); fs=d.get("findings")
    if not cfg: e.append("configuration_id required")
    if not isinstance(fs,list): return e+["findings array required"]
    for n,f in enumerate(fs):
        if f.get("type") not in {"MISSING","REDUNDANT"}: e.append(f"finding {n} type invalid")
        if isinstance(r,dict) and f.get("commit")!=r.get("commit"): e.append(f"finding {n} commit mismatch")
        if f.get("configuration_id")!=cfg: e.append(f"finding {n} config mismatch")
        if not isinstance(f.get("evidence"),list) or not f["evidence"]: e.append(f"finding {n} evidence required")
    return e
def main():
    bad=[]
    for n in ("full-check.request.json","incremental-check.request.json"):
        x=validate_request(load(EX/n)); print(("PASS " if not x else "FAIL ")+n); bad += [f"{n}: {z}" for z in x]
    for n in ("incremental-without-baseline.json","incremental-config-mismatch.json"):
        x=validate_request(load(EX/"invalid"/n)); print("EXPECTED REJECTION "+n if x else "FAIL "+n)
        if not x: bad.append(n+" was accepted")
    for p in (ART/"job-full-a13-001"/"md-report.json",ART/"job-incremental-a13-001"/"md-report.json"):
        x=validate_report(load(p)); print(("PASS " if not x else "FAIL ")+str(p.relative_to(ROOT))); bad += [f"{p}: {z}" for z in x]
    if bad:
        print("\n".join("FAIL "+x for x in bad),file=sys.stderr); return 1
    print("All A13 E2 semantic checks passed."); return 0
if __name__=="__main__": raise SystemExit(main())
