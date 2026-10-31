from host_metrics_client import snapshot
import asyncio
import contextlib
import shutil
import time
from pathlib import Path


class Alarm:
    def __init__(self):
        self.since = None
        self.active = False
        self.last_sent = None

    def evaluate(self, bad, recovered, delay, now):
        if not self.active:
            if not bad:
                self.since = None
                return None
            if self.since is None:
                self.since = now
            if now - self.since < delay:
                return None
            self.active = True

        if recovered:
            if self.last_sent is None:
                self.active = False
                self.since = None
                return None
            return "Entwarnung"

        if self.last_sent is None or now - self.last_sent >= 3600:
            return "Warnung"
        return None

    def delivered(self, kind, now):
        if kind == "Entwarnung":
            self.active = False
            self.since = None
            self.last_sent = None
        else:
            self.last_sent = now


def measurements():
    data = snapshot()
    return data['root_disk_used_percent'], 100 * data['ram_available_mib'] / data['ram_total_mib']




# KIAGENT_RAID_MONITOR_V1
def raid_checks(alarms):
    checks = []
    for name, values in snapshot()['raid'].items():
        for kind in ('unavailable', 'degraded'):
            alarms.setdefault((name, kind), Alarm())
        try:
            missing = int(values['degraded'])
            if missing < 0:
                raise ValueError('Invalid status')
        except (ValueError, TypeError, KeyError):
            missing = None
        checks.append((alarms[(name,'unavailable')], missing is None, missing is not None, 120,
                       f'RAID {name}: Status nicht lesbar' if missing is None else f'RAID {name}: Status wieder lesbar'))
        if missing is not None:
            checks.append((alarms[(name,'degraded')], missing > 0, missing == 0, 60,
                           f'RAID {name}: {missing} fehlende RAID-Mitglieder'))
    return checks



async def watch(app):
    disk_alarm, ram_alarm = Alarm(), Alarm()
    raid_alarms = {
        (name, kind): Alarm()
        for name in ("md1", "md2", "md3", "md4")
        for kind in ("unavailable", "degraded")
    }
    failed = False
    print("Überwachung aktiv: Prüfintervall 60 Sekunden.", flush=True)

    while True:
        try:
            disk_percent, ram_available = measurements()
            now = time.monotonic()
            checks = [
                (disk_alarm, disk_percent >= 85, disk_percent < 82, 60,
                 f"Dateisystem /: {disk_percent:.1f} % belegt"),
                (ram_alarm, ram_available < 10, ram_available >= 15, 300,
                 f"RAM: {ram_available:.1f} % verfügbar"),
            ]
            checks.extend(raid_checks(raid_alarms))
            for alarm, bad, recovered, delay, detail in checks:
                kind = alarm.evaluate(bad, recovered, delay, now)
                if kind:
                    for user_id in sorted(app.bot_data["allowed_users"]):
                        await app.bot.send_message(
                            chat_id=user_id,
                            text=f"{kind}: {detail}",
                        )
                    alarm.delivered(kind, time.monotonic())

            if failed:
                print("Überwachung wieder erfolgreich.", flush=True)
            failed = False
        except Exception:
            if not failed:
                print("Überwachung oder Alarmversand fehlgeschlagen; "
                      "erneuter Versuch in 60 Sekunden.", flush=True)
            failed = True

        await asyncio.sleep(60)


async def start_monitor(app):
    app.bot_data["monitor_task"] = asyncio.create_task(watch(app))


async def stop_monitor(app):
    task = app.bot_data.get("monitor_task")
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


# KIAGENT_AUTO_MONITOR_LIFECYCLE_V1
_start_resource_monitor = start_monitor
_stop_resource_monitor = stop_monitor


async def start_monitor(app):
    from auto_monitor import watch_repairs
    await _start_resource_monitor(app)
    app.bot_data["auto_repair_task"] = asyncio.create_task(watch_repairs(app))


async def stop_monitor(app):
    task = app.bot_data.get("auto_repair_task")
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await _stop_resource_monitor(app)


# KIAGENT_EXTERNAL_BOT_HEARTBEAT_V1
from kiagent_heartbeat import start_heartbeat as _start_external_bot_heartbeat
from kiagent_heartbeat import stop_heartbeat as _stop_external_bot_heartbeat

_start_monitors_without_heartbeat = start_monitor
_stop_monitors_without_heartbeat = stop_monitor


async def start_monitor(app):
    await _start_monitors_without_heartbeat(app)
    await _start_external_bot_heartbeat(app)


async def stop_monitor(app):
    await _stop_external_bot_heartbeat(app)
    await _stop_monitors_without_heartbeat(app)
