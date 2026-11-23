"""Compose the existing E5-E10 teaching components using versioned artifacts.

适配：通过请求 JSON 中可选的 "profile" 段支持不同目标名/源布局/构建目标/输出断言。
不传 profile 时行为与课程原版完全一致。
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'labs/e8e10'), str(ROOT / 'labs/e11e12/vendor'), '/app']
from lab import scan, patch, validate, resolve_profile
from exchange_profile import check_scan_flags, check_snapshot, digest, load_exchange_profile

class Failure(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def artifact(path, out, job_id):
    return {'uri': f'artifact://{job_id}/{path.relative_to(out).as_posix()}',
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes':path.stat().st_size}

def check_envelope(report, commit, kind=None):
    if report.get('schema_version') != 'e11e12-1':
        raise Failure('SCHEMA_MISMATCH', 'Expected e11e12-1')
    if report.get('commit') != commit:
        raise Failure('STALE_REPORT', 'Report belongs to another commit')
    if report.get('status') != 'SUCCEEDED':
        raise Failure('UPSTREAM_FAILED', 'Upstream stage did not succeed')
    if kind and report.get('kind') != kind:
        raise Failure('ARTIFACT_TYPE_MISMATCH', kind)

def load_artifact(path, expected_sha256):
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=expected_sha256:
        raise Failure('ARTIFACT_HASH_MISMATCH','Artifact content changed during transfer')
    return json.loads(data)

def command(argv, cwd, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120)
    log.write_text(p.stdout+p.stderr, encoding='utf-8')
    if p.returncode:
        raise Failure('COMMAND_FAILED', f'{argv[0]} failed; see {log.name}')
    return p.stdout.strip()

def shape_ok(dest, profile=None):
    """项目形状检查：根目录（或递归）的 *.c 名字集合必须与 profile.units 的源文件一致，
    且配置头存在。单独提出来便于测试，不依赖 git clone。"""
    prof = resolve_profile(profile)
    pattern = '**/*.c' if prof['recursive_scan'] else '*.c'
    names = {p.name for p in dest.glob(pattern) if '.git' not in p.parts}
    expected = {Path(src).name for _target, src in prof['units']}
    ok_sources = (names == expected) if prof['strict_sources'] else (expected <= names)
    return ok_sources and (dest / prof['config_file']).is_file(), names, expected

def snapshot(repo, revision, dest, logs, profile=None):
    prof = resolve_profile(profile)
    sha = command(['git','rev-parse','--verify',revision+'^{commit}'], repo, logs/(dest.name+'-resolve.log'))
    command(['git','clone','--no-hardlinks','--no-checkout',str(repo),str(dest)], repo, logs/(dest.name+'-clone.log'))
    command(['git','checkout','--detach',sha], dest, logs/(dest.name+'-checkout.log'))
    # E8-E10 profile; fail early instead of silently ignoring other targets.
    okc, names, expected = shape_ok(dest, prof)
    if not okc:
        raise Failure('UNSUPPORTED_PROJECT',
                      'Expected %s plus %s and explicit Make rules; found %s'
                      % ('/'.join(sorted(expected)), prof['config_file'], '/'.join(sorted(names)) or '(none)'))
    return sha

def full(project, folder, profile=None):
    from buildchecker.fullcheck import full_check
    prof = resolve_profile(profile)
    report = full_check(project, folder,
                        clean_command='make ' + prof['clean_target'],
                        build_command='make ' + prof['build_target'])
    if report.get('status') != 'SUCCEEDED':
        raise Failure('FULL_CHECK_FAILED', str(report.get('error', report.get('error_code'))))
    return report

def normalized(findings, profile=None):
    prof = resolve_profile(profile)
    targets = {t for t, _s in prof['units']}
    return sorted((f['type'], f['target'], f['dependency']) for f in findings if f['target'] in targets)

def read_fixed_report(request, target_sha):
    """Validate the received bytes before starting a potentially costly DRAFT build."""
    raw = Path(request['fixed_report']).read_bytes()
    expected = request.get('fixed_report_sha256')
    if expected is not None:
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise Failure('INVALID_REQUEST', 'fixed_report_sha256 must be a SHA256')
        if hashlib.sha256(raw).hexdigest() != expected:
            raise Failure('ARTIFACT_HASH_MISMATCH', 'Received fixed report bytes changed')
    from handoff import strict_json
    report = strict_json(raw)
    check_envelope(report, target_sha, 'fixed-md')
    if not isinstance(report.get('data'), dict) or report['data'].get('commit') != target_sha:
        raise Failure('STALE_REPORT', 'Fixed report data commit mismatch')
    return report, raw

def execute(request, out, job_id=None):
    job_id = job_id or 'job-'+uuid.uuid4().hex
    trace_id = 'trace-'+uuid.uuid4().hex
    if out.exists() and any(out.iterdir()):
        raise Failure('OUTPUT_EXISTS', 'Use a fresh output directory')
    out.mkdir(parents=True, exist_ok=True)
    result = {'schema_version':'e11e12-1','job_id':job_id,'trace_id':trace_id,'status':'RUNNING','stages':[]}
    save(out/'request.json',request)
    def stage(name, commit, payload, files=(), profile_sha=None):
        envelope = {'schema_version':'e11e12-1','job_id':job_id,'trace_id':trace_id,'kind':name,
                    'commit':commit,'status':'SUCCEEDED','data':payload,
                    'artifacts':[artifact(p,out,job_id) for p in files]}
        if profile_sha is not None:
            envelope['profile_sha256'] = profile_sha
        save(out/(name+'.json'),envelope)
        result['stages'].append({'name':name,'artifact':artifact(out/(name+'.json'),out,job_id)})
        return envelope
    try:
        mode=request['mode']
        if mode not in ('e11-a','e11-b','e12'):
            raise Failure('INVALID_REQUEST','Unknown mode')
        exchange_bytes, runtime_profile, exchange = load_exchange_profile(request)
        try:
            profile=resolve_profile(runtime_profile)
        except ValueError as exc:
            raise Failure('UNSUPPORTED_PROFILE', str(exc))
        repo=Path(request['repo']).resolve()
        if not repo.is_dir():
            raise Failure('INVALID_REQUEST','Repository missing')
        base=out/'base-project'; target=out/'target-project'
        base_sha=snapshot(repo,request['base'],base,out/'logs',profile)
        target_sha=snapshot(repo,request['target'],target,out/'logs',profile)
        result.update(base_commit=base_sha,target_commit=target_sha,profile=profile)
        if exchange is not None:
            check_snapshot(base, exchange)
            check_snapshot(target, exchange)
            (out/'exchange-profile.json').write_bytes(exchange_bytes)
        if mode == 'e11-b':
            fixed_envelope, fixed_raw = read_fixed_report(request, target_sha)
        if mode in ('e11-b','e12'):
            from draft.autobuild import auto_build
            candidate=Path(request['candidate']).resolve()
            draft=auto_build(target,candidate,out/'draft-build',request.get('expected_output','1'),timeout=request.get('build_timeout',600))
            if draft['status']!='SUCCEEDED':
                raise Failure('DRAFT_FAILED',draft.get('error','Inspect draft-build logs'))
            stage('draft',target_sha,draft,[out/'draft-build/result.json'])
            draft_image=next((a.get('image_id') for a in (draft.get('attempts') or []) if a.get('iteration')==2),None)
            result['draft_image_id']=draft_image
        else:
            draft_image=None

        # DRAFT 镜像贯通：profile.exec_image='draft' 时，下游检测/修复/复检全部在 DRAFT 镜像内执行。
        # fail-closed：声明了 draft 却拿不到完整 image ID 时直接失败，不静默回退编排环境。
        if profile['exec_image']=='draft' and not draft_image:
            raise Failure('DRAFT_IMAGE_MISSING','exec_image=draft 但未取得 DRAFT 完整 image ID')
        use_image = profile['exec_image']=='draft'
        result['downstream_executed_in']=('image:'+draft_image) if use_image else 'orchestrator'

        def run_full(project, folder, tag):
            if use_image:
                from imgrunner import full_in_image
                full_in_image(draft_image, project, folder,
                              'make '+profile['clean_target'], 'make '+profile['build_target'],
                              timeout=max(300, request.get('build_timeout',600)),
                              evidence=out/'inimage', tag=tag)
                report=json.loads((Path(folder)/'findings.json').read_text())
                if report.get('status')!='SUCCEEDED':
                    raise Failure('FULL_CHECK_FAILED', str(report.get('error')))
                return report
            return full(project, folder, profile)

        def run_scan(project, old_path, out_json, tag):
            if use_image:
                from imgrunner import scan_in_image
                return scan_in_image(draft_image, project, out_json, profile, old_path,
                                     timeout=max(300, request.get('build_timeout',600)),
                                     evidence=out/'inimage', tag=tag)
            old=json.loads(Path(old_path).read_text()) if old_path and Path(old_path).exists() else None
            report=scan(project, old, profile)
            Path(out_json).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
            return report

        if mode in ('e11-a','e12'):
            base_full=run_full(base,out/'baseline-full','full-check-baseline')
            old=run_scan(base,None,out/'baseline-cache.json','scan-baseline')
            if exchange is not None:
                check_scan_flags(old, exchange)
            edges=json.loads((out/'baseline-full/actual-graph.json').read_text())
            targets=[t for t,_s in profile['units']]
            projected={t:sorted({e['dependency'] for e in edges if e['target']==t}) for t in targets}
            if projected != old['actual']:
                raise Failure('GRAPH_MISMATCH','BuildChecker baseline differs from GCC observations')
            old['actual']=projected
            save(out/'baseline-cache.json',old)
            baseline=stage('full-check',base_sha,base_full,[out/'baseline-full/actual-graph.json',out/'baseline-full/findings.json',out/'baseline-cache.json'])
            check_envelope(baseline,base_sha,'full-check')
            current=run_scan(target,out/'baseline-cache.json',out/'incremental-report.json','scan-target')
            reference=run_full(target,out/'target-full','full-check-target')
            if normalized(reference['findings'],profile) != normalized(current['findings'],profile):
                raise Failure('FINDINGS_MISMATCH','Incremental/full object-target findings differ')
            profile_sha = None
            if exchange is not None:
                check_scan_flags(current, exchange)
                profile_sha = digest(exchange_bytes)
                current['profile_sha256'] = profile_sha
                save(out/'incremental-report.json', current)
                result.update(exchange_profile_id=exchange['id'], profile_sha256=profile_sha)
            md_envelope=stage('incremental-check',target_sha,current,[out/'incremental-report.json',out/'target-full/findings.json'],profile_sha=profile_sha)
        else:
            # E11-B still consumes a fixed MD input, separately from A's live output.
            envelope=fixed_envelope
            current=envelope['data']
            if current.get('commit') != target_sha:
                raise Failure('STALE_REPORT','Fixed report data commit mismatch')
            (out/'fixed-md-input.json').write_bytes(fixed_raw)
            md_envelope=stage('fixed-md',target_sha,current,[out/'fixed-md-input.json'])
        if mode in ('e11-b','e12'):
            reference=result['stages'][-1]['artifact']
            md_envelope=load_artifact(out/(md_envelope['kind']+'.json'),reference['sha256'])
            check_envelope(md_envelope,target_sha)
            current=md_envelope['data']
            before=(target/'Makefile').read_bytes()
            diff,edits=patch(target,current)
            if not diff:
                raise Failure('NO_MISSING_DEPENDENCY','No MD to repair')
            patchfile=out/'candidate.patch';patchfile.write_text(diff,encoding='utf-8')
            save(out/'repair-plan.json',edits)
            stage('repair',target_sha,{'edits':edits,'input_report':artifact(out/(md_envelope['kind']+'.json'),out,job_id)},[patchfile,out/'repair-plan.json'])
            verdict=validate(target,patchfile,out/'validation',profile=profile,
                             exec_image=draft_image if use_image else None)
            if not verdict['accepted']:
                raise Failure('REPAIR_REJECTED',str(verdict))
            final=run_full(target,out/'final-full','full-check-recheck')
            # 只对被 profile 纳入依赖检查的目标负责：非 profile 目标（例如内联编译的
            # 可执行目标）的头文件依赖不在本工具的修复范围内，不能据此判定修复失败。
            remaining=[f for f in normalized(final['findings'],profile) if f[0]=='MISSING']
            if remaining:
                (target/'Makefile').write_bytes(before)
                raise Failure('RECHECK_FAILED','MD remains for profile targets: %s' % (remaining,))
            stage('recheck',target_sha,{'validation':verdict,'findings':final['findings'],
                                        'profile_targets':[t for t,_s in profile['units']],
                                        'remaining_md':[],
                                        'patched_makefile_sha256':hashlib.sha256((target/'Makefile').read_bytes()).hexdigest()},[out/'validation/validation.json',out/'final-full/findings.json'])
        result['status']='SUCCEEDED'
    except (Failure,ValueError,OSError,KeyError,subprocess.TimeoutExpired) as exc:
        result.update(status='TIMED_OUT' if isinstance(exc,subprocess.TimeoutExpired) else 'FAILED',error={'code':getattr(exc,'code','EXECUTION_FAILED'),'message':str(exc)})
    result['artifacts']=[artifact(p,out,job_id) for p in sorted(out.rglob('*')) if p.is_file() and '.git' not in p.parts and not p.is_symlink()]
    save(out/'result.json',result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=execute(json.loads(a.request.read_text(encoding='utf-8')),a.out.resolve());print(json.dumps(r,ensure_ascii=False,indent=2));return 0 if r['status']=='SUCCEEDED' else 1

if __name__=='__main__':raise SystemExit(main())
