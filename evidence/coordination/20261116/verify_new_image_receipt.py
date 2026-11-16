"""Read peer archives as data; never extract or execute peer code."""
from pathlib import Path,PurePosixPath
import tarfile,zipfile,json,hashlib
import argparse

def sha(b):return hashlib.sha256(b).hexdigest()
def files(p):
 out={}
 with tarfile.open(p) as t:
  for m in t:
   n=m.name
   while n.startswith('./'):n=n[2:]
   q=PurePosixPath(n)
   assert not q.is_absolute() and '..' not in q.parts and not m.issym() and not m.islnk(),n
   if m.isfile():
    assert n not in out,n
    out[n]=t.extractfile(m).read()
 return out

parser=argparse.ArgumentParser(description='Read-only audit of B13 fixed DRAFT receipt; never executes peer code')
parser.add_argument('--original-a',type=Path,required=True)
parser.add_argument('--received-dir',type=Path,required=True,help='B13 原件与核验 directory')
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
received=args.received_dir
receipt=received/'B13_A13_M2_DRAFT_reconsume_20261116.tar.gz'
assert hashlib.sha256(receipt.read_bytes()).hexdigest()=='aaf5dab5f2bcff149cb529e65dd41f01f1a9f5b4f07cacd61cf43ebac286d8f9'
assert hashlib.sha256(args.original_a.read_bytes()).hexdigest()=='507d5a4d627a6eab24c4095de99aca0e6f5cc82acd9faae9a481f7f40a7a37a9'
a=files(args.original_a);b=files(receipt)
input_hashes=json.loads(b['output/received-files.json'])
assert len(input_hashes)==270
for name,digest in input_hashes.items():
 candidates=[n for n in a if n==name or n.endswith('/'+name)]
 assert len(candidates)==1,(name,candidates)
 assert sha(a[candidates[0]])==digest,name
summary=json.loads(b['output/receipt-summary.json'])
assert summary['source_sha']=='64ee6c948693f8f35a30b53b31d0d69508cb7336'
expected_image='sha256:c2e79b20c4f8019b6ca2cf98f8eaa57502cc246ff90b002edc298f3285a187d0'
with zipfile.ZipFile(received/'B13-PR32-source-64ee6c9.zip') as z:
 code={n:sha(z.read(n)) for n in z.namelist() if not n.endswith('/')}
