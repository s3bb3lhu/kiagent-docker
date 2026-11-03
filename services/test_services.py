import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

def module(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'));value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

agent=module('host_agent');web=module('web')

class Actions(unittest.TestCase):
    def setUp(self):
        self.agent=agent.Agent();self.agent.sessions['session']={'until':time.monotonic()+1800,'epoch':'epoch'}
        self.auth=patch.object(agent,'auth_data',return_value={'epoch':'epoch'});self.auth.start();self.addCleanup(self.auth.stop)
        self.audit=patch.object(agent,'audit');self.audit.start();self.addCleanup(self.audit.stop)
        self.row={'id':'example.service','state':'active','name':'example.service'}
        self.inventory=patch.object(agent,'inventory',return_value={'services':[self.row],'containers':[]});self.inventory.start();self.addCleanup(self.inventory.stop)
    def prepare(self,**extra):return self.agent.handle({'op':'prepare','token':'session','kind':'service','target':'example.service','verb':'restart',**extra})
    def decide(self,identifier,confirm=True):return self.agent.handle({'op':'decide','token':'session','id':identifier,'confirm':confirm,'phrase':'example.service'})
    def test_replay_and_fixed_arguments(self):
        job=self.prepare()
        with patch.object(agent,'command',side_effect=['','ActiveState=active\nResult=success\nExecMainStatus=0']) as call:
            self.assertEqual(self.decide(job['id'])['result'],'success')
            self.assertEqual(call.call_args_list[0].args[0],['/usr/bin/systemctl','restart','--','example.service'])
            with self.assertRaises(ValueError):self.decide(job['id'])
            self.assertEqual(call.call_count,2)
    def test_cancel_never_executes(self):
        job=self.prepare()
        with patch.object(agent,'command') as call:self.decide(job['id'],False);call.assert_not_called()
    def test_timeout_no_replay(self):
        job=self.prepare()
        with patch.object(agent,'command',side_effect=TimeoutError):self.assertFalse(self.decide(job['id'])['ok'])
        with self.assertRaises(ValueError):self.decide(job['id'])
    def test_stale_state(self):
        job=self.prepare();self.row['state']='inactive'
        # Real inventory yields fresh objects; retain the saved pre-action copy here.
        self.agent.pending[job['id']]['before']={'id':'example.service','state':'active','name':'example.service'}
        with patch.object(agent,'command') as call:
            with self.assertRaises(ValueError):self.decide(job['id'])
            call.assert_not_called()
    def test_unknown_injection_and_options(self):
        for changes in ({'target':'example.service;reboot'},{'target':'--all'},{'verb':'kill'},{'extra':True}):
            with self.assertRaises(ValueError):self.prepare(**changes)
    def test_audit_failure_prevents_execution(self):
        job=self.prepare()
        with patch.object(agent,'audit',side_effect=OSError),patch.object(agent,'command') as call:
            with self.assertRaises(OSError):self.decide(job['id'])
            call.assert_not_called()
    def test_failed_oneshot_not_success(self):
        job=self.prepare()
        with patch.object(agent,'command',side_effect=['','ActiveState=inactive\nResult=exit-code\nExecMainStatus=1']):self.assertEqual(self.decide(job['id'])['result'],'unverified')

class WebSecurity(unittest.TestCase):
    def setUp(self):
        self.backend=unittest.mock.Mock(return_value={'ok':True,'token':'backend-session'})
        self.app=web.create_app(backend=self.backend,secret='test-only',origin='https://192.0.2.10:9999');self.app.testing=True;self.client=self.app.test_client()
    def test_auth_host_origin_csrf(self):
        base='https://192.0.2.10:9999'
        self.assertEqual(self.client.get('/',base_url=base).status_code,302)
        self.assertEqual(self.client.get('/',base_url='https://evil.invalid').status_code,400)
        self.client.get('/login',base_url=base)
        self.assertEqual(self.client.post('/login',base_url=base,data={'password':'secret'}).status_code,403)
        with self.client.session_transaction() as session:csrf=session.get('csrf')
        # Secure cookies are sent only for the configured HTTPS host.
        cookies=self.client.get('/login',base_url=base)
        with self.client.session_transaction(base_url=base) as session:csrf=session['csrf']
        result=self.client.post('/login',base_url=base,data={'password':'secret','csrf':csrf},headers={'Origin':base})
        self.assertEqual(result.status_code,302)
        self.assertEqual(self.client.get('/',base_url=base).status_code,200)
        self.assertEqual(self.client.post('/api/prepare',base_url=base,json={},headers={'Origin':'https://evil.invalid','X-CSRF-Token':csrf}).status_code,403)
    def test_unauthenticated_api_no_backend(self):
        self.assertEqual(self.client.get('/api/inventory',base_url='https://192.0.2.10:9999').status_code,401)
        self.backend.assert_not_called()
    def test_browser_form_policy_preserves_same_origin(self):
        base='https://192.0.2.10:9999'
        page=self.client.get('/login',base_url=base)
        self.assertEqual(page.headers['Referrer-Policy'],'same-origin')
        with self.client.session_transaction(base_url=base) as session:csrf=session['csrf']
        self.assertEqual(self.client.post('/login',base_url=base,data={'password':'invalid-test','csrf':csrf},headers={'Origin':'null'}).status_code,403)
        self.assertEqual(self.client.post('/login',base_url=base,data={'password':'invalid-test','csrf':csrf},headers={'Origin':base}).status_code,302)

class Credentials(unittest.TestCase):
    def test_only_targeted_credential_is_read(self):
        import os
        with tempfile.TemporaryDirectory() as temporary:
            credential=Path(temporary)/'admin-auth';credential.write_text(json.dumps({'mode':'ready','salt':'11','digest':'22','epoch':'33'}))
            with patch.dict(os.environ,{'CREDENTIALS_DIRECTORY':temporary}):self.assertEqual(agent.auth_data()['epoch'],'33')
            credential.write_text('11$22')
            with patch.dict(os.environ,{'CREDENTIALS_DIRECTORY':temporary}):self.assertEqual(agent.auth_data()['digest'],'22')
    def test_browser_setup_once_without_installation_token(self):
        with tempfile.TemporaryDirectory() as temporary,patch.object(agent,'STATE',Path(temporary)),patch.object(agent,'audit'):
            (Path(temporary)/'local-auth-enabled').write_text('test')
            backend=agent.Agent()
            self.assertTrue(backend.handle({'op':'setup_state'})['setup_required'])
            with self.assertRaises(ValueError):backend.handle({'op':'inventory','token':'unknown'})
            for password in ('abc1!','abcdefgh1!','Abcdefgh!','Abcdefgh1'):
                with self.assertRaises(ValueError):backend.handle({'op':'setup','username':'admin','password':password})
            backend.handle({'op':'setup','username':'admin','password':'Abcdef1!'})
            self.assertFalse(backend.handle({'op':'setup_state'})['setup_required'])
            saved=(Path(temporary)/'auth.json').read_bytes()
            self.assertNotIn(b'Abcdef1!',saved)
            with self.assertRaises(ValueError):backend.handle({'op':'setup','username':'other','password':'Abcdef1!'})
            self.assertEqual(saved,(Path(temporary)/'auth.json').read_bytes())
            with self.assertRaises(ValueError):backend.handle({'op':'login','username':'other','password':'Abcdef1!'})
            self.assertTrue(backend.handle({'op':'login','username':'admin','password':'Abcdef1!'})['ok'])

if __name__=='__main__':unittest.main()
