"""Read-only /automatik_status for allowlisted private Telegram chats."""
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram.ext import CommandHandler
from practice_action import authorized, identity, rpc


def duration(seconds):
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def timestamp(value):
    date = datetime.fromtimestamp(value, timezone.utc)
    try:
        date = date.astimezone(ZoneInfo("Europe/Berlin"))
    except ZoneInfoNotFoundError:
        pass
    return date.strftime("%d.%m.%Y %H:%M:%S %Z")


def loop_status(app):
    task = app.bot_data.get("auto_repair_task")
    last = app.bot_data.get("auto_repair_last_ok")
    age = None if last is None else max(0, int(time.monotonic()-last))
    return {"running":task is not None and not task.done(), "last_ok_age":age,
            "error":bool(app.bot_data.get("auto_repair_last_error",False))}


def build_text(data, loop):
    lines = ["AUTOMATIK-STATUS", "",
             "Automatische Reparaturen: " + ("eingeschaltet" if data["enabled"] else "ausgeschaltet"),
             "Überwachungsschleife: " + ("läuft" if loop["running"] else "läuft nicht")]
    if loop["last_ok_age"] is None:
        lines.append("Letzte erfolgreiche Automatikabfrage: seit Bot-Start noch keine")
    else:
        lines.append("Letzte erfolgreiche Automatikabfrage: vor " + duration(loop["last_ok_age"]))
    if loop["error"]:
        lines.append("Letzte Automatikabfrage oder Telegram-Zustellung fehlgeschlagen.")
    elif loop["last_ok_age"] is not None and loop["last_ok_age"] > 180:
        lines.append("Achtung: Letzte Automatikabfrage liegt über drei Minuten zurück.")
    if not data["available"]:
        lines.append("RAID-Überwachungsdienste: Status derzeit nicht verfügbar")
    else:
        monitor = data["states"]["mdmonitor.service"]
        oneshot = data["states"]["mdmonitor-oneshot.service"]
        if monitor.get("ActiveState")=="active" and monitor.get("SubState")=="running":
            lines.append("RAID-Monitor: läuft")
        else:
            lines.append("RAID-Monitor: " + monitor.get("ActiveState","unbekannt"))
        if oneshot.get("ActiveState")=="inactive" and oneshot.get("Result")=="success" and oneshot.get("ExecMainStatus")=="0":
            lines.append("Einmalige RAID-Prüfung: zuletzt erfolgreich beendet")
        elif oneshot.get("ActiveState") in {"active","activating"}:
            lines.append("Einmalige RAID-Prüfung: läuft")
        else:
            lines.append("Einmalige RAID-Prüfung: " + oneshot.get("ActiveState","unbekannt") + "/" + oneshot.get("Result","unbekannt"))
    lines.extend(["", f"Automatische Versuche in 24 Stunden: {data['attempts_24h']} / {data['limit_24h']}",
                  "Verbleibende Sperrzeiten (Stunden:Minuten:Sekunden):",
                  "Stundenlimit: " + duration(data["hourly_seconds"]),
                  "Tageslimit: " + duration(data["daily_seconds"]),
                  "Gemeinsamer Aktions-Cooldown: " + duration(data["shared_seconds"])])
    if not data["enabled"]:
        lines.append("Automatische Reparaturen bleiben bis zur Aktivierung gesperrt.")
    if data["manual_required"]:
        lines.append("Fehler-/Unklarheitssperre: erfolgreiche manuelle Reparatur mit /raid_monitor_start erforderlich.")
    if data["enabled"] and not data["manual_required"]:
        if data["earliest_seconds"]:
            lines.append("Zeitlimits erlauben nächsten Versuch frühestens in " + duration(data["earliest_seconds"]))
        else:
            lines.append("Keine zeitliche Aktionssperre.")
    if data["available"] and data["unhealthy"]:
        lines.append("Störung erkannt; Erkennungswartezeit noch " + duration(data["observation_seconds"]) + " (Prüfintervall 60 Sekunden).")
    elif data["available"]:
        lines.append("Aktuell kein Reparaturbedarf an der RAID-Überwachung.")
    lines.append(f"Noch offene Ergebnisbenachrichtigungen: {data['notifications_pending']}")
    lines.extend(["", "Letzte automatische Reparaturversuche:"])
    labels = {"success":"erfolgreich", "pending":"Ergebnis unklar / unterbrochen", "uncertain":"Ergebnis unklar",
              "unverified":"Ergebnis nicht bestätigt", "cooldown":"durch Cooldown blockiert"}
    if not data["history"]:
        lines.append("Noch keine automatischen Versuche gespeichert.")
    for item in data["history"]:
        text = f"#{item['id']} · {timestamp(item['timestamp'])} · " + labels.get(item["result"],"nicht erfolgreich")
        if item["resolved"] and item["result"]!="success":
            text += " · Fehlersperre manuell aufgehoben"
        if item["notifications_pending"]:
            text += " · Ergebniszustellung offen"
        lines.append(text)
    lines.extend(["", "Nur Statusabfrage; keine Aktion ausgeführt. Die Anzeige betrifft die RAID-Überwachung, keine umfassende Festplattenprüfung."])
    return "\n".join(lines)


