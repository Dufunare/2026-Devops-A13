"""Operator-only C5 wrong-patch validation and new-job recovery preflight.

Use B's existing validator inside the verified DRAFT service, with its
actual successful image and a private clone of the original C1. Do not
expose an arbitrary bad-patch operation through the public-facing gateway
or weaken the broker's exact generated-patch check. Controlled fixture only.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from e14_gate import (ROOT, GateError, require, save, load, sha, get_health,
                      service_containers, verify_continuity, compose_logs)
from orchestrate import container_path, snapshot
from draft_executor import operation_tags, identity
from execution_attestation import verify_job
from real_job_gate import verify_result
from real_job_fault_gate import tree_snapshot, run_job


def derive_bad_patch(raw):
    text = raw.decode('utf-8')
    lines = text.splitlines(keepends=True)
    matches = [i for i,line in enumerate(lines)
               if line.startswith('+main.o: ') and re.search(r'\bextra\.h\b',line)]
    require(len(matches)==1,'C5_CONTROLLED_PATCH_SHAPE')
    i=matches[0]
    require(lines[i].count('extra.h')==1 and 'config.h' in lines[i],
            'C5_CONTROLLED_PATCH_SHAPE')
    lines[i]=lines[i].replace('extra.h','unused.h')
    wrong=''.join(lines).encode('utf-8')
    require(wrong!=raw,'C5_PATCH_NOT_CHANGED')
    return wrong


def pristine(project):
    env=os.environ.copy()
    env['GIT_OPTIONAL_LOCKS']='0'
    def git(*args):
        return subprocess.check_output(['git','-C',str(project),*args],
                                       env=env,text=True,timeout=30).strip()
    tracked={}
    for name in git('ls-files').splitlines():
        path=project/name
        require(path.is_file() and not path.is_symlink() and
                path.resolve().is_relative_to(project.resolve()),'C5_TRACKED_PATH_INVALID')
        tracked[name]=sha(path)
    return {'commit':git('rev-parse','HEAD'),'status':git('status','--porcelain'),
            'makefile_sha256':sha(project/'Makefile'),'tracked_sha256':tracked}


def verify_rejection(root, case, course_source):
    before,after=load(root/'before.json'),load(root/'after.json')
    require(before==after and before['status']=='' and
            before['commit']==case['target_commit'] and pristine(root/'project')==before,
            'C5_SOURCE_CHANGED')
    require(sha(root/'wrong.patch')==case['wrong_patch_sha256'],'C5_PATCH_CHANGED')
    verdict=load(root/'validation/validation.json')
    require(verdict.get('accepted') is False and verdict.get('rollback') is True and
            verdict.get('source_unchanged') is True and verdict.get('error') is None and
            verdict.get('executed_in')=='image:'+case['draft_image_id'],
            'C5_VALIDATION_DID_NOT_ROLLBACK')
    require(verdict.get('checks')=={'patch_applies':True,'build':True,'test':True,
                                    'header_change':True,'no_missing':False},
            'C5_WRONG_FAILURE_REASON')
    missing=sorted((f['target'],f['dependency']) for f in
                   load(root/'validation/recheck.json')['findings'] if f['type']=='MISSING')
    require(missing==[('main.o','extra.h')],'C5_EXPECTED_MISSING_NOT_PRESERVED')
    tags=operation_tags(case['profile'])['validate']
    checked=verify_job(root/'validation',case['draft_image_id'],course_source,tags)
    require(set(checked['verified_tags'])==set(tags),'C5_CHILD_EVIDENCE_MISMATCH')
    return {'status':'PASS','rollback':True,'source_unchanged':True,
            'makefile_sha256':before['makefile_sha256'],'missing':missing,
            'wrong_patch_sha256':case['wrong_patch_sha256'],
            'validation_children_verified':len(tags),'draft_image_id':case['draft_image_id']}


def worker(root):
    # This path is invoked locally by the operator, never from a service route.
    root=root.resolve()
    require(root.is_relative_to(ROOT/'work') and not (root/'validation').exists(),
            'C5_WORKER_ROOT_INVALID')
    case=load(root/'case.json')
    require(sha(root/'wrong.patch')==case['wrong_patch_sha256'],'C5_PATCH_CHANGED')
    sys.path[:0]=[str(ROOT/'labs/e8e10'),str(ROOT/'labs/e11e12')]
    from lab import validate
    before=pristine(root/'project')
    require(before['commit']==case['target_commit'] and before['status']=='',
            'C5_ORIGINAL_NOT_PRISTINE')
    save(root/'before.json',before)
    validate(root/'project',root/'wrong.patch',root/'validation',
             profile=case['profile'],exec_image=case['draft_image_id'])
    save(root/'after.json',pristine(root/'project'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--worker',type=Path)
    p.add_argument('--request',type=Path)
    p.add_argument('--request-sha256')
    p.add_argument('--candidate-sha256')
    p.add_argument('--success-out',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--project')
    p.add_argument('--image')
    a=p.parse_args()
    if a.worker is not None:
        worker(a.worker)
        return
    require(all(x is not None for x in (a.request,a.request_sha256,a.candidate_sha256,
                                       a.success_out,a.out,a.project,a.image)),'C5_ARGUMENTS_MISSING')
    out,prior=a.out.resolve(),a.success_out.resolve()
    require(out.is_relative_to(ROOT/'work') and out!=ROOT/'work' and not out.exists()
            and prior.is_relative_to(ROOT/'work') and not out.is_relative_to(prior),
            'C5_FRESH_DIRECTORY_REQUIRED')
    out.mkdir(parents=True)
    try:
        require(sha(a.request)==a.request_sha256 and load(prior/'summary.json')['status']=='PASS',
                'C5_PRIOR_INPUT_MISMATCH')
        normal=verify_result(prior/'job',a.request_sha256,a.candidate_sha256)
        old=tree_snapshot(prior)
        save(out/'prior-snapshot.json',old)
        save(out/'health-before.json',get_health())
        before=service_containers(out,a.project,a.image,'before')
        verify_continuity(load(prior/'containers-after.json')['services'],before,'prior','before')
        case_dir=out/'case'
        case_dir.mkdir()
        profile=load(prior/'job/result.json')['profile']
        require(profile['build_target']=='app' and profile['header_check']=='output',
                'C5_CONTROLLED_FIXTURE_ONLY')
        target=case_dir/'project'
        require(snapshot(prior/'job/target-project',normal['target_commit'],target,
                         case_dir/'git-logs',profile)==normal['target_commit'],'C5_CLONE_MISMATCH')
        good=(prior/'job/repair-work/candidate.patch').read_bytes()
        (case_dir/'good.patch').write_bytes(good)
        (case_dir/'wrong.patch').write_bytes(derive_bad_patch(good))
        case={**identity(normal),'profile':profile,
              'good_patch_sha256':sha(case_dir/'good.patch'),
              'wrong_patch_sha256':sha(case_dir/'wrong.patch')}
        save(case_dir/'case.json',case)
        argv=['docker','exec',before['draft']['container_id'],'python3',
              '/course/labs/e13e14/pair_c5_gate.py','--worker',container_path(case_dir)]
        save(out/'worker-command.json',argv)
        with (out/'worker.log').open('w') as stream:
            proc=subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT,timeout=7200)
        require(proc.returncode==0,'C5_WORKER_FAILED')
        rejected=verify_rejection(case_dir,case,str(ROOT.resolve()))
        require(sha(case_dir/'good.patch')==case['good_patch_sha256'] and
                tree_snapshot(prior)==old,'C5_PRIOR_EVIDENCE_CHANGED')
        save(out/'rejection-summary.json',rejected)
        case_snapshot=tree_snapshot(case_dir)
        save(out/'health-after-rejection.json',get_health())
        after=service_containers(out,a.project,a.image,'after-rejection')
        verify_continuity(before,after,'before','after-rejection')
        recovery=out/'recovery'
        run_job(a.request,recovery,out/'recovery.console.log',0)
        recovered=verify_result(recovery,a.request_sha256,a.candidate_sha256)
        require(recovered['job_id']!=normal['job_id'] and recovered['trace_id']!=normal['trace_id'],
                'C5_RECOVERY_ID_REUSED')
        require(tree_snapshot(case_dir)==case_snapshot and tree_snapshot(prior)==old,
                'C5_EVIDENCE_CHANGED')
        save(out/'health-after-recovery.json',get_health())
        final=service_containers(out,a.project,a.image,'after-recovery')
        continuity=verify_continuity(after,final,'after-rejection','after-recovery')
        compose_logs(out,a.project,a.image)
        summary={'status':'PASS','scope':'operator-side controlled C5; not HTTP or bilateral C5',
                 'prior_job':normal['job_id'],'rejection':rejected,'recovery':recovered,
                 'service_continuity':continuity,'prior_and_rejection_unchanged':True}
        save(out/'summary.json',summary)
        print('E14_C5_VALIDATOR_PREFLIGHT=PASS',flush=True)
        print(json.dumps(summary,ensure_ascii=False))
    except (GateError,ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        save(out/'summary.json',{'status':'FAIL','error':str(exc)})
        raise SystemExit('E14_C5_VALIDATOR_PREFLIGHT=FAIL: '+str(exc))


if __name__=='__main__':
    main()
