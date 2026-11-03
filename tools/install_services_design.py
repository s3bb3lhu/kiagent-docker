"""Backed-up UI-only update of the services portal. No credentials or agents changed."""
import hashlib
import os
import subprocess
import time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_services_portal import SOURCE,TARGET,atomic,run,services_ip

EXPECTED={
'static/app.js':'43ad2c3d597143b2c834fd8f0be42a77aa3f0dd19b546bf284ec1bdc4ea1077d',
'static/style.css':'b3216eb4ff5c06781b2ab6e7deb3f4a9fff6ad1eaf86d222ac992559ef317514',
'templates/index.html':'83f51d9b49a3f4f2bb70793bd29b3ffcd553cddd91db5f6f20dbf73916addaf8',
'templates/login.html':'1ba8e9790ffc248691c0558af300566164bacbf5486920ffc3210c4a1ed7b56f',
'templates/setup.html':'aad8feadd598347e8e814a4cdc3f69e036cc9dce9ff190be1a4efe9c02c805e4'}
ADDED=('static/ui.js','templates/brand.html','templates/appearance.html')

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausfuehren.')
    ip=services_ip()
    saved={};all_current=True
    for name in (*EXPECTED,*ADDED):
        target=TARGET/'app'/name;source=SOURCE/'services'/name
        if source.is_symlink() or not source.is_file():raise ValueError('Unbekannte Quelle.')
        if target.exists():
            info=target.lstat()
            if target.is_symlink() or info.st_uid!=0 or info.st_mode & 0o022:raise ValueError('Unsichere Zieldatei.')
            data=target.read_bytes();current=data==source.read_bytes();all_current=all_current and current
            if not current and (name not in EXPECTED or hashlib.sha256(data).hexdigest()!=EXPECTED[name]):raise ValueError('Oberflaeche wurde anderweitig geaendert. Keine Ueberschreibung.')
            saved[target]=data
        else:
            if name not in ADDED:raise ValueError('Erwartete Datei fehlt.')
            saved[target]=None;all_current=False
    if all_current:print('Designs sind bereits installiert. Keine Aenderung.');return
    backup=Path('/var/backups/kiagent-services-design-'+str(time.time_ns()));backup.mkdir(mode=0o700)
    for path,data in saved.items():
        if data is not None:atomic(backup/path.relative_to(TARGET/'app'),data,0o600)
    run(['/usr/bin/systemctl','stop','kiagent-services-web'])
    try:
        for name in (*EXPECTED,*ADDED):atomic(TARGET/'app'/name,(SOURCE/'services'/name).read_bytes())
        run(['/usr/bin/systemctl','start','kiagent-services-web'])
        for attempt in range(12):
            try:
                result=run(['/usr/bin/curl','--resolve',ip+':9999:127.0.0.1','--fail','--silent','--show-error','--max-time','5','https://'+ip+':9999/login'],capture_output=True)
                if b'/static/ui.js' not in result.stdout:raise ValueError('Neue Oberflaeche nicht bestaetigt.')
                break
            except subprocess.CalledProcessError:
                if attempt==11:raise
                time.sleep(.5)
    except BaseException:
        run(['/usr/bin/systemctl','stop','kiagent-services-web'])
        for path,data in saved.items():
            if data is None:path.unlink(missing_ok=True)
            else:atomic(path,data)
        run(['/usr/bin/systemctl','start','kiagent-services-web']);raise
    print('Drei Designs, sieben Farben, drei Logos und drei Button-Stile installiert.')
    print('Tag/Nacht-Schalter und Auswahlmenue im Header. Einstellungen bleiben im Browser gespeichert.')
    print('https://'+ip+':9999 mit Strg+F5 neu laden. Sicherung: '+str(backup))
    print('Anmeldung, Benutzerkonten, Host-Agent und andere Dienste unveraendert.')

if __name__=='__main__':main()
