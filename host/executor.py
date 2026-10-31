import sys
from pathlib import Path as _ImportPath
sys.path.insert(0, str(_ImportPath(__file__).resolve().parent))
from host_metrics import collect as collect_host_metrics
import math
import sqlite3
import json
import os
import pwd
import secrets
import socket
import struct
import subprocess
import time
from pathlib import Path

SOCKET = "/run/kiagent-executor/control.sock"
UNIT = "kiagent-practice.service"
CLIENT_UID = pwd.getpwnam("kiagent").pw_uid
credentials = Path(os.environ["CREDENTIALS_DIRECTORY"])
ALLOWED = {
    int(line.strip())
    for line in (credentials / "allowed-users").read_text().splitlines()
    if line.strip()
}
if not ALLOWED or any(uid <= 0 for uid in ALLOWED):
    raise ValueError("Ungültige Zugriffsliste")

pending = {}


COOLDOWN = 120
BOOT_ID = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
DB = sqlite3.connect(
    "/var/lib/kiagent-executor/history.sqlite3",
    timeout=5,
    isolation_level=None,
)
DB.execute("PRAGMA synchronous=FULL")
DB.execute("PRAGMA journal_mode=DELETE")
DB.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY,
        timestamp REAL NOT NULL,
        token TEXT,
        event TEXT NOT NULL,
        details TEXT NOT NULL
    )
""")
DB.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        name TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
""")


DB.executescript('\nCREATE TABLE IF NOT EXISTS auto_repairs (\n    id INTEGER PRIMARY KEY, wall REAL NOT NULL, boot TEXT NOT NULL,\n    mono REAL NOT NULL, result TEXT NOT NULL, details TEXT NOT NULL,\n    resolved INTEGER NOT NULL DEFAULT 0\n);\nCREATE TABLE IF NOT EXISTS auto_delivery (\n    run_id INTEGER NOT NULL, user_id INTEGER NOT NULL,\n    PRIMARY KEY(run_id, user_id)\n);\n')


class CooldownError(Exception):
    def __init__(self, seconds):
        self.seconds = seconds


def cooldown_remaining(last, boot, mono, wall):
    if last is None:
        return 0
    if last["boot"] == boot:
        elapsed = max(0, mono - last["mono"])
    else:
        elapsed = max(0, wall - last["wall"])
    return max(0, math.ceil(COOLDOWN - elapsed))


def read_last_attempt():
    row = DB.execute(
        "SELECT value FROM settings WHERE name = ?",
        ("last_attempt",),
    ).fetchone()
    return None if row is None else json.loads(row[0])


def audit(event, **fields):
    wall = time.time()
    mono = time.monotonic()
    blocked = 0
    DB.execute("BEGIN IMMEDIATE")
    try:
        if event == "confirmed":
            blocked = cooldown_remaining(
                read_last_attempt(), BOOT_ID, mono, wall
            )
            if blocked:
                event = "cooldown"
                fields["retry_after"] = blocked
            else:
                DB.execute(
                    "INSERT OR REPLACE INTO settings(name, value) VALUES (?, ?)",
                    ("last_attempt", json.dumps({
                        "boot": BOOT_ID, "mono": mono, "wall": wall
                    })),
                )
        DB.execute(
            "INSERT INTO events(timestamp, token, event, details) "
            "VALUES (?, ?, ?, ?)",
            (wall, fields.get("token"), event, json.dumps(fields)),
        )
        DB.execute("COMMIT")
    except Exception:
        DB.execute("ROLLBACK")
        raise

    print(json.dumps({"event": event, **fields}), flush=True)
    if blocked:
        raise CooldownError(blocked)


def show():
    result = subprocess.run(
        ["/usr/bin/systemctl", "show", UNIT,
         "--property=ActiveState", "--property=InvocationID"],
        capture_output=True, text=True, timeout=5, check=True,
    )
    return dict(
        line.split("=", 1)
        for line in result.stdout.splitlines() if "=" in line
    )



