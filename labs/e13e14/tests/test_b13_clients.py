"""Actual loopback HTTP with B13-shaped synthetic responses, NOT live B13."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from b13_wire import Wire,canonical,digest,record,strict_json
from b13_sync_client import Client,load_inputs
from b13_c8_client import campaign

FIX=Path(__file__).resolve().parent/'fixtures/b13-level-v1'
MANIFEST=(FIX/'manifest.json').read_bytes()
PROFILE=(FIX/'profile.json').read_bytes()
CANDIDATE=(FIX/'candidate.Dockerfile').read_bytes()
M=strict_json(MANIFEST)
SOURCE='6244f7699e8e9920e2185860542bed54afd2123b'
SERVICE='sha256:'+'1'*64
IMAGE='sha256:'+'2'*64
JOB='job-'+'3'*32
TRACE='trace-'+'4'*32
ROOT='/course/work/test-fixture/jobs/'+JOB
GOOD_CHECKS={k:True for k in ('patch_applies','build','test','header_change','no_missing')}


class Loopback(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.credential=secrets.token_urlsafe(32).encode()
        self.posts=[]
        self.calls=[]
        self.serial=0

    def listener(self,backend):
        test=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):
                pass
            def dispatch(self):
                raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
                data=strict_json(raw) if raw else None
                test.calls.append((self.command,self.path))
                code,body,headers=backend(self.command,self.path,data,self.headers)
                body=canonical(body) if isinstance(body,dict) else body
                self.send_response(code)
                self.send_header('Content-Length',str(len(body)))
                for k,v in headers.items():
                    self.send_header(k,v)
                self.end_headers()
                self.wfile.write(body)
            do_GET=dispatch
            do_POST=dispatch
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        def close():
            server.shutdown()
            server.server_close()
            thread.join(3)
        self.addCleanup(close)
        return server.server_port

    def assert_no_credential(self):
        self.assertFalse(any(self.credential in p.read_bytes()
                         for p in self.root.rglob('*') if p.is_file()))

    def test_exchange_original_pins(self):
        self.assertEqual((3613,'68198ff2848ef2584b08101772eb477c6e695adb8e4717632485f73e856f0915'),
                         (len(MANIFEST),digest(MANIFEST)))
        self.assertEqual((787,'25dc51446a584bf334b9ad64ae1efa502cb155816e5763cb9670f5af1ec34bbe'),
                         (len(PROFILE),digest(PROFILE)))
        self.assertEqual('f0367b454aff9cb0a5304e3e3330b61d4bbd01c3f19069eaf5930a1664d3733b',
                         digest(canonical(strict_json(PROFILE))))
        self.assertEqual((609,'8b26c9034b1535b243b99cb43361ad2d44625473c902e0f5f7a78ffbb678fd4a'),
                         (len(CANDIDATE),digest(CANDIDATE)))

    def sync(self,scenario='normal',wrong_image=False):
        m=copy.deepcopy(M)
        self.source_bytes={name:('synthetic original '+name+'\n').encode() for name in m['target_files']}
        if scenario=='C5':
            m['target_files']={name:digest(raw) for name,raw in self.source_bytes.items()}
        manifest_raw=canonical(m) if scenario=='C5' else MANIFEST
        def full_value(rows):
            return {'status':'SUCCEEDED','findings':rows,'whole_project_findings':rows,
                    'profile_sha256':m['profile_sha256']}
        graph=b'[\n {"target":"main.o","dependency":"main.c"}\n]\n'
        target=full_value(m['expected_missing'])
        target_raw=json.dumps(target,ensure_ascii=False,indent=2).encode()+b'\n'
        common={k:m[k] for k in ('project_id','base','target','profile','profile_sha256','candidate_sha256')}
        common.update(protocol='member2-e14-1',job_id=JOB,trace_id=TRACE)
        def role_backend(role):
            def backend(method,path,data,headers):
                if method=='GET':
                    return 200,{'status':'ok','role':role,'protocol':'member2-e14-1'},{}
                self.assertEqual('/v1/run',path)
                self.assertEqual(self.credential.decode(),headers.get('X-E14-Token'))
                self.assertIsNone(headers.get('Authorization'))
                self.assertTrue(all(data[k]==v for k,v in common.items()))
                self.assertTrue(data['project'] in (ROOT+'/base',ROOT+'/target'))
                name=data['out'].removeprefix(ROOT+'/')
                self.posts.append((role,name,copy.deepcopy(data)))
                if role=='draft':
                    self.assertEqual(ROOT+'/target',data['project'])
                    self.assertEqual('/course/data/test/candidate.Dockerfile',data['candidate'])
                    self.assertNotIn('image_id',data)
                    return 200,{'status':'SUCCEEDED','image_id':IMAGE,
                        'binding':dict(common,image_id=IMAGE,files={side:m[side+'_files'] for side in ('base','target')}),
                        'result':{'status':'SUCCEEDED','candidate_sha256':m['candidate_sha256'],
                                  'attempts':[{'image_id':IMAGE}]}},{}
                self.assertEqual(IMAGE,data['image_id'])
                ids={k:common[k] for k in ('job_id','trace_id','profile_sha256')}
                ids['image_id']=IMAGE
                if role=='echecker':
                    self.assertEqual(ROOT+'/base',data['base_project'])
                    self.assertEqual(ROOT+'/baseline-full/actual-graph.json',data['baseline_graph'])
                    self.assertEqual(digest(graph),data['baseline_graph_sha256'])
                    self.assertEqual(ROOT+'/target-full/findings.json',data['target_findings'])
                    self.assertEqual(digest(target_raw),data['target_findings_sha256'])
                    return 200,dict(status='SUCCEEDED',job_id=JOB,trace_id=TRACE,
                                    report=ROOT+'/incremental/incremental-check.json',
                                    report_sha256='a'*64,payload=ROOT+'/incremental/incremental-report.json',
                                    payload_sha256='b'*64),{}
                self.serial+=1
                cid='%064x'%self.serial
                result=dict(ids,status='SUCCEEDED',cleanup_verified=True,source_unchanged=True)
                if name=='timeout-full':
                    self.assertEqual(('sleep',1),(data['fault'],data['timeout_seconds']))
                    return 200,dict(result,status='TIMED_OUT',operation='full',container_id=cid),{}
                side='base' if name=='baseline-full' else 'target'
                source=dict(m[side+'_files'])
                if name=='final-full':
                    source['Makefile']='9'*64
                result['execution']={'operation':'full' if role=='buildchecker' else 'validate',
                    'image_id':IMAGE,'actual_container_image':'sha256:'+'0'*64 if wrong_image else IMAGE,
                    'container_id':cid,'container_exit_code':0,'profile_sha256':m['profile_sha256'],
                    'input_source_sha256':source,'ownership_label':'7'*32}
                if role=='buildchecker':
                    result['result']=result['payload']=target if name=='target-full' else full_value([])
                else:
                    self.assertEqual(('a'*64,'b'*64),(data['report_sha256'],data['payload_sha256']))
                    if name=='bad-repair':
                        self.assertIs(data['fault_patch'],True)
                        result.update(status='REJECTED',payload={'accepted':False,'rollback':True,
                                       'source_unchanged':True,'checks':{},'error':'apply-check: invalid patch'})
                    else:
                        self.assertNotIn('fault_patch',data)
                        result['payload']={'accepted':True,'checks':GOOD_CHECKS}
                return 200,result,{}
            return backend
        ports={role:self.listener(role_backend(role)) for role in ('buildchecker','echecker','draft','mdfixer')}
        session={'schema_version':'b13-sync-session-1','scenario':scenario,'service_source_sha':SOURCE,
                 'service_image_id':SERVICE,'job_id':JOB,'trace_id':TRACE,'run_root':'/course/work/test-fixture',
                 'candidate_path':'/course/data/test/candidate.Dockerfile','ports':ports,
                 'manifest_sha256':digest(manifest_raw),'profile_raw_sha256':digest(PROFILE),
                 'profile_canonical_sha256':m['profile_sha256'],'candidate_sha256':digest(CANDIDATE)}
        s,m=load_inputs(canonical(session),manifest_raw,PROFILE,CANDIDATE)
        return Client(self.root,s,m,self.credential,10),graph,target_raw,session

    def test_sync_six_post_chain_and_actual_wire(self):
        client,graph,target,_=self.sync()
        first=client.start()
        self.assertEqual('WAITING_FOR_FULL_ORIGINALS',first['status'])
        self.assertEqual(3,len(self.posts))
        final=client.finish(graph,digest(graph),target,digest(target))
        self.assertEqual(('CLIENT_CHAIN_PASS',6,0),(final['status'],final['run_requests'],final['remaining_missing']))
        self.assertEqual(['draft','baseline-full','target-full','incremental','repair','final-full'],
                         [name for _,name,_ in self.posts])
        for label in ('01-draft','02-baseline-full','03-target-full','04-incremental','05-repair','06-final-full'):
            p=self.root/'wire'/label
            self.assertEqual(digest((p/'request.body').read_bytes()),
                             strict_json((p/'request.json').read_bytes())['body_sha256'])
            self.assertEqual(digest((p/'response.body').read_bytes()),
                             strict_json((p/'response.json').read_bytes())['sha256'])
        self.assertFalse(final['formal_pair_acceptance'])
        self.assert_no_credential()

    def test_c4_only_two_posts_and_no_false_recovery_claim(self):
        client,_,_,_=self.sync('C4')
        s=client.start()
        self.assertEqual('C4_CLIENT_TIMEOUT_OBSERVED',s['status'])
        self.assertEqual(['draft','timeout-full'],[n for _,n,_ in self.posts])
        self.assertFalse(s['server_originals_verified'])
        self.assert_no_credential()

    def c5_handoff(self,client,wrong=None):
        folder=self.root/'peer-originals'
        folder.mkdir(exist_ok=False)
        raw=(self.root/'wire/05-bad-repair/response.body').read_bytes()
        witness=strict_json(raw)['execution']
        source=client.m['target_files']
        values={'source-before.json':canonical(source),'after-bad-source.json':canonical(source),
                'git-before.txt':b'','after-bad-git.txt':b'',
                'bad-repair/runtime/output/evidence/apply-check.stderr':b'error: patch does not apply\n',
                'bad-repair/runtime/execution.json':canonical(witness),
                'bad-repair/runtime/cleanup.json':canonical({'ownership_label':witness['ownership_label'],
                    'removed':[witness['container_id']],'verified_no_owned_containers':True})}
        for name,body in self.source_bytes.items():
            for prefix in ('source-before-bytes','source-after-bad-bytes'):
                values[prefix+'/'+name]=body
        if wrong=='source':
            values['source-after-bad-bytes/Makefile']+=b'changed'
        if wrong=='cleanup':
            values['bad-repair/runtime/cleanup.json']=canonical({'ownership_label':witness['ownership_label'],
                'removed':[witness['container_id']],'verified_no_owned_containers':False})
        for name,body in values.items():
            path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        manifest=canonical({'schema_version':'c5-handoff-1','job_id':JOB,'trace_id':TRACE,
             'bad_response_sha256':digest(raw),'files':{n:{'bytes':len(v),'sha256':digest(v)} for n,v in values.items()}})
        return folder,manifest

    def test_c5_pauses_then_recovers_only_after_verified_originals(self):
        client,graph,target,_=self.sync('C5')
        client.start()
        pause=client.finish(graph,digest(graph),target,digest(target))
        self.assertEqual('WAITING_FOR_C5_ROLLBACK_ORIGINALS',pause['status'])
        self.assertEqual(5,len(self.posts))
        self.assertEqual('bad-repair',self.posts[-1][1])
        folder,manifest=self.c5_handoff(client)
        # A new invocation reuses saved wire responses, not in-memory state.
        resumed=Client(self.root,client.s,client.m,self.credential,10)
        result=resumed.recover(folder,manifest,digest(manifest))
        self.assertEqual(7,result['run_requests'])
        self.assertEqual(['bad-repair','repair','final-full'],[n for _,n,_ in self.posts][-3:])
        self.assertTrue(result['c5_rollback_originals_verified'])
        self.assertFalse(result['formal_pair_acceptance'])
        self.assert_no_credential()
        with self.assertRaisesRegex(ValueError,'POST_ALREADY_ATTEMPTED'):
            resumed.recover(folder,manifest,digest(manifest))
        self.assertEqual(7,len(self.posts))

    def test_c5_rejects_self_consistent_manifest_changed_source(self):
        client,graph,target,_=self.sync('C5')
        client.start()
        client.finish(graph,digest(graph),target,digest(target))
        folder,manifest=self.c5_handoff(client,'source')
        with self.assertRaisesRegex(ValueError,'C5_SOURCE_BYTES_MISMATCH'):
            client.recover(folder,manifest,digest(manifest))
        self.assertEqual(5,len(self.posts))

    def test_c5_rejects_unverified_cleanup_and_wrong_job(self):
        client,graph,target,_=self.sync('C5')
        client.start()
        client.finish(graph,digest(graph),target,digest(target))
        folder,manifest=self.c5_handoff(client,'cleanup')
        wrong=canonical(dict(strict_json(manifest),job_id='job-'+'0'*32))
        with self.assertRaisesRegex(ValueError,'C5_HANDOFF_IDENTITY_MISMATCH'):
            client.recover(folder,wrong,digest(wrong))
        with self.assertRaisesRegex(ValueError,'C5_CLEANUP_ORIGINAL_MISMATCH'):
            client.recover(folder,manifest,digest(manifest))
        self.assertEqual(5,len(self.posts))

    def test_wrong_image_and_wrong_graph_fail_closed(self):
        client,graph,target,_=self.sync(wrong_image=True)
        with self.assertRaisesRegex(ValueError,'WORKER_WITNESS_MISMATCH'):
            client.start()
        self.assertEqual(2,len(self.posts))

    def test_handoff_rejects_hash_and_semantic_substitution(self):
        client,graph,target,_=self.sync()
        client.start()
        with self.assertRaisesRegex(ValueError,'BASELINE_GRAPH_SHA256_MISMATCH'):
            client.finish(graph+b' ',digest(graph),target,digest(target))
        forged=canonical({'status':'SUCCEEDED','findings':[]})
        with self.assertRaisesRegex(ValueError,'TARGET_FINDINGS_DIFFERS'):
            client.finish(graph,digest(graph),forged,digest(forged))
        self.assertEqual(3,len(self.posts))

    def test_session_rejects_wrong_profile_and_paths_before_network(self):
        _,_,_,session=self.sync()
        for field,value in [('profile_raw_sha256','0'*64),('run_root','/course/work/../other'),
                            ('candidate_path','/course/data/../other'),('service_image_id','latest')]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                load_inputs(canonical(dict(session,**{field:value})),MANIFEST,PROFILE,CANDIDATE)
        self.assertEqual([],self.calls)

    def test_echoed_credential_is_not_persisted(self):
        port=self.listener(lambda *_:(200,b'echo:'+self.credential,{}))
        wire=Wire(self.root,port,self.credential,10)
        with self.assertRaisesRegex(ValueError,'CREDENTIAL_IN_RESPONSE'):
            wire.call('probe','POST','/v1/run',{})
        self.assertTrue((self.root/'wire/probe/transport-failure.json').is_file())
        self.assertFalse((self.root/'wire/probe/response.body').exists())
        self.assert_no_credential()

    def async_backend(self,tamper=False,bad_inspect=False,scoped=False,in_scope_missing=False,
                      forged_scope=False):
        request={'mode':'e12','repo':'/course/data/project','candidate':'/course/data/candidate.Dockerfile',
                 'base':M['base'],'target':M['target'],'expected_output':'1'}
        profile={'id':'synthetic-tomlc99','repair_targets':['toml.o']} if scoped else None
        scope={'profile_sha256':digest(canonical(profile)),'success_scope':profile['repair_targets']} if scoped else {}
        if scoped:
            request.update(profile=profile,profile_sha256=scope['profile_sha256'])
        rows=([{'type':'MISSING','target':'toml_json','dependency':'toml.h'},
               {'type':'REDUNDANT','target':'toml.o','dependency':'unused.h'}] if scoped else [])
        if in_scope_missing:
            rows.append({'type':'MISSING','target':'toml.o','dependency':'toml.h'})
        raw=json.dumps(request,indent=2).encode()+b'\n'
        store_hash=digest(json.dumps(request,sort_keys=True).encode())
        files={'request.json':raw,'draft-build/result.json':canonical({'status':'SUCCEEDED'})}
        def entry(name):
            return {'uri':'artifact://'+JOB+'/'+name,'bytes':len(files[name]),'sha256':digest(files[name])}
        operations=[]
        for i,kind in enumerate(('full','scan','scan','full','validate','full'),1):
            cid='%064x'%i
            label='%032x'%i
            op={'operation':kind,'project_commit':M['base'] if i<=2 else M['target'],
                'image_id':IMAGE,'actual_container_image':IMAGE,'container_id':cid,
                'container_exit_code':0,'profile_sha256':scope.get('profile_sha256')}
            operations.append(op)
            prefix='image-execution/%02d-%s/'%(i,kind)
            files[prefix+'execution.json']=canonical(op)
            def command(stem,argv,stdout=b''):
                files[prefix+stem+'.command.json']=canonical({'argv':argv})
                files[prefix+stem+'.exit.json']=canonical({'exit_code':0})
                files[prefix+stem+'.stdout.log']=stdout
            command('02-create',['docker','create','--label','devops.member2.operation='+label,
                                  '--entrypoint','python3',IMAGE,'/tmp/m2-input/image_worker.py'],
                    cid.encode()+b'\n')
            info=[{'Id':cid,'Image':'sha256:'+'0'*64 if bad_inspect else IMAGE,
                   'Config':{'Labels':{'devops.member2.operation':label}},
                   'State':{'Running':False,'ExitCode':0}}]
            command('05-inspect',['docker','inspect',cid],canonical(info))
            command('06-start',['docker','start','--attach',cid])
            command('07-inspect',['docker','inspect',cid],canonical(info))
            command('09-rm',['docker','rm','-f',cid])
        stages=[]
        for name,prefix_count in zip(('draft','full-check','incremental-check','repair','recheck'),(0,2,4,4,6)):
            data={};refs=[]
            if name=='draft':
                data={'candidate_sha256':digest(CANDIDATE),'attempts':[{'image_id':IMAGE}]}
            elif name=='repair':
                data={'input_report':entry('incremental-check.json')}
            elif name=='recheck':
                verdict=dict(accepted=True,**scope)
                full=dict(status='SUCCEEDED',findings=rows,**scope)
                data={'validation':verdict,'findings':rows}
                for fname,val in (('validation/validation.json',verdict),('final-full/findings.json',full)):
                    files[fname]=canonical(val)
                    refs.append(entry(fname))
            files[name+'.json']=canonical({'schema_version':'e11e12-1','kind':name,'job_id':JOB,
                 'trace_id':TRACE,'status':'SUCCEEDED','commit':M['base' if name=='full-check' else 'target'],
                 'image_id':IMAGE,'execution_environment':'draft-image','data':data,'artifacts':refs,
                 'image_operations':operations[:prefix_count],**scope})
            stages.append({'name':name,'artifact':entry(name+'.json')})
        result={'schema_version':'e11e12-1','job_id':JOB,'trace_id':TRACE,'status':'SUCCEEDED',
                'base_commit':M['base'],'target_commit':M['target'],'stages':stages,
                'draft_image_id':IMAGE,'execution_environment':'draft-image','draft_image_reused':True,
                'image_operations':operations,
                'artifacts':[entry(n) for n in files],**scope}
        if forged_scope:
            result['success_scope']=['toml_json']
        key='example-c8-run'
        state={'job_id':JOB,'trace_id':TRACE,'status':'SUCCEEDED',
               'request_hash':store_hash,'idempotency_key':key}
        def backend(method,path,data,headers):
            self.assertIsNone(headers.get('X-E14-Token'))
            self.assertIsNone(headers.get('Authorization'))
            if path=='/health':
                return 200,{'status':'ok','schema_version':'e11e12-1'},{}
            if method=='POST':
                self.posts.append(data)
                self.assertEqual(key,data['idempotency_key'])
                if data['input']['target']=='0'*40:
                    self.assertEqual(dict(request,target='0'*40),data['input'])
                    return 409,{'error':'IDEMPOTENCY_CONFLICT'},{}
                self.assertEqual(request,data['input'])
                return 202,state,{}
            self.assertTrue(path.startswith('/v1/jobs/'+JOB))
            if path.endswith('/artifacts'):
                return 200,result,{}
            if '/files/' in path:
                name=path.split('/files/',1)[1]
                data=files[name]+(b'bad' if tamper else b'')
                return 200,data,{'X-Content-SHA256':digest(files[name])}
            return 200,state,{}
        port=self.listener(backend)
        return port,raw,key

    def test_async_raw_b13_api_c8_download_and_completed_replay(self):
        port,raw,key=self.async_backend()
        s=campaign(self.root,port,raw,CANDIDATE,digest(CANDIDATE),SOURCE,SERVICE,10,key)
        self.assertEqual('CLIENT_C8_PASS',s['status'])
        self.assertEqual(4,len(self.posts))
        self.assertEqual(self.posts[0],self.posts[1])
        self.assertEqual(self.posts[0],self.posts[3])
        self.assertEqual(409,s['conflict_http'])
        self.assertEqual(105,s['http_artifacts_verified'])
        self.assertTrue(s['recheck_scope']['whole_project_missing_zero'])
        self.assertEqual(12,s['downloaded_inspect_originals_verified'])
        self.assertEqual(6,s['image_operations'])
        self.assertNotEqual(s['request_raw_sha256'],s['request_canonical_sha256'])
        self.assertNotEqual(s['request_canonical_sha256'],s['store_request_hash'])
        self.assertFalse(s['server_store_job_count_verified'])
        self.assertFalse(s['formal_pair_acceptance'])

    def test_async_rejects_self_consistent_manifest_with_wrong_inspect_image(self):
        port,raw,key=self.async_backend(bad_inspect=True)
        with self.assertRaisesRegex(ValueError,'IMAGE_INSPECT_BINDING_MISMATCH'):
            campaign(self.root,port,raw,CANDIDATE,digest(CANDIDATE),SOURCE,SERVICE,10,key)
        self.assertFalse((self.root/'summary.json').exists())
        self.assertEqual(3,len(self.posts))

    def run_scoped(self,**kwargs):
        port,raw,key=self.async_backend(scoped=True,**kwargs)
        profile=canonical(strict_json(raw)['profile'])
        return campaign(self.root,port,raw,CANDIDATE,digest(CANDIDATE),SOURCE,SERVICE,10,key,
                        profile_raw=profile,profile_raw_sha=digest(profile))

    def test_async_scoped_pass_preserves_outside_missing_and_redundant(self):
        s=self.run_scoped()
        scope=s['recheck_scope']
        self.assertTrue(scope['repair_scope_pass'])
        self.assertFalse(scope['whole_project_missing_zero'])
        self.assertEqual((0,1,1),(scope['in_scope_missing_count'],scope['out_of_scope_missing_count'],
                                  scope['whole_project_missing_count']))
        self.assertEqual([{'type':'MISSING','target':'toml_json','dependency':'toml.h'}],
                         scope['out_of_scope_missing'])
        self.assertEqual(2,len(scope['whole_project_findings']))
        self.assertEqual('CLIENT_COMPLETED_REPLAY_PASS',s['idempotency_status'])
        self.assertFalse(s['formal_pair_acceptance'])

    def test_async_in_scope_missing_preserves_initial_idempotency_but_fails(self):
        with self.assertRaisesRegex(ValueError,'REPAIR_SCOPE_RECHECK_NOT_CLEAN'):
            self.run_scoped(in_scope_missing=True)
        self.assertEqual(3,len(self.posts))
        self.assertEqual(1,strict_json((self.root/'recheck-scope.json').read_bytes())['in_scope_missing_count'])
        self.assertEqual('CLIENT_INITIAL_IDEMPOTENCY_PASS',
                         strict_json((self.root/'idempotency-observation.json').read_bytes())['status'])
        self.assertFalse((self.root/'summary.json').exists())

    def test_async_rejects_scope_substitution(self):
        with self.assertRaisesRegex(ValueError,'RESULT_PROFILE_OR_SCOPE_MISMATCH'):
            self.run_scoped(forged_scope=True)
        self.assertEqual(3,len(self.posts))

    def test_async_rejects_tampered_download(self):
        port,raw,key=self.async_backend(tamper=True)
        with self.assertRaisesRegex(ValueError,'DOWNLOAD_HASH_MISMATCH'):
            campaign(self.root,port,raw,CANDIDATE,digest(CANDIDATE),SOURCE,SERVICE,10,key)
        self.assertFalse((self.root/'summary.json').exists())
        self.assertEqual(3,len(self.posts))


if __name__=='__main__':
    unittest.main()
