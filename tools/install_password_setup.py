#!/usr/bin/env python3
"""Upgrade the UI and reset access to an IP-restricted browser setup, no codes."""
import argparse
import hashlib
import ipaddress
import json
import os
import pwd
import secrets
import subprocess
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from install_web import SOURCE,PROJECT,CONFIG,COMPOSE,atomic,run
from install_https import nginx_config,SITE,MARKER

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausfuehren.')
    parser=argparse.ArgumentParser()
    parser.add_argument('--admin-ip')
    args=parser.parse_args()
    proposed=args.admin_ip or os.environ.get('SSH_CONNECTION','').split(' ')[0]
    if not proposed:
        proposed=input('Oeffentliche IP-Adresse deines PCs fuer die Ersteinrichtung: ').strip()
    admin_ip=str(ipaddress.ip_address(proposed))
    env_path=CONFIG/'deployment.env'
    env=dict(line.split('=',1) for line in env_path.read_text().splitlines() if line and not line.startswith('#'))
    origin=env['CONFIG_ORIGIN']
    address=urlsplit(origin).hostname
    if not origin.startswith('https://') or not SITE.read_text().startswith(MARKER):
        raise SystemExit('Zuerst den verwalteten HTTPS-Zugang einrichten.')
    for path in Path('/var/lib/kiagent-config/jobs').glob('*.json'):
        row=json.loads(path.read_text())
        if row.get('state') not in {'success','rolled_back','failed','unchanged'} or row.get('code')=='rollback_failed':
            raise SystemExit('Offene Aenderung: zuerst pruefen.')
    print('Ersteinrichtung wird nur fuer Administrator-IP '+admin_ip+' freigegeben.')
    print('Das alte Passwort und alle Web-Sitzungen werden ungueltig. Bot-Tokens bleiben erhalten.')
    run(['/usr/bin/python3',str(SOURCE/'tools/scan_secrets.py')])
    run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    backup=Path('/var/backups')/('kiagent-password-setup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    saved={}
    def replace(path,data,mode=0o644,gid=0):
        path=Path(path)
        if path.is_symlink():raise ValueError('Unerwarteter Symlink.')
        if path not in saved:
            if path.exists():
                info=path.stat()
                if info.st_uid!=0 or info.st_mode & 0o022:raise ValueError('Unsichere Datei.')
                saved[path]=(path.read_bytes(),info.st_mode & 0o777,info.st_gid)
                atomic(backup/str(path).lstrip('/'),saved[path][0],0o600)
            else:saved[path]=None
        atomic(path,data,mode,gid)
    account=pwd.getpwnam('kiagent-config')
    directory=Path('/var/lib/kiagent-web/auth')
    if directory.is_symlink():raise ValueError('Unsicheres Auth-Verzeichnis.')
    directory.mkdir(parents=True,mode=0o700,exist_ok=True)
    if directory.stat().st_uid not in (0,account.pw_uid):raise ValueError('Unerwarteter Besitzer.')
    os.chown(directory,account.pw_uid,account.pw_gid)
    os.chmod(directory,0o700)
    if (directory/'auth.json').is_symlink():raise ValueError('Unsichere Auth-Datei.')
    old_auth=(directory/'auth.json').read_bytes() if (directory/'auth.json').exists() else None
    if old_auth is not None:atomic(backup/'auth.json',old_auth,0o600)
    old_image=subprocess.check_output(['/usr/bin/docker','image','inspect','kiagent-config:local','--format','{{.Id}}'],text=True).strip()
    changed=False
    try:
        run(['/usr/bin/python3',str(SOURCE/'tools/test_portable.py')])
        run(['/usr/bin/docker','build','-t','kiagent-config:local',str(SOURCE)])
        changed=True
        for path in SOURCE.rglob('*'):
            relative=path.relative_to(SOURCE)
            if '.git' in relative.parts or '__pycache__' in relative.parts:continue
            if path.is_symlink():raise ValueError('Symlinks im Projekt nicht erlaubt.')
            if path.is_file():replace(PROJECT/relative,path.read_bytes())
        env.update(CONFIG_SETUP_ALLOWED_IP=admin_ip,CONFIG_SETUP_PROXY='1',CONFIG_SETUP_LOCAL_ONLY='0')
        replace(env_path,('\n'.join(k+'='+v for k,v in env.items())+'\n').encode(),0o600)
        replace(SITE,nginx_config(address,True,admin_ip).encode())
        run(['/usr/sbin/nginx','-t'])
        run(['/usr/bin/systemctl','reload','nginx.service'])
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','90','config-web'])
        # Discard the old fallback credential too, so deleting state cannot revive it.
        salt=secrets.token_hex(16)
        digest=hashlib.pbkdf2_hmac('sha256',secrets.token_bytes(48),bytes.fromhex(salt),600000).hex()
        replace(CONFIG/'secrets/web-admin-hash',(salt+'$'+digest+'\n').encode(),0o440,account.pw_gid)
        code="import sys; sys.path.insert(0,"+repr(str(PROJECT/'src/app'))+"); from web_auth import AuthStore; AuthStore("+repr(str(directory))+ ").reset()"
        run(['/usr/bin/setpriv','--reuid='+str(account.pw_uid),'--regid='+str(account.pw_gid),'--clear-groups','--','/usr/bin/python3','-I','-c',code])
        # Check setup through the private backend with the exact trusted proxy header.
        import urllib.request
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req=urllib.request.Request('http://127.0.0.1:8787/setup',headers={'Host':address,'X-Kiagent-Setup-IP':admin_ip})
        with opener.open(req,timeout=10) as response:
            text=response.read().decode()
            if 'name="repeat"' not in text or 'name="code"' in text:raise ValueError('Ersteinrichtung nicht bereit.')
        run(['/usr/bin/systemctl','is-active','--quiet','nginx','kiagent-config','kiagent-docker','kiagent-executor','kiagent-packages'])
    except BaseException:
        if changed:subprocess.run(['/usr/bin/docker','tag',old_image,'kiagent-config:local'])
        for path,previous in reversed(list(saved.items())):
            if previous is None:path.unlink(missing_ok=True)
            else:atomic(path,*previous)
        if old_auth is not None:atomic(directory/'auth.json',old_auth,0o600,account.pw_gid);os.chown(directory/'auth.json',account.pw_uid,account.pw_gid)
        else:(directory/'auth.json').unlink(missing_ok=True)
        subprocess.run(['/usr/sbin/nginx','-t'])
        subprocess.run(['/usr/bin/systemctl','reload','nginx'])
        if changed:subprocess.run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','90','config-web'])
        raise
    report={'result':'success','setup_url':origin+'/setup','password_reset':True,'setup_restricted_to_admin_ip':True,'bootstrap_code':False,'backup':str(backup),'checked_utc':datetime.now(timezone.utc).isoformat()}
    owner=pwd.getpwnam(os.environ.get('SUDO_USER','root'))
    if owner.pw_uid!=0:
        target=Path(owner.pw_dir)/'kiagent-password-setup-result.json'
        atomic(target,json.dumps(report,indent=2).encode(),0o600)
        os.chown(target,owner.pw_uid,owner.pw_gid)
    print(json.dumps(report,indent=2))
    print('Oeffne '+origin+'/setup und lege dein Passwort im Browser fest. Kein Einrichtungscode erforderlich.')

if __name__=='__main__':main()
