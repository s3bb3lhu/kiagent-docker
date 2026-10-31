#!/usr/bin/env python3
"""Interactive installation: configure locally, prepare agents, activate containers."""
import os
import subprocess
import sys
from pathlib import Path

def main():
    if os.geteuid() != 0:
        raise SystemExit('Bitte mit sudo im Server-Terminal ausfuehren.')
    source = Path(__file__).resolve().parents[1]
    if Path('/opt/kiagent-docker/project').exists():
        raise SystemExit('Docker-Projekt existiert bereits. Keine automatische Neuinstallation; aktuellen Zustand zuerst pruefen.')
    if not Path('/etc/kiagent-docker/deployment.env').exists():
        subprocess.run([sys.executable,str(source/'tools/configure.py')],check=True)
    subprocess.run([sys.executable,str(source/'tools/install_host.py')],check=True)
    subprocess.run([sys.executable,'/opt/kiagent-docker/project/tools/activate.py'],check=True)
    print('Installation abgeschlossen. Jetzt /status und /automatik_status in Telegram und Discord pruefen.')

if __name__ == '__main__':
    main()
