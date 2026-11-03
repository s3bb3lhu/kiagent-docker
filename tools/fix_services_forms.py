"""Fix same-origin HTML form submission without weakening request validation."""
import hashlib
import os
import subprocess
import time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_services_portal import atomic,run,services_ip

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausfuehren.')
    ip=services_ip()
    target=Path('/opt/kiagent-services/app/web.py');before=target.read_bytes()
    if target.is_symlink() or target.stat().st_uid!=0 or hashlib.sha256(before).hexdigest()!='c787b71679ef29430839fbc87820fa7a2ddb0b01bb2645c89b75e25c827c0b83':raise SystemExit('Web-Quellstand weicht ab. Keine Aenderung.')
    old=b"'Referrer-Policy':'no-referrer'"
    if before.count(old)!=1:raise ValueError('Unerwarteter Quellstand.')
    backup=Path('/var/backups/kiagent-services-form-'+str(time.time_ns()));backup.mkdir(mode=0o700);atomic(backup/'web.py',before,0o600)
    try:
        atomic(target,before.replace(old,b"'Referrer-Policy':'same-origin'"))
        run(['/usr/bin/systemctl','restart','kiagent-services-web'])
        for attempt in range(12):
            try:
                result=run(['/usr/bin/curl','--resolve',ip+':9999:127.0.0.1','--fail','--silent','--show-error','--max-time','5','--head','https://'+ip+':9999/login'],capture_output=True)
                if b'referrer-policy: same-origin' not in result.stdout.lower():raise ValueError('Antwortheader nicht bestaetigt.')
                break
            except subprocess.CalledProcessError:
                if attempt==11:raise
                time.sleep(.5)
    except BaseException:
        atomic(target,before);run(['/usr/bin/systemctl','restart','kiagent-services-web']);raise
    print('Formular-Korrektur aktiv. Herkunfts- und CSRF-Pruefung bleiben unveraendert.')
    print('https://'+ip+':9999/setup neu laden und Konto erstellen.')
    print('Sicherung: '+str(backup))

if __name__=='__main__':main()
