import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
sys.path.insert(0,str(ROOT/'src/app'))
from portable_web import PortableBackend
from config_fixtures import files,request

class PortableTests(unittest.TestCase):
    def test_configuration_is_durable_and_never_returns_tokens(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            backend=PortableBackend(root,b'fixture-only-key')
            initial=backend({'op':'overview'})
            self.assertIn('nicht verbunden',initial['capability_notice'])
            self.assertFalse(initial['configured']['telegram'])
            values=files(root)
            packet=request(backend.store)
            packet['public']['raid_devices']=''
            result=backend({'op':'save','data':packet})
            self.assertEqual(result['state'],'saved')
            view=PortableBackend(root,b'fixture-only-key')({'op':'overview'})
            self.assertEqual(view['public']['raid_devices'],'')
            encoded=json.dumps(view)
            for value in values.values():
                if value:self.assertNotIn(value,encoded)
            self.assertEqual(backend({'op':'restart','command':'anything'})['code'],'schema')
            self.assertEqual(backend({'op':'save','data':packet})['code'],'stale')

if __name__=='__main__':unittest.main()
