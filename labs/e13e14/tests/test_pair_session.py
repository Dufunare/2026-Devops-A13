"""Actual loopback HTTP tests with a synthetic backend; not a Docker/SSH claim."""
import hashlib
import json
import secrets
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pair_session import Session, make_server, canonical, digest, artifact_index
from pair_c8_client import Recorder, campaign


class PairSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        self.credential = secrets.token_urlsafe(32).encode()
        self.input = {'mode':'e12','base':'a'*40,'target':'b'*40,
                      'repo':'/course/data/repo','candidate':'/course/data/Dockerfile',
                      'profile':{'exec_image':'draft'}}
        self.raw = canonical(self.input)
        self.source = 'c'*40
        self.candidate = 'd'*64
        self.job = 'job-'+'e'*32
        self.trace = 'trace-'+'f'*32
        self.calls = []
        self.files = {'request.json':self.raw}
        self.state = {'job_id':self.job,'trace_id':self.trace,'status':'SUCCEEDED',
                      'request_hash':digest(json.dumps(self.input,sort_keys=True).encode())}
        self.result = {'job_id':self.job,'trace_id':self.trace,'status':'SUCCEEDED',
                       'base_commit':self.input['base'],'target_commit':self.input['target'],
                       'draft_image_id':'sha256:'+'1'*64,
                       'downstream_executed_in':'image:sha256:'+'1'*64,'stages':[]}
        def entry(name):
            return {'uri':'artifact://'+self.job+'/'+name,'bytes':len(self.files[name]),
                    'sha256':digest(self.files[name])}
        for name in ('draft','full-check','incremental-check','repair','recheck'):
            self.files[name+'.json'] = canonical({'kind':name,'job_id':self.job,
                 'trace_id':self.trace,'status':'SUCCEEDED',
                 'commit':self.input['base' if name=='full-check' else 'target'],'artifacts':[],
                 'data':{'candidate_sha256':self.candidate} if name=='draft' else {}})
            self.result['stages'].append({'name':name,'artifact':entry(name+'.json')})
        self.result['artifacts'] = [entry(n) for n in self.files]
        self.session = Session(self.raw,digest(self.raw),self.candidate,self.source,
                               time.time()+120,self.credential)

    def tearDown(self):
        self.tmp.cleanup()

    def backend(self,method,path,raw):
        self.calls.append((method,path,raw))
        if path == '/health':
            return 200, canonical({'schema_version':'e11e12-1'}), {}
        if method == 'POST':
            body=json.loads(raw)
            if body['input']['target']=='0'*40:
                return 409,canonical({'error':'IDEMPOTENCY_CONFLICT'}),{}
            return 202,canonical(dict(self.state,idempotency_key=body['idempotency_key'])),{}
        if path.endswith('/artifacts'):
            return 200,canonical(self.result),{}
        if '/files/' in path:
            data=self.files[path.split('/files/',1)[1]]
            return 200,data,{'x-content-sha256':digest(data)}
        return 200,canonical(self.state),{}

    def run_server(self, role='api'):
        server = make_server(0,self.session,self.backend,role)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(2)
        self.addCleanup(cleanup)
        return Recorder(server.server_port,self.credential,self.out)

    def test_client_downloads_and_records_without_credential(self):
        rec=self.run_server()
        summary=campaign(rec,self.raw,self.source,self.candidate,10,key='example-session')
        self.assertEqual('PASS',summary['status'])
        self.assertFalse(summary['formal_pair_acceptance'])
        posts=[p for method,p,_ in self.calls if method=='POST']
        self.assertEqual(4,len(posts))
        self.assertFalse(any(self.credential in p.read_bytes() for p in self.out.rglob('*') if p.is_file()))

    def test_auth_expiry_no_backend(self):
        rec=self.run_server()
        self.assertEqual(401,rec.call('GET','/health',authorized=False)[0])
        rec.credential=b'wrong-credential'
        self.assertEqual(401,rec.call('GET','/health')[0])
        self.session.expires=time.time()-1
        self.assertEqual(403,rec.call('GET','/health')[0])
        self.assertEqual([],self.calls)

    def test_role_never_forwards_mutations(self):
        rec=self.run_server('draft')
        for path in ('/v1/run','/v1/execute','/v1/jobs'):
            self.assertEqual(404,rec.call('POST',path,b'{}')[0])
        self.assertEqual(404,rec.call('GET','/v1/jobs')[0])
        self.assertEqual([],self.calls)

    def test_reject_unapproved_input_and_duplicate_json(self):
        rec=self.run_server()
        for raw in (canonical({'input':dict(self.input,repo='/course/data/other'),'idempotency_key':'x'}),
                    b'{"input":{},"input":{},"idempotency_key":"x"}',
                    canonical({'input':dict(self.input,target='0'*40),'idempotency_key':'x'})):
            self.assertEqual(403,rec.call('POST','/v1/jobs',raw)[0])
        self.assertEqual([],self.calls)

    def test_unsafe_manifest_is_rejected(self):
        for name in ('../x','.git/config','CON.txt','foo.','a:b','x%2fy'):
            bad=dict(self.result,artifacts=[{'uri':'artifact://'+self.job+'/'+name,
                      'bytes':1,'sha256':'a'*64}])
            with self.subTest(name=name), self.assertRaises(ValueError):
                artifact_index(bad,self.job)


if __name__=='__main__':
    unittest.main()
