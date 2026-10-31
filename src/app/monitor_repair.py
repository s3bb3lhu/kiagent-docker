"""Confirmed, fixed mdmonitor recovery; no AI tool execution."""
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler
from practice_action import authorized, identity, rpc

ACTION = "repair_mdmonitor"
UNITS = ["mdmonitor.service", "mdmonitor-oneshot.service"]


async def propose_repair(update, context):
    if not authorized(update, context) or update.message is None:
        return
    if context.args:
        await update.message.reply_text("Bitte /raid_monitor_start ohne Argumente senden.")
        return
    try:
        result = await rpc({"op": "new", "action": ACTION, **identity(update)})
        token = result.get("token")
        if (result.get("ok") is not True or result.get("action") != ACTION
                or result.get("units") != UNITS or not isinstance(token, str)
                or re.fullmatch(r"[0-9a-f]{32}", token) is None):
            raise ValueError("Invalid proposal")
        sent = await update.message.reply_text(
            "RAID-Überwachung: Freigabe wird vorbereitet …"
        )
        bound = await rpc({"op": "bind", **identity(update),
                           "token": token, "message_id": sent.message_id})
        if bound.get("ok") is not True:
            await sent.edit_text("Freigabe nicht bereitgestellt. Keine Reparatur angefordert.")
            return
        await sent.edit_text(
            "RAID-ÜBERWACHUNG STARTEN\n"
            "Festgelegte Dienste: mdmonitor.service und mdmonitor-oneshot.service\n"
            "Wirkung: Fehlerstatus und Startsperren dieser Dienste zurücksetzen; "
            "Monitor starten und einmalige Prüfung ausführen. "
            "Ein laufender Monitor wird nicht neu gestartet.\n"
            "Keine Änderung der RAID-Mitglieder oder SSH-Konfiguration.\n"
            "Einmalige Freigabe; läuft zwei Minuten nach Anforderung ab.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Bestätigen", callback_data=f"mdmon:{token}:confirm"),
                InlineKeyboardButton("Abbrechen", callback_data=f"mdmon:{token}:cancel"),
            ]]),
        )
    except Exception as error:
        print(f"Monitor-Freigabe fehlgeschlagen ({type(error).__name__}).", flush=True)
        await update.message.reply_text("Freigabe nicht bereitgestellt. Keine Reparatur angefordert.")


async def decide_repair(update, context):
    query = update.callback_query
    if query is None:
        return
    if not authorized(update, context):
        await query.answer("Nicht erlaubt.", show_alert=True)
        return
    match = re.fullmatch(r"mdmon:([0-9a-f]{32}):(confirm|cancel)", query.data or "")
    if query.message is None or match is None:
        await query.answer("Ungültige Anfrage.")
        return
    await query.answer("Freigabe wird geprüft.")
    try:
        result = await rpc({"op": match[2], **identity(update),
                            "token": match[1], "message_id": query.message.message_id})
    except Exception as error:
        print(f"Monitor-Ergebnis unklar ({type(error).__name__}).", flush=True)
        await query.edit_message_text(
            "Ergebnis unklar. Die Aktion könnte bereits ausgeführt worden sein. "
            "Keine automatische Wiederholung; Dienststatus und Executor-Journal prüfen.",
            reply_markup=None,
        )
        return
    status = result.get("result")
    if status == "success" and result.get("ok") is True and result.get("action") == ACTION:
        text = ("RAID-Überwachung erfolgreich geprüft: mdmonitor läuft; "
                "die einmalige Prüfung wurde erfolgreich beendet. "
                "Dies bestätigt keine umfassende Festplattengesundheit.")
    elif status == "cancelled":
        text = "Abgebrochen. Keine Reparatur ausgeführt."
    elif status == "expired":
        text = "Freigabe abgelaufen. Keine Reparatur ausgeführt."
    elif status == "cooldown":
        text = (f"Gemeinsame Aktionssperre: noch {result.get('retry_after', 120)} Sekunden. "
                "Freigabe verbraucht; keine Reparatur ausgeführt.")
    elif status == "already":
        await query.message.reply_text("Freigabe bereits verbraucht. Keine weitere Aktion ausgelöst.")
        return
    elif status == "unknown":
        text = "Freigabe nicht mehr vorhanden. Keine Aktion ausgelöst."
    elif status in {"uncertain", "unverified"}:
        text = ("Aktion angefordert, Ergebnis nicht sicher bestätigt. "
                "Keine automatische Wiederholung; Dienststatus und Executor-Journal prüfen.")
    else:
        text = "Anfrage abgelehnt oder Ergebnis unklar. Executor-Journal prüfen."
    await query.edit_message_text(text, reply_markup=None)


def register_monitor_repair(app):
    app.add_handler(CommandHandler("raid_monitor_start", propose_repair))
    app.add_handler(CallbackQueryHandler(
        decide_repair, pattern=r"^mdmon:[0-9a-f]{32}:(confirm|cancel)$", block=False,
    ))
