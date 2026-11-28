"""Authenticated preflight for four explicitly agreed loopback SSH forwards."""
import argparse
import json
from pathlib import Path

from pair_session import ROLES, COMMIT, HASH, canonical, strict_json, need
from pair_c8_client import Recorder, save, read_credential


def probe(mapping, credential, out, source, request_sha, candidate_sha):
    need(set(mapping)==set(ROLES) and len(set(mapping.values()))==len(ROLES)
         and all(1024<=x<=65535 for x in mapping.values()), 'ROLE_PORT_MAPPING_INVALID')
    need(COMMIT.fullmatch(source) and HASH.fullmatch(request_sha)
         and HASH.fullmatch(candidate_sha),'PIN_INVALID')
    results={}
    for role in ROLES:
        rec=Recorder(mapping[role],credential,out/role)
        code,_,_=rec.call('GET','/health',authorized=False)
        need(code==401,'MISSING_AUTH_NOT_REJECTED')
        code,body,_=rec.call('GET','/v1/session')
        need(code==200,'SESSION_UNAVAILABLE')
        info=strict_json(body)
        need(all(info.get(k)==v for k,v in (
            ('role',role),('declared_source_commit',source),
            ('request_sha256',request_sha),('candidate_sha256',candidate_sha))),
            'SESSION_PIN_MISMATCH')
        code,body,_=rec.call('GET','/health')
        need(code==200 and strict_json(body)=={'status':'ok','role':role},
             'ROLE_HEALTH_INVALID')
        for route in ('/v1/run','/v1/execute'):
            # An empty, invalid body cannot execute even on a mistakenly
            # forwarded raw service; require the proposed facade's 404.
            code,_,_=rec.call('POST',route,b'{}')
            need(code==404,'RAW_ROLE_ROUTE_NOT_BLOCKED')
        results[role]={'status':'PASS','local_port':mapping[role]}
    summary={'status':'PASS','roles':results,'declared_source_commit':source,
             'request_sha256':request_sha,'candidate_sha256':candidate_sha,
             'formal_pair_acceptance':False,'operator_identity_verified':False,
             'scope':'authenticated health preflight, not synchronous execution'}
    save(out/'summary.json',canonical(summary))
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for role in ROLES:
        p.add_argument('--'+role,type=int,required=True)
    p.add_argument('--source-commit',required=True)
    p.add_argument('--request-sha256',required=True)
    p.add_argument('--candidate-sha256',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    credential=read_credential()
    a.out.mkdir(parents=True,exist_ok=False)
    result=probe({role:getattr(a,role) for role in ROLES},credential,a.out,
                 a.source_commit,a.request_sha256,a.candidate_sha256)
    print('PAIR_FOUR_ROLE_HEALTH_GATE=PASS')
    print(json.dumps(result))


if __name__=='__main__':
    main()