# KIAGENT_MDMONITOR_REPAIR_V1
REPAIR_ACTION = "repair_mdmonitor"
REPAIR_UNITS = ("mdmonitor.service", "mdmonitor-oneshot.service")


def repair_show(timeout=5):
    result = subprocess.run(
        ["/usr/bin/systemctl", "show", *REPAIR_UNITS,
         "--property=Id", "--property=LoadState", "--property=ActiveState",
         "--property=SubState", "--property=Result", "--property=ExecMainStatus",
         "--property=InvocationID"],
        capture_output=True, text=True, timeout=timeout, check=True,
    )
    states = {}
    for block in result.stdout.strip().split("\n\n"):
        values = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        name = values.get("Id")
        if name in REPAIR_UNITS:
            states[name] = values
    if set(states) != set(REPAIR_UNITS):
        raise ValueError("Incomplete service status")
    if any(item.get("LoadState") != "loaded" for item in states.values()):
        raise ValueError("Service unavailable")
    return states


def repair_mdmonitor(record, token, uid):
    # Consume before audit or side effects; never retry an uncertain result.
    record["state"] = "consumed"
    audit("confirmed", token=token, user_id=uid,
          action=REPAIR_ACTION, units=REPAIR_UNITS)
    before = None
    try:
        before = repair_show()
        audit("started", token=token, action=REPAIR_ACTION, before=before)
        # Fixed commands only. start leaves an already running monitor running.
        for arguments in (
            ("reset-failed", *REPAIR_UNITS),
            ("start", "mdmonitor.service"),
            ("start", "mdmonitor-oneshot.service"),
        ):
            subprocess.run(
                ["/usr/bin/systemctl", "--no-ask-password", *arguments],
                capture_output=True, timeout=6, check=True,
            )
        # systemctl start may return before this Type=simple job exits.
        # Poll status only; never repeat any mutating command.
        deadline = time.monotonic() + 8
        after = repair_show(timeout=2)
        while (
            after["mdmonitor-oneshot.service"].get("ActiveState")
            in {"active", "activating", "deactivating", "reloading"}
            and time.monotonic() < deadline
        ):
            remaining = deadline - time.monotonic()
            time.sleep(min(0.2, max(0, remaining)))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            after = repair_show(timeout=min(2, remaining))
        monitor = after["mdmonitor.service"]
        oneshot = after["mdmonitor-oneshot.service"]
        verified = (
            monitor.get("ActiveState") == "active"
            and monitor.get("SubState") == "running"
            and monitor.get("Result") == "success"
            and oneshot.get("ActiveState") == "inactive"
            and oneshot.get("Result") == "success"
            and oneshot.get("ExecMainStatus") == "0"
            and bool(oneshot.get("InvocationID"))
            and oneshot.get("InvocationID") != before["mdmonitor-oneshot.service"].get("InvocationID")
        )
        status = "success" if verified else "unverified"
        audit(status, token=token, action=REPAIR_ACTION, before=before, after=after)
        if verified and not record.get("automatic", False):
            auto_resolve()
        return {"ok": verified, "result": status, "action": REPAIR_ACTION,
                "before": before, "after": after}
    except Exception as error:
        audit("uncertain", token=token, action=REPAIR_ACTION,
              error=type(error).__name__)
        return {"ok": False, "result": "uncertain", "action": REPAIR_ACTION,
                "before": before}



# KIAGENT_AUTO_MDMONITOR_V1
AUTO_INTERVAL = 3600
AUTO_DAILY_LIMIT = 3


def auto_elapsed(row):
    if row["boot"] == BOOT_ID:
        return max(0, time.monotonic() - row["mono"])
    return max(0, time.time() - row["wall"])


