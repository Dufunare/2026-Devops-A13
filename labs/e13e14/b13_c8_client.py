"""B13 raw asynchronous E11/E12 API consumer, only through approved SSH.

Unlike A13 pair_c8_client this API has no Bearer facade or /v1/session.
B13 must approve the exact request and the 8081 forward beforehand.
"""
import argparse
import http.client
import json
import re
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from b13_wire import (Wire,pinned_file,pin,record,canonical,digest,strict_json,need,
                      HASH,COMMIT,JOB,TRACE,IMAGE,save)
from pair_session import artifact_index, STAGES


def verify_downloaded_operations(out,files,result,request,image):
    """Check the actual downloaded B13 ImageRuntime originals, not only summary IDs."""
    operations=result.get('image_operations')
    expected=['full','scan','scan','full','validate','full']
    need(isinstance(operations,list) and len(operations)==len(expected),'IMAGE_OPERATIONS_MISSING')
    ids=[]
    def read(name,object_only=True):
        need(name in files,'IMAGE_ORIGINAL_MISSING')
        raw=(out/'downloads'/name).read_bytes()
        return strict_json(raw) if object_only else raw
    for i,(op,kind) in enumerate(zip(operations,expected),1):
        prefix='image-execution/%02d-%s/'%(i,kind)
        cid=op.get('container_id','')
        commit=request['base'] if i<=2 else request['target']
        need(isinstance(cid,str) and re.fullmatch(r'[0-9a-f]{64}',cid)
             and op.get('operation')==kind and op.get('project_commit')==commit
             and op.get('container_exit_code')==0
             and op.get('image_id')==image and op.get('actual_container_image')==image
             and op.get('profile_sha256')==request.get('profile_sha256'),
             'IMAGE_OPERATION_MISMATCH')
        need(read(prefix+'execution.json')==op,'IMAGE_WITNESS_ORIGINAL_MISMATCH')
        commands={}
        for name in files:
            if name.startswith(prefix) and re.fullmatch(r'\d+-[a-z-]+\.command\.json',name[len(prefix):]):
                commands[name.removesuffix('.command.json')]=read(name)['argv']
        def one(action):
            found=[(name,argv) for name,argv in commands.items()
                   if isinstance(argv,list) and len(argv)>=2 and argv[:2]==['docker',action]]
            need(len(found)==1,'IMAGE_COMMAND_ORIGINAL_MISSING_'+action)
            name,argv=found[0]
            need(read(name+'.exit.json').get('exit_code')==0,'IMAGE_COMMAND_FAILED_'+action)
            return name,argv
        create_name,create=one('create')
        need(create[-2:]==[image,'/tmp/m2-input/image_worker.py']
             and read(create_name+'.stdout.log',False).decode().strip()==cid
             and '--label' in create,'IMAGE_CREATE_ID_MISMATCH')
        label=create[create.index('--label')+1]
        need(re.fullmatch(r'devops\.member2\.operation=[0-9a-f]{32}',label),
             'IMAGE_OWNERSHIP_LABEL_INVALID')
        _,start=one('start')
        _,remove=one('rm')
        need(start==['docker','start','--attach',cid] and
             remove==['docker','rm','-f',cid],'IMAGE_START_REMOVE_ID_MISMATCH')
        inspections=sorted((name,argv) for name,argv in commands.items()
                           if argv==['docker','inspect',cid])
        need(len(inspections)==2,'IMAGE_INSPECT_ORIGINALS_MISSING')
        for name,_ in inspections:
            need(read(name+'.exit.json').get('exit_code')==0,'IMAGE_INSPECT_FAILED')
            items=json.loads(read(name+'.stdout.log',False))
            need(isinstance(items,list) and len(items)==1,'IMAGE_INSPECT_INVALID')
            info=items[0]
            need(info['Id']==cid and info['Image']==image
                 and info['Config']['Labels'].get('devops.member2.operation')==label.split('=',1)[1]
                 and info['State']['Running'] is False,'IMAGE_INSPECT_BINDING_MISMATCH')
        final=json.loads(read(inspections[-1][0]+'.stdout.log',False))[0]
        need(final['State']['ExitCode']==0,'IMAGE_INSPECT_EXIT_MISMATCH')
        ids.append(cid)
    need(len(ids)==len(set(ids)),'IMAGE_OPERATION_CONTAINER_REUSED')
    return ids


