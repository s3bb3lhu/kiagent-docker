import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
access = {'users': [42], 'guild_id': 70, 'channel_id': 80}
with tempfile.TemporaryDirectory() as temporary:
    Path(temporary, 'discord-access').write_text(json.dumps(access))
    os.environ['CREDENTIALS_DIRECTORY'] = temporary
    os.environ['DISCORD_APPLICATION_ID'] = '90'
    sys.modules['diagnose'] = types.SimpleNamespace(snapshot=lambda: {})
    spec = importlib.util.spec_from_file_location('discord_bot_test', ROOT / 'src/app/discord_bot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def interaction(**changes):
        result = types.SimpleNamespace(user=types.SimpleNamespace(id=access['users'][0], bot=False),
            guild_id=access['guild_id'], channel_id=access['channel_id'])
        for key, value in changes.items():
            setattr(result, key, value)
        return result

    assert module.allowed(interaction())
    for value in [interaction(guild_id=0), interaction(channel_id=0), interaction(guild_id=None),
                  interaction(user=types.SimpleNamespace(id=1, bot=False)),
                  interaction(user=types.SimpleNamespace(id=access['users'][0], bot=True))]:
        assert not module.allowed(value)
    commands = module.client.tree.get_commands(guild=module.GUILD)
    assert {cmd.name for cmd in commands} == {'status', 'ki', 'ki_install', 'ki_install_status', 'automatik_status', 'automatik_an', 'automatik_aus'}
    assert module.client.tree.get_commands() == []
    for command in commands:
        command.to_dict(module.client.tree)
    assert module.client.intents.message_content is False
    assert module.client.intents.members is False
    assert module.client.intents.presences is False
    async def view_test():
        view = module.Confirmation(access['users'][0], 10, 'a' * 32, kind='automation')
        view.confirm.label = 'Bestaetigen'
        assert view.confirm.label == 'Bestaetigen'
        view.stop()
    asyncio.run(view_test())
    print('Discord: Identitaet, Server/Kanal, DM-Ausschluss, Bot-Ausschluss, lokale Slash-Command-Schemas und minimale Intents: OK')
