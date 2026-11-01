import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'host'),str(ROOT/'src/app'),str(ROOT/'tools')]
from config_store import Store,Invalid
from config_fixtures import files
from first_setup import apply_first_configuration
from runtime_start import services
from web_control import WebControl
from config_broker import PublicError
from install_browser_host import initialize_database
import sqlite3
import threading
from contextlib import closing

class BrowserSetupTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.values=files(self.root)
  for name in ('telegram-token','discord-token','openai-api-key','hc-bot','hc-server','allowed-users'):(self.root/'secrets'/name).write_text('')
  (self.root/'secrets/discord-access.json').write_text('{"users":[],"guild_id":"","channel_id":""}')
  (self.root/'deployment.env').write_text('DISCORD_APPLICATION_ID=\nKIAGENT_RAID_DEVICES=\n')
  (self.root/'pending-setup').write_text('{"kind":"browser-setup-pending-v1"}')
  self.store=Store(self.root,os.getgid(),b'fixture-signing-key',owner=os.getuid())
  self.backups=self.root/'backups';self.backups.mkdir()
 def prepared(self):
  request={'revision':self.store.revision(),'public':{'telegram_users':'42','discord_users':'42','discord_application':'90','discord_guild':'70','discord_channel':'80','raid_devices':''},'secrets':{key:{'mode':'keep'} for key in ('telegram','discord','openai','hc_bot','hc_server')}}
  request['secrets']['telegram']={'mode':'replace','value':self.values['telegram-token']}
  request['secrets']['discord']={'mode':'replace','value':self.values['discord-token']}
  return self.store.prepare(request)
 def apply(self,runner=None,login=None):
  return apply_first_configuration(self.store,self.prepared(),lambda _:None,run=runner or Mock(),login_check=login or Mock(),state_read=lambda:{'settings':[('auto_enabled','false')]},barrier=Mock(),compose=['compose'],backup_root=self.backups)
 def test_success_commits_only_after_services_are_healthy(self):
  def runner(command):
   self.assertTrue((self.root/'pending-setup').exists())
   self.assertEqual(services(self.root),['config-web'])
  self.assertEqual(self.apply(Mock(side_effect=runner)),'success')
  self.assertFalse((self.root/'pending-setup').exists());self.assertTrue((self.root/'runtime-ready').exists())
  self.assertEqual(services(self.root),['config-web','telegram','discord','server-heartbeat'])
 def test_invalid_provider_login_writes_nothing_and_starts_nothing(self):
  before=self.store.read();runner=Mock()
  with self.assertRaises(PublicError):self.apply(runner,Mock(side_effect=PublicError('telegram_login')))
  runner.assert_not_called();self.assertEqual(self.store.read(),before)
  self.assertFalse((self.root/'runtime-ready').exists());self.assertTrue((self.root/'pending-setup').exists())
 def test_failed_start_restores_empty_configuration_without_activation(self):
  before=self.store.read()
  def runner(command):
   if command[:2]==['compose','up']:raise RuntimeError('fixture startup failure')
  self.assertEqual(self.apply(Mock(side_effect=runner)),'rolled_back')
  self.assertEqual(self.store.read(),before);self.assertEqual(services(self.root),['config-web'])
  self.assertFalse((self.root/'runtime-ready').exists())
 def test_runtime_fails_closed_if_ready_marker_is_missing(self):
  (self.root/'pending-setup').unlink();self.assertEqual(services(self.root),['config-web'])
 def test_pending_setup_blocks_actions_even_with_ready_marker(self):
  (self.root/'runtime-ready').write_text('validated')
  control=WebControl(self.root,self.root/'actions',threading.Lock(),rpc=Mock())
  reply=control.handle({'op':'web_prepare','actor':'a'*64,'action':'server_restart'})
  self.assertEqual(reply,{'ok':False,'code':'setup_required'});control.rpc.assert_not_called()
 def test_empty_kept_required_tokens_are_rejected(self):
  request={'revision':self.store.revision(),'public':{'telegram_users':'42','discord_users':'42','discord_application':'90','discord_guild':'70','discord_channel':'80','raid_devices':''},'secrets':{key:{'mode':'keep'} for key in ('telegram','discord','openai','hc_bot','hc_server')}}
  with self.assertRaises(Invalid):self.store.prepare(request)
 def test_new_database_contains_no_jobs_and_disabled_automation(self):
  path=self.root/'db/history.sqlite3';initialize_database(path)
  with closing(sqlite3.connect(path)) as db:
   self.assertEqual(db.execute('SELECT * FROM settings').fetchall(),[('auto_enabled','false')])
   for table in ('events','auto_repairs','auto_delivery','package_jobs'):self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)
  with self.assertRaises(ValueError):initialize_database(path)

if __name__=='__main__':unittest.main()
