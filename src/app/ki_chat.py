"""Telegram entry point for server questions and installation planning."""
import asyncio
import os
import time
from pathlib import Path

from ai_install import resolve
from package_action import propose_package
from telegram.ext import CommandHandler
from diagnose import snapshot
import json

LOCK = asyncio.Lock()
NEXT_ALLOWED = 0.0



def authorized(update, context):
    user, chat = update.effective_user, update.effective_chat
    return bool(user and not user.is_bot and chat and chat.type == 'private'
                and user.id == chat.id and update.message
                and user.id in context.application.bot_data['allowed_users'])


async def ki(update, context):
    global NEXT_ALLOWED
    if not authorized(update, context):
        return
    message = update.message
    request = ' '.join(context.args).strip()
    if not request:
        await message.reply_text(
            'Sende zum Beispiel: /ki Ich moechte Docker installieren.\n'
            'Du erhaeltst einen Plan. Dieser Befehl fuehrt noch keine '
            'Installationen aus. Bitte keine Zugangsdaten senden.')
        return
    if len(request) > 1200:
        await message.reply_text('Bitte den Auftrag auf 1200 Zeichen kuerzen.')
        return
    if LOCK.locked():
        await message.reply_text('Ein KI-Auftrag wird bereits bearbeitet.')
        return
    async with LOCK:
        remaining = NEXT_ALLOWED - time.monotonic()
        if remaining > 0:
            await message.reply_text(f'Bitte noch {int(remaining) + 1} Sekunden warten.')
            return
        NEXT_ALLOWED = time.monotonic() + 30
        await message.reply_text(
            'Dein Auftrag und feste Statusmesswerte werden an OpenAI gesendet. '
            'Bei Installationswuenschen bereite ich einen echten Paketplan mit gesonderter Bestaetigung vor.')
        try:
            key = (Path(os.environ['CREDENTIALS_DIRECTORY']) /
                   'openai-api-key').read_text().strip()
            decision=await asyncio.wait_for(resolve(key,request,await asyncio.to_thread(snapshot)),timeout=50)
            if decision['intent']=='install':
                await message.reply_text('Installationswunsch erkannt: '+decision['package']+'. Der echte APT-Plan wird jetzt vorbereitet. Erst nach deiner Bestaetigung wird installiert.')
                await propose_package(update,context,decision['package'])
                return
            text='KI-Antwort – keine Aenderungen ausgefuehrt:\n\n'+decision['answer'][:3400]
        except Exception:
            text = ('KI-Antwort derzeit nicht verfuegbar. Keine Aenderungen '
                    'ausgefuehrt. /status und /automatik_status bleiben verfuegbar.')
        await message.reply_text(text, parse_mode=None)


def register_ki_chat(app):
    app.add_handler(CommandHandler('ki', ki, block=False))
