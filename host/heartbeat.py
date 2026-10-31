import asyncio
import contextlib
import os
import re
import sys
from pathlib import Path
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_url(url):
    if not re.fullmatch(
        r"https://hc-ping\.com/"
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        url,
    ):
        raise ValueError("Unerwartetes Ping-URL-Format")
    return url


def ping(name):
    if name not in {"hc-server", "hc-bot"}:
        raise ValueError("Unbekannte Zugangsdaten")
    credentials = Path(os.environ["CREDENTIALS_DIRECTORY"])
    value = (credentials / name).read_text().strip()
    if not value:
        return
    url = validate_url(value)
    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(url, headers={"User-Agent": "kiagent-heartbeat/1"})
    with opener.open(request, timeout=10) as response:
        if response.status != 200 or response.read(64).strip() != b"OK":
            raise ValueError("Lebenszeichen nicht angenommen")


async def bot_heartbeat(app):
    failed = False
    print("Bot-Heartbeat aktiv: Prüfintervall 60 Sekunden.", flush=True)

    while True:
        try:
            monitor = app.bot_data.get("monitor_task")
            healthy = (
                app.running
                and app.updater is not None
                and app.updater.running
                and monitor is not None
                and not monitor.done()
            )
            if not healthy:
                raise RuntimeError("Bot noch nicht bereit oder Task beendet")

            await asyncio.wait_for(app.bot.get_me(), timeout=12)
            await asyncio.to_thread(ping, "hc-bot")

            if failed:
                print("Bot-Heartbeat wieder erfolgreich.", flush=True)
            failed = False
        except Exception as error:
            if not failed:
                print(
                    f"Bot-Heartbeat ausgesetzt ({type(error).__name__}); "
                    "keine vertraulichen Details ausgegeben.",
                    flush=True,
                )
            failed = True

        await asyncio.sleep(60)


async def start_heartbeat(app):
    app.bot_data["heartbeat_task"] = asyncio.create_task(bot_heartbeat(app))


async def stop_heartbeat(app):
    task = app.bot_data.get("heartbeat_task")
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    try:
        ping("hc-server")
    except Exception as error:
        print(
            f"Server-Heartbeat fehlgeschlagen ({type(error).__name__}); "
            "keine vertraulichen Details ausgegeben.",
            flush=True,
        )
        sys.exit(1)
