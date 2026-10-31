import asyncio
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/app'))
from ai_install import decode

class IntentTests(unittest.TestCase):
    def test_only_structured_package_intent_is_accepted(self):
        good={'intent':'install','package':'nginx','answer':'Plan vorbereiten.'}
        self.assertEqual(decode(json.dumps(good))['package'],'nginx')
        for bad in ({**good,'package':'curl; id'},{**good,'command':'id'},
                    {**good,'intent':'execute'},{**good,'package':'https://example.com/x'},
                    {**good,'intent':'answer'}):
            with self.assertRaises(ValueError):decode(json.dumps(bad))

class TelegramIntentTests(unittest.IsolatedAsyncioTestCase):
    async def test_ai_install_request_reaches_confirmation_flow(self):
        import ki_chat
        with tempfile.TemporaryDirectory() as directory:
            Path(directory,'openai-api-key').write_text('fixture-only')
            update=types.SimpleNamespace(effective_user=types.SimpleNamespace(id=42,is_bot=False),
                effective_chat=types.SimpleNamespace(id=42,type='private'),message=types.SimpleNamespace(reply_text=AsyncMock()))
            context=types.SimpleNamespace(args=['Installiere','nginx'],application=types.SimpleNamespace(bot_data={'allowed_users':{42}}))
            proposal=AsyncMock()
            with patch.dict(os.environ,{'CREDENTIALS_DIRECTORY':directory}),patch.object(ki_chat,'NEXT_ALLOWED',0),patch.object(ki_chat,'LOCK',asyncio.Lock()),patch.object(ki_chat,'snapshot',return_value={}),patch.object(ki_chat,'resolve',AsyncMock(return_value={'intent':'install','package':'nginx','answer':'Plan wird vorbereitet.'})),patch.object(ki_chat,'propose_package',proposal):
                await ki_chat.ki(update,context)
            proposal.assert_awaited_once_with(update,context,'nginx')

if __name__=='__main__':unittest.main()
