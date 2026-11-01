import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import host_compose_install as install

class CertificatePolicyTests(unittest.TestCase):
    def setUp(self):
        patches=[patch.object(sys,'argv',['install','--address','8.8.8.8','--admin-ip','203.0.113.5']),patch.object(install.os,'geteuid',return_value=0),patch.object(install.os,'chdir'),patch.object(install.Path,'exists',return_value=False),patch.object(install,'atomic')]
        for item in patches:item.start();self.addCleanup(item.stop)

    def test_missing_certificate_on_free_host_invokes_issuance(self):
        with patch.object(install.subprocess,'check_output',return_value=''),patch.object(install.parallel_https,'discover',return_value=None),patch.object(install.subprocess,'run') as run:
            install.main()
            commands=[call.args[0] for call in run.call_args_list]
            self.assertEqual(len(commands),2)
            self.assertIn('--unattended',commands[1]);self.assertTrue(commands[1][3].endswith('/tools/install_https.py'))

    def test_valid_certificate_is_reused_even_when_ports_are_free(self):
        certificate={'root':'/fixture'}
        with patch.object(install.subprocess,'check_output',return_value=''),patch.object(install.parallel_https,'discover',return_value=certificate),patch.object(install.parallel_https,'free_port',side_effect=[18787,9443]),patch.object(install.parallel_https,'configure') as configure,patch.object(install.subprocess,'run') as run:
            install.main();self.assertEqual(run.call_count,1)
            configure.assert_called_once_with('8.8.8.8','203.0.113.5',9443,18787,certificate)

    def test_busy_foreign_server_without_certificate_is_not_modified(self):
        with patch.object(install.subprocess,'check_output',return_value='LISTEN 0 5 0.0.0.0:80 0.0.0.0:*\n'),patch.object(install.parallel_https,'discover',return_value=None),patch.object(install.subprocess,'run') as run:
            with self.assertRaises(ValueError):install.main()
            run.assert_not_called()

if __name__=='__main__':unittest.main()
