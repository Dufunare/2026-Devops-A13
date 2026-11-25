"""Real local four-role health and authenticated facade regression, not SSH."""
import argparse
from contextlib import ExitStack
import secrets
import threading
import time
from pathlib import Path

from e14_gate import ROOT, PORTS, require, service_containers, verify_continuity, save
from pair_session import Session, make_server, upstream_for, verify_deployment, digest
from pair_health_client import probe


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,required=True)
    p.add_argument('--request-sha256',required=True)
    p.add_argument('--candidate-sha256',required=True)
    p.add_argument('--source-commit',required=True)
    p.add_argument('--project',required=True)
    p.add_argument('--image',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    out=a.out.resolve()
    require(out.is_relative_to(ROOT/'work') and out!=ROOT/'work' and not out.exists(),
            'FRESH_OUT_REQUIRED')
    raw=a.request.read_bytes()
    require(digest(raw)==a.request_sha256,'REQUEST_HASH_MISMATCH')
    verify_deployment(ROOT,raw,a.candidate_sha256,a.source_commit)
    out.mkdir(parents=True)
    before=service_containers(out,a.project,a.image,'before')
    credential=secrets.token_urlsafe(32).encode()
    session=Session(raw,a.request_sha256,a.candidate_sha256,a.source_commit,
                    time.time()+120,credential)
    mapping={}
    with ExitStack() as stack:
        for role,port in PORTS.items():
            server=stack.enter_context(make_server(0,session,upstream_for(port),role))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            def close(s=server,t=thread):
                s.shutdown()
                t.join(5)
            stack.callback(close)
            mapping[role]=server.server_port
        summary=probe(mapping,credential,out/'client',a.source_commit,
                      a.request_sha256,a.candidate_sha256)
    after=service_containers(out,a.project,a.image,'after')
    summary['service_continuity']=verify_continuity(before,after,'before','after')
    summary['scope']='real local Compose health via four distinct loopback gateways; no SSH'
    for path in out.rglob('*'):
        if path.is_file():
            require(credential not in path.read_bytes(),'CREDENTIAL_IN_EVIDENCE')
    save(out/'summary.json',summary)
    print('PAIR_REAL_FOUR_ROLE_HEALTH_GATE=PASS')


if __name__=='__main__':
    main()
