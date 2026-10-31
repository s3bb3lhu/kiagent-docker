import asyncio
import contextlib
import json
import time
from pathlib import Path
from monitor import start_monitor as _start, stop_monitor as _stop

async def _health(app):
    while True:
        last = app.bot_data.get('auto_repair_last_ok')
        tasks = [app.bot_data.get(name) for name in ('monitor_task','auto_repair_task')]
        healthy = bool(app.running and app.updater and app.updater.running and all(task and not task.done() for task in tasks) and last is not None and time.monotonic() - last < 180)
        Path('/tmp/kiagent-health.json').write_text(json.dumps({'ready':healthy,'checked_at':time.time()}))
        await asyncio.sleep(15)

async def start_monitor(app):
    await _start(app)
    app.bot_data['container_health_task'] = asyncio.create_task(_health(app))

async def stop_monitor(app):
    task = app.bot_data.get('container_health_task')
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await _stop(app)
