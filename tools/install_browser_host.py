#!/usr/bin/env python3
"""Fresh web-first installation: no provider credential input, no bots until onboarding."""
import grp
import argparse
import hashlib
import json
import os
import pwd
import secrets
import shutil
import sqlite3
from contextlib import closing
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_web import SOURCE,PROJECT,CONFIG,atomic

def account(name):
    try:value=pwd.getpwnam(name)
    except KeyError:
        subprocess.run(['/usr/sbin/useradd','--system','--user-group','--no-create-home','--home-dir','/nonexistent','--shell','/usr/sbin/nologin',name],check=True)
        value=pwd.getpwnam(name)
    if value.pw_uid<=0 or value.pw_shell not in {'/usr/sbin/nologin','/sbin/nologin','/bin/false'}:raise ValueError('Unerwarteter Dienstbenutzer.')
    return value

def initialize_database(path):
    if path.exists():raise ValueError('Vorhandene Datenbank wird nicht ueberschrieben.')
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript('''
CREATE TABLE events(id INTEGER PRIMARY KEY,timestamp REAL NOT NULL,token TEXT,event TEXT NOT NULL,details TEXT NOT NULL);
CREATE TABLE settings(name TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE auto_repairs(id INTEGER PRIMARY KEY,wall REAL NOT NULL,boot TEXT NOT NULL,mono REAL NOT NULL,result TEXT NOT NULL,details TEXT NOT NULL,resolved INTEGER NOT NULL DEFAULT 0);
CREATE TABLE auto_delivery(run_id INTEGER NOT NULL,user_id INTEGER NOT NULL,PRIMARY KEY(run_id,user_id));
CREATE TABLE package_jobs(token TEXT PRIMARY KEY,uid INTEGER,message INTEGER,expires REAL,state TEXT,plan TEXT,result TEXT);
INSERT INTO settings VALUES('auto_enabled','false');
''')
    path.chmod(0o600)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--loopback-port',type=int,default=8787);parser.add_argument('--install-owner');args=parser.parse_args()
    if args.install_owner and (len(args.install_owner)!=64 or any(c not in '0123456789abcdef' for c in args.install_owner)):raise ValueError('Ungueltige Installationskennung.')
    if not 1024<=args.loopback_port<=65535:raise ValueError('Ungueltiger interner Web-Port.')
    if os.geteuid()!=0:raise SystemExit('Host-Einrichtung benoetigt root.')
    guarded=[PROJECT.parent,CONFIG,Path('/opt/kiagent/executor'),Path('/var/lib/kiagent-executor'),Path('/usr/local/lib/kiagent-config'),Path('/var/lib/kiagent-web'),Path('/etc/kiagent-services'),Path('/var/lib/kiagent-services'),Path('/usr/local/lib/kiagent-services')]
    if any(path.exists() or path.is_symlink() for path in guarded):raise SystemExit('Bestehende Einrichtung erkannt. Keine automatische Uebernahme.')
    if any(Path('/etc/systemd/system',name).exists() for name in ('kiagent-docker.service','kiagent-executor.service','kiagent-packages.service','kiagent-config.service')):raise SystemExit('Vorhandene Host-Dienste zuerst pruefen.')
    subprocess.run(['/usr/bin/python3','-B',str(SOURCE/'tools/release_check.py')],check=True)
    # Build before changing host services; provider credentials are not required.
    subprocess.run(['/usr/bin/docker','build','-t','kiagent:browser-candidate',str(SOURCE)],check=True)
    bot=account('kiagent');discord=account('kiagent-discord');web=account('kiagent-config');gid=grp.getgrnam('kiagent').gr_gid
    PROJECT.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
    PROJECT.parent.chmod(0o755)
    shutil.copytree(SOURCE,PROJECT,ignore=shutil.ignore_patterns('.git','__pycache__','.env','.env.*','.venv','.installation'))
    for path in [PROJECT,*PROJECT.rglob('*')]:
        if path.is_symlink():raise ValueError('Symlink im Quellstand.')
        os.chown(path,0,0);path.chmod(0o755 if path.is_dir() else 0o644)
    compose_path=PROJECT/'compose.yaml'
    compose_path.write_text((SOURCE/'compose.runtime.yaml').read_text().replace("ports: ['127.0.0.1:8787:8080']","ports: ['127.0.0.1:"+str(args.loopback_port)+":8080']"))
    CONFIG.mkdir(mode=0o700);(CONFIG/'secrets').mkdir(mode=0o700)
    if args.install_owner:atomic(CONFIG/'first-install-owner',args.install_owner.encode(),0o600)
    env={'KIAGENT_UID':str(bot.pw_uid),'DISCORD_UID':str(discord.pw_uid),'KIAGENT_GID':str(gid),
         'CONFIG_UID':str(web.pw_uid),'CONFIG_GID':str(web.pw_gid),'DISCORD_APPLICATION_ID':'','KIAGENT_RAID_DEVICES':'',
         'KIAGENT_SECRETS_DIR':str(CONFIG/'secrets'),'CONFIG_ORIGIN':'http://127.0.0.1:'+str(args.loopback_port),'CONFIG_SETUP_LOCAL_ONLY':'1'}
    atomic(CONFIG/'deployment.env',('\n'.join(k+'='+v for k,v in env.items())+'\n').encode(),0o600)
    for name in ('telegram-token','discord-token','openai-api-key','hc-bot','hc-server','allowed-users'):atomic(CONFIG/'secrets'/name,b'',0o440,gid)
    atomic(CONFIG/'secrets/discord-access.json',b'{"users":[],"guild_id":"","channel_id":""}\n',0o440,gid)
    salt=secrets.token_hex(16);digest=hashlib.pbkdf2_hmac('sha256',secrets.token_bytes(48),bytes.fromhex(salt),600000).hex()
    atomic(CONFIG/'secrets/web-admin-hash',(salt+'$'+digest+'\n').encode(),0o440,web.pw_gid)
    atomic(CONFIG/'secrets/web-session-key',(secrets.token_hex(32)+'\n').encode(),0o440,web.pw_gid)
    atomic(CONFIG/'pending-setup',b'{"kind":"browser-setup-pending-v1"}\n',0o600)
    web_state=Path('/var/lib/kiagent-web');web_state.mkdir(mode=0o755);web_state.chmod(0o755)
    auth=web_state/'auth';auth.mkdir(mode=0o700);os.chown(auth,web.pw_uid,web.pw_gid);auth.chmod(0o700)
    code='import sys;sys.path.insert(0,'+repr(str(PROJECT/'src/app'))+');from web_auth import AuthStore;AuthStore('+repr(str(auth))+','+repr((salt,digest))+').reset()'
    subprocess.run(['/usr/bin/setpriv','--reuid='+str(web.pw_uid),'--regid='+str(web.pw_gid),'--clear-groups','--','/usr/bin/python3','-I','-B','-c',code],check=True)
    initialize_database(Path('/var/lib/kiagent-executor/history.sqlite3'))
    for source,target in (('executor.py','server.py'),('package_executor.py','package_server.py'),('host_metrics.py','host_metrics.py')):atomic(Path('/opt/kiagent/executor')/target,(SOURCE/'host'/source).read_bytes(),0o600)
    Path('/opt/kiagent/executor').chmod(0o700)
    atomic(Path('/opt/kiagent/executor/package_policy.py'),(SOURCE/'src/app/package_policy.py').read_bytes(),0o600)
    for name in ('config_broker.py','config_store.py','web_control.py','web_status.py','web_activity.py','first_setup.py','runtime_start.py'):atomic(Path('/usr/local/lib/kiagent-config')/name,(SOURCE/'host'/name).read_bytes())
    atomic(Path('/usr/local/lib/kiagent-config/package_policy.py'),(SOURCE/'src/app/package_policy.py').read_bytes())
    atomic(Path('/usr/local/lib/kiagent-heartbeat/kiagent_heartbeat.py'),(SOURCE/'host/heartbeat.py').read_bytes())
    atomic(Path('/usr/local/lib/kiagent-backup/backup.py'),(SOURCE/'host/backup.py').read_bytes())
    for directory in ('/var/backups/kiagent-daily','/var/backups/kiagent-config','/var/lib/kiagent-config','/var/lib/kiagent-backup','/var/lib/kiagent-backup/work'):Path(directory).mkdir(mode=0o700,parents=True,exist_ok=True)
    for path in (SOURCE/'host/systemd').iterdir():atomic(Path('/etc/systemd/system')/path.name,path.read_bytes())
    subprocess.run(['/usr/bin/python3','-I','-B',str(PROJECT/'tools/provision_services.py'),'--prepare'],check=True)
    condition=b'[Unit]\nConditionPathExists=/etc/kiagent-docker/runtime-ready\n'
    for unit in ('kiagent-executor.service','kiagent-packages.service'):
        atomic(Path('/etc/systemd/system')/(unit+'.d')/'10-browser-setup.conf',condition)
    atomic(Path('/etc/systemd/system/kiagent-docker.service.d/10-browser-setup.conf'),b'[Service]\nExecStart=\nExecStart=/usr/bin/python3 -I -B /usr/local/lib/kiagent-config/runtime_start.py\n')
    for tag in ('kiagent:local','kiagent-config:local'):subprocess.run(['/usr/bin/docker','tag','kiagent:browser-candidate',tag],check=True)
    subprocess.run(['/usr/bin/systemctl','daemon-reload'],check=True)
    subprocess.run(['/usr/bin/systemctl','enable','--now','kiagent-config.service','kiagent-docker.service'],check=True)
    print('Web-Einrichtung bereit. Externe Dienstschluessel wurden nicht abgefragt; Bots und Host-Aktionen warten auf die Browser-Konfiguration.')

if __name__=='__main__':main()
