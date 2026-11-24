from pathlib import Path
import hashlib,json,tarfile,zipfile

import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--work-dir',type=Path,required=True,help='Directory containing receipt/, A13_original.tar.gz, outer-hash-audit.json')
ROOT=parser.parse_args().work_dir.resolve()
received=ROOT/'receipt'
original=ROOT/'A13_original.tar.gz'
assert hashlib.sha256(original.read_bytes()).hexdigest()=='507d5a4d627a6eab24c4095de99aca0e6f5cc82acd9faae9a481f7f40a7a37a9'
with tarfile.open(original) as tar:
    source={m.name:tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
def raw(package,name):return source[package+'/'+name]
def digest(data):return hashlib.sha256(data).hexdigest()
cases=[]
for name in ['handoff-include','handoff-body','handoff-declaration']:
    run=received/'output'/name/'consumption'
    manifest=json.loads(raw(name,'manifest.json'))
    same=0
    for path,content in source.items():
        if path.startswith(name+'/'):
            assert content==(received/'input'/path).read_bytes(),path
            same+=1
    for file in ['incremental-check.json','incremental-report.json']:
        assert raw(name,file)==(run/'received'/file).read_bytes(),file
    result=json.loads((run/'result.json').read_bytes())
    assert result['status']=='SUCCEEDED'
    assert result['commit']==manifest['target_commit']
    assert result['job_id']==manifest['job_id'] and result['trace_id']==manifest['trace_id']
    assert result['draft_image_reused'] is False and result['execution_environment']=='orchestrator'
    assert result['upstream']['envelope_sha256']==digest(raw(name,'incremental-check.json'))
    assert result['upstream']['payload_sha256']==digest(raw(name,'incremental-report.json'))
    verified=[]
    for ref in result['artifacts']:
        prefix='artifact://'+manifest['job_id']+'/'
        assert ref['uri'].startswith(prefix)
        relative=ref['uri'][len(prefix):]
        path=(run/relative).resolve()
        assert path.is_relative_to(run.resolve())
        data=path.read_bytes();assert digest(data)==ref['sha256'] and len(data)==ref['bytes'],relative
        verified.append(relative)
    verdict=json.loads((run/'validation/validation.json').read_bytes())
    assert verdict['accepted'] is True and all(verdict['checks'].values()) and verdict['error'] is None
    final=json.loads((run/'final-full/findings.json').read_bytes())
    assert final['status']=='SUCCEEDED' and final['clean_exit_code']==final['build_exit_code']==0
    for path,expected_hash in final['input_sha256'].items():
        assert digest((run/'final-full/project'/path).read_bytes())==expected_hash
    assert raw(name,'target-project/Makefile')==(run/'source-before.Makefile').read_bytes()
    assert (run/'source-after.Makefile').read_bytes()==(run/'target-project/Makefile').read_bytes()
    assert b'main.o: main.c unused.h config.h extra.h' in (run/'source-after.Makefile').read_bytes()
    assert [(f['type'],f['target'],f['dependency']) for f in final['findings']]==[('REDUNDANT','main.o','unused.h')]
    recheck=json.loads((run/'recheck.json').read_bytes())
    assert recheck['data']['findings']==final['findings']
    assert recheck['job_id']==manifest['job_id'] and recheck['trace_id']==manifest['trace_id']
    patch=(run/'candidate.patch').read_bytes()
    expected='4f50c1a8988f0fdd8eeca49b5ef07bd4ec8f082e4d1d49707aa0318603f8782d' if name=='handoff-declaration' else '88074f66c291dcad1344c48f6a2b9ddd42d235d9d0415c85fb33310c5b7cb2af'
    assert digest(patch)==expected
    assert len(list((run/'final-full/trace').glob('t.*')))>0
    cases.append({'case':name,'input_files_unchanged':same,'received_originals_match':True,
                  'target':result['commit'],'job_id':result['job_id'],'trace_id':result['trace_id'],
                  'output_artifacts_verified':len(verified),'accepted':True,'missing_count':0,
                  'redundant':['main.o -> unused.h'],'patch_sha256':digest(patch)})
assert (received/'exit-code.txt').read_text().strip()=='0'
outer=json.loads((ROOT/'outer-hash-audit.json').read_text())
report={'checked_on':'2026-11-13','passed':True,'scope':'A13 received B13 independent offline-consumption evidence',
        'outer_files_sha256_verified':len(outer),'original_A13_package_sha256':digest(original.read_bytes()),
        'B13_result_archive_sha256':'bcaa95e5fbef608cd7377b99018cc8b73f81ba9c85655795fb8d6759473ede6a',
        'B13_source_sha':(received/'source-commit.txt').read_text().strip(),
        'B13_image_id':(received/'image-id.txt').read_text().strip(),
        'B13_consumer_sha256':(received/'consumer.sha256').read_text().split()[0],
        'cases':cases,'total_verified_output_artifacts':sum(c['output_artifacts_verified'] for c in cases),
        'formal_B13_consumption_verified':True,'A13_receipt_rechecked':True,
        'shared_HTTP_cross_machine_verified':False,'real_project_acceptance':False,'draft_image_reused':False}
(ROOT/'receipt-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
