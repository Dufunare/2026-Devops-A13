"""No authorization is installed; test plan generation and deny unsafe mappings."""
import base64
import copy
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pair_access_plan import plan,read_public_key
from pair_session import ROLES


class AccessPlan(unittest.TestCase):
    def setUp(self):
        self.data={'schema_version':'e14-access-plan-1','connector':'test connector',
                   'ssh_user':'course_peer_example','ssh_host':'example.invalid',
                   'windows':[{'start':'2030-01-01T09:00:00+08:00','end':'2030-01-01T10:00:00+08:00'},
                              {'start':'2030-01-01T11:00:00+08:00','end':'2030-01-01T12:00:00+08:00'}],
                   'ports':{role:{'backend':18081+i,'gateway':18181+i,'client':18281+i}
                            for i,role in enumerate(ROLES)}}
        self.key='ssh-ed25519 example'
        self.fingerprint='SHA256:example'

    def test_only_gateway_ports_and_no_shell(self):
        s,match,keys=plan(self.data,self.key,self.fingerprint)
        self.assertFalse(s['async_api_included'])
        self.assertIn('AllowTcpForwarding local',match)
        self.assertIn('AllowStreamLocalForwarding no',match)
        self.assertIn('MaxSessions 0',match)
        self.assertFalse(s['not_before_enforced'])
        for i in range(4):
            self.assertIn('127.0.0.1:'+str(18181+i),match)
            self.assertNotIn('127.0.0.1:'+str(18081+i),match)
        self.assertIn('expiry-time="20300101020000Z"',keys[0])
        self.assertIn('expiry-time="20300101040000Z"',keys[1])
        self.assertNotEqual(keys[0],keys[1])

    def test_reject_root_overlap_and_collisions(self):
        cases=[]
        for user in ('root','bad user'):
            bad=copy.deepcopy(self.data);bad['ssh_user']=user;cases.append(bad)
        bad=copy.deepcopy(self.data);bad['windows'][1]=bad['windows'][0];cases.append(bad)
        bad=copy.deepcopy(self.data);bad['ports']['draft']['gateway']=18081;cases.append(bad)
        bad=copy.deepcopy(self.data);bad['ports']['draft']['client']=18281;cases.append(bad)
        bad=copy.deepcopy(self.data);bad['ports'].pop('draft');cases.append(bad)
        for case in cases:
            with self.subTest(case=case),self.assertRaises(ValueError):
                plan(case,self.key,self.fingerprint)

    def test_real_ssh_keygen_fingerprint_without_private_key(self):
        # A synthetic ed25519 public blob, not an actual authorization.
        def field(raw):
            return struct.pack('>I',len(raw))+raw
        encoded=base64.b64encode(field(b'ssh-ed25519')+field(bytes(range(32)))).decode()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'sample.pub'
            path.write_text('ssh-ed25519 '+encoded+' example\n')
            key,fingerprint=read_public_key(path)
            self.assertEqual('ssh-ed25519 '+encoded,key)
            self.assertTrue(fingerprint.startswith('SHA256:'))
            path.write_text('restrict '+key+'\n')
            with self.assertRaises(ValueError):
                read_public_key(path)


if __name__=='__main__':
    unittest.main()