def auto_rows():
    rows = DB.execute(
        "SELECT id, wall, boot, mono, result, details, resolved "
        "FROM auto_repairs ORDER BY id DESC"
    ).fetchall()
    fields = ("id", "wall", "boot", "mono", "result", "details", "resolved")
    return [dict(zip(fields, row)) for row in rows]


def auto_gate():
    enabled = DB.execute("SELECT value FROM settings WHERE name = ?", ("auto_enabled",)).fetchone()
    if enabled is not None and enabled[0] != "true":
        return {"eligible": False, "reason": "disabled", "retry_after": 0}
    rows = auto_rows()
    if any(row["result"] != "success" and not row["resolved"] for row in rows):
        return {"eligible": False, "reason": "manual_required", "retry_after": 0}
    recent = [row for row in rows if auto_elapsed(row) < 86400]
    if len(recent) >= AUTO_DAILY_LIMIT:
        return {"eligible": False, "reason": "daily_limit",
                "retry_after": math.ceil(86400 - auto_elapsed(recent[AUTO_DAILY_LIMIT-1]))}
    if rows and auto_elapsed(rows[0]) < AUTO_INTERVAL:
        return {"eligible": False, "reason": "hourly_limit",
                "retry_after": math.ceil(AUTO_INTERVAL-auto_elapsed(rows[0]))}
    remaining = cooldown_remaining(read_last_attempt(), BOOT_ID, time.monotonic(), time.time())
    if remaining:
        return {"eligible": False, "reason": "cooldown", "retry_after": remaining}
    return {"eligible": True, "reason": "ready", "retry_after": 0}


def auto_unhealthy(states):
    monitor = states["mdmonitor.service"]
    oneshot = states["mdmonitor-oneshot.service"]
    # A successfully completed inactive oneshot is healthy.
    # An active/activating oneshot is not a reason to start it again.
    return (
        monitor.get("ActiveState") not in {"active", "activating", "reloading"}
        or (monitor.get("ActiveState") == "active" and monitor.get("SubState") != "running")
        or oneshot.get("ActiveState") == "failed"
        or (oneshot.get("ActiveState") == "inactive" and (
            oneshot.get("Result") != "success" or oneshot.get("ExecMainStatus") != "0"
        ))
    )


def auto_observe(unhealthy):
    if not unhealthy:
        DB.execute("DELETE FROM settings WHERE name = ?", ("auto_bad_since",))
        return False
    row = DB.execute("SELECT value FROM settings WHERE name = ?", ("auto_bad_since",)).fetchone()
    observed = None if row is None else json.loads(row[0])
    now = time.monotonic()
    if observed is None or observed["boot"] != BOOT_ID or observed["mono"] > now:
        DB.execute("INSERT OR REPLACE INTO settings(name,value) VALUES (?,?)",
                   ("auto_bad_since", json.dumps({"boot": BOOT_ID, "mono": now})))
        return False
    return now - observed["mono"] >= 120


def auto_notices():
    notices = []
    for row in reversed(auto_rows()):
        sent = {entry[0] for entry in DB.execute(
            "SELECT user_id FROM auto_delivery WHERE run_id = ?", (row["id"],)
        ).fetchall()}
        recipients = sorted(ALLOWED - sent)
        if recipients:
            notices.append({"id": row["id"], "timestamp": row["wall"],
                            "result": row["result"], "recipients": recipients})
    return notices


def auto_status():
    try:
        states = repair_show()
        unhealthy = auto_unhealthy(states)
        available = True
    except Exception:
        states, unhealthy, available = {}, False, False
    stable = auto_observe(available and unhealthy)
    return {"ok": True, "available": available, "unhealthy": unhealthy,
            "stable": stable, "states": states, "gate": auto_gate(), "notices": auto_notices()}


