import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from web_control import WebControl

class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'secrets').mkdir();(self.root/'secrets/allowed-users').write_text('42\n')
        self.rpc=Mock(return_value={'ok':True,'result':'success'})
        self.control=WebControl(self.root,self.root/'actions',threading.Lock(),self.rpc)
        self.actor='a'*64

    def prepare(self,action='testaktion'):
        return self.control.handle({'op':'web_prepare','actor':self.actor,'action':action})
    def decide(self,job,confirm=True,actor=None):
        return self.control.handle({'op':'web_decide','actor':actor or self.actor,'id':job,'confirm':confirm})
    def wait(self,job):
        for _ in range(100):
            data=self.control.handle({'op':'web_job','actor':self.actor,'id':job})
            if data['state']!='running':return data
            time.sleep(.01)
        self.fail('Worker did not finish')

    def test_no_shell_or_unapproved_action(self):
        for value in ('reboot; id','install_curl',{},None):self.assertFalse(self.prepare(value)['ok'])
        self.rpc.assert_not_called()

    def test_actor_binding_cancel_expiry_and_no_replay(self):
        job=self.prepare()['id']
        self.assertFalse(self.decide(job,actor='b'*64)['ok'])
        self.assertEqual(self.decide(job,False)['state'],'cancelled')
        self.assertFalse(self.decide(job)['ok'])
        job=self.prepare()['id'];path=self.root/'actions'/(job+'.json');row=json.loads(path.read_text());row['expires']=0;path.write_text(json.dumps(row))
        self.assertEqual(self.decide(job)['code'],'expired')
        self.rpc.assert_not_called()

    def test_durable_consumption_before_reboot_and_exact_command(self):
        job=self.prepare('server_restart')['id']
        def run(command,**kwargs):
            row=json.loads((self.root/'actions'/(job+'.json')).read_text())
            self.assertEqual(row['state'],'running')
            self.assertEqual(command,['/usr/bin/systemd-run','--unit=kiagent-web-reboot-'+job,'--on-active=10s','/usr/bin/systemctl','reboot'])
        with patch('web_control.subprocess.run',side_effect=run) as command:
            self.decide(job);self.assertEqual(self.wait(job)['state'],'scheduled');self.assertFalse(self.decide(job)['ok']);command.assert_called_once()

    def test_audit_failure_executes_nothing(self):
        job=self.prepare('server_restart')['id']
        with patch.object(self.control,'write',side_effect=OSError),patch('web_control.subprocess.run') as command:
            with self.assertRaises(OSError):self.decide(job)
            command.assert_not_called()

    def test_prior_running_is_uncertain_and_never_replayed(self):
        job=self.prepare()['id'];path=self.root/'actions'/(job+'.json');row=json.loads(path.read_text());row['state']='running';path.write_text(json.dumps(row))
        other=WebControl(self.root,self.root/'actions',threading.Lock(),self.rpc)
        self.assertTrue(other.blocked);self.assertFalse(other.prepare('automatik_an',self.actor)['ok']);self.rpc.assert_not_called()

    def test_existing_raid_protocol_is_used(self):
        self.rpc.side_effect=[{'ok':True,'token':'f'*32},{'ok':True},{'ok':False,'result':'cooldown','retry_after':90}]
        job=self.prepare('raid_monitor_start')['id'];self.decide(job);result=self.wait(job)
        self.assertEqual(result['state'],'failed');self.assertEqual(result['result']['retry_after'],90)
        calls=[call.args[1] for call in self.rpc.call_args_list]
        self.assertEqual([p['op'] for p in calls],['new','bind','confirm'])
        self.assertEqual(calls[0]['action'],'repair_mdmonitor')
        self.assertEqual(calls[1]['message_id'],calls[2]['message_id'])

    def test_restart_expires_unused_grants(self):
        job=self.prepare('server_restart')['id']
        other=WebControl(self.root,self.root/'actions',threading.Lock(),self.rpc)
        reply=other.handle({'op':'web_decide','actor':self.actor,'id':job,'confirm':True})
        self.assertFalse(reply['ok']);self.rpc.assert_not_called()

    def test_result_audit_failure_blocks_further_execution(self):
        job=self.prepare()['id'];original=self.control.write
        def failing(row):
            if row['state']=='success':raise OSError('fixture failure')
            original(row)
        with patch.object(self.control,'write',side_effect=failing):
            self.decide(job);self.assertEqual(self.wait(job)['state'],'uncertain')
        self.assertFalse(self.prepare('server_restart')['ok'])

if __name__=='__main__':unittest.main()
