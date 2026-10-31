import ast
import json
import secrets
import sqlite3
import time
import unittest
from pathlib import Path

source = Path(__file__).resolve().parents[1] / 'host/executor.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in {'discord_handle', 'automation_set_enabled'}]

class Tests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:', isolation_level=None)
        self.db.executescript('CREATE TABLE settings(name TEXT PRIMARY KEY,value TEXT); CREATE TABLE events(timestamp REAL,token TEXT,event TEXT,details TEXT);')
        self.db.execute("INSERT INTO settings VALUES('last_attempt','preserve-me')")
        def audit(event, **fields):
            self.db.execute('INSERT INTO events VALUES(?,NULL,?,?)', (time.time(), event, json.dumps(fields)))
        self.env = dict(DB=self.db, time=time, secrets=secrets, json=json,
            DISCORD_ACCESS={'users': [42], 'guild_id': 70, 'channel_id': 80},
            discord_pending={}, audit=audit,
            automation_overview=lambda: {'ok': True, 'kind': 'automation_overview_v1'})
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), self.env)
    def call(self, op, **fields):
        request = dict(op=op, user_id=42, guild_id=70, chat_id=80, message_id=10)
        request.update(fields)
        return self.env['discord_handle'](request)
    def new(self, enabled=False):
        return self.call('new_control', enabled=enabled)['token']
    def test_confirm_preserves_limits_and_audits_actor(self):
        token = self.new()
        self.assertIsNone(self.db.execute("SELECT value FROM settings WHERE name='auto_enabled'").fetchone())
        self.assertTrue(self.call('confirm', token=token)['ok'])
        self.assertEqual(self.db.execute("SELECT value FROM settings WHERE name='auto_enabled'").fetchone()[0], 'false')
        self.assertEqual(self.db.execute("SELECT value FROM settings WHERE name='last_attempt'").fetchone()[0], 'preserve-me')
        details = json.loads(self.db.execute("SELECT details FROM events WHERE event='auto_control'").fetchone()[0])
        self.assertEqual(details['actor'], 'discord')
        self.assertEqual(self.call('confirm', token=token)['result'], 'consumed')
    def test_cancel_and_expiry(self):
        token = self.new()
        self.assertEqual(self.call('cancel', token=token)['result'], 'cancelled')
        self.assertEqual(self.call('confirm', token=token)['result'], 'consumed')
        token = self.new()
        self.env['discord_pending'][token]['expires'] = time.monotonic() - 1
        self.assertEqual(self.call('confirm', token=token)['result'], 'expired')
        self.assertIsNone(self.db.execute("SELECT value FROM settings WHERE name='auto_enabled'").fetchone())
    def test_identity_and_binding(self):
        token = self.new()
        for key, value in [('user_id', 41), ('guild_id', 71), ('chat_id', 81), ('message_id', 11), ('user_id', True)]:
            self.assertFalse(self.call('confirm', token=token, **{key: value})['ok'])
        self.assertEqual(self.call('confirm', token=token)['kind'], 'automation_control_v1')
    def test_unsupported_privileged_operations(self):
        for op in ['auto_repair', 'auto_ack', 'health', 'new', 'auto_control']:
            self.assertFalse(self.call(op)['ok'])
        self.assertFalse(self.call('new_control', enabled=1)['ok'])
        self.assertFalse(self.call('new_control', enabled=False, action='repair_mdmonitor')['ok'])
    def test_read_only_status(self):
        before = self.db.total_changes
        self.assertTrue(self.call('auto_overview')['ok'])
        self.assertEqual(self.db.total_changes, before)
    def test_audit_failure_rolls_back_and_consumes(self):
        token = self.new()
        self.db.execute("CREATE TRIGGER reject_audit BEFORE INSERT ON events WHEN NEW.event='auto_control' BEGIN SELECT RAISE(ABORT,'audit failure'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            self.call('confirm', token=token)
        self.assertIsNone(self.db.execute("SELECT value FROM settings WHERE name='auto_enabled'").fetchone())
        self.assertEqual(self.call('confirm', token=token)['result'], 'consumed')
    def test_restart_invalidates_confirmation(self):
        token = self.new()
        self.env['discord_pending'].clear()
        self.assertEqual(self.call('confirm', token=token)['result'], 'unknown')

if __name__ == '__main__':
    unittest.main(verbosity=2)
