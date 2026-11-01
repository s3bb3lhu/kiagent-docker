#!/usr/bin/env python3
"""Upgrade UI and phase-only activity; preserve secrets, auth and action history."""
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
from install_packages import idle
import sys
sys.path.insert(0,str(SOURCE/'src/app'))
from release_version import VERSION

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausfuehren.')
    library=Path('/usr/local/lib/kiagent-config')
    for name in ('config_broker.py','web_control.py','web_status.py'):
        if hashlib.sha256((library/name).read_bytes()).digest()!=hashlib.sha256((PROJECT/'host'/name).read_bytes()).digest():
            raise SystemExit('Host-Dienst weicht vom Projekt ab. Keine Aenderung.')
    idle()
    run(['/usr/bin/python3',str(SOURCE/'tools/scan_secrets.py')])
    run(['/usr/bin/python3','-B',str(SOURCE/'tools/release_check.py')])
    run(['/usr/bin/systemctl','is-active','--quiet','kiagent-config','kiagent-docker','kiagent-executor','kiagent-packages'])
    run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    run(['/usr/bin/python3',str(SOURCE/'tools/test_docker.py')])
    run(['/usr/bin/python3',str(SOURCE/'tools/test_portable.py')])
    run(['/usr/bin/docker','build','-t','kiagent:ui-candidate',str(SOURCE)])
    backup=Path('/var/backups')/('kiagent-ui-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    saved={}
    def replace(path,data):
        path=Path(path)
        if path.is_symlink():raise ValueError('Unerwarteter Symlink.')
        if path not in saved:
            if path.exists():
                info=path.stat()
                if info.st_uid!=0 or info.st_mode & 0o022:raise ValueError('Unsichere Programmdatei.')
                saved[path]=(path.read_bytes(),info.st_mode & 0o777,info.st_gid)
                atomic(backup/str(path).lstrip('/'),saved[path][0],0o600)
            else:saved[path]=None
        atomic(path,data)
    images={tag:subprocess.check_output(['/usr/bin/docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip() for tag in ('kiagent:local','kiagent-config:local')}
    maintenance=Path('/var/lib/kiagent-config/maintenance')
    fd=os.open(maintenance,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600);os.close(fd)
    changed=False
    try:
        idle()
        # Stop bot submissions before the final idle check. Host agents remain running.
        run(COMPOSE+['stop','telegram','discord'])
        idle();changed=True
        run(['/usr/bin/systemctl','stop','kiagent-config'])
        for path in SOURCE.rglob('*'):
            relative=path.relative_to(SOURCE)
            if '.git' in relative.parts or '__pycache__' in relative.parts:continue
            if path.is_symlink():raise ValueError('Symlinks im Projekt nicht erlaubt.')
            if path.is_file():replace(PROJECT/relative,path.read_bytes())
        for name in ('config_broker.py','config_store.py','web_control.py','web_status.py','web_activity.py','first_setup.py','runtime_start.py'):
            replace(library/name,(SOURCE/'host'/name).read_bytes())
        replace(library/'package_policy.py',(SOURCE/'src/app/package_policy.py').read_bytes())
        for tag in images:run(['/usr/bin/docker','tag','kiagent:ui-candidate',tag])
        run(['/usr/bin/systemctl','start','kiagent-config'])
        account=pwd.getpwnam('kiagent-config')
        probe="""import json,socket,time
def read(op):
 s=socket.socket(socket.AF_UNIX);s.settimeout(15);s.connect('/run/kiagent-config/control.sock');s.sendall(json.dumps({'op':op}).encode()+bytes([10]));d=bytearray()
 while bytes([10]) not in d:
  b=s.recv(4096)
  if not b:raise ValueError()
  d.extend(b)
  if len(d)>1048576:raise ValueError()
 s.close();return json.loads(d)
r=read('web_status');assert r['ok'] and r['data']['available'] and r['data']['scope']=='host'
assert r['data']['cores'] and r['server_clock']['timestamp']>0
print('Host clock and CPU cores: OK')
"""
        for attempt in range(20):
            result=subprocess.run(['/usr/bin/setpriv','--reuid='+str(account.pw_uid),'--regid='+str(account.pw_gid),'--clear-groups','--','/usr/bin/python3','-I','-B','-c',probe],capture_output=True,text=True,timeout=20)
            if result.returncode==0:break
            if attempt==19:raise ValueError('Host-Messwerte nicht bereit.')
            time.sleep(.5)
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','180','telegram','discord','config-web'])
        activity=probe+"\nr=read('web_activity');assert r['ok'] and r['data']['available'];assert all(r['data']['sources'].get(x) for x in ('telegram','discord'));print('Read-only activity: OK')"
        run(['/usr/bin/setpriv','--reuid='+str(account.pw_uid),'--regid='+str(account.pw_gid),'--clear-groups','--','/usr/bin/python3','-I','-B','-c',activity])
        env=dict(line.split('=',1) for line in (CONFIG/'deployment.env').read_text().splitlines() if line and not line.startswith('#'))
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for lang in ('de','en','es','fr'):
            with opener.open(env['CONFIG_ORIGIN']+'/login?lang='+lang,timeout=15) as response:
                text=response.read().decode()
                if response.headers.get('Content-Language')!=lang or 'Crimson Glass' not in text or 'Ruby Control' not in text or 'v'+VERSION not in text:raise ValueError('Design-/Sprach-/Versionsseite nicht bereit.')
        run(['/usr/bin/systemctl','is-active','--quiet','kiagent-config','kiagent-docker','kiagent-executor','kiagent-packages'])
    except BaseException:
        if changed:
            subprocess.run(['/usr/bin/systemctl','stop','kiagent-config'])
            for path,old in reversed(list(saved.items())):
                if old is None:path.unlink(missing_ok=True)
                else:atomic(path,*old)
            for tag,image in images.items():subprocess.run(['/usr/bin/docker','tag',image,tag])
            subprocess.run(['/usr/bin/systemctl','start','kiagent-config'])
        subprocess.run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','180','telegram','discord','config-web'])
        raise
    finally:maintenance.unlink(missing_ok=True)
    report={'result':'success','version':VERSION,'documentation_languages':['de','en','es','fr'],'logo':'connected-s','checked_utc':datetime.now(timezone.utc).isoformat(),'backup':str(backup),'styles':['ruby','glass'],'colors':['red','blue','green','purple','anthracite'],'modes':['light','dark'],'host_clock_and_cores_verified':True,'readonly_activity_verified':True,'secrets_or_password_changed':False,'host_action_executed':False}
    user=pwd.getpwnam(os.environ.get('SUDO_USER','root'))
    if user.pw_uid!=0:
        path=Path(user.pw_dir)/'kiagent-ui-upgrade-result.json';atomic(path,json.dumps(report,indent=2).encode(),0o600);os.chown(path,user.pw_uid,user.pw_gid)
    print(json.dumps(report,indent=2))
    print('Oberflaeche bereit. Browser mit Strg+F5 neu laden. Vorhandenes Passwort verwenden.')

if __name__=='__main__':main()
