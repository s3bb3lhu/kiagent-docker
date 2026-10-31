import asyncio
import json
import io
import re
import socket

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler
from practice_action import authorized, identity
from package_policy import valid_package


def exchange(request):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(180)
        sock.connect('/run/kiagent-packages/control.sock')
        sock.sendall(json.dumps(request).encode() + b'\n')
        data = bytearray()
        while b'\n' not in data and len(data) < 1048576:
            part = sock.recv(4096)
            if not part:
                break
            data.extend(part)
        if not data.endswith(b'\n') or len(data) >= 1048576:
            raise ValueError('Invalid broker response')
        return json.loads(data)


async def rpc(request):
    return await asyncio.to_thread(exchange, request)


def fields(update, message_id):
    return {**identity(update), 'message_id': message_id}


def describe(reply):
    status = reply.get('result')
    package = reply.get('package')
    package = package if valid_package(package) else 'Das Paket'
    messages = {
        'success': package + ' wurde erfolgreich installiert und die Paketversion geprueft.\n' + reply.get('version', ''),
        'installed': package + ' ist bereits installiert. Keine Installation ausgefuehrt.',
        'already_installed': package + ' war vor Ausfuehrung bereits installiert. Keine Installation ausgefuehrt.',
        'cancelled': 'Abgebrochen. Keine Installation ausgefuehrt.',
        'expired': 'Freigabe abgelaufen. Keine Installation ausgefuehrt.',
        'plan_failed': 'Paketplan konnte nicht erneut geprueft werden. Keine Installation ausgefuehrt.',
        'changed': 'Der Paketplan hat sich geaendert. Keine Installation ausgefuehrt. Bitte einen neuen Plan anfordern.',
        'locked': 'Ein Versuch ist noch offen oder unklar. Keine neue Installation gestartet; Pruefung per SSH erforderlich.',
        'failed_reviewed': 'Der vorherige Versuch ist vor der Paketinstallation gescheitert und wurde per SSH geprueft. Fuer einen neuen Versuch ist ein neuer Paketplan mit Bestaetigung erforderlich.',
        'pending': 'Ein Installationsplan wartet auf Bestaetigung.',
        'none': 'Noch kein Installationsauftrag gespeichert.',
        'started': 'Installation gestartet. Nicht erneut ausloesen; Ergebnis spaeter mit /ki_install_status pruefen.',
        'checking': 'Die Freigabe wird geprueft.',
    }
    return messages.get(status, 'Ergebnis unklar. Keine automatische Wiederholung. /ki_install_status und Pruefung per SSH verwenden.')


async def propose(update, context):
    if not authorized(update, context) or update.message is None:
        return
    if len(context.args) != 1 or not valid_package(context.args[0].lower()):
        await update.message.reply_text('Verwendung: /ki_install PAKETNAME. Alle Pakete aus den eingerichteten APT-Quellen sind freigegeben; erst Plan und Bestaetigung, dann Installation.')
        return
    await propose_package(update,context,context.args[0].lower())


async def propose_package(update,context,package):
    if not authorized(update,context) or update.message is None or not valid_package(package):
        return
    sent = await update.message.reply_text(f'Paketplan fuer {package} wird lesend geprueft. Noch keine Installation.')
    try:
        reply = await rpc({'op': 'new', 'package': package, **fields(update, sent.message_id)})
        if reply.get('result') != 'pending' or reply.get('ok') is not True:
            await sent.edit_text(describe(reply))
            return
        token = reply['token']
        if re.fullmatch('[0-9a-f]{32}', token) is None:
            raise ValueError('Invalid token')
        changes = '\n'.join(reply['changes'])
        if len(changes)>2500:
            await update.message.reply_document(document=io.BytesIO(changes.encode()),filename='apt-plan.txt',caption='Vollstaendiger APT-Paketplan zur Bestaetigung.')
            changes=f"{len(reply['changes'])} Planschritte. Vollstaendigen Plan in apt-plan.txt pruefen."
        await sent.edit_text(
            package.upper() + ' INSTALLIEREN\n\n' + changes + '\n\n'
            'Pakete aus den eingerichteten APT-Paketquellen. Abhaengigkeiten koennen aktualisiert und Dienste neu gestartet werden. '
            'Der Plan wird vor Ausfuehrung erneut verglichen. '
            'Einmalige Freigabe, zwei Minuten gueltig.',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('Installieren', callback_data=f'pkg:{token}:confirm'),
                InlineKeyboardButton('Abbrechen', callback_data=f'pkg:{token}:cancel'),
            ]]))
    except Exception:
        await sent.edit_text('Paketplan nicht bereitgestellt: Paketname, Paketquellen oder Abhaengigkeiten pruefen. Keine Installation ausgefuehrt.')


async def decide(update, context):
    query = update.callback_query
    if query is None:
        return
    if not authorized(update, context):
        await query.answer('Nicht erlaubt.', show_alert=True)
        return
    match = re.fullmatch(r'pkg:([0-9a-f]{32}):(confirm|cancel)', query.data or '')
    if match is None or query.message is None:
        await query.answer('Ungueltige Anfrage.')
        return
    await query.answer('Freigabe wird geprueft.')
    request = {'op': match[2], 'token': match[1], **fields(update, query.message.message_id)}
    try:
        # Successful Telegram notice is required before contacting the executor.
        await query.edit_message_text('Bestaetigung erhalten. Installation wird geprueft und gegebenenfalls ausgefuehrt.'
                                      if match[2] == 'confirm' else 'Abbruch wird verarbeitet.', reply_markup=None)
        reply = await rpc(request)
        if reply.get('result') == 'consumed':
            reply = await rpc({**request, 'op': 'result'})
        for _ in range(900):
            if reply.get('result') not in {'started','checking'}:break
            await asyncio.sleep(2)
            reply=await rpc({**request,'op':'result'})
        await query.edit_message_text(describe(reply), reply_markup=None)
    except Exception:
        await query.message.reply_text('Ergebnis nicht sicher zugestellt. Keine Wiederholung ausloesen. Bitte /ki_install_status abfragen.')


async def status(update, context):
    if not authorized(update, context) or update.message is None:
        return
    if context.args:
        await update.message.reply_text('Bitte /ki_install_status ohne Argumente senden.')
        return
    try:
        reply = await rpc({'op': 'status', **fields(update, update.message.message_id)})
        text = describe(reply)
    except Exception:
        text = 'Installationsstatus derzeit nicht erreichbar. Keine Aktion angefordert.'
    await update.message.reply_text(text)


def register_package_action(app):
    app.add_handler(CommandHandler('ki_install', propose, block=False))
    app.add_handler(CommandHandler('ki_install_status', status, block=False))
    app.add_handler(CallbackQueryHandler(decide, pattern=r'^pkg:[0-9a-f]{32}:(confirm|cancel)$', block=False))
