import json
import sys
import time
from pathlib import Path
path = {'telegram':'/tmp/kiagent-health.json','discord':'/run/kiagent-discord/health.json','heartbeat':'/tmp/kiagent-heartbeat.json'}[sys.argv[1]]
try:
    data = json.loads(Path(path).read_text())
    ok = data['ready'] is True and 0 <= time.time() - data['checked_at'] < 180
except Exception:
    ok = False
raise SystemExit(0 if ok else 1)
