import asyncio
import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler

SOCKET = "/run/kiagent-executor/control.sock"
UNIT = "kiagent-practice.service"


def authorized(update, context):
    user = update.effective_user
    chat = update.effective_chat
    return (
        user is not None
        and not user.is_bot
        and user.id in context.application.bot_data["allowed_users"]
        and chat is not None
        and chat.type == "private"
        and chat.id == user.id
    )


async def rpc(request):
    async def exchange():
        reader, writer = await asyncio.open_unix_connection(
            SOCKET, limit=8192
        )
        try:
            writer.write((json.dumps(request) + "\n").encode())
            await writer.drain()
            raw = await reader.readline()
            if not raw.endswith(b"\n") or len(raw) > 8192:
                raise ValueError("Ungültige Helferantwort")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError("Ungültige Helferantwort")
            return result
        finally:
            writer.close()
            await writer.wait_closed()

    # Keine Wiederholung: Eine Aktion könnte bereits ausgeführt worden sein.
    return await asyncio.wait_for(exchange(), timeout=40)


def identity(update):
    return {
        "user_id": update.effective_user.id,
        "chat_id": update.effective_chat.id,
    }


async def propose(update, context):
    if not authorized(update, context) or update.message is None:
        return
    if context.args:
        await update.message.reply_text(
            "Bitte /uebung_neustart ohne Argumente senden."
        )
        return

    try:
        result = await rpc({"op": "new", **identity(update)})
        if result.get("ok") is not True or result.get("unit") != UNIT:
            raise ValueError("Freigabe nicht erstellt")
        token = result["token"]

        # Zunächst ohne Schaltflächen senden, dann beim Helfer binden.
        sent = await update.message.reply_text(
            "NEUSTART DES ÜBUNGSDIENSTES\n"
            f"Dienst: {UNIT}\n"
            "Wirkung: Der wartende Übungsprozess wird beendet und neu gestartet.\n"
            "Keine Unterbrechung von SSH oder Telegram-Bot.\n"
            "Freigabe: einmalig, maximal zwei Minuten gültig.\n\n"
            "Freigabe wird vorbereitet …"
        )
        bound = await rpc({
            "op": "bind", **identity(update),
            "token": token, "message_id": sent.message_id,
        })
        if bound.get("ok") is not True:
            await sent.edit_text(
                "Freigabe konnte nicht gebunden werden. Kein Neustart angefordert."
            )
            return

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "Bestätigen", callback_data=f"practice:{token}:confirm"
            ),
            InlineKeyboardButton(
                "Abbrechen", callback_data=f"practice:{token}:cancel"
            ),
        ]])
        await sent.edit_text(
            "NEUSTART DES ÜBUNGSDIENSTES\n"
            f"Dienst: {UNIT}\n"
            "Wirkung: Der wartende Übungsprozess wird beendet und neu gestartet.\n"
            "Keine Unterbrechung von SSH oder Telegram-Bot.\n"
            "Einmalige Freigabe; läuft zwei Minuten nach Anforderung ab.",
            reply_markup=keyboard,
        )
    except Exception as error:
        print(f"Neustart-Anfrage fehlgeschlagen ({type(error).__name__}).",
              flush=True)
        await update.message.reply_text(
            "Freigabe nicht bereitgestellt. Es wurde kein Neustart angefordert."
        )


async def decide(update, context):
    query = update.callback_query
    if query is None:
        return
    if not authorized(update, context):
        await query.answer("Nicht erlaubt.", show_alert=True)
        return
    if query.message is None or not isinstance(query.data, str):
        await query.answer("Ungültige Anfrage.")
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer("Ungültige Anfrage.")
        return
    _, token, operation = parts

    await query.answer("Freigabe wird geprüft.")
    try:
        result = await rpc({
            "op": operation, **identity(update),
            "token": token, "message_id": query.message.message_id,
        })
    except Exception as error:
        print(f"Neustart-Ergebnis unklar ({type(error).__name__}).",
              flush=True)
        await query.edit_message_text(
            "Ergebnis unklar: Der Helfer war nicht zuverlässig erreichbar.\n"
            "Keine automatische Wiederholung. Bitte Dienststatus und "
            "Helfer-Journal im SSH-Terminal prüfen.",
            reply_markup=None,
        )
        return

    status = result.get("result")
    if status == "success" and result.get("ok") is True:
        before = result["before"]["InvocationID"]
        after = result["after"]["InvocationID"]
        text = (
            f"Neustart erfolgreich: {UNIT}\n"
            "Dienst ist active; InvocationID hat sich geändert.\n"
            f"Vorher: {before}\nNachher: {after}"
        )
    elif status == "cancelled":
        text = "Abgebrochen. Kein Neustart ausgeführt."
    elif status == "expired":
        text = "Freigabe abgelaufen. Kein Neustart ausgeführt."
    elif status == "cooldown":
        seconds = int(result.get("retry_after", 120))
        text = (
            f"Neustart gesperrt: noch ungefähr {seconds} Sekunden warten.\n"
            "Diese Freigabe wurde verbraucht; kein Neustart ausgeführt.\n"
            "Nach der Sperrzeit bitte eine neue Anfrage stellen."
        )
    elif status == "already":
        await query.message.reply_text(
            "Diese Freigabe ist bereits abgeschlossen oder verbraucht. "
            "Kein weiterer Neustart ausgelöst."
        )
        return
    elif status == "unknown":
        text = "Freigabe nicht mehr vorhanden. Kein Neustart ausgelöst."
    elif status in {"unverified", "uncertain"}:
        text = (
            "Neustart angefordert, Ergebnis aber nicht sicher bestätigt.\n"
            "Nicht automatisch wiederholt. Bitte Dienststatus und "
            "Helfer-Journal im SSH-Terminal prüfen."
        )
    else:
        text = "Anfrage abgelehnt. Bitte Helfer-Journal prüfen."

    await query.edit_message_text(text=text, reply_markup=None)


def register_practice_action(app):
    app.add_handler(CommandHandler("uebung_neustart", propose))
    app.add_handler(CallbackQueryHandler(
        decide,
        pattern=r"^practice:[0-9a-f]{32}:(confirm|cancel)$",
        block=False,
    ))
