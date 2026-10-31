import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from config_store import Store,Invalid
import config_broker
from config_fixtures import files,request

class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)/'config'
        self.values = files(self.root)
        self.store = Store(self.root,os.getgid(),b'fixture-signing-key')

    def test_overview_never_returns_saved_tokens(self):
        view = json.dumps(self.store.overview())
        for value in self.values.values():
            if value:
                self.assertNotIn(value,view)
        self.assertTrue(self.store.overview()['configured']['telegram'])

    def test_blank_keeps_every_secret_and_is_noop(self):
        prepared = self.store.prepare(request(self.store))
        self.assertEqual(prepared['before'],prepared['desired'])
        self.assertFalse(prepared['changed'])

    def test_only_optional_keys_can_be_removed(self):
        data = request(self.store)
        data['secrets']['telegram'] = {'mode':'clear'}
        with self.assertRaises(Invalid):
            self.store.prepare(data)
        data = request(self.store)
        data['secrets']['openai'] = {'mode':'clear'}
        self.assertEqual(self.store.prepare(data)['desired']['secrets/openai-api-key'],b'\n')

    def test_validation_rejects_injection_urls_and_extra_fields(self):
        for key,value in [('discord_channel','80\nX=Y'),('raid_devices','md1;reboot'),('discord_users','42,42')]:
            data = request(self.store)
            data['public'][key] = value
            with self.assertRaises(Invalid):
                self.store.prepare(data)
        data = request(self.store)
        data['secrets']['hc_bot'] = {'mode':'replace','value':'http://127.0.0.1/admin'}
        with self.assertRaises(Invalid):
            self.store.prepare(data)
        data = request(self.store)
        data['command'] = 'id'
        with self.assertRaises(Invalid):
            self.store.prepare(data)

    def test_stale_revision_rejected_before_write(self):
        data = request(self.store)
        (self.root/'secrets/openai-api-key').write_text('changed-locally')
        with self.assertRaisesRegex(Invalid,'stale'):
            self.store.prepare(data)

    def test_failed_restart_restores_previous_values(self):
        data = request(self.store)
        data['secrets']['openai'] = {'mode':'clear'}
        prepared = self.store.prepare(data)
        backups = Path(self.temporary.name)/'backups'
        backups.mkdir()
        calls = []
        failed = False
        def run(command,timeout=240):
            nonlocal failed
            calls.append(command)
            if '--force-recreate' in command and not failed:
                failed = True
                raise config_broker.PublicError('apply')
            return ''
        with patch.object(config_broker,'BACKUPS',backups),patch.object(config_broker,'check_logins'),patch.object(config_broker,'durable_state',return_value={'unchanged':True}),patch.object(config_broker,'barrier'),patch.object(config_broker,'run',side_effect=run),patch.object(config_broker.time,'sleep'),patch('config_store.os.fchown'):
            result = config_broker.apply_configuration(self.store,prepared,lambda stage:None)
        self.assertEqual(result,'rolled_back')
        self.assertEqual(self.store.read(),prepared['before'])
        self.assertEqual(sum('--force-recreate' in command for command in calls),2)

    def test_interrupted_job_is_not_replayed(self):
        jobs = Path(self.temporary.name)/'jobs'
        jobs.mkdir()
        (jobs/('a'*32+'.json')).write_text(json.dumps({'state':'starting','job':'a'*32}))
        with patch.object(config_broker,'apply_configuration') as apply:
            broker = config_broker.Broker(self.store,jobs,apply)
            self.assertTrue(broker.handle({'op':'overview'})['blocked'])
            with self.assertRaisesRegex(Invalid,'interrupted'):
                broker.handle({'op':'save','data':request(self.store)})
            apply.assert_not_called()

if __name__ == '__main__':
    unittest.main()
