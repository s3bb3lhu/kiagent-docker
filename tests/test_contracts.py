import ast
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/app'))
sys.path.insert(0,str(ROOT/'tools'))
import scan_secrets

class Contracts(unittest.TestCase):
    def test_no_credentials_or_personal_identifiers(self):
        self.assertEqual(scan_secrets.findings(), [])
    def test_all_python_syntax(self):
        for path in ROOT.rglob('*.py'):
            if '.git' not in path.parts:
                ast.parse(path.read_text(), filename=str(path))
    def test_secret_scanner_rejects_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'auth.json').write_text('{}')
            self.assertTrue(scan_secrets.findings(root))
    def test_host_metrics_only_fixed_paths(self):
        source = (ROOT/'host/host_metrics.py').read_text()
        self.assertNotIn('shell=True',source)
        self.assertIn("re.fullmatch(r'md[0-9]+'",source)
    def test_metrics_do_not_fall_back_to_container_metrics(self):
        import host_metrics_client
        host_metrics_client._cached = None
        with patch.object(host_metrics_client.socket, 'socket', side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                host_metrics_client.snapshot()
    def test_telegram_frontend_uses_host_values(self):
        text = (ROOT/'src/app/bot.py').read_text()
        self.assertNotIn('os.getloadavg()',text)
        self.assertNotIn('shutil.disk_usage(',text)
        self.assertIn('host_metrics_client import snapshot',text)
    def test_container_security_contract(self):
        text = (ROOT/'compose.yaml').read_text()
        self.assertNotIn('privileged:',text)
        self.assertNotIn('docker.sock',text)
        self.assertNotIn('pid: host',text)
        self.assertIn('read_only: true',text)
        self.assertIn('cap_drop: [ALL]',text)
        dockerignore = (ROOT/'.dockerignore').read_text()
        self.assertTrue(dockerignore.startswith('*\n'))

if __name__ == '__main__':
    unittest.main()
