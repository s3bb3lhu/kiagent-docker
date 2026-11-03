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
from web_i18n import LANGUAGES,ROWS

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

    def test_ai_settings_are_authenticated_and_keep_tokens_separate(self):
        self.assertEqual(self.get('/api/ai').status_code,401)
        self.assertEqual(self.get('/settings/ai').status_code,302)
        self.login()
        for language in ('de','en','es','fr'):
            page=self.get('/settings/ai?lang='+language)
            self.assertEqual(page.status_code,200);self.assertIn('id="ai-form"',page.text)
            self.assertNotIn('data-secret=',page.text)
        token=self.csrf()
        result=self.client.post('/api/ai',base_url=ORIGIN,headers={'Origin':ORIGIN,'X-CSRF-Token':token},json={'provider':'ollama','model':'small:existing'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.calls[-1],{'op':'ai_select','provider':'ollama','model':'small:existing'})

    def test_custom_https_ports_keep_secure_cookies_and_setup_ip_restriction(self):
        root=Path(self.temporary.name)
        AuthStore(root/'auth').reset()
        for port in (8443,9443,9444):
            origin='https://8.8.8.8:'+str(port)
            app=create_app(root,lambda request:{'ok':True},origin,state_dir=root/'auth',setup_ip='203.0.113.5')
            client=app.test_client()
            response=client.get('/setup',base_url=origin,environ_overrides={'REMOTE_ADDR':'203.0.113.5'})
            self.assertEqual(response.status_code,200)
            self.assertIn('Secure',response.headers.get('Set-Cookie',''))
            self.assertEqual(client.get('/setup',base_url=origin).status_code,403)
        for port in (22,80,8787):
            with self.assertRaises(ValueError):create_app(root,lambda request:{},'https://8.8.8.8:'+str(port),state_dir=root/'auth')

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
        self.assertEqual(page.headers['Referrer-Policy'],'same-origin')
        self.assertIn("frame-ancestors 'none'",page.headers['Content-Security-Policy'])
        for link in ('https://t.me/BotFather','https://discord.com/developers/applications','https://platform.openai.com/api-keys','https://healthchecks.io/checks/'):
            pages=''.join(self.get('/settings/'+provider).text for provider in ('telegram','discord','openai','health'))
            self.assertIn(link,pages)

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
        bad=self.client.post('/setup',base_url=ORIGIN,headers={'Origin':ORIGIN},data={'csrf':token,'username':'admin','password':'weakpass','repeat':'weakpass'})
        self.assertIn('Mindestens 8',bad.text)
        good=self.client.post('/setup',base_url=ORIGIN,headers={'Origin':ORIGIN},data={'csrf':token,'username':'admin','password':'Abcdef1!','repeat':'Abcdef1!'})
        self.assertEqual(good.status_code,302)
        self.assertTrue(store.verify('Abcdef1!'))
        self.assertEqual(store.read()['username'],'admin')
        self.client.post('/logout',base_url=ORIGIN,headers={'Origin':ORIGIN},data={'csrf':re.search(r'name="csrf" value="([^"]+)"',self.get('/').text)[1]})
        login=self.get('/login');token=re.search(r'name="csrf" value="([^"]+)"',login.text)[1]
        denied=self.client.post('/login',base_url=ORIGIN,headers={'Origin':ORIGIN},data={'csrf':token,'username':'wrong','password':'Abcdef1!'})
        self.assertEqual(denied.status_code,200)
        accepted=self.client.post('/login',base_url=ORIGIN,headers={'Origin':ORIGIN},data={'csrf':token,'username':'admin','password':'Abcdef1!'})
        self.assertEqual(accepted.status_code,302)
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

    def test_localized_pages_and_persisted_language(self):
        self.login()
        for lang in LANGUAGES:
            for path in ('/','/status','/control','/console','/settings','/settings/telegram','/settings/discord','/settings/openai','/settings/health','/settings/monitoring','/password'):
                response=self.get(path+'?lang='+lang)
                self.assertEqual(response.status_code,200)
                self.assertIn('lang="'+lang+'"',response.text)
                self.assertEqual(response.headers['Content-Language'],lang)
        for row in ROWS.values():self.assertEqual(len(row),4);self.assertTrue(all(row))
        self.assertEqual(self.get('/status').headers['Content-Language'],'fr')

    def test_control_requires_login_csrf_and_confirmation_phrase(self):
        self.assertEqual(self.get('/api/server/status').status_code,401)
        self.login();page=self.get('/control');token=re.search(r'name="csrf-token" content="([^"]+)"',page.text)[1]
        self.assertEqual(self.client.post('/api/control/prepare',base_url=ORIGIN,headers={'Origin':ORIGIN},json={'action':'server_restart'}).status_code,403)
        result=self.client.post('/api/control/decide',base_url=ORIGIN,headers={'Origin':ORIGIN,'X-CSRF-Token':token},json={'id':'a'*32,'confirm':True,'phrase':'wrong','restart':True})
        self.assertEqual(result.status_code,403)

    def test_pending_setup_redirects_to_combined_browser_wizard(self):
        root=Path(self.temporary.name)
        self.app=create_app(root,lambda packet:{'ok':True,'setup_required':True},ORIGIN,state_dir=root/'auth')
        self.client=self.app.test_client();self.login()
        self.assertEqual(self.get('/').headers['Location'],'/settings/setup')
        self.assertEqual(self.get('/settings/telegram').headers['Location'],'/settings/setup')
        for lang in LANGUAGES:
            response=self.get('/settings/setup?lang='+lang)
            self.assertEqual(response.status_code,200)
            self.assertIn('data-provider="all"',response.text)
            for key in ('telegram','discord','openai','hc_bot','hc_server'):self.assertIn('data-secret="'+key+'"',response.text)

if __name__ == '__main__':
    unittest.main()
