"""Remote consumer of B13 member2-e14-1; no local Docker/SSH administration.

start runs DRAFT and two full requests (C4: DRAFT and timeout only).
finish consumes the two actual server originals and resumes the same job.
C5 pauses after bad-repair; recover verifies peer rollback originals before good repair.
This is a client receipt, not proof of server cleanup or bilateral acceptance.
"""
import argparse
import http.client
import json
import re
import uuid
from pathlib import Path, PurePosixPath

from b13_wire import (Wire, pin, pinned_file, json_file, record, original_response,
                      canonical, digest, strict_json, need, HASH, COMMIT, JOB, TRACE,
                      IMAGE, CID, save, read_credential)

PROTOCOL='member2-e14-1'
ROLES=('buildchecker','echecker','draft','mdfixer')
SCENARIOS=('normal','C4','C5')


def remote_path(value, prefix):
    need(isinstance(value,str) and re.fullmatch(r'/[A-Za-z0-9_./-]+',value)
         and all(p not in ('','.','..','.git') for p in value[1:].split('/'))
         and value.startswith(prefix+'/'),'INVALID_REMOTE_PATH')
    return value


def findings(value):
    need(isinstance(value,list),'FINDINGS_NOT_LIST')
    rows=[]
    for row in value:
        need(isinstance(row,dict) and row.get('type') in ('MISSING','REDUNDANT')
             and all(isinstance(row.get(k),str) and row[k] for k in ('target','dependency')),
             'FINDING_INVALID')
        rows.append((row['type'],row['target'],row['dependency']))
    need(len(rows)==len(set(rows)),'DUPLICATE_FINDING')
    return set(rows)


def load_inputs(session_raw, manifest_raw, profile_raw, candidate_raw):
    s=strict_json(session_raw);m=strict_json(manifest_raw);p=strict_json(profile_raw)
    need(set(s)=={'schema_version','scenario','service_source_sha','service_image_id',
         'job_id','trace_id','run_root','candidate_path','ports','manifest_sha256',
         'profile_raw_sha256','profile_canonical_sha256','candidate_sha256'},
         'SESSION_FIELDS_INVALID')
    need(s['schema_version']=='b13-sync-session-1' and s['scenario'] in SCENARIOS
         and COMMIT.fullmatch(s['service_source_sha']) and IMAGE.fullmatch(s['service_image_id'])
         and JOB.fullmatch(s['job_id']) and TRACE.fullmatch(s['trace_id']),'SESSION_IDENTITY_INVALID')
    remote_path(s['run_root'],'/course/work')
    remote_path(s['candidate_path'],'/course/data')
    ports=s['ports']
    need(isinstance(ports,dict) and set(ports)==set(ROLES) and
         all(type(v) is int and 1024<=v<=65535 for v in ports.values()) and
         len(set(ports.values()))==4,'PORT_MAPPING_INVALID')
    pin(manifest_raw,s['manifest_sha256'],'MANIFEST')
    pin(profile_raw,s['profile_raw_sha256'],'PROFILE_RAW')
    pin(canonical(p),s['profile_canonical_sha256'],'PROFILE_CANONICAL')
    pin(candidate_raw,s['candidate_sha256'],'CANDIDATE')
    need(m.get('schema_version')=='b13-e14-project-1' and
         m['profile']==p and m['project_id']==p['id'] and
         m['profile_sha256']==s['profile_canonical_sha256'] and
         m['candidate_sha256']==s['candidate_sha256'] and
         all(COMMIT.fullmatch(m[k]) for k in ('base','target')) and m['base']!=m['target'],
         'PROJECT_MANIFEST_BINDING_INVALID')
    for side in ('base','target'):
        fs=m[side+'_files']
        need(isinstance(fs,dict) and 'Makefile' in fs and all(
             isinstance(k,str) and isinstance(v,str) and HASH.fullmatch(v)
             for k,v in fs.items()),'MANIFEST_SOURCE_FINGERPRINT_INVALID')
    expected=findings(m['expected_missing'])
    need(expected and all(row[0]=='MISSING' for row in expected),'EXPECTED_MISSING_INVALID')
    return s,m