def auto_ack(request):
    if set(request) != {"op", "run_id", "user_id"}:
        return {"ok": False, "result": "invalid"}
    run_id, uid = request["run_id"], request["user_id"]
    if type(uid) is not int or uid not in ALLOWED or type(run_id) is not int or run_id <= 0:
        return {"ok": False, "result": "denied"}
    if DB.execute("SELECT id FROM auto_repairs WHERE id = ?", (run_id,)).fetchone() is None:
        return {"ok": False, "result": "unknown"}
    DB.execute("INSERT OR IGNORE INTO auto_delivery(run_id, user_id) VALUES (?, ?)", (run_id, uid))
    return {"ok": True, "result": "acknowledged"}


def auto_resolve():
    DB.execute("UPDATE auto_repairs SET resolved = 1 WHERE resolved = 0")


def auto_execute():
    # Only the kiagent socket peer can reach this function (SO_PEERCRED in main).
    # The root server independently rechecks health and persistent limits.
    gate = auto_gate()
    if not gate["eligible"]:
        return {"ok": False, "result": "blocked", **gate}
    try:
        states = repair_show()
    except Exception:
        return {"ok": False, "result": "unavailable"}
    if not auto_unhealthy(states):
        auto_observe(False)
        return {"ok": True, "result": "not_needed"}
    if not auto_observe(True):
        return {"ok": False, "result": "not_stable"}
    cursor = DB.execute(
        "INSERT INTO auto_repairs(wall, boot, mono, result, details) VALUES (?, ?, ?, ?, ?)",
        (time.time(), BOOT_ID, time.monotonic(), "pending", json.dumps({"before": states})),
    )
    run_id = cursor.lastrowid
    token = secrets.token_hex(16)
    # The durable reservation precedes all side effects. A crash leaves a lockout,
    # never an automatic replay. SQLite FULL synchronous remains unchanged.
    audit("auto_reserved", run_id=run_id, action=REPAIR_ACTION)
    try:
        result = repair_mdmonitor({"state": "pending", "automatic": True}, token, None)
    except CooldownError as error:
        result = {"ok": False, "result": "cooldown", "retry_after": error.seconds}
    except Exception as error:
        result = {"ok": False, "result": "uncertain", "error": type(error).__name__}
    status = result.get("result", "uncertain")
    DB.execute("UPDATE auto_repairs SET result = ?, details = ? WHERE id = ?",
               (status, json.dumps(result), run_id))
    audit("auto_finished", run_id=run_id, action=REPAIR_ACTION, result=status)
    return {**result, "run_id": run_id}



# KIAGENT_AUTOMATION_OVERVIEW_V1: read-only, no auto_observe/ack/audit calls.
def automation_overview():
    try:
        states = repair_show()
        unhealthy = auto_unhealthy(states)
        available = True
    except Exception:
        states, unhealthy, available = {}, False, False
    rows = auto_rows()
    recent = [row for row in rows if auto_elapsed(row) < 86400]
    enabled_row = DB.execute("SELECT value FROM settings WHERE name = ?", ("auto_enabled",)).fetchone()
    enabled = enabled_row is None or enabled_row[0] == "true"
    manual_required = any(row["result"] != "success" and not row["resolved"] for row in rows)
    hourly = max(0, math.ceil(AUTO_INTERVAL-auto_elapsed(rows[0]))) if rows else 0
    daily = (max(0, math.ceil(86400-auto_elapsed(recent[AUTO_DAILY_LIMIT-1])))
             if len(recent) >= AUTO_DAILY_LIMIT else 0)
    shared = cooldown_remaining(read_last_attempt(), BOOT_ID, time.monotonic(), time.time())
    observation_wait = 0
    if available and unhealthy:
        observed = DB.execute("SELECT value FROM settings WHERE name = ?", ("auto_bad_since",)).fetchone()
        age = 0
        if observed is not None:
            value = json.loads(observed[0])
            if value["boot"] == BOOT_ID:
                age = max(0, time.monotonic()-value["mono"])
        observation_wait = max(0, math.ceil(120-age))
    history = []
    outstanding = 0
    for row in rows:
        sent = {entry[0] for entry in DB.execute(
            "SELECT user_id FROM auto_delivery WHERE run_id = ?", (row["id"],)
        ).fetchall()}
        missing = len(ALLOWED-sent)
        outstanding += missing
        if len(history) < 5:
            history.append({"id":row["id"], "timestamp":row["wall"],
                            "result":row["result"], "resolved":bool(row["resolved"]),
                            "notifications_pending":missing})
    return {"ok":True, "kind":"automation_overview_v1", "enabled":enabled,
            "available":available, "unhealthy":unhealthy, "states":states,
            "manual_required":manual_required, "gate":auto_gate(),
            "hourly_seconds":hourly, "daily_seconds":daily, "shared_seconds":shared,
            "observation_seconds":observation_wait,
            "earliest_seconds":max(hourly,daily,shared),
            "attempts_24h":len(recent), "limit_24h":AUTO_DAILY_LIMIT,
            "notifications_pending":outstanding, "history":history}



