import re
from html import unescape
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/app'),str(ROOT/'tools')]
from config_web import create_app,password_hash
from user_docs import LANGS,categories,documents,GUIDES
from release_version import VERSION
from export_docs import render

class DocumentationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
  salt='01'*16;self.password='fixture-admin-password-only'
  (root/'web-admin-hash').write_text(salt+'$'+password_hash(self.password,salt))
  (root/'web-session-key').write_text('fixture-session-key-only-'+('s'*32))
  self.calls=[]
  self.app=create_app(root,lambda packet:self.calls.append(packet) or {'ok':True},'http://127.0.0.1:8787',state_dir=root/'auth')
  self.client=self.app.test_client();self.origin='http://127.0.0.1:8787'
 def get(self,path):return self.client.get(path,base_url=self.origin)
 def login(self):
  token=re.search(r'name="csrf" value="([^"]+)"',self.get('/login').text)[1]
  self.client.post('/login',base_url=self.origin,headers={'Origin':self.origin},data={'csrf':token,'password':self.password})
 def test_manual_is_authenticated_and_never_calls_host(self):
  self.assertEqual(self.get('/settings/documentation').status_code,302)
  self.assertEqual(self.get('/settings/documentation/telegram').status_code,302)
  self.login()
  for lang in LANGS:
   overview=self.get('/settings/documentation?lang='+lang)
   self.assertEqual(overview.status_code,200);self.assertIn('v'+VERSION,overview.text)
   for category in categories(lang):self.assertIn(category['title'],unescape(overview.text))
   for doc in documents(lang):
    response=self.get('/settings/documentation/'+doc['slug']+'?lang='+lang)
    self.assertEqual(response.status_code,200)
    self.assertEqual(response.headers['Content-Language'],lang)
    self.assertIn(doc['title'],unescape(response.text))
    for _,link in doc['links']:self.assertIn(link,response.text)
  self.assertEqual(self.get('/settings/documentation/not-a-guide').status_code,404)
  self.assertEqual(self.get('/settings/documentation?lang=invalid').headers['Content-Language'],'de')
  self.assertFalse(self.calls)
 def test_brand_wordmark_is_localized_and_symbol_shared(self):
  self.login()
  names=('Serversteuerung','Server Control','Control del servidor','Contrôle serveur')
  for lang,name in zip(LANGS,names):
   page=self.get('/settings?lang='+lang)
   self.assertIn(name,unescape(page.text));self.assertIn('class="brand-symbol"',page.text)
   self.assertNotIn('K<span>✦</span>',page.text)
 def test_exported_manual_matches_web_source(self):
  self.assertEqual(len({row['slug'] for row in GUIDES}),len(GUIDES))
  for path,text in render().items():self.assertEqual(path.read_text(encoding='utf-8'),text)
  self.assertEqual((ROOT/'VERSION').read_text().strip(),VERSION)
  for name in ('Dockerfile','Dockerfile.portable'):self.assertIn('org.opencontainers.image.version="'+VERSION+'"',(ROOT/name).read_text())

if __name__=='__main__':unittest.main()
