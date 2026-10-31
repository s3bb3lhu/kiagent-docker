import secrets
import time
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler


@dataclass
class Pending:
    user_id: int
    chat_id: int
    message_id: int
    expires: float
    state: str = "pending"

    def decide(self, user_id, chat_id, message_id, choice, now):
        if (user_id, chat_id, message_id) != (
            self.user_id, self.chat_id, self.message_id
        ):
            return "denied"
        if choice not in ("yes", "no"):
            return "denied"
        if self.state != "pending":
            return "already"
        if now >= self.expires:
            self.state = "expired"
            return "expired"
        self.state = "confirmed" if choice == "yes" else "cancelled"
        return self.state


def authorized(update, context):
    user = update.effective_user
    chat = update.effective_chat
    return (
        user is not None
        and not user.is_bot
        and user.id in context.application.bot_data["allowed_users"]
        and chat is not None
        and chat.type == "private"
    )


async def propose(update, context):
    if not authorized(update, context) or update.message is None:
        return
    if context.args:
        await update.message.reply_text("Bitte /testaktion ohne Argumente senden.")
        return

    records = context.application.bot_data.setdefault("test_actions", {})
    now = time.monotonic()
    for key in list(records):
        if now > records[key].expires + 600:
            del records[key]
    if len(records) >= 100:
        await update.message.reply_text("Zu viele Testanfragen. Bitte später erneut versuchen.")
        return

    token = secrets.token_hex(12)
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("Bestätigen", callback_data=f"gatetest:{token}:yes"),
        InlineKeyboardButton("Abbrechen", callback_data=f"gatetest:{token}:no"),
    ]])
    sent = await update.message.reply_text(
        "TESTAKTION\n"
        "Aktion: Eine Ausführung simulieren und im Journal vermerken.\n"
        "Keine Systemänderung und kein KI-Aufruf.\n"
        "Freigabe: einmalig, gültig für zwei Minuten.",
        reply_markup=buttons,
    )
    records[token] = Pending(
        update.effective_user.id,
        sent.chat.id,
        sent.message_id,
        time.monotonic() + 120,
    )
    print(f"Testaktion angefragt: {token}", flush=True)


async def decide(update, context):
    query = update.callback_query
    if query is None:
        return
    if not authorized(update, context):
        await query.answer("Nicht erlaubt.", show_alert=True)
        return

    data = query.data
    if not isinstance(data, str):
        await query.answer("Ungültige Anfrage.")
        return
    parts = data.split(":")
    if len(parts) != 3 or query.message is None:
        await query.answer("Ungültige Anfrage.")
        return

    _, token, choice = parts
    records = context.application.bot_data.get("test_actions", {})
    record = records.get(token)
    if record is None:
        await query.answer("Anfrage nicht mehr gültig.", show_alert=True)
        return

    # Zustand wird vor dem ersten await endgültig geändert.
    result = record.decide(
        query.from_user.id,
        update.effective_chat.id,
        query.message.message_id,
        choice,
        time.monotonic(),
    )
    print(f"Testaktion Entscheidung: {token} {result}", flush=True)

    if result == "confirmed":
        # Ausschließlich eine Simulation, kein externer Befehl.
        print(f"TEST_EXECUTED {token}", flush=True)
        text = "TEST: Einmalig bestätigt und simuliert. Keine Systemänderung."
    elif result == "cancelled":
        text = "TEST: Abgebrochen. Keine Ausführung."
    elif result == "expired":
        text = "TEST: Freigabe abgelaufen. Keine Ausführung."
    elif result == "already":
        await query.answer("Bereits abgeschlossen; keine erneute Ausführung.",
                           show_alert=True)
        return
    else:
        await query.answer("Anfrage passt nicht zur Freigabe.", show_alert=True)
        return

    await query.answer()
    await query.edit_message_text(text=text, reply_markup=None)


def register_test_actions(app):
    app.add_handler(CommandHandler("testaktion", propose))
    app.add_handler(CallbackQueryHandler(
        decide, pattern=r"^gatetest:[0-9a-f]{24}:(yes|no)$"
    ))
