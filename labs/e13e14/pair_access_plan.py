"""Generate ONLY a proposed, private SSH forwarding plan; never edit sshd.

The actual administrator must verify the temporary account is unprivileged,
effective Match settings and window, then install/revoke the approved key.
Do not authorize any raw backend port.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess

from pair_session import ROLES, need, strict_json, canonical, expiry

KEY_TYPES = {'ssh-ed25519','ssh-rsa','ecdsa-sha2-nistp256','ecdsa-sha2-nistp384',
             'ecdsa-sha2-nistp521','sk-ssh-ed25519@openssh.com',
             'sk-ecdsa-sha2-nistp256@openssh.com'}


def read_public_key(path):
    path=Path(path).resolve()
    raw=path.read_text(encoding='utf-8').strip()
    parts=raw.split()
    need('\n' not in raw and '\r' not in raw and len(parts)>=2
         and parts[0] in KEY_TYPES and re.fullmatch(r'[A-Za-z0-9+/]+={0,2}',parts[1]),
         'PLAIN_SINGLE_PUBLIC_KEY_REQUIRED')
    p=subprocess.run(['ssh-keygen','-lf',str(path),'-E','sha256'],
                     capture_output=True,text=True,timeout=10)
    need(p.returncode==0 and len(p.stdout.splitlines())==1,'PUBLIC_KEY_INVALID')
    fingerprint=p.stdout.split()[1]
    need(re.fullmatch(r'SHA256:[A-Za-z0-9+/]+',fingerprint),'FINGERPRINT_INVALID')
    return ' '.join(parts[:2]),fingerprint


def plan(data, key, fingerprint):
    need(set(data)=={'schema_version','connector','ssh_user','ssh_host','windows','ports'},
         'PLAN_FIELDS_INVALID')
    need(data['schema_version']=='e14-access-plan-1','PLAN_SCHEMA_INVALID')
    connector=data['connector']
    need(isinstance(connector,str) and bool(connector.strip()) and
         all(ord(ch)>=32 for ch in connector),'CONNECTOR_REQUIRED')
    user=data['ssh_user']
    host=data['ssh_host']
    need(isinstance(user,str) and re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}',user)
         and user!='root','TEMPORARY_NONROOT_USER_REQUIRED')
    need(isinstance(host,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,253}',host),
         'SSH_HOST_INVALID')
    windows=data['windows']
    need(isinstance(windows,list) and len(windows)==2,'TWO_WINDOWS_REQUIRED')
    ranges=[]
    for window in windows:
        need(isinstance(window,dict) and set(window)=={'start','end'},'WINDOW_FIELDS_INVALID')
        start,end=expiry(window['start']),expiry(window['end'])
        need(0<end-start<=86400,'WINDOW_DURATION_INVALID')
        ranges.append((start,end))
    ordered=sorted(ranges)
    need(ordered[0][1]<=ordered[1][0],'WINDOWS_OVERLAP')
    ports=data['ports']
    need(isinstance(ports,dict) and set(ports) in (set(ROLES),set((*ROLES,'api'))),
         'ROLE_MAPPING_INVALID')
    server,client=[],[]
    for role,row in ports.items():
        need(isinstance(row,dict) and set(row)=={'backend','gateway','client'},
             'PORT_FIELDS_INVALID')
        need(all(type(v) is int and 1024<=v<=65535 for v in row.values()),'PORT_INVALID')
        server.extend([row['backend'],row['gateway']])
        client.append(row['client'])
    need(len(server)==len(set(server)) and len(client)==len(set(client)),'PORT_COLLISION')
    dests=['127.0.0.1:'+str(ports[role]['gateway']) for role in (*ROLES,'api') if role in ports]
    match='\n'.join([
        'Match User '+user,
        '    AuthenticationMethods publickey',
        '    PasswordAuthentication no',
        '    KbdInteractiveAuthentication no',
        '    PermitEmptyPasswords no',
        '    AllowTcpForwarding local',
        '    AllowStreamLocalForwarding no',
        '    PermitOpen '+' '.join(dests),
        '    GatewayPorts no',
        '    PermitTunnel no',
        '    AllowAgentForwarding no',
        '    X11Forwarding no',
        '    PermitTTY no',
        '    PermitUserRC no',
        '    MaxSessions 0',
        '    ForceCommand /bin/false',
        'Match all',''])
    key_lines=[]
    for _,end in ranges:
        end_value=datetime.fromtimestamp(end,timezone.utc).strftime('%Y%m%d%H%M%SZ')
        options=['restrict','port-forwarding','command="/bin/false"',
                 'expiry-time="'+end_value+'"']+['permitopen="'+d+'"' for d in dests]
        key_lines.append(','.join(options)+' '+key+'\n')
    command=['ssh','-N','-T','-o','ExitOnForwardFailure=yes','-o','StrictHostKeyChecking=yes']
    for role in (*ROLES,'api'):
        if role in ports:
            row=ports[role]
            command.extend(['-L','127.0.0.1:%d:127.0.0.1:%d'%(row['client'],row['gateway'])])
    command.append(user+'@'+host)
    summary={'status':'PROPOSED_NOT_INSTALLED','connector':connector,
             'public_key_fingerprint':fingerprint,'windows':windows,
             'permit_open':dests,'async_api_included':'api' in ports,
             'ssh_user':user,'ssh_host':host,'ports':ports,
             'ssh_argv':command,'not_before_enforced':False,
             'active_sessions_terminated_by_expiry':False}
    return summary,match,key_lines


def write_private(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(data)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--public-key',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    key,fingerprint=read_public_key(a.public_key)
    summary,match,keys=plan(strict_json(a.plan.read_bytes()),key,fingerprint)
    a.out.mkdir(mode=0o700,parents=False,exist_ok=False)
    write_private(a.out/'plan.json',canonical(summary))
    write_private(a.out/'sshd-match.proposed.conf',match.encode())
    for i,line in enumerate(keys,1):
        write_private(a.out/('authorized-key-window-%d.proposed'%i),line.encode())
    print('PAIR_ACCESS_PLAN=PROPOSED_NOT_INSTALLED')
    print('Public key fingerprint:',fingerprint)


if __name__=='__main__':
    main()
