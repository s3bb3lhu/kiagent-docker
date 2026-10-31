from host_metrics_client import snapshot
from package_action import register_package_action
from ki_chat import register_ki_chat
from practice_action import register_practice_action
from monitor_repair import register_monitor_repair
from automation_status import register_automation_status
from actions_test import register_test_actions
from diagnose import diagnose
from container_lifecycle import start_monitor, stop_monitor
import logging
import os
import shutil
import sys
from pathlib import Path

from telegram.ext import ApplicationBuilder, CommandHandler

# Keine Bibliotheksprotokolle mit möglichen Token-URLs ausgeben.
logging.disable(logging.CRITICAL)


def ram():
    data = snapshot()
    return (f"RAM: {data['ram_total_mib'] - data['ram_available_mib']:.0f} / {data['ram_total_mib']:.0f} MiB belegt\n"
            f"Verfuegbar: {data['ram_available_mib']:.0f} MiB")



def disk():
    data = snapshot()
    return f"Dateisystem /: {data['root_disk_used_percent']:.1f} % belegt ({data['root_disk_total_gib']:.1f} GiB gesamt)"



def uptime():
    seconds = snapshot()['uptime_seconds']
    return f"Systemlaufzeit: {seconds // 86400} Tage, {seconds // 3600 % 24} Stunden, {seconds // 60 % 60} Minuten"



async def command(update, context):
    user = update.effective_user
    chat = update.effective_chat
    message = update.message

    if (
        user is None
        or user.is_bot
        or user.id not in context.application.bot_data["allowed_users"]
        or chat is None
        or chat.type != "private"
        or message is None
    ):
        return

    name = message.text.split()[0].split("@")[0].lower()
    if context.args:
        await message.reply_text("Bitte den Befehl ohne Argumente senden.")
        return

    if name == "/ram":
        text = ram()
    elif name == "/disk":
        text = disk()
    elif name == "/uptime":
        text = uptime()
    else:
        load = snapshot()["load_1_5_15_minutes"]
        text = (
            "Statusabfrage erfolgreich.\n"
            f"Systemlast (1/5/15 Minuten): "
            f"{load[0]:.2f} / {load[1]:.2f} / {load[2]:.2f}\n\n"
            f"{uptime()}\n{ram()}\n{disk()}\n\n"
            "Befehle: /status /ram /disk /uptime"
        )

    await message.reply_text(text)


async def on_error(update, context):
    print("Bot-Anfrage fehlgeschlagen; Details werden nicht protokolliert.",
          flush=True)


def main():
    credentials = Path(os.environ["CREDENTIALS_DIRECTORY"])
    token = (credentials / "telegram-token").read_text().strip()
    lines = (credentials / "allowed-users").read_text().splitlines()
    allowed = {int(line.strip()) for line in lines if line.strip()}

    if not allowed or any(uid <= 0 for uid in allowed):
        raise ValueError("Ungültige Zugriffsliste")
    if not token or any(char.isspace() for char in token):
        raise ValueError("Ungültiger Token")

    app = (ApplicationBuilder().token(token).post_init(start_monitor).post_stop(stop_monitor).build())
    app.bot_data["allowed_users"] = allowed
    app.add_handler(
        CommandHandler(["status", "ram", "disk", "uptime"], command)
    )
    app.add_handler(CommandHandler("diagnose", diagnose, block=False))
    register_test_actions(app)
    register_practice_action(app)
    register_monitor_repair(app)
    register_automation_status(app)
    register_ki_chat(app)
    register_package_action(app)
    app.add_error_handler(on_error)
    print("Bot startet mit aktivierter Zugriffsliste.", flush=True)
    app.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Bot gestoppt: Konfiguration oder Telegram-Verbindung prüfen.",
              flush=True)
        sys.exit(1)