# KIAGENT_TELEGRAM_AUTO_CONTROL_V1
def automation_set_enabled(enabled, uid, actor="telegram"):
    kind = "automation_control_v1"
    if type(enabled) is not bool:
        return {"ok":False, "kind":kind, "result":"invalid"}
    # Setting and audit entry commit together, or neither does.
    DB.execute("BEGIN IMMEDIATE")
    try:
        row = DB.execute("SELECT value FROM settings WHERE name = ?", ("auto_enabled",)).fetchone()
        before = row is None or row[0] == "true"
        changed = before != enabled
        details = {"actor":actor, "user_id":uid,
                   "enabled":enabled, "changed":changed, "before":before}
        DB.execute("INSERT OR REPLACE INTO settings(name,value) VALUES (?,?)",
                   ("auto_enabled", "true" if enabled else "false"))
        DB.execute("INSERT INTO events(timestamp,token,event,details) VALUES (?,?,?,?)",
                   (time.time(), None, "auto_control", json.dumps(details)))
        DB.execute("COMMIT")
    except Exception:
        DB.execute("ROLLBACK")
        raise
    print(json.dumps({"event":"auto_control", "enabled":enabled, "changed":changed}), flush=True)
    return {"ok":True, "kind":kind, "enabled":enabled, "changed":changed,
            "result":"enabled" if enabled else "disabled"}



# KIAGENT_DISCORD_AUTOMATION_V1
DISCORD_UID = pwd.getpwnam("kiagent-discord").pw_uid
DISCORD_ACCESS = json.loads((credentials / "discord-access").read_text())
if (set(DISCORD_ACCESS) != {"users", "guild_id", "channel_id"}
    or not DISCORD_ACCESS["users"]
    or any(type(value) is not int or not 0 < value < 2**63 for value in
           [*DISCORD_ACCESS["users"], DISCORD_ACCESS["guild_id"], DISCORD_ACCESS["channel_id"]])
    or DISCORD_UID == CLIENT_UID):
    raise ValueError("Invalid Discord access configuration")
discord_pending = {}