class Client:
    def __init__(self,out,s,m,credential,timeout=2000):
        self.out,self.s,self.m=Path(out),s,m
        self.root=s['run_root']+'/jobs/'+s['job_id']
        self.common={k:m[k] for k in ('base','target','profile','profile_sha256','candidate_sha256','project_id')}
        self.common.update(protocol=PROTOCOL,job_id=s['job_id'],trace_id=s['trace_id'])
        self.wires={role:Wire(out,port,credential,timeout) for role,port in s['ports'].items()}

    def health(self,prefix):
        for role in ROLES:
            got=self.wires[role].obj(prefix+'-'+role,'GET','/health')
            need((got.get('status'),got.get('role'),got.get('protocol'))==
                 ('ok',role,PROTOCOL),'HEALTH_ROLE_PROTOCOL_MISMATCH')

    def call(self,label,role,name,side='target',**extra):
        body=dict(self.common,project=self.root+'/'+side,out=self.root+'/'+name,**extra)
        return self.wires[role].obj(label,'POST','/v1/run',body)

    def draft(self,response):
        image=response.get('image_id','')
        need(response.get('status')=='SUCCEEDED' and IMAGE.fullmatch(image),'DRAFT_NOT_SUCCEEDED')
        binding=response['binding']
        for k in ('job_id','trace_id','project_id','base','target','profile_sha256','candidate_sha256'):
            need(binding[k]==self.common[k],'DRAFT_BINDING_MISMATCH_'+k)
        need(binding['image_id']==image and binding['files']=={
             side:self.m[side+'_files'] for side in ('base','target')},'DRAFT_SOURCE_BINDING_MISMATCH')
        result=response['result']
        need(result.get('status')=='SUCCEEDED' and result.get('candidate_sha256')==self.m['candidate_sha256']
             and result['attempts'][-1]['image_id']==image,'DRAFT_BUILD_ORIGINAL_MISMATCH')
        self.common['image_id']=image
        return image

    def bound(self,response,status):
        need(response.get('status')==status and all(response.get(k)==self.common[k]
             for k in ('job_id','trace_id','profile_sha256','image_id'))
             and response.get('cleanup_verified') is True and response.get('source_unchanged') is True,
             'ROLE_RESULT_BINDING_OR_CLEANUP_MISMATCH')

    def worker(self,response,status,operation,source=None):
        self.bound(response,status)
        w=response['execution']
        need(w.get('operation')==operation and w.get('image_id')==self.common['image_id']
             and w.get('actual_container_image')==self.common['image_id']
             and CID.fullmatch(w.get('container_id','')) and w.get('container_exit_code')==0
             and w.get('profile_sha256')==self.common['profile_sha256'],
             'WORKER_WITNESS_MISMATCH')
        if source is not None:
            need(w.get('input_source_sha256')==source,'WORKER_SOURCE_MISMATCH')
        return w

    def full(self,response,side,final=False):
        w=self.worker(response,'SUCCEEDED','full',None if final else self.m[side+'_files'])
        result=response['result']
        need(result==response['payload'] and result['status']=='SUCCEEDED'
             and result.get('profile_sha256')==self.m['profile_sha256']
             and result['whole_project_findings']==result['findings'],
             'FULL_RESULT_MISMATCH')
        f=findings(result['findings'])
        missing={x for x in f if x[0]=='MISSING'}
        need(missing==(findings(self.m['expected_missing']) if side=='target' and not final else set()),
             'FULL_MISSING_SET_MISMATCH')
        if final:
            before=self.m['target_files'];after=w['input_source_sha256']
            need(set(before)==set(after) and [k for k in before if before[k]!=after[k]]==['Makefile'],
                 'FINAL_SOURCE_CHANGE_SCOPE_MISMATCH')
        return result

    def start(self):
        self.health('start-health')
        image=self.draft(self.call('01-draft','draft','draft',candidate=self.s['candidate_path'],
                                  build_timeout=self.m.get('build_timeout',900)))
        if self.s['scenario']=='C4':
            timed=self.call('02-timeout-full','buildchecker','timeout-full',fault='sleep',timeout_seconds=1)
            self.bound(timed,'TIMED_OUT')
            need(CID.fullmatch(timed.get('container_id','')) and timed.get('operation')=='full',
                 'C4_ACTUAL_CHILD_MISSING')
            return self.summary('C4_CLIENT_TIMEOUT_OBSERVED',image,2)
        self.full(self.call('02-baseline-full','buildchecker','baseline-full','base'),'base')
        self.full(self.call('03-target-full','buildchecker','target-full'),'target')
        result=self.summary('WAITING_FOR_FULL_ORIGINALS',image,3)
        result['required_server_originals']=[self.root+'/baseline-full/actual-graph.json',
                                             self.root+'/target-full/findings.json']
        return result

    def incremental_refs(self,inc):
        need(inc.get('status')=='SUCCEEDED' and all(inc.get(k)==self.common[k]
             for k in ('job_id','trace_id')),'INCREMENTAL_IDENTITY_MISMATCH')
        refs={k:inc[k] for k in ('report','report_sha256','payload','payload_sha256')}
        need(refs['report']==self.root+'/incremental/incremental-check.json' and
             refs['payload']==self.root+'/incremental/incremental-report.json' and
             HASH.fullmatch(refs['report_sha256']) and HASH.fullmatch(refs['payload_sha256']),
             'INCREMENTAL_REFERENCE_MISMATCH')
        return refs

    def bad_repair(self,bad):
        w=self.worker(bad,'REJECTED','validate',self.m['target_files'])
        verdict=bad['payload']
        need(verdict.get('accepted') is False and verdict.get('rollback') is True and
             verdict.get('source_unchanged') is True and verdict.get('error') and
             not verdict.get('checks',{}).get('patch_applies',False),'C5_NOT_EXPECTED_PATCH_REJECTION')
        return w

    def finish(self,graph_raw,graph_sha,findings_raw,findings_sha):
        need(self.s['scenario'] in ('normal','C5'),'C4_HAS_NO_FINISH')
        need(not (self.out/'wire/04-incremental').exists(),'POST_ALREADY_ATTEMPTED_RECONCILE')
        image=self.draft(original_response(self.out,'01-draft'))
        self.full(original_response(self.out,'02-baseline-full'),'base')
        target=self.full(original_response(self.out,'03-target-full'),'target')
        pin(graph_raw,graph_sha,'BASELINE_GRAPH')
        pin(findings_raw,findings_sha,'TARGET_FINDINGS')
        graph=json.loads(graph_raw)
        need(isinstance(graph,list) and all(isinstance(row,dict) and
             all(isinstance(row.get(k),str) and row[k] for k in ('target','dependency'))
             for row in graph),'BASELINE_GRAPH_INVALID')
        need(strict_json(findings_raw)==target,'TARGET_FINDINGS_DIFFERS_FROM_HTTP_PAYLOAD')
        save(self.out/'handoff/actual-graph.json',graph_raw)
        save(self.out/'handoff/findings.json',findings_raw)
        record(self.out/'handoff/hashes.json',{'baseline_graph_sha256':graph_sha,
                                             'target_findings_sha256':findings_sha})
        self.health('finish-health')
        inc=self.call('04-incremental','echecker','incremental',
                     base_project=self.root+'/base',
                     baseline_graph=self.root+'/baseline-full/actual-graph.json',
                     baseline_graph_sha256=graph_sha,
                     target_findings=self.root+'/target-full/findings.json',
                     target_findings_sha256=findings_sha)
        refs=self.incremental_refs(inc)
        if self.s['scenario']=='C5':
            bad=self.call('05-bad-repair','mdfixer','bad-repair',fault_patch=True,**refs)
            w=self.bad_repair(bad)
            result=self.summary('WAITING_FOR_C5_ROLLBACK_ORIGINALS',image,5)
            result.update(bad_container_id=w['container_id'],
                          bad_response_sha256=digest((self.out/'wire/05-bad-repair/response.body').read_bytes()),
                          required_handoff='c5-handoff-1')
            return result
        return self.good_and_final(image,refs,5,[])

    def recover(self,handoff,manifest_raw,manifest_sha):
        need(self.s['scenario']=='C5','RECOVERY_REQUIRES_C5')
        need(not (self.out/'wire/06-repair').exists(),'POST_ALREADY_ATTEMPTED_RECONCILE')
        image=self.draft(original_response(self.out,'01-draft'))
        self.full(original_response(self.out,'02-baseline-full'),'base')
        self.full(original_response(self.out,'03-target-full'),'target')
        refs=self.incremental_refs(original_response(self.out,'04-incremental'))
        bad=original_response(self.out,'05-bad-repair')
        w=self.bad_repair(bad)
        pin(manifest_raw,manifest_sha,'C5_HANDOFF_MANIFEST')
        manifest=strict_json(manifest_raw)
        need(set(manifest)=={'schema_version','job_id','trace_id','bad_response_sha256','files'}
             and manifest['schema_version']=='c5-handoff-1'
             and all(manifest[k]==self.s[k] for k in ('job_id','trace_id'))
             and manifest['bad_response_sha256']==digest(
                 (self.out/'wire/05-bad-repair/response.body').read_bytes()),
             'C5_HANDOFF_IDENTITY_MISMATCH')
        # Use B13's own original names, including raw source snapshots.
        expected=self.m['target_files']
        fixed={'source-before.json','after-bad-source.json','git-before.txt','after-bad-git.txt',
               'bad-repair/runtime/output/evidence/apply-check.stderr',
               'bad-repair/runtime/cleanup.json','bad-repair/runtime/execution.json'}
        names=fixed|{prefix+'/'+name for prefix in ('source-before-bytes','source-after-bad-bytes')
                     for name in expected}
        need(isinstance(manifest['files'],dict) and set(manifest['files'])==names,
             'C5_HANDOFF_FILES_MISMATCH')
        root=Path(handoff).resolve()
        originals={}
        for name in sorted(names):
            parts=name.split('/')
            need(all(re.fullmatch(r'[A-Za-z0-9_.-]+',p) and p not in ('.','..','.git')
                     for p in parts),'C5_HANDOFF_PATH_INVALID')
            path=root.joinpath(*parts)
            need(path.is_file() and path.resolve()==path and not path.is_symlink(),
                 'C5_HANDOFF_ORIGINAL_MISSING')
            meta=manifest['files'][name]
            need(isinstance(meta,dict) and set(meta)=={'bytes','sha256'} and
                 type(meta['bytes']) is int and 0<=meta['bytes']<=64*1024*1024
                 and path.stat().st_size==meta['bytes'],'C5_HANDOFF_SIZE_MISMATCH')
            originals[name]=pin(path.read_bytes(),meta['sha256'],'C5_HANDOFF_ORIGINAL')
            credential=self.wires['mdfixer'].credential
            need(credential is None or credential not in originals[name],
                 'CREDENTIAL_IN_C5_HANDOFF')
        need(strict_json(originals['source-before.json'])==expected==
             strict_json(originals['after-bad-source.json']),'C5_SOURCE_FINGERPRINT_MISMATCH')
        need(originals['git-before.txt']==originals['after-bad-git.txt']==b'',
             'C5_GIT_NOT_UNCHANGED_PRISTINE')
        for name,sha in expected.items():
            before=originals['source-before-bytes/'+name]
            after=originals['source-after-bad-bytes/'+name]
            need(before==after and digest(before)==sha,'C5_SOURCE_BYTES_MISMATCH')
        need(bool(originals['bad-repair/runtime/output/evidence/apply-check.stderr'].strip()),
             'C5_APPLY_CHECK_STDERR_MISSING')
        need(strict_json(originals['bad-repair/runtime/execution.json'])==w,
             'C5_EXECUTION_ORIGINAL_MISMATCH')
        cleanup=strict_json(originals['bad-repair/runtime/cleanup.json'])
        need(re.fullmatch(r'[0-9a-f]{32}',w.get('ownership_label',''))
             and cleanup.get('ownership_label')==w['ownership_label']
             and cleanup.get('removed')==[w['container_id']]
             and cleanup.get('verified_no_owned_containers') is True
             and not cleanup.get('error'),'C5_CLEANUP_ORIGINAL_MISMATCH')
        for name,raw in originals.items():
            save(self.out/'c5-handoff'/name,raw)
        save(self.out/'c5-handoff/manifest.original.json',manifest_raw)
        record(self.out/'c5-handoff/verified.json',{'status':'PASS','job_id':self.s['job_id'],
               'trace_id':self.s['trace_id'],'manifest_sha256':manifest_sha,
               'bad_container_id':w['container_id'],'originals_verified':len(originals),
               'scope':'peer supplied pre-correct-repair originals, not live daemon inspection'})
        self.health('recover-health')
        result=self.good_and_final(image,refs,6,[w['container_id']])
        result.update(c5_rollback_originals_verified=True,c5_handoff_sha256=manifest_sha)
        return result

    def good_and_final(self,image,refs,counter,children):
        good=self.call('%02d-repair'%counter,'mdfixer','repair',**refs)
        children.append(self.worker(good,'SUCCEEDED','validate',self.m['target_files'])['container_id'])
        verdict=good['payload']
        need(verdict.get('accepted') is True and isinstance(verdict.get('checks'),dict)
             and set(verdict['checks'])=={'patch_applies','build','test','header_change','no_missing'}
             and all(v is True for v in verdict['checks'].values()),'REPAIR_NOT_ACCEPTED')
        final=self.call('%02d-final-full'%(counter+1),'buildchecker','final-full')
        self.full(final,'target',True)
        children.extend([original_response(self.out,k)['execution']['container_id']
                         for k in ('02-baseline-full','03-target-full')])
        children.append(final['execution']['container_id'])
        need(len(children)==len(set(children)),'WORKER_CONTAINER_REUSED')
        result=self.summary('CLIENT_CHAIN_PASS',image,counter+1)
        result.update(remaining_missing=0,visible_worker_ids=children,
                      incremental_report_sha256=refs['report_sha256'],
                      incremental_payload_sha256=refs['payload_sha256'],
                      final_findings=final['result']['findings'])
        return result

    def summary(self,status,image,count):
        return {'status':status,'scenario':self.s['scenario'],'job_id':self.s['job_id'],
                'trace_id':self.s['trace_id'],'project_id':self.m['project_id'],
                'base':self.m['base'],'target':self.m['target'],
                'profile_sha256':self.m['profile_sha256'],'candidate_sha256':self.m['candidate_sha256'],
                'declared_service_source_sha':self.s['service_source_sha'],
                'declared_service_image_id':self.s['service_image_id'],'draft_image_id':image,
                'run_requests':count,'server_originals_verified':False,
                'formal_pair_acceptance':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='phase',required=True)
    start=sub.add_parser('start')
    for name in ('session','manifest','profile','candidate'):
        start.add_argument('--'+name,type=Path,required=True)
    start.add_argument('--session-sha256',required=True)
    finish=sub.add_parser('finish')
    finish.add_argument('--graph',type=Path,required=True)
    finish.add_argument('--graph-sha256',required=True)
    finish.add_argument('--findings',type=Path,required=True)
    finish.add_argument('--findings-sha256',required=True)
    recover=sub.add_parser('recover')
    recover.add_argument('--handoff',type=Path,required=True)
    recover.add_argument('--handoff-manifest',type=Path,required=True)
    recover.add_argument('--handoff-sha256',required=True)
    for q in (start,finish,recover):
        q.add_argument('--out',type=Path,required=True)
        q.add_argument('--http-timeout',type=int,default=2000)
    a=p.parse_args();out=a.out
    names=('session','manifest','profile','candidate')
    if a.phase=='start':
        raw=[getattr(a,n).read_bytes() for n in names]
        pin(raw[0],a.session_sha256,'SESSION')
        s,m=load_inputs(*raw)
        out.mkdir(parents=True,exist_ok=False)
        for n,v in zip(names,raw):
            save(out/'inputs'/n,v)
        record(out/'inputs/pin.json',{'session_sha256':a.session_sha256})
    else:
        raw=[(out/'inputs'/n).read_bytes() for n in names]
        pin(raw[0],json_file(out/'inputs/pin.json')['session_sha256'],'SESSION')
        s,m=load_inputs(*raw)
        prior=json_file(out/'start.json')
        need(prior['status']=='WAITING_FOR_FULL_ORIGINALS' and prior['job_id']==s['job_id']
             and prior['trace_id']==s['trace_id'],'START_NOT_READY')
        if a.phase=='finish':
            need(not (out/'finish.json').exists() and not (out/'wire/04-incremental').exists(),
                 'FINISH_ALREADY_ATTEMPTED_RECONCILE')
        else:
            prior=json_file(out/'finish.json')
            need(s['scenario']=='C5' and prior['status']=='WAITING_FOR_C5_ROLLBACK_ORIGINALS'
                 and prior['job_id']==s['job_id'] and prior['trace_id']==s['trace_id']
                 and not (out/'recover.json').exists() and not (out/'wire/06-repair').exists(),
                 'C5_RECOVERY_NOT_READY_OR_ALREADY_ATTEMPTED')
    # Prompt anew on each phase; never persist the credential.
    client=Client(out,s,m,read_credential(),a.http_timeout)
    try:
        if a.phase=='start':
            result=client.start()
        elif a.phase=='finish':
            result=client.finish(a.graph.read_bytes(),a.graph_sha256,
                                 a.findings.read_bytes(),a.findings_sha256)
        else:
            result=client.recover(a.handoff,a.handoff_manifest.read_bytes(),a.handoff_sha256)
        record(out/(a.phase+'.json'),result)
        print(canonical(result).decode('utf-8'))
    except (ValueError,KeyError,TypeError,OSError,http.client.HTTPException) as exc:
        record(out/('failure-'+uuid.uuid4().hex+'.json'),{'status':'FAIL',
               'phase':a.phase,'error_type':type(exc).__name__,
               'note':'Preserve wire originals; reconcile any attempted POST with B13 before retry'})
        raise SystemExit('B13_SYNC_CLIENT_FAILED: '+type(exc).__name__)


if __name__=='__main__':
    main()
