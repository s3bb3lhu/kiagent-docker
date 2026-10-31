#!/usr/bin/env python3
"""Return to previous native chat services; preserve audit databases and limits."""
import json
import os
import subprocess
from pathlib import Path

if os.geteuid() != 0:
    raise SystemExit('Bitte mit sudo ausfuehren.')
record = json.loads(Path('/etc/kiagent-docker/migration.json').read_text())
if not record['legacy_frontends']:
    raise SystemExit('Frische Installation: keine vorherigen nativen Chat-Dienste vorhanden.')
subprocess.run(['/usr/bin/systemctl','disable','--now','kiagent-docker.service'],check=True)
for unit in record['legacy_frontends']:
    subprocess.run(['/usr/bin/systemctl','enable','--now',unit],check=True)
if record.get('previous_heartbeat_timer'):
    subprocess.run(['/usr/bin/systemctl','enable','--now','kiagent-server-heartbeat.timer'],check=True)
print('Native Frontends wieder aktiv. Audit-Datenbank, Sperrzeiten und Host-Agenten wurden nicht zurueckgesetzt.')
