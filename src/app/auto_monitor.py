"""Fixed RAID-monitor autorepair; no AI or arbitrary commands."""
import asyncio
import time

from practice_action import rpc

INTERVAL = 60
PERSISTENCE = 120


async def send_all(app, text):
    recipients = sorted(app.bot_data["allowed_users"])
    if not recipients:
        raise ValueError("Empty recipient list")
    for uid in recipients:
        await app.bot.send_message(chat_id=uid, text=text, parse_mode=None)


async def deliver_notices(app, notices):
    for item in notices:
        status = item["result"]
        if status == "success":
            outcome = ("Erfolgreich: RAID-Monitor läuft; einmalige Prüfung erfolgreich beendet. "
                       "Keine Änderung der RAID-Mitglieder.")
        else:
            outcome = ("Ergebnis fehlgeschlagen oder unklar (" + status + "). "
                       "Automatik gesperrt; keine automatische Wiederholung. "
                       "Bitte Dienststatus prüfen. Eine erfolgreiche manuelle Aktion "
                       "/raid_monitor_start hebt diese Sperre auf; Zeitlimits bleiben bestehen.")
        for uid in item["recipients"]:
            if uid not in app.bot_data["allowed_users"]:
                raise ValueError("Recipient mismatch")
            await app.bot.send_message(
                chat_id=uid, text=f"Automatische RAID-Überwachungsreparatur #{item['id']}: {outcome}",
                parse_mode=None,
            )
            acknowledged = await rpc({"op": "auto_ack", "run_id": item["id"], "user_id": uid})
            if acknowledged.get("ok") is not True:
                raise ValueError("Notification acknowledgement failed")


async def cycle(app, state):
    status = await rpc({"op": "auto_status"})
    if status.get("ok") is not True:
        raise ValueError("Invalid automation status")
    # Persisted results are delivered before considering any new action.
    await deliver_notices(app, status["notices"])
    if not status["available"] or not status["unhealthy"]:
        state["since"] = None
        return
    now = time.monotonic()
    if state["since"] is None:
        state["since"] = now
        return
    if now - state["since"] < PERSISTENCE:
        return
    gate = status["gate"]
    if not gate["eligible"]:
        reason = gate["reason"]
        if state.get("blocked") != reason:
            await send_all(app,
                "RAID-Überwachung gestört; automatische Reparatur derzeit gesperrt "
                f"({reason}, Wartezeit etwa {gate['retry_after']} Sekunden). "
                "Es wurde keine Aktion ausgeführt.")
            state["blocked"] = reason
        return
    # No Telegram delivery, no new automatic repair request.
    await send_all(app,
        "Automatische Reparatur wird angefordert: RAID-Überwachung seit mindestens "
        "zwei Minuten gestört. Nur mdmonitor.service und mdmonitor-oneshot.service: "
        "Fehlerstatus zurücksetzen und starten; keine Änderung der RAID-Mitglieder.")
    state["since"] = None
    state["blocked"] = None
    result = await rpc({"op": "auto_repair"})
    if result.get("run_id") is None:
        outcome = result.get("result", "unknown")
        if outcome in {"blocked", "not_needed", "not_stable", "unavailable"}:
            text = "Automatische RAID-Reparatur nicht ausgeführt: " + outcome + "."
        else:
            text = ("Ergebnis der automatischen RAID-Reparaturanfrage unklar. "
                    "Keine automatische Wiederholung; gespeichertes Ergebnis wird geprüft.")
        await send_all(app, text)
    # Fetch durable outcome immediately; an exception never triggers action replay.
    latest = await rpc({"op": "auto_status"})
    if latest.get("ok") is not True:
        raise ValueError("Outcome unavailable")
    await deliver_notices(app, latest["notices"])


async def watch_repairs(app):
    state = {"since": None, "blocked": None}
    app.bot_data["auto_repair_state"] = state
    failed = False
    announced = False
    print("RAID-Automatik aktiv: 60s-Prüfung, 120s-Störung, 1h-Abstand, maximal 3/24h.", flush=True)
    while True:
        try:
            if not announced:
                await send_all(app,
                    "RAID-Überwachungsautomatik gestartet: Prüfung alle 60 Sekunden; "
                    "Reparatur erst nach 120 Sekunden Störung, höchstens einmal pro Stunde "
                    "und dreimal in 24 Stunden. Nur die beiden RAID-Überwachungsdienste.")
                announced = True
            await cycle(app, state)
            app.bot_data["auto_repair_last_ok"] = time.monotonic()
            app.bot_data["auto_repair_last_error"] = False
            if failed:
                print("RAID-Automatik wieder erreichbar.", flush=True)
            failed = False
        except Exception as error:
            app.bot_data["auto_repair_last_error"] = True
            state["since"] = None
            if not failed:
                print(f"RAID-Automatik unterbrochen ({type(error).__name__}); keine Aktionswiederholung.", flush=True)
            failed = True
        await asyncio.sleep(INTERVAL)