async def automation_status(update, context):
    if not authorized(update, context) or update.message is None:
        return
    if context.args:
        await update.message.reply_text("Bitte /automatik_status ohne Argumente senden.")
        return
    try:
        result = await rpc({"op":"auto_overview", **identity(update)})
        if result.get("ok") is not True or result.get("kind") != "automation_overview_v1":
            raise ValueError("Status unavailable")
        text = build_text(result, loop_status(context.application))
    except Exception as error:
        print(f"Automatikstatus nicht verfügbar ({type(error).__name__}).", flush=True)
        text = "Automatikstatus derzeit nicht verfügbar. Diese Abfrage hat keine Reparatur ausgelöst."
    await update.message.reply_text(text, parse_mode=None)



async def automation_switch(update, context):
    if not authorized(update, context) or update.message is None:
        return
    if context.args:
        await update.message.reply_text("Bitte /automatik_an oder /automatik_aus ohne Argumente senden.")
        return
    command = (update.message.text or "").split()
    name = command[0].split("@")[0].lower() if command else ""
    if name not in {"/automatik_an", "/automatik_aus"}:
        return
    desired = name == "/automatik_an"
    try:
        result = await rpc({"op":"auto_control", "enabled":desired, **identity(update)})
        if (result.get("ok") is not True or result.get("kind") != "automation_control_v1"
                or result.get("enabled") is not desired or type(result.get("changed")) is not bool):
            raise ValueError("Control result not confirmed")
        if result["changed"]:
            text = "Automatische Reparaturen " + ("eingeschaltet." if desired else "ausgeschaltet.")
        else:
            text = "Automatische Reparaturen sind bereits " + ("eingeschaltet." if desired else "ausgeschaltet.")
        if desired:
            text += ("\nDie Automatik darf bei einer erkannten Störung wieder innerhalb der bestehenden Grenzen reparieren. "
                     "Stundenlimit, Tageslimit und Fehlersperren bleiben erhalten.")
        else:
            text += ("\nNeue automatische Reparaturversuche sind gesperrt. "
                     "Eine bereits laufende Aktion wird nicht abgebrochen.")
        text += ("\nÜberwachung, Telegram-Meldungen, Statusabfragen und manuelle Reparaturen bleiben verfügbar. "
                 "Die Einstellung bleibt nach Neustarts erhalten.\nStatus: /automatik_status")
    except Exception as error:
        print(f"Automatikumschaltung nicht bestätigt ({type(error).__name__}).", flush=True)
        text = ("Änderung nicht sicher bestätigt. Bitte /automatik_status prüfen. "
                "Keine automatische Wiederholung der Umschaltung.")
    await update.message.reply_text(text, parse_mode=None)


def register_automation_status(app):
    app.add_handler(CommandHandler("automatik_status", automation_status, block=False))
    app.add_handler(CommandHandler(["automatik_an", "automatik_aus"], automation_switch, block=False))
