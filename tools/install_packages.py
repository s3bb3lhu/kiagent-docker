#!/usr/bin/env python3
"""Upgrade confirmed repository installs. Does not install a test package."""
import hashlib
import json
import os
import pwd
import sqlite3
import subprocess
import time
import urllib.request
from datetime import datetime,timezone
from pathlib import Path
from install_web import SOURCE,PROJECT,CONFIG,COMPOSE,atomic,run

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def idle():
    with sqlite3.connect('file:/var/lib/kiagent-executor/history.sqlite3?mode=ro',uri=True) as db:
        if db.execute("SELECT 1 FROM package_jobs WHERE state IN ('started','checking','uncertain')").fetchone():
            raise ValueError('Aktiver oder unklarer Paketauftrag. Zuerst pruefen.')
        if db.execute("SELECT 1 FROM auto_repairs WHERE result='pending'").fetchone():
            raise ValueError('Automatische Reparatur noch aktiv. Spaeter erneut pruefen.')
    for directory in (Path('/var/lib/kiagent-config/jobs'),Path('/var/lib/kiagent-config/actions')):
        for path in directory.glob('*.json'):
            row=json.loads(path.read_text())
            if row.get('state') in {'running','queued','stopping','starting','checking','restoring','uncertain'} or (row.get('state')=='pending' and row.get('expires',0)>time.time()):
                raise ValueError('Offener Web-Auftrag. Zuerst abschliessen.')

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausfuehren.')
    legacy={'host/package_executor.py':'bb1f118d2a47ae8a89ca53d6112505ed469a6d95497f4294b9c1742fbbb660ed',
            'host/web_control.py':'c4205130bc7bdb83ddff01337b256cf7d32f2c9375b547aa17e178b28c39710e'}
    for actual,expected in (('/opt/kiagent/executor/package_server.py','host/package_executor.py'),('/usr/local/lib/kiagent-config/web_control.py','host/web_control.py')):
        if digest(actual) not in {digest(PROJECT/expected),digest(SOURCE/expected),legacy[expected]}:raise SystemExit('Dienstcode weicht vom Projekt ab. Zuerst lesend pruefen; keine Aenderung.')
    idle()
    run(['/usr/bin/python3',str(SOURCE/'tools/scan_secrets.py')])
    run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    run(['/usr/bin/python3',str(SOURCE/'tools/test_docker.py')])
    run(['/usr/bin/python3',str(SOURCE/'tools/test_portable.py')])
    run(['/usr/bin/docker','build','-t','kiagent:packages-candidate',str(SOURCE)])
    backup=Path('/var/backups')/('kiagent-packages-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    saved={}
    def replace(path,data,mode=0o644):
        path=Path(path)
        if path.is_symlink():raise ValueError('Unerwarteter Symlink.')
        if path not in saved:
            if path.exists():
                info=path.stat()
                if info.st_uid!=0 or info.st_mode & 0o022:raise ValueError('Unsichere Programmdatei.')
                saved[path]=(path.read_bytes(),info.st_mode & 0o777,info.st_gid)
                atomic(backup/str(path).lstrip('/'),saved[path][0],0o600)
            else:saved[path]=None
        atomic(path,data,mode)
    images={tag:subprocess.check_output(['/usr/bin/docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip() for tag in ('kiagent:local','kiagent-config:local')}
    maintenance=Path('/var/lib/kiagent-config/maintenance')
    fd=os.open(maintenance,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    os.close(fd)
    changed=False
    try:
        idle()
        run(COMPOSE+['stop','telegram','discord'])
        idle()
        changed=True
        run(['/usr/bin/systemctl','stop','kiagent-config','kiagent-packages'])
        for path in SOURCE.rglob('*'):
            rel=path.relative_to(SOURCE)
            if '.git' in rel.parts or '__pycache__' in rel.parts:continue
            if path.is_symlink():raise ValueError('Symlinks im Projekt nicht erlaubt.')
            if path.is_file():replace(PROJECT/rel,path.read_bytes())
        replace('/opt/kiagent/executor/package_server.py',(SOURCE/'host/package_executor.py').read_bytes(),0o600)
        replace('/opt/kiagent/executor/package_policy.py',(SOURCE/'src/app/package_policy.py').read_bytes(),0o600)
        for name in ('config_broker.py','config_store.py','web_control.py','web_status.py','web_activity.py','first_setup.py','runtime_start.py'):
            replace('/usr/local/lib/kiagent-config/'+name,(SOURCE/'host'/name).read_bytes())
        replace('/usr/local/lib/kiagent-config/package_policy.py',(SOURCE/'src/app/package_policy.py').read_bytes())
        for name in ('kiagent-docker.service','kiagent-packages.service'):
            replace('/etc/systemd/system/'+name,(SOURCE/'host/systemd'/name).read_bytes())
        run(['/usr/bin/systemctl','daemon-reload'])
        for tag in images:run(['/usr/bin/docker','tag','kiagent:packages-candidate',tag])
        run(['/usr/bin/systemctl','start','kiagent-packages','kiagent-config'])
        # Only read/ simulate an arbitrary repository package, no install or confirmation.
        probe="import sys;sys.path.insert(0,'/opt/kiagent/executor');import package_server;assert package_server.valid_package('curl');p=package_server.plan('curl');assert p['package']=='curl';print('General APT plan probe: OK (no install)')"
        run(['/usr/bin/python3','-I','-B','-c',probe])
        probe="import sys;from pathlib import Path;sys.path.insert(0,'/usr/local/lib/kiagent-config');from web_control import peer_rpc,PKG;u=int(Path('/etc/kiagent-docker/secrets/allowed-users').read_text().splitlines()[0]);r=peer_rpc(PKG,{'op':'status','user_id':u,'chat_id':u,'message_id':1});assert r.get('ok');print('Package socket status: OK')"
        for attempt in range(20):
            result=subprocess.run(['/usr/bin/python3','-I','-B','-c',probe],capture_output=True,text=True,timeout=12)
            if result.returncode==0:break
            if attempt==19:raise ValueError('Paketdienst nicht bereit.')
            time.sleep(.5)
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','180','telegram','discord','config-web'])
        env=dict(line.split('=',1) for line in (CONFIG/'deployment.env').read_text().splitlines() if line and not line.startswith('#'))
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(env['CONFIG_ORIGIN']+'/health',timeout=15) as response:
            if json.load(response).get('ok') is not True:raise ValueError('Webdienst nicht bereit.')
        run(['/usr/bin/systemctl','is-active','--quiet','kiagent-packages','kiagent-config','kiagent-docker','kiagent-executor'])
        run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    except BaseException:
        if changed:
            # Never restore SQLite history or replay a package request.
            subprocess.run(COMPOSE+['stop','telegram','discord'],timeout=90)
            subprocess.run(['/usr/bin/systemctl','stop','kiagent-config','kiagent-packages'])
            for path,old in reversed(list(saved.items())):
                if old is None:path.unlink(missing_ok=True)
                else:atomic(path,*old)
            for tag,image in images.items():subprocess.run(['/usr/bin/docker','tag',image,tag])
            subprocess.run(['/usr/bin/systemctl','daemon-reload'])
            subprocess.run(['/usr/bin/systemctl','start','kiagent-packages','kiagent-config'])
        subprocess.run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--wait','--wait-timeout','180','telegram','discord','config-web'])
        raise
    finally:
        maintenance.unlink(missing_ok=True)
    report={'result':'success','checked_utc':datetime.now(timezone.utc).isoformat(),'all_apt_packages':True,
            'confirmation_required':True,'ai_install_intent_enabled':True,'test_package_installed':False,'backup':str(backup)}
    user=pwd.getpwnam(os.environ.get('SUDO_USER','root'))
    if user.pw_uid!=0:
        path=Path(user.pw_dir)/'kiagent-packages-upgrade-result.json';atomic(path,json.dumps(report,indent=2).encode(),0o600);os.chown(path,user.pw_uid,user.pw_gid)
    print(json.dumps(report,indent=2))
    print('Alle konfigurierten APT-Pakete freigegeben. Beispiel: /ki_install curl oder /ki Installiere nginx. Erst Plan bestaetigen, dann echte Installation.')

if __name__=='__main__':main()
