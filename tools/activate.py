#!/usr/bin/env python3
"""Build first, then switch frontends. Roll back to native services on failure."""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path('/opt/kiagent-docker/project')
STATE = Path('/etc/kiagent-docker')
COMPOSE = ['/usr/bin/docker','compose','--env-file',str(STATE/'deployment.env'),'-f',str(ROOT/'compose.yaml')]

def run(*args):
    return subprocess.run(args,check=True,timeout=900)

def main():
    if os.geteuid() != 0:
        raise SystemExit('Bitte mit sudo ausfuehren.')
    if not (STATE/'migration.json').is_file():
        raise SystemExit('Zuerst install_host.py ausfuehren.')
    record = json.loads((STATE/'migration.json').read_text())
    run(*COMPOSE,'config','--quiet')
    run(*COMPOSE,'build')
    legacy = record['legacy_frontends']
    old_timer = subprocess.run(['/usr/bin/systemctl','is-active','--quiet','kiagent-server-heartbeat.timer']).returncode == 0
    record['previous_heartbeat_timer'] = old_timer
    (STATE/'migration.json').write_text(json.dumps(record))
    try:
        for unit in legacy:
            run('/usr/bin/systemctl','stop',unit)
        if old_timer:
            run('/usr/bin/systemctl','stop','kiagent-server-heartbeat.timer')
        run(*COMPOSE,'up','-d','--wait','--wait-timeout','180')
        run('/usr/bin/systemctl','enable','--now','kiagent-docker.service')
        for unit in legacy:
            run('/usr/bin/systemctl','disable',unit)
        if old_timer:
            run('/usr/bin/systemctl','disable','kiagent-server-heartbeat.timer')
        run('/usr/bin/systemctl','enable','--now','kiagent-backup.timer')
        run('/usr/bin/systemctl','start','kiagent-backup.service')
    except BaseException:
        subprocess.run(['/usr/bin/systemctl','disable','--now','kiagent-docker.service'],timeout=90)
        subprocess.run(COMPOSE + ['stop'],timeout=90)
        for unit in legacy:
            subprocess.run(['/usr/bin/systemctl','enable','--now',unit],timeout=60)
        if old_timer:
            subprocess.run(['/usr/bin/systemctl','enable','--now','kiagent-server-heartbeat.timer'],timeout=60)
        raise
    print('Docker-Umstellung abgeschlossen; alle drei Container gesund. Bestehende native Frontends sind deaktiviert, nicht geloescht.')
    print('Pruefen: Telegram /status und /automatik_status; Discord /status und /ki_install_status.')

if __name__ == '__main__':
    main()
