import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import parallel_https as tls

class ParallelHttpsTests(unittest.TestCase):
    def test_port_selection_skips_an_existing_listener(self):
        with socket.socket() as listener:
            listener.bind(('0.0.0.0',0));listener.listen()
            port=listener.getsockname()[1]
            selected=tls.free_port(port)
            self.assertNotEqual(port,selected)
            self.assertEqual(listener.getsockname()[1],port)

    def test_compose_changes_only_the_new_web_service(self):
        text=(ROOT/'compose.yaml').read_text()
        rendered=tls.render_compose(text,8787,9443)
        before=text.split('  config-web:',1)[0];after=rendered.split('  config-web:',1)[0]
        self.assertEqual(before,after)
        self.assertIn("ports: ['0.0.0.0:9443:8080']",rendered)
        self.assertIn('CONFIG_DIRECT_TLS:',rendered)
        self.assertIn('source: /etc/kiagent-docker/tls',rendered)
        self.assertNotIn('source: /etc/letsencrypt',rendered)
        self.assertNotIn('privileged:',rendered)
        self.assertNotIn('docker.sock',rendered)
        with self.assertRaises(ValueError):tls.render_compose(rendered,8787,9443)

    def test_wrong_ip_is_rejected_even_when_openssl_exits_successfully(self):
        with patch.object(tls,'paths',return_value=(Path('/cert'),Path('/key'))),patch.object(tls,'output',return_value='IP 8.8.8.8 does NOT match certificate') as run:
            with self.assertRaises(ValueError):tls.validate({},'8.8.8.8')
            self.assertEqual(run.call_count,1)

    def test_certificate_symlink_must_stay_within_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'key').write_text('fixture')
            for field in ('../outside','/etc/passwd'):
                with patch.object(tls,'protected'):
                    with self.assertRaises(ValueError):tls.paths({'root':str(root),'certificate':field,'key':'key'})

    def test_reload_failure_is_retried_without_new_certificate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);state=root/'state';state.write_text('{"kind":"parallel-https-v1","source":{},"address":"8.8.8.8"}')
            pending=root/'reload-pending';pending.touch()
            with patch.object(tls,'STATE',state),patch.object(tls,'TLS',root),patch.object(tls,'protected'),patch.object(tls,'copy_certificate',return_value=False),patch.object(tls.subprocess,'run') as run:
                tls.sync();run.assert_called_once();self.assertFalse(pending.exists())

if __name__=='__main__':unittest.main()
