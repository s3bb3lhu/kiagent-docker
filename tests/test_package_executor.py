import importlib.util
import sqlite3
import unittest
import sys
import types
from unittest.mock import patch
from pathlib import Path

if sys.platform == 'win32':
    sys.modules['pwd'] = types.SimpleNamespace()
spec = importlib.util.spec_from_file_location('packages', Path(__file__).resolve().parents[1] / 'host/package_executor.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class Tests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:', isolation_level=None)
        self.calls = []
        self.proposal = {'installed': False, 'digest': 'abc', 'changes': ['Inst htop (1 Ubuntu [amd64])'], 'versions': ['htop=1']}
        self.b = p.Broker(self.db, {42}, lambda package: {**self.proposal, 'package': package},
                          lambda plan: self.calls.append(plan) or 'install ok installed 1')
    def request(self, op, **extra):
        return dict(op=op, user_id=42, chat_id=42, message_id=10, **extra)
    def new(self):
        return self.b.handle(self.request('new', package='htop'))['token']
    def test_explicit_confirmation_and_replay(self):
        token = self.new()
        self.assertFalse(self.calls)
        request = self.request('confirm', token=token)
        self.assertEqual(self.b.handle(request)['result'], 'success')
        self.assertEqual(self.b.handle(request)['result'], 'consumed')
        self.assertEqual(len(self.calls), 1)
    def test_cancel(self):
        token = self.new()
        self.b.handle(self.request('cancel', token=token))
        self.b.handle(self.request('confirm', token=token))
        self.assertFalse(self.calls)
    def test_identity_and_message(self):
        token = self.new()
        for field, value in [('user_id', 99), ('chat_id', 99), ('message_id', 99), ('user_id', True)]:
            request = self.request('confirm', token=token)
            request[field] = value
            with self.assertRaises(ValueError):
                self.b.handle(request)
        self.assertFalse(self.calls)
    def test_expiry(self):
        token = self.new()
        self.db.execute('UPDATE package_jobs SET expires=0')
        self.assertEqual(self.b.handle(self.request('confirm', token=token))['result'], 'expired')
        self.assertFalse(self.calls)
    def test_changed_plan(self):
        token = self.new()
        self.proposal = {**self.proposal, 'digest': 'different'}
        self.assertEqual(self.b.handle(self.request('confirm', token=token))['result'], 'changed')
        self.assertFalse(self.calls)
    def test_unknown_package_and_extra_fields(self):
        for req in [self.request('new', package='curl'), self.request('new', package='htop; id'), self.request('new', package='htop', command='id')]:
            with self.assertRaises(ValueError):
                self.b.handle(req)
        self.assertFalse(self.calls)
    def test_db_failure_fails_closed(self):
        token = self.new()
        self.db.execute("CREATE TRIGGER reject_update BEFORE UPDATE ON package_jobs BEGIN SELECT RAISE(ABORT, 'audit failure'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            self.b.handle(self.request('confirm', token=token))
        self.assertFalse(self.calls)
    def test_uncertain_locks_new_attempt(self):
        token = self.new()
        def fail(plan):
            raise RuntimeError()
        self.b.runner = fail
        self.assertEqual(self.b.handle(self.request('confirm', token=token))['result'], 'uncertain')
        self.assertEqual(self.b.handle(self.request('new', package='htop'))['result'], 'locked')
    def test_restart_no_replay(self):
        self.new()
        self.db.execute("UPDATE package_jobs SET state='started'")
        restored = p.Broker(self.db, {42}, lambda package: self.proposal, lambda plan: self.calls.append(plan))
        self.assertEqual(restored.handle(self.request('status'))['result'], 'uncertain')
        self.assertFalse(self.calls)
    def test_read_status_and_result(self):
        token = self.new()
        self.assertEqual(self.b.handle(self.request('result', token=token))['result'], 'pending')
        self.assertEqual(self.b.handle(self.request('status'))['result'], 'pending')
        self.assertFalse(self.calls)
    def test_tree_binding_and_no_substitution(self):
        token = self.b.handle(self.request('new', package='tree'))['token']
        with self.assertRaises(ValueError):
            self.b.handle(self.request('confirm', token=token, package='htop'))
        reply = self.b.handle(self.request('confirm', token=token))
        self.assertEqual(reply['package'], 'tree')
        self.assertEqual(self.calls[0]['package'], 'tree')
    def test_discord_namespace_and_access(self):
        access = {'users': [42], 'guild_id': 70, 'channel_id': 80}
        self.b.discord_access = access
        request = dict(op='new', user_id=42, chat_id=80, guild_id=70, message_id=10, package='tree')
        for key, value in [('guild_id', 71), ('chat_id', 81), ('user_id', 43)]:
            with self.assertRaises(ValueError):
                self.b.handle({**request, key: value}, platform='discord')
        token = self.b.handle(request, platform='discord')['token']
        self.assertEqual(self.db.execute('SELECT uid FROM package_jobs WHERE token=?', (token,)).fetchone()[0], -42)
        # Even equal numeric user/message IDs cannot reuse a Discord token on Telegram.
        with self.assertRaises(ValueError):
            self.b.handle(self.request('confirm', token=token))
        confirmed = {k: v for k, v in request.items() if k != 'package'}
        confirmed.update(op='confirm', token=token)
        self.assertEqual(self.b.handle(confirmed, platform='discord')['result'], 'success')
        self.assertEqual(len(self.calls), 1)
    def test_real_parser_and_unsafe_changes(self):
        safe = 'Inst tree (2.3.1-1 Ubuntu:26.04/resolute [amd64])\nConf tree (2.3.1-1 Ubuntu:26.04/resolute [amd64])\n'
        for text, allowed in [(safe, True), (safe + 'Remv ssh [1]\n', False),
                              (safe + 'Inst libc6 [1] (2 Ubuntu [amd64])\n', False)]:
            with patch.object(p, 'installed', return_value=None), patch.object(p.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=text)):
                if allowed:
                    result = p.plan('tree')
                    self.assertEqual(result['versions'], ['tree=2.3.1-1'])
                    self.assertEqual(result['package'], 'tree')
                else:
                    with self.assertRaises(ValueError):
                        p.plan('tree')

if __name__ == '__main__':
    unittest.main(verbosity=2)
