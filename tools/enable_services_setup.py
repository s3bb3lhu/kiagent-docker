"""Enable first browser account setup on the already installed port-9999 portal."""
import hashlib
import os
import subprocess
import time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_services_portal import SOURCE,TARGET,atomic,run,services_ip

EXPECTED={
 'host_agent.py':'f178f19865078df76a1e754b8b048e543a6392fab4d8740c1a37b5d3cfed7401',
 'web.py':'09cf8a8da9618d3f64a5a9324f80489a474700a7c95785f86f44d77ebee0be4d',
 'templates/login.html':'5e9d0e2acbbd6c8ad9b0253f8611be724e2f011c1917f8fa97e0dc987b5981ec'}

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausfuehren.')
    ip=services_ip()
    state=Path('/var/lib/kiagent-services');marker=state/'local-auth-enabled'
    if marker.exists() or (state/'auth.json').exists():raise SystemExit('Eigene Einrichtung bereits begonnen oder abgeschlossen. Kein Zuruecksetzen.')
    saved={}
    for name,digest in EXPECTED.items():
        path=TARGET/'app'/name
        if path.is_symlink() or path.stat().st_uid!=0 or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Installierter Quellstand weicht ab. Keine Aenderung.')
    unit=Path('/etc/systemd/system/kiagent-services-agent.service');unit_before=unit.read_bytes()
    credential=b'LoadCredential=admin-auth:/var/lib/kiagent-web/auth/auth.json\n'
    if unit_before.count(credential)!=1:raise ValueError('Unerwartete Dienstdefinition.')
    backup=Path('/var/backups/kiagent-services-setup-'+str(time.time_ns()));backup.mkdir(mode=0o700)
    paths=[TARGET/'app'/name for name in (*EXPECTED,'templates/setup.html')]+[unit]
    for path in paths:
        if path.exists():
            if path.is_symlink() or path.stat().st_uid!=0 or path.stat().st_mode & 0o022:raise ValueError('Unsichere Datei.')
            saved[path]=path.read_bytes();atomic(backup/path.name,saved[path],0o600)
        else:saved[path]=None
    run(['/usr/bin/systemctl','stop','kiagent-services-auth.path','kiagent-services-web','kiagent-services-agent'])
    changed=False
    try:
        for name in (*EXPECTED,'templates/setup.html'):atomic(TARGET/'app'/name,(SOURCE/'services'/name).read_bytes())
        atomic(unit,unit_before.replace(credential,b''))
        atomic(marker,b'local-browser-setup-v1',0o600);changed=True
        run(['/usr/bin/systemctl','daemon-reload'])
        run(['/usr/bin/systemctl','disable','kiagent-services-auth.path'])
        run(['/usr/bin/systemctl','start','kiagent-services-agent','kiagent-services-web'])
        for attempt in range(12):
            try:
                result=run(['/usr/bin/curl','--resolve',ip+':9999:127.0.0.1','--fail','--silent','--show-error','--max-time','5','https://'+ip+':9999/setup'],capture_output=True)
                break
            except subprocess.CalledProcessError:
                if attempt==11:raise
                time.sleep(.5)
        if b'name="username"' not in result.stdout or b'name="confirm"' not in result.stdout:raise ValueError('Einrichtungsseite konnte nicht bestaetigt werden.')
    except BaseException:
        if (state/'auth.json').exists():raise RuntimeError('Ein Konto wurde bereits angelegt; kein automatisches Zuruecksetzen. Zustand manuell pruefen.') from None
        run(['/usr/bin/systemctl','stop','kiagent-services-web','kiagent-services-agent'])
        for path,data in saved.items():
            if data is None:path.unlink(missing_ok=True)
            else:atomic(path,data)
        if changed:marker.unlink(missing_ok=True)
        run(['/usr/bin/systemctl','daemon-reload'])
        run(['/usr/bin/systemctl','enable','--now','kiagent-services-auth.path'])
        run(['/usr/bin/systemctl','start','kiagent-services-agent','kiagent-services-web'])
        raise
    print('Ersteinrichtung aktiv: https://'+ip+':9999/setup')
    print('Dort Benutzername und Passwort festlegen. Kein Einrichtungstoken erforderlich.')
    print('Passwort: mindestens 8 Zeichen, 1 Grossbuchstabe, 1 Zahl und 1 Sonderzeichen.')
    print('Sicherung: '+str(backup)+'. Serversteuerung auf 9898 und Bots unveraendert.')

if __name__=='__main__':main()
