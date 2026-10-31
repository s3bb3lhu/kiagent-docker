#!/usr/bin/env python3
"""Recover the UI after agent credential reload without changing saved credentials."""
import hashlib
import json
import os
import pwd
import subprocess
import time
import urllib.request
from datetime import datetime,timezone
from pathlib import Path
from install_web import SOURCE,PROJECT,CONFIG,COMPOSE,atomic,run

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausfuehren.')
    run(['/usr/bin/python3',str(SOURCE/'tools/scan_secrets.py')])
    rows=[]
    for path in Path('/var/lib/kiagent-config/jobs').glob('*.json'):
        row=json.loads(path.read_text());rows.append(row)
        if row.get('state') in {'queued','stopping','starting','checking','restoring'}:
            raise SystemExit('Speichervorgang noch offen. Nicht erneut speichern; zuerst Journal pruefen.')
    rows=sorted(rows,key=lambda row:row.get('updated_at',0),reverse=True)[:3]
    print('Letzte Speichervorgaenge (ohne Konfigurationswerte):')
    print(json.dumps([{key:row.get(key) for key in ('state','code','updated_at')} for row in rows],indent=2))
    if any(row.get('state')=='interrupted' or row.get('code')=='rollback_failed' for row in rows):
        raise SystemExit('Speicherzustand unklar. Keine Dienste oder Zugangsdaten automatisch veraendern; Ausgabe per SSH pruefen lassen.')
    env=dict(line.split('=',1) for line in (CONFIG/'deployment.env').read_text().splitlines() if line and not line.startswith('#'))
    origin=env['CONFIG_ORIGIN']
    secret_paths=[CONFIG/'deployment.env',*(CONFIG/'secrets').iterdir(),Path('/var/lib/kiagent-web/auth/auth.json')]
    before={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in secret_paths if path.is_file()}
    backup=Path('/var/backups')/('kiagent-save-lifecycle-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    saved={}
    for path in (Path('/etc/systemd/system/kiagent-docker.service'),PROJECT/'host/systemd/kiagent-docker.service'):
        info=path.lstat()
        if path.is_symlink() or info.st_uid!=0 or info.st_mode & 0o022:raise ValueError('Unsichere Dienstdatei.')
        saved[path]=(path.read_bytes(),info.st_mode & 0o777,info.st_gid)
        atomic(backup/str(path).lstrip('/'),saved[path][0],0o600)
    try:
        data=(SOURCE/'host/systemd/kiagent-docker.service').read_bytes()
        for path in saved:atomic(path,data)
        run(['/usr/bin/systemd-analyze','verify','/etc/systemd/system/kiagent-docker.service'])
        run(['/usr/bin/systemctl','daemon-reload'])
        requires=subprocess.check_output(['/usr/bin/systemctl','show','kiagent-docker','--property=Requires','--value'],text=True).split()
        if any(name in requires for name in ('kiagent-executor.service','kiagent-packages.service','kiagent-config.service')):
            raise ValueError('Zusaetzliche harte Dienstabhaengigkeit vorhanden. Drop-ins zuerst pruefen.')
        run(['/usr/bin/systemctl','start','kiagent-executor','kiagent-packages','kiagent-config'])
        run(['/usr/bin/systemctl','start','kiagent-docker'])
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--wait','--wait-timeout','90','config-web'])
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(origin+'/health',timeout=15) as response:
            if json.load(response).get('ok') is not True:raise ValueError('Web-Dienst nicht bereit.')
        after={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in secret_paths if path.is_file()}
        if before!=after:raise ValueError('Konfiguration hat sich parallel geaendert. Bitte pruefen.')
        run(['/usr/bin/systemctl','is-active','--quiet','kiagent-docker','kiagent-config','kiagent-executor','kiagent-packages'])
        run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    except BaseException:
        # Keep the recovered services running. Never replay or restore old credentials.
        print('Pruefung nicht vollstaendig erfolgreich. Keine Zugangsdaten zurueckgesetzt. Zustand per SSH pruefen.')
        raise
    report={'result':'success','checked_utc':datetime.now(timezone.utc).isoformat(),'backup':str(backup),'configuration_unchanged':True,
            'health_verified':True,'save_results':[{k:row.get(k) for k in ('state','code')} for row in rows]}
    user=pwd.getpwnam(os.environ.get('SUDO_USER','root'))
    if user.pw_uid!=0:
        path=Path(user.pw_dir)/'kiagent-save-lifecycle-result.json';atomic(path,json.dumps(report,indent=2).encode(),0o600);os.chown(path,user.pw_uid,user.pw_gid)
    print(json.dumps(report,indent=2))
    print('Webseite wieder bereit. Konfigurationswerte und Passwort wurden nicht geaendert.')

if __name__=='__main__':main()