def discord_handle(request):
    if request == {"op": "metrics"}:
        return {"ok": True, "kind": "host_metrics_v1", "data": collect_host_metrics()}

    common = {"op", "user_id", "chat_id", "guild_id", "message_id"}
    op = request.get("op")
    expected = common if op == "auto_overview" else common | ({"enabled"} if op == "new_control" else {"token"})
    if set(request) != expected or op not in {"auto_overview", "new_control", "confirm", "cancel"}:
        return {"ok": False, "result": "invalid"}
    uid, chat, guild, message = (request[k] for k in ("user_id", "chat_id", "guild_id", "message_id"))
    if (any(type(x) is not int or not 0 < x < 2**63 for x in (uid, chat, guild, message))
        or uid not in DISCORD_ACCESS["users"] or guild != DISCORD_ACCESS["guild_id"]
        or chat != DISCORD_ACCESS["channel_id"]):
        return {"ok": False, "result": "denied"}
    if op == "auto_overview":
        return automation_overview()
    now = time.monotonic()
    for key in list(discord_pending):
        if now > discord_pending[key]["expires"] + 600:
            del discord_pending[key]
    if op == "new_control":
        if type(request["enabled"]) is not bool:
            return {"ok": False, "result": "invalid"}
        if len(discord_pending) >= 100:
            return {"ok": False, "result": "busy"}
        token = secrets.token_hex(16)
        # Audit must commit before offering the confirmation.
        audit("discord_control_requested", user_id=uid, enabled=request["enabled"])
        discord_pending[token] = {"identity": (uid, chat, guild, message),
            "expires": now + 120, "state": "pending", "enabled": request["enabled"]}
        return {"ok": True, "kind": "automation_control_proposal_v1", "token": token,
                "enabled": request["enabled"], "result": "pending"}
    token = request["token"]
    if type(token) is not str or len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
        return {"ok": False, "result": "invalid"}
    record = discord_pending.get(token)
    if record is None or record["identity"] != (uid, chat, guild, message):
        return {"ok": False, "result": "unknown"}
    if record["state"] != "pending":
        return {"ok": False, "result": "consumed"}
    # Consume before all later processing. Never retry an uncertain control action.
    record["state"] = "consumed"
    if now > record["expires"]:
        return {"ok": False, "result": "expired"}
    if op == "cancel":
        audit("discord_control_cancelled", user_id=uid, enabled=record["enabled"])
        return {"ok": True, "result": "cancelled"}
    return automation_set_enabled(record["enabled"], uid, actor="discord")


def _handle(request):
    if request == {"op": "metrics"}:
        return {"ok": True, "kind": "host_metrics_v1", "data": collect_host_metrics()}

    now = time.monotonic()
    for token in list(pending):
        if now > pending[token]["expires"] + 600:
            del pending[token]

    op = request.get("op")
    if op == "auto_status" and set(request) == {"op"}:
        return auto_status()
    if op == "auto_repair" and set(request) == {"op"}:
        return auto_execute()
    if op == "auto_ack":
        return auto_ack(request)
    if op == "health" and set(request) == {"op"}:
        return {"ok": True, "unit": UNIT, **show()}

    uid = request.get("user_id")
    chat = request.get("chat_id")
    if (
        type(uid) is not int or uid not in ALLOWED
        or type(chat) is not int or chat != uid
    ):
        return {"ok": False, "result": "denied"}

    if op == "auto_control":
        if set(request) != {"op", "user_id", "chat_id", "enabled"}:
            return {"ok":False, "result":"invalid"}
        return automation_set_enabled(request["enabled"], uid)

    if op == "auto_overview":
        if set(request) != {"op", "user_id", "chat_id"}:
            return {"ok":False, "result":"invalid"}
        return automation_overview()

    if op == "new":
        keys = {"op", "user_id", "chat_id"}
        if set(request) not in (keys, keys | {"action"}):
            return {"ok": False, "result": "invalid"}
        action = request.get("action", "practice_restart")
        if type(action) is not str or action not in {"practice_restart", REPAIR_ACTION}:
            return {"ok": False, "result": "invalid"}
        if len(pending) >= 100:
            return {"ok": False, "result": "busy"}
        token = secrets.token_hex(16)
        pending[token] = {
            "user_id": uid, "chat_id": chat, "message_id": None,
            "expires": now + 120, "state": "pending", "action": action,
        }
        units = REPAIR_UNITS if action == REPAIR_ACTION else (UNIT,)
        audit("requested", token=token, user_id=uid, action=action, units=units)
        return {"ok": True, "token": token, "expires_in": 120, "unit": UNIT,
                "action": action, "units": units}

    expected = {"op", "user_id", "chat_id", "token", "message_id"}
    if op not in {"bind", "confirm", "cancel"} or set(request) != expected:
        return {"ok": False, "result": "invalid"}

    token = request.get("token")
    message = request.get("message_id")
    if not isinstance(token, str) or type(message) is not int or message <= 0:
        return {"ok": False, "result": "invalid"}
    record = pending.get(token)
    if record is None:
        return {"ok": False, "result": "unknown"}
    if (uid, chat) != (record["user_id"], record["chat_id"]):
        return {"ok": False, "result": "denied"}
    if record["state"] != "pending":
        return {"ok": False, "result": "already"}
    if now >= record["expires"]:
        record["state"] = "expired"
        audit("expired", token=token)
        return {"ok": False, "result": "expired"}

    if op == "bind":
        if record["message_id"] is not None:
            return {"ok": False, "result": "already_bound"}
        record["message_id"] = message
        return {"ok": True, "result": "bound"}

    if record["message_id"] != message:
        return {"ok": False, "result": "denied"}

    if op == "cancel":
        record["state"] = "cancelled"
        audit("cancelled", token=token, user_id=uid)
        return {"ok": True, "result": "cancelled"}

    # Action is bound to the record, never supplied by a confirmation request.
    if record["action"] == REPAIR_ACTION:
        return repair_mdmonitor(record, token, uid)

    # Vor jeder Systemaktion verbrauchen; niemals automatisch wiederholen.
    record["state"] = "consumed"
    audit("confirmed", token=token, user_id=uid, unit=UNIT)
    before = None
    try:
        before = show()
        audit("started", token=token, before=before)
        subprocess.run(
            ["/usr/bin/systemctl", "restart", UNIT],
            capture_output=True, timeout=15, check=True,
        )
        after = show()
        verified = (
            after.get("ActiveState") == "active"
            and bool(before.get("InvocationID"))
            and bool(after.get("InvocationID"))
            and before["InvocationID"] != after["InvocationID"]
        )
        result = "success" if verified else "unverified"
        audit(result, token=token, before=before, after=after)
        return {
            "ok": verified, "result": result,
            "before": before, "after": after,
        }
    except Exception as error:
        audit("uncertain", token=token, error=type(error).__name__)
        return {
            "ok": False, "result": "uncertain",
            "before": before,
        }



