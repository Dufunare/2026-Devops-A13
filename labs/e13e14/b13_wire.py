"""B13 client transport: direct IPv4 loopback through an agreed SSH tunnel.

No automatic POST retry, redirects, external URL, or credential in evidence.
A transport failure is ambiguous: reconcile with the server before a new job.
"""
import http.client
import json
import time
from pathlib import Path
import re

from pair_session import canonical, digest, strict_json, need, HASH, COMMIT, JOB, TRACE, MAX_RESPONSE
from pair_c8_client import save, read_credential

IMAGE = re.compile(r'sha256:[0-9a-f]{64}\Z')
CID = re.compile(r'[0-9a-f]{64}\Z')


def pin(raw, expected, label):
    need(isinstance(expected,str) and HASH.fullmatch(expected) and digest(raw)==expected,
         label+'_SHA256_MISMATCH')
    return raw


def pinned_file(path, expected, label):
    return pin(Path(path).read_bytes(),expected,label)


def json_file(path):
    return strict_json(Path(path).read_bytes())


def record(path, value):
    save(path,canonical(value))


class Wire:
    def __init__(self, out, port, credential=None, timeout=2000):
        need(type(port) is int and 1024<=port<=65535,'INVALID_LOCAL_PORT')
        need(type(timeout) is int and 1<=timeout<=7200,'INVALID_HTTP_TIMEOUT')
        if credential is not None:
            need(isinstance(credential,bytes) and 32<=len(credential)<=256 and
                 all(33<=ch<=126 for ch in credential),'INVALID_SYNC_CREDENTIAL')
        self.out,self.port,self.credential,self.timeout=Path(out),port,credential,timeout

    def call(self, label, method, route, body=None):
        need(re.fullmatch(r'[A-Za-z0-9_-]+',label) and method in ('GET','POST')
             and route.startswith('/') and not route.startswith('//') and
             '?' not in route and '#' not in route,'INVALID_HTTP_CALL')
        raw=canonical(body) if body is not None else None
        folder=self.out/'wire'/label
        folder.mkdir(parents=True,exist_ok=False)
        # Exclusive creation BEFORE sending. Never silently reuse an attempt.
        record(folder/'request.json',{'method':method,'path':route,'loopback_port':self.port,
              'body_sha256':digest(raw) if raw is not None else None,
              'x_e14_token_present':self.credential is not None})
        if raw is not None:
            need(self.credential is None or self.credential not in raw,'CREDENTIAL_IN_REQUEST_BODY')
            save(folder/'request.body',raw)
        headers={}
        if raw is not None:
            headers['Content-Type']='application/json'
        if self.credential is not None:
            headers['X-E14-Token']=self.credential.decode('ascii')
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=self.timeout)
        start=time.time()
        try:
            conn.request(method,route,body=raw,headers=headers)
            response=conn.getresponse()
            data=response.read(MAX_RESPONSE+1)
            need(len(data)<=MAX_RESPONSE,'RESPONSE_TOO_LARGE')
            # A peer should never echo the credential. Do not archive it even
            # if the peer violates that contract.
            need(self.credential is None or self.credential not in data,'CREDENTIAL_IN_RESPONSE')
            kept={k.lower():v for k,v in response.getheaders()
                  if k.lower() in ('content-type','content-length','date','x-content-sha256')}
            need(self.credential is None or self.credential not in canonical(kept),
                 'CREDENTIAL_IN_RESPONSE_HEADER')
            save(folder/'response.body',data)
            record(folder/'response.json',{'http':response.status,'headers':kept,
                   'bytes':len(data),'sha256':digest(data),'start_epoch':start,'end_epoch':time.time()})
            return response.status,data,kept
        except (OSError,http.client.HTTPException,ValueError) as exc:
            record(folder/'transport-failure.json',{'error_type':type(exc).__name__,
                   'ambiguous_if_post':method=='POST','automatic_retry':False})
            raise
        finally:
            conn.close()

    def obj(self,label,method,route,body=None,expected=200):
        status,raw,_=self.call(label,method,route,body)
        need(status==expected,'UNEXPECTED_HTTP_STATUS_'+str(status))
        return strict_json(raw)


def original_response(out,label,expected=200):
    folder=Path(out)/'wire'/label
    raw=(folder/'response.body').read_bytes()
    meta=json_file(folder/'response.json')
    need(meta['http']==expected and meta['bytes']==len(raw) and
         meta['sha256']==digest(raw),'RECORDED_RESPONSE_CHANGED')
    return strict_json(raw)
