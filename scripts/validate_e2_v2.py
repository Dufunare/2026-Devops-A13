"""Semantic validation for Pair13 finding-report v2.0 candidate."""
from __future__ import annotations
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; EX=ROOT/"contracts"/"examples"/"v2"
SHA40=re.compile(r"^[0-9a-fA-F]{40}$"); JOB=re.compile(r"^job-[A-Za-z0-9-]+$"); EXT=re.compile(r"^(a13|b13|pair13)\.[A-Za-z0-9_.-]+$")
TOP={"schema_version","report_id","repository","configuration_id","environment","detector","provenance","producer_job_id","findings","artifact_locator","extensions"}
def load(p): return json.loads(p.read_text(encoding="utf-8"))
def nonempty(v): return isinstance(v,str) and bool(v.strip())
def safe(v):
    return nonempty(v) and not v.startswith("/") and not v.startswith("./") and "\\" not in v and all(x not in {"",".",".."} for x in v.split("/"))
def unknown(obj,allowed,where,e):
    x=sorted(set(obj)-allowed)
    if x:e.append(f"{where}: unknown core fields {x}")
def structure_errors(d):
    """Check the fixed v2 Schema's object/type constraints before semantics.

    No third-party dependency; this is the Pair13 contract, not a general
    JSON Schema interpreter. The published Schema itself remains unchanged.
    """
    errors=[]
    def obj(value,allowed,required,where):
        if not isinstance(value,dict):
            errors.append(where+": object required");return False
        unknown(value,set(allowed),where,errors)
        for key in required:
            if key not in value:errors.append(where+"."+key+": missing")
        return True
    def string(value,where):
        if not nonempty(value):errors.append(where+": non-empty string required")
    def extensions(value,where):
        if obj(value,value.keys() if isinstance(value,dict) else (),(),where):
            for key in value:
                if not isinstance(key,str) or not EXT.fullmatch(key):errors.append(where+": namespaced key required")
    def uri(value,where):
        if not isinstance(value,str) or not value.startswith("artifact://pair13/"):
            errors.append(where+": artifact://pair13/ URI string required")
    for key in ("report_id","configuration_id","provenance"):
        string(d.get(key),key)
    repository=d.get("repository")
    if obj(repository,("url","commit"),("url","commit"),"repository"):
        string(repository.get("url"),"repository.url")
    environment=d.get("environment")
    if obj(environment,("os","arch","make_version","cc_version","image_ref"),("os","arch"),"environment"):
        for key,value in environment.items():string(value,"environment."+key)
    if d.get("detector") not in ("BUILDCHECKER","ECHECKER","INSTRUCTOR_ORACLE","A13_MANUAL_ORACLE","B13_MANUAL_ORACLE"):
        errors.append("detector: invalid enum")
    if "producer_job_id" in d and d["producer_job_id"] is not None and not isinstance(d["producer_job_id"],str):
        errors.append("producer_job_id: string or null required")
    if "extensions" in d:extensions(d["extensions"],"extensions")
    if "artifact_locator" in d:
        loc=d["artifact_locator"]
        keys=("uri","repository_url","repository_commit","repository_path","sha256")
        if obj(loc,keys,keys,"artifact_locator"):
            uri(loc.get("uri"),"artifact_locator.uri")
            string(loc.get("repository_url"),"artifact_locator.repository_url")
            if not isinstance(loc.get("repository_commit"),str) or not SHA40.fullmatch(loc["repository_commit"]):errors.append("artifact_locator.repository_commit: 40-hex required")
            if not safe(loc.get("repository_path")):errors.append("artifact_locator.repository_path: expected safe project-relative POSIX path")
            if not isinstance(loc.get("sha256"),str) or not re.fullmatch(r"[0-9a-fA-F]{64}",loc["sha256"]):errors.append("artifact_locator.sha256: 64-hex required")
    findings=d.get("findings")
    if isinstance(findings,list):
        for i,finding in enumerate(findings):
            where=f"findings[{i}]"
            keys=("finding_id","type","target","dependency","commit","configuration_id","location","evidence","extensions")
            if not obj(finding,keys,("finding_id","type","target","dependency","location","evidence"),where):continue
            for key in ("finding_id","target"):string(finding.get(key),where+"."+key)
            if finding.get("type") not in ("MISSING","REDUNDANT"):errors.append(where+".type: invalid enum")
            if "configuration_id" in finding:string(finding["configuration_id"],where+".configuration_id")
            if "extensions" in finding:extensions(finding["extensions"],where+".extensions")
            location=finding.get("location")
            if isinstance(location,dict) and "declaration" in location:string(location["declaration"],where+".location.declaration")
            evidence=finding.get("evidence")
            if isinstance(evidence,list):
                for j,item in enumerate(evidence):
                    w=f"{where}.evidence[{j}]"
                    if obj(item,("kind","detail","uri"),("kind","detail"),w):
                        string(item.get("kind"),w+".kind");string(item.get("detail"),w+".detail")
                        if "uri" in item:uri(item["uri"],w+".uri")
    return errors
