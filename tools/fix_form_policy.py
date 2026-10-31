#!/usr/bin/env python3
"""Fix browser form Origin suppression without touching credentials or containers."""
import os
import subprocess
from datetime import datetime,timezone
from pathlib import Path
from install_web import atomic

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausfuehren.')
    path=Path('/etc/nginx/sites-available/kiagent-config')
    info=path.lstat()
    if path.is_symlink() or info.st_uid!=0 or info.st_mode & 0o022:
        raise SystemExit('Unsichere nginx-Datei.')
    before=path.read_bytes()
    text=before.decode()
    if not text.startswith('# Kiagent managed HTTPS v1\n') or text.count('    ssl_session_tickets off;')!=1:
        raise SystemExit('Unerwartete Konfiguration. Keine Aenderung.')
    if 'add_header Referrer-Policy same-origin always;' not in text:
        text=text.replace('    ssl_session_tickets off;','    ssl_session_tickets off;\n    proxy_hide_header Referrer-Policy;\n    add_header Referrer-Policy same-origin always;')
    backup=Path('/var/backups')/('kiagent-form-policy-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    atomic(backup/'nginx.conf',before,0o600)
    try:
        atomic(path,text.encode(),info.st_mode & 0o777,info.st_gid)
        subprocess.run(['/usr/sbin/nginx','-t'],check=True)
        subprocess.run(['/usr/bin/systemctl','reload','nginx'],check=True)
    except BaseException:
        atomic(path,before,info.st_mode & 0o777,info.st_gid)
        subprocess.run(['/usr/bin/systemctl','reload','nginx'])
        raise
    print('Formular-Korrektur aktiv. Passwort, Sitzungen und Bot-Dienste wurden nicht geaendert.')
    print('Backup: '+str(backup))
    print('Browserseite jetzt mit Strg+F5 neu laden und eigenes Passwort festlegen.')

if __name__=='__main__':main()
