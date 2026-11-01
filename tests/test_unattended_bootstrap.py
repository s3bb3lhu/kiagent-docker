import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import unattended_bootstrap as boot

class UnattendedTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.result=self.root/'result';self.result.mkdir();self.config=self.root/'config';self.config.mkdir()
        self.owner='a'*64
        patches=[patch.object(boot,'RESULT',self.result),patch.object(boot,'HOST_CONFIG',self.config),patch.object(boot,'protected_directory'),patch.object(boot,'protected_file',side_effect=lambda path:path.read_text())]
        for item in patches:item.start();self.addCleanup(item.stop)
        (self.result/'owner').write_text(self.owner)
        (self.config/'first-install-owner').write_text(self.owner)
        self.record={'kind':'compose-host-install-v1','network_ready':True,'origin':'https://8.8.8.8:9443'}
        self.marker=self.config/'compose-install.json';self.marker.write_text(json.dumps(self.record))

    def call(self,facts,stage=None):
        return boot.run(lambda:facts,stage or Mock(return_value='/staged'),['namespace'],lambda:{})

    def test_fresh_install_records_url_and_requires_no_input(self):
        with patch.object(boot.subprocess,'run') as execute,patch('builtins.input',side_effect=AssertionError('No questions')):
            self.call({'installed':False,'configured':False})
            self.assertIn('--install-owner',execute.call_args.args[0])
            self.assertEqual(json.loads((self.result/'status.json').read_text())['state'],'ready')
            self.assertEqual((self.result/'WEBADRESSE.txt').read_text().strip(),'https://8.8.8.8:9443/setup')

    def test_existing_own_install_is_started_without_staging_or_update(self):
        stage=Mock(side_effect=AssertionError('No code replacement'))
        before=self.marker.read_bytes()
        with patch.object(boot.subprocess,'run') as execute:
            self.call({'installed':True,'configured':True},stage)
            self.assertIn('start',execute.call_args.args[0]);stage.assert_not_called()
            self.assertEqual(before,self.marker.read_bytes())

    def test_another_install_is_never_started_or_updated(self):
        (self.config/'first-install-owner').write_text('b'*64)
        with patch.object(boot.subprocess,'run') as execute:
            with self.assertRaises(ValueError):self.call({'installed':True,'configured':True})
            execute.assert_not_called()
            self.assertEqual(json.loads((self.result/'status.json').read_text())['state'],'failed')

    def test_failed_https_resumes_installed_source_not_new_payload(self):
        self.record['network_ready']=False;self.marker.write_text(json.dumps(self.record))
        stage=Mock(side_effect=AssertionError('No update'))
        def finish(*args,**kwargs):self.record['network_ready']=True;self.marker.write_text(json.dumps(self.record))
        with patch.object(boot.subprocess,'run',side_effect=finish) as execute:
            self.call({'installed':True,'configured':True},stage)
            self.assertIn('/opt/kiagent-docker/project/tools/host_compose_install.py',execute.call_args.args[0])
            self.assertIn('--resume-network',execute.call_args.args[0]);stage.assert_not_called()

    def test_default_compose_is_a_one_shot_without_runtime_secrets(self):
        text=(ROOT/'compose.yaml').read_text()
        self.assertIn('command: [--detached]',text);self.assertIn("restart: 'no'",text)
        self.assertNotIn('KIAGENT_SECRETS_DIR',text);self.assertNotIn('DISCORD_APPLICATION_ID',text)

if __name__=='__main__':unittest.main()
