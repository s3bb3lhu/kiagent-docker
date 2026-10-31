import json
import time
from pathlib import Path
from kiagent_heartbeat import ping
while True:
    try:
        ping('hc-server')
        ready = True
    except Exception:
        ready = False
        print('Server-Heartbeat fehlgeschlagen; keine vertraulichen Details ausgegeben.', flush=True)
    Path('/tmp/kiagent-heartbeat.json').write_text(json.dumps({'ready':ready,'checked_at':time.time()}))
    time.sleep(60)