def handle(request, platform="telegram"):
    if platform == "discord":
        return discord_handle(request)
    if platform != "telegram":
        return {"ok": False, "result": "denied"}
    try:
        result = _handle(request)
        if request.get("op") == "health" and result.get("ok") is True:
            result["cooldown_seconds"] = cooldown_remaining(
                read_last_attempt(), BOOT_ID, time.monotonic(), time.time()
            )
        return result
    except CooldownError as error:
        return {
            "ok": False,
            "result": "cooldown",
            "retry_after": error.seconds,
        }


def main():
    Path(SOCKET).unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(SOCKET)
        os.chmod(SOCKET, 0o660)
        server.listen(8)
        audit("ready", unit=UNIT)
        while True:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(2)
                try:
                    peer = connection.getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED, 12
                    )
                    _, uid, _ = struct.unpack("3i", peer)
                    if uid not in {CLIENT_UID, DISCORD_UID}:
                        audit("local_client_denied", uid=uid)
                        continue
                    with connection.makefile("rb") as stream:
                        raw = stream.readline(4097)
                    if len(raw) > 4096 or not raw.endswith(b"\n"):
                        raise ValueError("Ungültige Anfrage")
                    request = json.loads(raw)
                    if not isinstance(request, dict):
                        raise ValueError("Ungültige Anfrage")
                    response = handle(request, platform="telegram" if uid == CLIENT_UID else "discord")
                except Exception as error:
                    audit("request_error", error=type(error).__name__)
                    response = {"ok": False, "result": "error"}
                try:
                    connection.sendall(
                        (json.dumps(response) + "\n").encode()
                    )
                except OSError:
                    pass


if __name__ == "__main__":
    main()
