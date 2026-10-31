#!/usr/bin/env python3
"""Backed-up dashboard upgrade. Never resets credentials or executes a host action."""
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
    library=Path('/usr/local/lib/kiagent-config')
    expected=PROJECT/'host/config_broker.py'
    if hashlib.sha256((library/'config_broker.py').read_bytes()).digest()!=hashlib.sha256(expected.read_bytes()).digest():
        raise SystemExit('Host-Konfigurationsdienst weicht vom Projektstand ab. Keine Aenderung.')
    for directory in (Path('/var/lib/kiagent-config/jobs'),Path('/var/lib/kiagent-config/actions')):
        for path in directory.glob('*.json'):
            row=json.loads(path.read_text())
            if row.get('state') in {'running','queued','stopping','starting','checking','restoring','uncertain'} or (row.get('state')=='pending' and row.get('expires',0)>time.time()):
                raise SystemExit('Offener oder unklarer Web-Auftrag. Zuerst pruefen.')
    run(['/usr/bin/systemctl','is-active','--quiet','kiagent-config','kiagent-docker','kiagent-executor','kiagent-packages'])
    run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    # Isolated fixtures: no real bot tokens, sockets or server restart.
    run(['/usr/bin/python3',str(SOURCE/'tools/test_docker.py')])
    run(['/usr/bin/python3',str(SOURCE/'tools/test_portable.py')])
    backup=Path('/var/backups')/('kiagent-dashboard-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    saved={}
    def replace(path,data):
        path=Path(path)
        if path.is_symlink():raise ValueError('Unerwarteter Symlink.')
        if path not in saved:
            if path.exists():
                info=path.stat()
                if info.st_uid!=0 or info.st_mode & 0o022:raise ValueError('Unsichere Datei.')
                saved[path]=(path.read_bytes(),info.st_mode & 0o777,info.st_gid)
                atomic(backup/str(path).lstrip('/'),saved[path][0],0o600)
            else:saved[path]=None
        atomic(path,data)
    old_image=subprocess.check_output(['/usr/bin/docker','image','inspect','kiagent-config:local','--format','{{.Id}}'],text=True).strip()
    changed=False
    try:
        run(['/usr/bin/docker','build','-t','kiagent-config:local',str(SOURCE)])
        changed=True
        run(['/usr/bin/systemctl','stop','kiagent-config'])
        for path in SOURCE.rglob('*'):
            relative=path.relative_to(SOURCE)
            if '.git' in relative.parts or '__pycache__' in relative.parts:continue
            if path.is_symlink():raise ValueError('Symlinks im Quellstand nicht erlaubt.')
            if path.is_file():replace(PROJECT/relative,path.read_bytes())
        for name in ('config_broker.py','config_store.py','web_control.py','web_status.py','web_activity.py'):
            replace(library/name,(SOURCE/'host'/name).read_bytes())
        replace(library/'package_policy.py',(SOURCE/'src/app/package_policy.py').read_bytes())
        replace('/etc/systemd/system/kiagent-docker.service',(SOURCE/'host/systemd/kiagent-docker.service').read_bytes())
        run(['/usr/bin/systemctl','daemon-reload'])
        run(['/usr/bin/systemctl','start','kiagent-config'])
        account=pwd.getpwnam('kiagent-config')
        code="import json,socket;s=socket.socket(socket.AF_UNIX);s.settimeout(12);s.connect('/run/kiagent-config/control.sock');s.sendall(b'{\"op\":\"web_status\"}'+bytes([10]));d=bytearray()\nwhile bytes([10]) not in d:\n b=s.recv(4096)\n if not b:raise ValueError()\n d.extend(b)\n if len(d)>32000:raise ValueError()\nr=json.loads(d);assert r.get('ok') and r['data']['available'] and r['data']['scope']=='host';print('Host telemetry: OK')"
        code+="\nfor command in ('automatik_status','ki_install_status'):\n s=socket.socket(socket.AF_UNIX);s.settimeout(15);s.connect('/run/kiagent-config/control.sock');s.sendall(json.dumps({'op':'web_read','actor':'0'*64,'command':command}).encode()+bytes([10]));d=bytearray()\n while bytes([10]) not in d:\n  b=s.recv(4096)\n  if not b:raise ValueError()\n  d.extend(b)\n  if len(d)>32000:raise ValueError()\n r=json.loads(d);assert r.get('ok') and isinstance(r.get('data'),dict) and r['data'].get('ok',True);s.close()\nprint('Read-only agent bridge: OK')"
        for attempt in range(20):
            probe=subprocess.run(['/usr/bin/setpriv','--reuid='+str(account.pw_uid),'--regid='+str(account.pw_gid),'--clear-groups','--','/usr/bin/python3','-I','-c',code],capture_output=True,text=True,timeout=15)
            if probe.returncode==0:break
            if attempt==19:raise ValueError('Host-Messwerte nicht bereit.')
            time.sleep(.5)
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','90','config-web'])
        env=dict(line.split('=',1) for line in (CONFIG/'deployment.env').read_text().splitlines() if line and not line.startswith('#'))
        origin=env['CONFIG_ORIGIN']
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for lang in ('de','en','es','fr'):
            with opener.open(origin+'/login?lang='+lang,timeout=15) as response:
                if response.headers.get('Content-Language')!=lang or 'lang="'+lang+'"' not in response.read().decode():raise ValueError('Sprachseite nicht bereit.')
        run(['/usr/bin/systemctl','is-active','--quiet','kiagent-config','kiagent-docker','kiagent-executor','kiagent-packages'])
    except BaseException:
        if changed:
            subprocess.run(['/usr/bin/systemctl','stop','kiagent-config'])
            subprocess.run(['/usr/bin/docker','tag',old_image,'kiagent-config:local'])
        for path,previous in reversed(list(saved.items())):
            if previous is None:path.unlink(missing_ok=True)
            else:atomic(path,*previous)
        subprocess.run(['/usr/bin/systemctl','daemon-reload'])
        subprocess.run(['/usr/bin/systemctl','start','kiagent-config'])
        if changed:subprocess.run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','90','config-web'])
        raise
    report={'result':'success','checked_utc':datetime.now(timezone.utc).isoformat(),'backup':str(backup),'host_metrics_verified':True,'readonly_agent_bridge_verified':True,
            'languages':['de','en','es','fr'],'password_reset':False,'server_restart_executed':False,'repair_executed':False}
    user=pwd.getpwnam(os.environ.get('SUDO_USER','root'))
    if user.pw_uid!=0:
        path=Path(user.pw_dir)/'kiagent-dashboard-install-result.json';atomic(path,json.dumps(report,indent=2).encode(),0o600);os.chown(path,user.pw_uid,user.pw_gid)
    print(json.dumps(report,indent=2))
    print('Dashboard bereit. Browser mit Strg+F5 neu laden. Vorhandenes Passwort verwenden.')

if __name__=='__main__':main()