source_hashes={name:code[path] for name,path in [('image_worker.py','labs/e11e12/image_worker.py'),('lab.py','labs/e8e10/lab.py'),('fullcheck.py','labs/e11e12/environment/services/buildchecker/buildchecker/fullcheck.py')]}
cases=[];ops=[];total=0
for c in summary['cases']:
 case=c['case'];prefix='output/'+case+'/consumption/'
 r=json.loads(b[prefix+'result.json'])
 assert r['status']=='SUCCEEDED' and r['execution_environment']=='draft-image' and r['draft_image_reused'] is True
 assert r['draft_image_id']==expected_image and r['commit']==c['target_commit']
 assert r['job_id']==c['job_id'] and r['trace_id']==c['trace_id']
 originals={}
 for name in ['incremental-check.json','incremental-report.json']:
  n=next(n for n in a if n==case+'/'+name or n.endswith('/'+case+'/'+name))
  original=a[n];got=b[prefix+'received/'+name]
  assert original==got,(case,name)
  originals[name]=sha(got)
 payload=json.loads(b[prefix+'received/incremental-report.json']);env=json.loads(b[prefix+'received/incremental-check.json'])
 assert payload['commit']==r['commit'] and env['commit']==r['commit'] and env['job_id']==r['job_id'] and env['trace_id']==r['trace_id']
 refs={}
 for ref in r['artifacts']:
  uri='artifact://'+r['job_id']+'/'
  assert ref['uri'].startswith(uri)
  name=ref['uri'][len(uri):]
  assert name not in refs and '..' not in PurePosixPath(name).parts
  raw=b[prefix+name]
  assert sha(raw)==ref['sha256'] and len(raw)==ref['bytes'],(case,name)
  refs[name]=ref
 total+=len(refs)
 for stage in r['stages']:
  name=stage['name']+'.json';assert refs[name]==stage['artifact']
  e=json.loads(b[prefix+name]);assert e['job_id']==r['job_id'] and e['trace_id']==r['trace_id'] and e['commit']==r['commit'] and e['status']=='SUCCEEDED'
 recheck=json.loads(b[prefix+'recheck.json'])['data']
 assert recheck['validation']['accepted'] is True and all(x is True for x in recheck['validation']['checks'].values())
 assert not any(x['type']=='MISSING' for x in recheck['findings'])
 assert any(x['type']=='REDUNDANT' and x['target']=='main.o' and x['dependency']=='unused.h' for x in recheck['findings'])
 for step,operation in [('01-validate','validate'),('02-full','full')]:
  base=prefix+'image-execution/'+step+'/'
  execution=json.loads(b[base+'execution.json'])
  assert execution['operation']==operation and execution['project_commit']==r['commit']
  assert execution['image_id']==expected_image and execution['actual_container_image']==expected_image and execution['container_exit_code']==0
  assert execution['code_sha256']==source_hashes
  for index in ['05','07']:
   inspect=json.loads(b[base+index+'-inspect.stdout.log'])[0]
   assert inspect['Image']==expected_image and inspect['Id']==execution['container_id']
   assert not inspect['HostConfig'].get('Binds') and not inspect.get('Mounts')
   if index=='07':assert inspect['State']['ExitCode']==0 and inspect['State']['Status']=='exited'
  ops.append({'case':case,'operation':operation,'container_id':execution['container_id'],'image_id':expected_image,'exit_code':0,'raw_inspects_verified':2})
 cases.append({'case':case,'job_id':r['job_id'],'trace_id':r['trace_id'],'target_commit':r['commit'],'artifacts_verified':len(refs),'original_report_sha256':originals,'accepted':True,'missing_count':0,'RD_unused_retained':True,'patch_sha256':sha(b[prefix+'candidate.patch'])})
assert total==567 and len(ops)==6 and len(set(x['container_id'] for x in ops))==6
member2=received/'member2-repo-evidence.tar.gz';assert sha(member2.read_bytes())=='a4030eaabb292f1663ecadc1ebccd3193e7e6da0cff18f65fde8a9dd2029d06a'
draft=[]
with tarfile.open(member2) as t:
 for m in t:
  if m.name.endswith('retest/image-tests/e12/draft-build/result.json'):
   d=json.load(t.extractfile(m));assert d['status']=='SUCCEEDED'
   assert any(x.get('image_id')==expected_image and x.get('build_exit_code')==0 for x in d['attempts'])
   assert d['verification']['exit_code']==0 and expected_image in d['verification']['command']
   draft.append({'path':m.name,'image_id':expected_image,'build_and_runtime_succeeded':True})
assert len(draft)==1
result={'schema_version':'a13-new-image-receipt-audit-1','status':'PASS','receipt_archive_sha256':sha(receipt.read_bytes()),'B13_executed_source':'64ee6c948693f8f35a30b53b31d0d69508cb7336','original_input_hashes_verified':270,'artifact_hashes_and_bytes_verified':567,'cases':cases,'image_operations':ops,'B13_member2_archive_sha256':sha(member2.read_bytes()),'DRAFT_source_result_verified':draft,'scopes':{'teaching_three_original_reports_in_B13_DRAFT_image':True,'A13_candidate_cross_host_import':False,'tomlc99_acceptance':False,'formal_HTTP_acceptance':False},'peer_code_executed':False}
args.out.parent.mkdir(parents=True,exist_ok=True)
args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','original_input_hashes_verified','artifact_hashes_and_bytes_verified']},ensure_ascii=False));print('6 containers / 12 inspect records / successful source DRAFT result verified')