def validate_report(d):
    e=[]
    if not isinstance(d,dict): return ["root: expected object"]
    e=structure_errors(d)
    if e:return e
    unknown(d,TOP,"root",e)
    for k in ("schema_version","report_id","repository","configuration_id","environment","detector","provenance","findings"):
        if k not in d:e.append(f"{k}: missing")
    if d.get("schema_version")!="2.0":e.append("schema_version: expected 2.0")
    repo=d.get("repository") if isinstance(d.get("repository"),dict) else {}
    commit=repo.get("commit")
    if not isinstance(commit,str) or not SHA40.fullmatch(commit):e.append("repository.commit: 40-hex required")
    env=d.get("environment") if isinstance(d.get("environment"),dict) else {}
    for k in ("os","arch"):
        if not nonempty(env.get(k)):e.append(f"environment.{k}: required")
    det=d.get("detector"); job=d.get("producer_job_id")
    if det in {"BUILDCHECKER","ECHECKER"} and (not isinstance(job,str) or not JOB.fullmatch(job)):e.append("producer_job_id: real detector output requires job-*")
    if det not in {"BUILDCHECKER","ECHECKER"} and job is not None:e.append("producer_job_id: oracle reports must be null/absent")
    fs=d.get("findings")
    if not isinstance(fs,list): return e+["findings: array required"]
    for i,f in enumerate(fs):
        w=f"findings[{i}]"
        if not isinstance(f,dict):e.append(w+": object required");continue
        unknown(f,{"finding_id","type","target","dependency","commit","configuration_id","location","evidence","extensions"},w,e)
        if f.get("type") not in {"MISSING","REDUNDANT"}:e.append(w+".type invalid")
        if not safe(f.get("dependency")):e.append(w+".dependency: expected safe project-relative POSIX path")
        if "commit" in f and f.get("commit")!=commit:e.append(w+".commit: must equal repository.commit")
        if "configuration_id" in f and f.get("configuration_id")!=d.get("configuration_id"):e.append(w+".configuration_id: must equal top-level")
        loc=f.get("location")
        if not isinstance(loc,dict):e.append(w+".location: object required")
        elif loc.get("status")=="RESOLVED":
            unknown(loc,{"status","path","line","declaration"},w+".location",e)
            if not safe(loc.get("path")):e.append(w+".location.path invalid")
            if type(loc.get("line")) is not int or loc["line"]<1:e.append(w+".location.line invalid")
        elif loc.get("status")=="UNRESOLVED":
            unknown(loc,{"status","reason"},w+".location",e)
            if not nonempty(loc.get("reason")):e.append(w+".location.reason required")
        else:e.append(w+".location.status invalid")
        ev=f.get("evidence")
        if not isinstance(ev,list) or not ev:e.append(w+".evidence: non-empty array required")
        else:
            for j,item in enumerate(ev):
                if not isinstance(item,dict) or not nonempty(item.get("kind")) or not nonempty(item.get("detail")):e.append(f"{w}.evidence[{j}] invalid")
    ext=d.get("extensions")
    if ext is not None:
        if not isinstance(ext,dict):e.append("extensions: object required")
        else:
            for k in ext:
                if not EXT.fullmatch(k):e.append(f"extensions.{k}: namespaced key required")
    return e
def main():
    failures=[]
    p=EX/"md-report.valid.json"; x=validate_report(load(p))
    print(("PASS " if not x else "FAIL ")+str(p.relative_to(ROOT))); failures += x
    for p in sorted((EX/"invalid").glob("*.json")):
        x=validate_report(load(p))
        print(("EXPECTED REJECTION " if x else "FAIL ")+p.name)
        if not x:failures.append(p.name+" accepted")
    if failures:
        print("\n".join(failures),file=sys.stderr);return 1
    print("All Pair13 finding-report v2 semantic checks passed.");return 0
if __name__=="__main__":raise SystemExit(main())
