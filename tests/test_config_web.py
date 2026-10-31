import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/app'))
from config_web import create_app,password_hash

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
        self.app = create_app(root,backend,ORIGIN)
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

if __name__ == '__main__':
    unittest.main()
