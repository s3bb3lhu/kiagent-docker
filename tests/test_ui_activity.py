import json
import sys
import tempfile
import sqlite3
import time
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'host'),str(ROOT/'src/app')]
import ai_activity
from web_status import Telemetry
import web_activity

class ActivityTests(unittest.TestCase):
    def test_console_never_returns_raw_bot_or_apt_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);database=root/'history.sqlite3';log=root/'apt.log'
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE package_jobs(uid,state,plan,expires)')
                db.execute('INSERT INTO package_jobs VALUES(?,?,?,?)',(42,'success',json.dumps({'package':'tree','versions':['tree=1.0']}),time.time()+120))
            log.write_text('Unpacking tree (1.0) ...\nSetting up tree (1.0) ...\nSECRET=never-return-this\nUnpacking unrelated (1.0) ...\n')
            bot=SimpleNamespace(stdout=json.dumps([{'event':'ai_started','time':time.time(),'prompt':'private-prompt'}]))
            with patch.object(web_activity,'DATABASE',database),patch.object(web_activity,'APT_LOG',log),patch('web_activity.subprocess.run',return_value=bot):
                data=web_activity.collect(root,root,[])
            serialized=json.dumps(data)
            for forbidden in ('never-return-this','private-prompt','unrelated','SECRET'):self.assertNotIn(forbidden,serialized)
            self.assertTrue(any(row['event']=='apt_setup' for row in data['events']))
            self.assertTrue(any(row['event']=='ai_started' for row in data['events']))

    def test_bounded_phase_only_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'activity.json'
            with patch.dict(ai_activity.PATHS,{'telegram':path}):
                path.write_text(json.dumps([{'time':float('nan'),'event':'ai_started'},{'time':1,'event':'secret-value'},{'time':2,'event':'ai_started','prompt':'must-disappear'}]))
                self.assertEqual(ai_activity.read('telegram'),[{'time':2,'event':'ai_started','platform':'telegram'}])
                for _ in range(40):ai_activity.record('telegram','ai_finished')
                self.assertEqual(len(ai_activity.read('telegram')),32)
                self.assertNotIn('prompt',path.read_text())

    def test_symlink_not_read(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'private';target.write_text('secret')
            path=Path(directory)/'activity';path.symlink_to(target)
            with patch.dict(ai_activity.PATHS,{'telegram':path}):self.assertEqual(ai_activity.read('telegram'),[])

    def test_cpu_per_core_delta_and_hotplug(self):
        frames=iter(['cpu 40 0 0 60 0 0 0 0\ncpu0 40 0 0 60 0 0 0 0\n',
                     'cpu 60 0 0 140 0 0 0 0\ncpu0 60 0 0 140 0 0 0 0\ncpu1 0 0 0 10 0 0 0 0\n'])
        original=Path.read_text
        def read(path,*args,**kwargs):
            if str(path)=='/proc/stat':return next(frames)
            if str(path)=='/proc/net/dev':return 'header\nheader\n'
            if str(path)=='/proc/meminfo':return 'MemTotal: 100 kB\nMemAvailable: 50 kB\n'
            if str(path)=='/proc/uptime':return '10 0'
            if str(path)=='/proc/sys/kernel/random/boot_id':return 'fixture'
            return original(path,*args,**kwargs)
        with patch.object(Path,'read_text',read),patch('web_status.subprocess.check_output',return_value='{}'),patch('web_status.time.monotonic',side_effect=[10,13]):
            telemetry=Telemetry();self.assertIsNone(telemetry.read()['cores'][0]['percent'])
            second=telemetry.read();self.assertEqual(second['cores'][0]['percent'],20)
            self.assertIsNone(second['cores'][1]['percent'])
            self.assertEqual(second['cpu_percent'],20)

if __name__=='__main__':unittest.main()
