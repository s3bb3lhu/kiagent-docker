import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import compose_bootstrap as bootstrap
from install_https import nginx_config,origin_for,web_port
import host_compose_install as install

class FullComposeTests(unittest.TestCase):
 def test_custom_https_port_preserves_origin_and_csrf_host(self):
  text=nginx_config('198.51.100.10',True,'203.0.113.10',port=8443)
  self.assertIn('listen 8443 ssl default_server;',text)
  self.assertNotIn('listen 443 ssl',text)
  self.assertEqual(text.count('proxy_set_header Host 198.51.100.10:8443;'),3)
  self.assertIn('return 308 https://198.51.100.10:8443$request_uri;',text)
  self.assertIn('allow 203.0.113.10; deny all;',text)
  self.assertEqual(origin_for('198.51.100.10'),'https://198.51.100.10')
  self.assertIn('listen 443 ssl',nginx_config('198.51.100.10',True))
 def test_unsafe_ports_and_addresses_fail_before_installation(self):
  for port in (0,22,80,8787,65536,'8443;id'):
   with self.assertRaises(ValueError):web_port(port)
  for address in ('127.0.0.1','10.0.0.1','198.51.100.10','example.com','8.8.8.8;id'):
   with self.assertRaises(ValueError):bootstrap.parameters(address,'203.0.113.5',8443)
  self.assertEqual(bootstrap.parameters('8.8.8.8','203.0.113.5',8443),('8.8.8.8','203.0.113.5',8443))
 def test_unsupported_host_and_uid_remapping_are_rejected(self):
  facts={'os':'ubuntu','release':'26.04','architecture':'x86_64','systemd':True,'python':[3,14],'security':['name=seccomp']}
  self.assertEqual(bootstrap.validate_host(facts),facts)
  for change in ({'os':'windows'},{'release':'22.04'},{'architecture':'aarch64'},{'systemd':False},{'python':[3,8]},{'security':['name=rootless']},{'security':['name=userns']}):
   with self.assertRaises(ValueError):bootstrap.validate_host({**facts,**change})
 def test_payload_symlinks_are_rejected_before_host_writes(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);payload=root/'payload';payload.mkdir();host=root/'host';host.mkdir()
   (payload/'link').symlink_to('/etc/passwd')
   with self.assertRaises(ValueError):bootstrap.stage_payload(payload,host)
   self.assertEqual(list(host.iterdir()),[])
 def test_fresh_install_refuses_existing_project_without_commands(self):
  with patch.object(install,'PROJECT',ROOT),patch.object(install.os,'geteuid',return_value=0),patch.object(sys,'argv',['installer','--address','8.8.8.8','--admin-ip','203.0.113.5']),patch.object(install.subprocess,'run') as execute:
   with self.assertRaises(SystemExit):install.main()
   execute.assert_not_called()
 def test_runtime_compose_never_inherits_installer_privileges(self):
  runtime=(ROOT/'compose.runtime.yaml').read_text()
  self.assertNotIn('privileged:',runtime);self.assertNotIn('pid: host',runtime);self.assertNotIn('docker.sock',runtime)
  setup=(ROOT/'compose.install.yaml').read_text()
  self.assertIn('profiles: [install]',setup);self.assertIn("restart: 'no'",setup);self.assertIn('driver: none',setup)

if __name__=='__main__':unittest.main()
