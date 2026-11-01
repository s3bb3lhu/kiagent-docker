import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from network_defaults import discover

class NetworkDefaultsTests(unittest.TestCase):
    def test_direct_ssh_connection_needs_no_probe(self):
        run=Mock(side_effect=AssertionError('No external probe needed'))
        self.assertEqual(discover('203.0.113.5 55000 8.8.8.8 22',run),('8.8.8.8','203.0.113.5'))

    def test_sudo_fallback_uses_unique_host_login_and_public_interface(self):
        run=Mock(side_effect=['seb pts/0 2026-11-01 12:00 (203.0.113.5)\n',json.dumps([{'addr_info':[{'local':'10.0.0.3'},{'local':'8.8.8.8'}]}])])
        self.assertEqual(discover('',run),('8.8.8.8','203.0.113.5'))

    def test_ambiguous_or_missing_sessions_never_expose_setup(self):
        for text in ('','a pts/0 date time (203.0.113.1)\nb pts/1 date time (203.0.113.2)\n'):
            run=Mock(return_value=text)
            with self.assertRaises(ValueError):discover('',run)
            self.assertEqual(run.call_count,1)

    def test_nat_and_multiple_public_addresses_fail_closed(self):
        for entries in ([{'local':'10.0.0.1'}],[{'local':'8.8.8.8'},{'local':'1.1.1.1'}]):
            run=Mock(return_value=json.dumps([{'addr_info':entries}]))
            with self.assertRaises(ValueError):discover('203.0.113.1 55000 10.0.0.1 22',run)

    def test_malformed_connection_never_runs_a_command(self):
        for value in ('bad','203.0.113.1 xx 8.8.8.8 22','127.0.0.1 5 8.8.8.8 22','203.0.113.1 5 8.8.8.8;id 22'):
            run=Mock()
            with self.assertRaises(ValueError):discover(value,run)
            run.assert_not_called()

if __name__=='__main__':unittest.main()