def campaign(out,port,raw,candidate_raw,candidate_sha,service_source,service_image,
             wait=1500,key=None,profile_raw=None,profile_raw_sha=None):
    out=Path(out)
    request=strict_json(raw)
    need(request.get('mode')=='e12' and all(COMMIT.fullmatch(request[k]) for k in ('base','target'))
         and request['base']!=request['target'] and request['target']!='0'*40,'E12_COMMIT_PINS_REQUIRED')
    need(all(isinstance(request.get(k),str) and request[k].startswith('/course/data/')
             and all(p not in ('','.','..','.git') for p in request[k][1:].split('/'))
             and '\\' not in request[k] for k in ('repo','candidate')),'E12_PATH_INVALID')
    need(COMMIT.fullmatch(service_source) and IMAGE.fullmatch(service_image),'SERVICE_PINS_REQUIRED')
    pin(candidate_raw,candidate_sha,'CANDIDATE')
    if request.get('profile') is not None:
        need(isinstance(request['profile'],dict),'PROFILE_INVALID')
        pin(canonical(request['profile']),request.get('profile_sha256'),'PROFILE_CANONICAL')
        need(profile_raw is not None and profile_raw_sha is not None,'PROFILE_ORIGINAL_REQUIRED')
        pin(profile_raw,profile_raw_sha,'PROFILE_RAW')
        need(strict_json(profile_raw)==request['profile'],'PROFILE_ORIGINAL_CONTENT_MISMATCH')
    else:
        need(request.get('profile_sha256') is None and profile_raw is None and
             profile_raw_sha is None,'UNEXPECTED_PROFILE_ORIGINAL')
    need(type(wait) is int and 1<=wait<=7200,'INVALID_WAIT')
    save(out/'inputs/request.original.json',raw)
    save(out/'inputs/candidate.original.Dockerfile',candidate_raw)
    if profile_raw is not None:
        save(out/'inputs/profile.original.json',profile_raw)
    key=key or 'a13-c8-'+uuid.uuid4().hex
    wire=Wire(out,port,timeout=30)
    h=wire.obj('001-health','GET','/health')
    need(h.get('status')=='ok' and h.get('schema_version')=='e11e12-1','API_HEALTH_MISMATCH')
    payload={'input':request,'idempotency_key':key}
    # B13 Store hashes its sorted JSON (with spaces, ensure_ascii=True).
    # This is NOT the exchanged canonical profile/request digest.
    expected_store_hash=digest(json.dumps(request,sort_keys=True).encode())
    first=wire.obj('002-submit','POST','/v1/jobs',payload,202)
    job=first.get('job_id','')
    def check_state(state):
        need(JOB.fullmatch(job) and state.get('job_id')==job and
             state.get('request_hash')==expected_store_hash and state.get('idempotency_key')==key,
             'STORE_IDENTITY_MISMATCH')
    check_state(first)
    dup=wire.obj('003-duplicate','POST','/v1/jobs',payload,202)
    check_state(dup)
    conflict=wire.obj('004-conflict','POST','/v1/jobs',
                     {'input':dict(request,target='0'*40),'idempotency_key':key},409)
    need(request['target']!='0'*40 and conflict.get('error')=='IDEMPOTENCY_CONFLICT',
         'CONFLICT_NOT_REJECTED')
    prefix='/v1/jobs/'+job
    deadline=time.monotonic()+wait
    counter=5
    while time.monotonic()<deadline:
        state=wire.obj('%05d-poll'%counter,'GET',prefix)
        counter+=1
        check_state(state)
        if state.get('status') in ('SUCCEEDED','FAILED','TIMED_OUT'):
            break
        time.sleep(1)
    else:
        raise ValueError('POLL_DEADLINE_RECONCILE_SERVER')
    trace=state.get('trace_id','')
    need(state.get('status')=='SUCCEEDED' and TRACE.fullmatch(trace),'JOB_NOT_SUCCEEDED')
    result=wire.obj('%05d-artifacts'%counter,'GET',prefix+'/artifacts');counter+=1
    files=artifact_index(result,job)
    image=result.get('draft_image_id','')
    need(result.get('trace_id')==trace and result.get('base_commit')==request['base']
         and result.get('target_commit')==request['target'] and
         [s['name'] for s in result['stages']]==STAGES and IMAGE.fullmatch(image)
         and result.get('execution_environment')=='draft-image' and result.get('draft_image_reused') is True,
         'RESULT_IDENTITY_OR_DRAFT_MISMATCH')
    if request.get('profile') is not None:
        need(result.get('profile_sha256')==request['profile_sha256'],'RESULT_PROFILE_MISMATCH')
    for name,item in files.items():
        code,data,headers=wire.call('%05d-download'%counter,'GET',prefix+'/files/'+quote(name,safe='/'))
        counter+=1
        need(code==200 and len(data)==item['bytes'] and
             digest(data)==item['sha256']==headers.get('x-content-sha256'),'DOWNLOAD_HASH_MISMATCH')
        save(out/'downloads'/name,data)
    def ref(entry):
        name=entry['uri'].removeprefix('artifact://'+job+'/')
        need(name in files and all(entry[k]==files[name][k] for k in ('uri','sha256','bytes')),
             'STAGE_REFERENCE_MISMATCH')
        return out/'downloads'/name
    need('request.json' in files and strict_json((out/'downloads/request.json').read_bytes())==request,
         'EXECUTED_REQUEST_MISMATCH')
    incremental_ref=None
    for stage,prefix_count in zip(result['stages'],(0,2,4,4,6)):
        name=stage['name'];env=strict_json(ref(stage['artifact']).read_bytes())
        need(env.get('schema_version')=='e11e12-1' and env.get('kind')==name and
             env.get('job_id')==job and env.get('trace_id')==trace and env.get('status')=='SUCCEEDED'
             and env.get('commit')==request['base' if name=='full-check' else 'target']
             and env.get('image_id')==image and env.get('execution_environment')=='draft-image',
             'STAGE_IDENTITY_MISMATCH')
        if request.get('profile') is not None:
            need(env.get('profile_sha256')==request['profile_sha256'],'STAGE_PROFILE_MISMATCH')
        need(env.get('image_operations')==result.get('image_operations',[])[:prefix_count],
             'STAGE_IMAGE_OPERATIONS_MISMATCH')
        for item in env['artifacts']:
            ref(item)
        if name=='incremental-check':
            incremental_ref=stage['artifact']
        if name=='draft':
            need(env['data']['candidate_sha256']==candidate_sha and
                 env['data']['attempts'][-1]['image_id']==image,'DRAFT_CANDIDATE_MISMATCH')
        if name=='repair':
            repair_ref=env['data']['input_report']
            need(repair_ref==incremental_ref,'REPAIR_INPUT_NOT_INCREMENTAL_ORIGINAL')
            ref(repair_ref)
        if name=='recheck':
            need(env['data']['validation']['accepted'] is True and
                 not any(x['type']=='MISSING' for x in env['data']['findings']),
                 'FULL_RECHECK_NOT_CLEAN')
    ids=verify_downloaded_operations(out,files,result,request,image)
    after=wire.obj('%05d-completed-replay'%counter,'POST','/v1/jobs',payload,202)
    check_state(after)
    need(after.get('status')=='SUCCEEDED' and after.get('trace_id')==trace,'COMPLETED_REPLAY_MISMATCH')
    summary={'status':'CLIENT_C8_PASS','job_id':job,'trace_id':trace,'same_key_same_job':True,
             'conflict_http':409,'http_artifacts_verified':len(files),'image_operations':len(ids),
             'request_raw_sha256':digest(raw),'request_canonical_sha256':digest(canonical(request)),
             'store_request_hash':expected_store_hash,'candidate_sha256':candidate_sha,
             'profile_sha256':request.get('profile_sha256'),'profile_raw_sha256':profile_raw_sha,
             'downloaded_inspect_originals_verified':2*len(ids),'draft_image_id':image,
             'declared_service_source_sha':service_source,'declared_service_image_id':service_image,
             'server_store_job_count_verified':False,'formal_pair_acceptance':False}
    record(out/'summary.json',summary)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,required=True)
    p.add_argument('--request',type=Path,required=True)
    p.add_argument('--request-sha256',required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--candidate-sha256',required=True)
    p.add_argument('--profile',type=Path)
    p.add_argument('--profile-raw-sha256')
    p.add_argument('--service-source-sha',required=True)
    p.add_argument('--service-image-id',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--wait',type=int,default=1500)
    a=p.parse_args()
    raw=pinned_file(a.request,a.request_sha256,'REQUEST')
    candidate=pinned_file(a.candidate,a.candidate_sha256,'CANDIDATE')
    profile_raw=a.profile.read_bytes() if a.profile is not None else None
    a.out.mkdir(parents=True,exist_ok=False)
    try:
        summary=campaign(a.out,a.port,raw,candidate,a.candidate_sha256,
                         a.service_source_sha,a.service_image_id,a.wait,
                         profile_raw=profile_raw,profile_raw_sha=a.profile_raw_sha256)
        print(canonical(summary).decode())
    except (ValueError,KeyError,TypeError,OSError,http.client.HTTPException) as exc:
        record(a.out/'failure.json',{'status':'FAIL','error_type':type(exc).__name__,
               'note':'Preserve originals and reconcile server; do not blindly submit a new key'})
        raise SystemExit('B13_C8_CLIENT_FAILED: '+type(exc).__name__)


if __name__=='__main__':
    main()
