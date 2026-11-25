"""B13 raw asynchronous E11/E12 API consumer, only through approved SSH.

Unlike A13 pair_c8_client this API has no Bearer facade or /v1/session.
B13 must approve the exact request and the 8081 forward beforehand.
"""
import argparse
import json
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from b13_wire import (Wire,pinned_file,pin,record,canonical,digest,strict_json,need,
                      HASH,COMMIT,JOB,TRACE,IMAGE,save)
from pair_session import artifact_index, STAGES


def campaign(out,port,raw,candidate_raw,candidate_sha,service_source,service_image,wait=1500,key=None):
    out=Path(out)
    request=strict_json(raw)
    need(request.get('mode')=='e12' and all(COMMIT.fullmatch(request[k]) for k in ('base','target'))
         and request['base']!=request['target'],'E12_COMMIT_PINS_REQUIRED')
    need(all(isinstance(request.get(k),str) and request[k].startswith('/course/data/')
             and all(p not in ('','.','..','.git') for p in request[k][1:].split('/'))
             and '\\' not in request[k] for k in ('repo','candidate')),'E12_PATH_INVALID')
    need(COMMIT.fullmatch(service_source) and IMAGE.fullmatch(service_image),'SERVICE_PINS_REQUIRED')
    pin(candidate_raw,candidate_sha,'CANDIDATE')
    if request.get('profile') is not None:
        need(isinstance(request['profile'],dict),'PROFILE_INVALID')
        pin(canonical(request['profile']),request.get('profile_sha256'),'PROFILE_CANONICAL')
    need(type(wait) is int and 1<=wait<=7200,'INVALID_WAIT')
    save(out/'inputs/request.original.json',raw)
    save(out/'inputs/candidate.original.Dockerfile',candidate_raw)
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
    for stage in result['stages']:
        name=stage['name'];env=strict_json(ref(stage['artifact']).read_bytes())
        need(env.get('schema_version')=='e11e12-1' and env.get('kind')==name and
             env.get('job_id')==job and env.get('trace_id')==trace and env.get('status')=='SUCCEEDED'
             and env.get('commit')==request['base' if name=='full-check' else 'target']
             and env.get('image_id')==image and env.get('execution_environment')=='draft-image',
             'STAGE_IDENTITY_MISMATCH')
        if request.get('profile') is not None:
            need(env.get('profile_sha256')==request['profile_sha256'],'STAGE_PROFILE_MISMATCH')
        for item in env['artifacts']:
            ref(item)
        if name=='draft':
            need(env['data']['candidate_sha256']==candidate_sha and
                 env['data']['attempts'][-1]['image_id']==image,'DRAFT_CANDIDATE_MISMATCH')
        if name=='repair':
            ref(env['data']['input_report'])
        if name=='recheck':
            need(env['data']['validation']['accepted'] is True and
                 not any(x['type']=='MISSING' for x in env['data']['findings']),
                 'FULL_RECHECK_NOT_CLEAN')
    operations=result.get('image_operations')
    need(isinstance(operations,list) and len(operations)>=6,'IMAGE_OPERATIONS_MISSING')
    ids=[]
    for op in operations:
        cid=op.get('container_id','')
        need(isinstance(cid,str) and __import__('re').fullmatch(r'[0-9a-f]{64}',cid)
             and op.get('image_id')==image and op.get('actual_container_image')==image,
             'IMAGE_OPERATION_MISMATCH')
        ids.append(cid)
    need(len(ids)==len(set(ids)),'IMAGE_OPERATION_CONTAINER_REUSED')
    after=wire.obj('%05d-completed-replay'%counter,'POST','/v1/jobs',payload,202)
    check_state(after)
    need(after.get('status')=='SUCCEEDED' and after.get('trace_id')==trace,'COMPLETED_REPLAY_MISMATCH')
    summary={'status':'CLIENT_C8_PASS','job_id':job,'trace_id':trace,'same_key_same_job':True,
             'conflict_http':409,'http_artifacts_verified':len(files),'image_operations':len(ids),
             'request_raw_sha256':digest(raw),'request_canonical_sha256':digest(canonical(request)),
             'store_request_hash':expected_store_hash,'candidate_sha256':candidate_sha,
             'profile_sha256':request.get('profile_sha256'),'draft_image_id':image,
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
    p.add_argument('--service-source-sha',required=True)
    p.add_argument('--service-image-id',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--wait',type=int,default=1500)
    a=p.parse_args()
    raw=pinned_file(a.request,a.request_sha256,'REQUEST')
    candidate=pinned_file(a.candidate,a.candidate_sha256,'CANDIDATE')
    a.out.mkdir(parents=True,exist_ok=False)
    try:
        summary=campaign(a.out,a.port,raw,candidate,a.candidate_sha256,
                         a.service_source_sha,a.service_image_id,a.wait)
        print(canonical(summary).decode())
    except (ValueError,KeyError,TypeError,OSError) as exc:
        record(a.out/'failure.json',{'status':'FAIL','error_type':type(exc).__name__,
               'note':'Preserve originals and reconcile server; do not blindly submit a new key'})
        raise SystemExit('B13_C8_CLIENT_FAILED: '+type(exc).__name__)


if __name__=='__main__':
    main()
