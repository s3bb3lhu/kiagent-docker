import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/app'))
from config_web import create_app,password_hash
from web_auth import AuthStore,valid_password

ORIGIN = 'http://127.0.0.1:8787'

class WebTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.password = 'fixture-admin-password-only'
        salt = '01'*16
        (root/'web-admin-hash').write_text(salt+'$'+password_hash(self.password,salt))
        (root/'web-session-key').write_text('fixture-session-key-only-'+('s'*32))
        self.calls = []
        def backend(payload):
            self.calls.append(payload)
            return {'ok':True,'revision':'r','public':{},'configured':{}}
        self.app = create_app(root,backend,ORIGIN,state_dir=root/'auth')
        self.client = self.app.test_client()

    def get(self,path,**kwargs):
        return self.client.get(path,base_url=ORIGIN,**kwargs)

    def csrf(self):
        page = self.get('/login')
        return re.search(r'name="csrf" value="([^"]+)"',page.text)[1]

    def login(self):
        token = self.csrf()
        return self.client.post('/login',base_url=ORIGIN,headers={'Origin':ORIGIN},data={'csrf':token,'password':self.password})

    def test_unauthenticated_cannot_access_configuration(self):
        self.assertEqual(self.get('/api/overview').status_code,401)
        self.assertFalse(self.calls)

    def test_login_logout_and_cookie_flags(self):
        response = self.login()
        self.assertEqual(response.status_code,302)
        self.assertIn('HttpOnly',response.headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',response.headers['Set-Cookie'])
        page = self.get('/')
        self.assertEqual(page.status_code,200)
        self.assertNotIn(self.password,page.text)
        token = re.search(r'name="csrf-token" content="([^"]+)"',page.text)[1]
        response = self.client.post('/logout',base_url=ORIGIN,headers={'Origin':ORIGIN},data={'csrf':token})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.get('/api/overview').status_code,401)

    def test_host_origin_and_csrf_enforced(self):
        self.assertEqual(self.client.get('/login',base_url='http://evil.example').status_code,400)
        token = self.csrf()
        self.assertEqual(self.client.post('/login',base_url=ORIGIN,headers={'Origin':'http://evil.example'},data={'csrf':token,'password':self.password}).status_code,403)
        self.login()
        self.assertEqual(self.client.post('/api/config',base_url=ORIGIN,headers={'Origin':ORIGIN},json={}).status_code,403)
        self.assertFalse(self.calls)

    def test_no_store_csp_and_help_links(self):
        self.login()
        page = self.get('/')
        self.assertEqual(page.headers['Cache-Control'],'no-store')
        self.assertIn("frame-ancestors 'none'",page.headers['Content-Security-Policy'])
        for link in ('https://t.me/BotFather','https://discord.com/developers/applications','https://platform.openai.com/api-keys','https://healthchecks.io/checks/'):
            self.assertIn(link,page.text)

    def test_login_rate_limit(self):
        token = self.csrf()
        for _ in range(5):
            self.client.post('/login',base_url=ORIGIN,headers={'Origin':ORIGIN},data={'csrf':token,'password':'wrong'})
        result = self.client.post('/login',base_url=ORIGIN,headers={'Origin':ORIGIN},data={'csrf':token,'password':self.password})
        self.assertEqual(result.status_code,429)

    def test_https_proxy_fixed_host_secure_cookie_and_origin(self):
        origin = 'https://192.0.2.10'
        app = create_app(Path(self.temporary.name),lambda data:{'ok':True},origin,state_dir=Path(self.temporary.name)/'auth')
        client = app.test_client()
        # TLS terminates at the proxy; the backend connection is HTTP.
        page = client.get('/login',base_url='http://192.0.2.10')
        self.assertEqual(page.status_code,200)
        self.assertIn('Secure;',page.headers['Set-Cookie'])
        self.assertIn('Strict-Transport-Security',page.headers)
        csrf = re.search(r'name="csrf" value="([^"]+)"',page.text)[1]
        self.assertEqual(client.post('/login',base_url='https://192.0.2.10',headers={'Origin':origin},data={'csrf':csrf,'password':self.password}).status_code,302)
        self.assertEqual(client.post('/logout',base_url=origin,headers={'Origin':'http://192.0.2.10'},data={'csrf':csrf}).status_code,403)
        self.assertEqual(client.get('/login',base_url='http://evil.example',headers={'X-Forwarded-Host':'192.0.2.10'}).status_code,400)

    def test_public_plain_http_origin_rejected(self):
        with self.assertRaises(ValueError):
            create_app(Path(self.temporary.name),origin='http://192.0.2.10')

    def test_setup_network_restriction_policy_and_no_second_claim(self):
        store=AuthStore(Path(self.temporary.name)/'auth')
        store.reset()
        self.assertEqual(self.get('/login').status_code,302)
        denied=self.client.get('/setup',base_url=ORIGIN,environ_overrides={'REMOTE_ADDR':'192.0.2.99'})
        self.assertEqual(denied.status_code,403)
        self.assertNotIn('name="password"',denied.text)
        page=self.get('/setup')
        self.assertNotIn('name="code"',page.text)
        token=re.search(r'name="csrf" value="([^"]+)"',page.text)[1]
        bad=self.client.post('/setup',base_url=ORIGIN,headers={'Origin':ORIGIN},data={'csrf':token,'password':'weakpass','repeat':'weakpass'})
        self.assertIn('Mindestens 8',bad.text)
        good=self.client.post('/setup',base_url=ORIGIN,headers={'Origin':ORIGIN},data={'csrf':token,'password':'Abcdef1!','repeat':'Abcdef1!'})
        self.assertEqual(good.status_code,302)
        self.assertTrue(store.verify('Abcdef1!'))
        self.assertIsNone(store.set_password('Otherpa1!',setup=True))
        self.assertEqual(self.get('/api/overview').status_code,200)

    def test_reset_and_password_change_invalidate_existing_sessions(self):
        self.login()
        store=AuthStore(Path(self.temporary.name)/'auth')
        old=store.read()['epoch']
        self.assertIsNotNone(store.set_password('Newpass1!',current=self.password))
        self.assertNotEqual(old,store.read()['epoch'])
        self.assertEqual(self.get('/api/overview').status_code,401)
        store.reset()
        self.assertFalse(store.verify('Newpass1!'))
        self.assertEqual(self.get('/api/overview').status_code,401)

    def test_password_policy(self):
        for password in ('abcdef1!','Abcdefgh!','Abcdef12','Ab1!','Abc def1!'):
            self.assertFalse(valid_password(password))
        self.assertTrue(valid_password('Abcdef1!'))

    def test_missing_state_cannot_restore_legacy_password(self):
        root=Path(self.temporary.name)/'auth'
        (root/'auth.json').unlink()
        with self.assertRaises(ValueError):
            AuthStore(root,('01'*16,password_hash(self.password,'01'*16)))

if __name__ == '__main__':
    unittest.main()
