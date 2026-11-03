"""Add independent HTTPS services portal: 9999; move management origin to 9898."""
import hashlib
import ipaddress
import json
import os
import pwd
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

SOURCE=Path(__file__).resolve().parents[1]
TARGET=Path('/opt/kiagent-services')
CONFIG=Path('/etc/kiagent-docker')
PROJECT=Path('/opt/kiagent-docker/project')
COMPOSE=['/usr/bin/docker','compose','--env-file',str(CONFIG/'deployment.env'),'-f',str(PROJECT/'compose.yaml')]

def run(args,**kw):return subprocess.run(args,check=True,timeout=kw.pop('timeout',180),**kw)

def atomic(path,data,mode=0o644):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name('.'+path.name+'.install')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)

def proxy(port,upstream,ip,cert,key):
    return f'''server {{
    listen {port} ssl;
    server_name {ip};
    ssl_certificate {cert};
    ssl_certificate_key {key};
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 32k;
    location / {{
        proxy_pass http://127.0.0.1:{upstream};
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_read_timeout 75s;
    }}
}}
'''

def auth_units():
    source=Path('/var/lib/kiagent-web/auth/auth.json')
    if not source.is_file():source=CONFIG/'secrets/web-admin-hash'
    if not source.is_file():raise ValueError('Bestehende Anmeldung fehlt.')
    path=f'''[Unit]
Description=Refresh services portal authentication after password change
[Path]
PathChanged={source}
Unit=kiagent-services-auth-refresh.service
[Install]
WantedBy=multi-user.target
'''
    refresh='''[Unit]
Description=Reload targeted service portal credentials
[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl restart kiagent-services-agent.service kiagent-services-web.service
'''
    return source,path,refresh

def services_ip():
    env=dict(line.split('=',1) for line in (CONFIG/'deployment.env').read_text().splitlines() if line and not line.startswith('#'))
    return str(ipaddress.ip_address(urlsplit(env['CONFIG_ORIGIN']).hostname))

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausfuehren.')
    if TARGET.exists():raise SystemExit('Dienstemanager existiert bereits. Keine automatische Ueberschreibung.')
    current_web=(PROJECT/'src/app/config_web.py').read_text()
    if "public_tls = parsed.scheme == 'https' and bool(parsed.hostname) and parsed.port in (None,443)" in current_web:raise ValueError('Version 1.0.0.0 benoetigt zuerst die gesonderte Port-Kompatibilitaetskorrektur. Keine Aenderungen ausgefuehrt.')
    for port in (9898,9999,9990):
        with socket.socket() as probe:probe.bind(('0.0.0.0',port))
    env_path=CONFIG/'deployment.env';before=env_path.read_bytes()
    env=dict(line.split('=',1) for line in before.decode().splitlines() if line and not line.startswith('#'))
    parsed=urlsplit(env['CONFIG_ORIGIN']);ip=str(ipaddress.ip_address(parsed.hostname))
    if parsed.scheme!='https':raise ValueError('Vorhandenen HTTPS-Zugang zuerst pruefen.')
    # Reuse the existing certificate paths, retaining their normal renewal mechanism.
    site=Path('/etc/nginx/sites-available/kiagent-config').read_text()
    certificate=re.search(r'^\s*ssl_certificate\s+([^;\s]+);',site,re.M)
    private_key=re.search(r'^\s*ssl_certificate_key\s+([^;\s]+);',site,re.M)
    if not certificate or not private_key:raise ValueError('Keine eindeutige bestehende TLS-Konfiguration.')
    cert,key=certificate[1],private_key[1]
    if any(not re.fullmatch(r'/[A-Za-z0-9_./-]+',path) or not Path(path).is_file() for path in (cert,key)):raise ValueError('TLS-Pfade pruefen.')
    run(['/usr/bin/openssl','x509','-in',cert,'-noout','-checkip',ip],capture_output=True)
    run(['/usr/bin/openssl','x509','-in',cert,'-noout','-checkend','86400'],capture_output=True)
    # Make an application-consistent backup using the installed, verified backup facility.
    for path,mode in ((Path('/var/lib/kiagent-backup'),0o755),(Path('/var/lib/kiagent-backup/work'),0o700)):
        if not path.exists():path.mkdir(mode=mode)
        st=path.lstat()
        if path.is_symlink() or not path.is_dir() or st.st_uid!=0 or st.st_mode & 0o022 or mode==0o700 and st.st_mode & 0o077:raise ValueError('Unsicheres Backup-Verzeichnis.')
    run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    backup=Path('/var/backups/kiagent-services-'+str(time.time_ns()));backup.mkdir(mode=0o700)
    atomic(backup/'deployment.env',before,0o600)
    run(['/usr/bin/python3','-B',str(SOURCE/'tools/scan_secrets.py')])
    TARGET.mkdir(mode=0o755)
    shutil.copytree(SOURCE/'services',TARGET/'app',ignore=shutil.ignore_patterns('__pycache__'))
    for path in (TARGET/'app',*(TARGET/'app').rglob('*')):
        if path.is_symlink():raise ValueError('Symlink in source')
        os.chown(path,0,0);path.chmod(0o755 if path.is_dir() else 0o644)
    run(['/usr/bin/python3','-m','venv',str(TARGET/'venv')])
    run([str(TARGET/'venv/bin/python'),'-m','pip','install','--only-binary=:all:','-r',str(SOURCE/'requirements-web.lock')],timeout=600)
    try:account=pwd.getpwnam('kiagent-services')
    except KeyError:
        run(['/usr/sbin/useradd','--system','--user-group','--no-create-home','--shell','/usr/sbin/nologin','kiagent-services']);account=pwd.getpwnam('kiagent-services')
    if account.pw_uid<=0 or account.pw_shell not in ('/usr/sbin/nologin','/sbin/nologin','/bin/false'):raise ValueError('Unerwarteter Dienstbenutzer.')
    import secrets
    directory=Path('/etc/kiagent-services');directory.mkdir(mode=0o700)
    atomic(directory/'session',secrets.token_hex(48).encode(),0o600)
    auth_state=Path('/var/lib/kiagent-services')
    if not auth_state.exists():
        auth_state.mkdir(mode=0o700)
        atomic(auth_state/'local-auth-enabled',b'local-browser-setup-v1',0o600)
    auth_source,auth_path,auth_refresh=auth_units()
    agent='''[Unit]
Description=Server control service and container action broker
After=network.target
[Service]
User=root
Group=kiagent-services
ExecStart=/usr/bin/python3 -I -B /opt/kiagent-services/app/host_agent.py
RuntimeDirectory=kiagent-services
RuntimeDirectoryMode=0750
StateDirectory=kiagent-services
StateDirectoryMode=0700
UMask=0077
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
CapabilityBoundingSet=
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_UNIX
MemoryMax=256M
TasksMax=32
[Install]
WantedBy=multi-user.target
'''
    agent=agent.replace('UMask=0077','UMask=0077\nLoadCredential=admin-auth:'+str(auth_source))
    web=f'''[Unit]
Description=Server control service and container web portal
After=kiagent-services-agent.service
Requires=kiagent-services-agent.service
[Service]
User=kiagent-services
Group=kiagent-services
WorkingDirectory=/opt/kiagent-services/app
ExecStart=/opt/kiagent-services/venv/bin/gunicorn --bind 127.0.0.1:9990 --workers 1 --threads 4 --timeout 80 web:create_app()
Environment=SERVICES_ORIGIN=https://{ip}:9999
Environment=PYTHONDONTWRITEBYTECODE=1
LoadCredential=session:/etc/kiagent-services/session
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
CapabilityBoundingSet=
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
RestrictAddressFamilies=AF_UNIX AF_INET
MemoryMax=192M
TasksMax=16
[Install]
WantedBy=multi-user.target
'''
    nginx_file=Path('/etc/nginx/conf.d/kiagent-services-ports.conf')
    if nginx_file.exists():raise ValueError('Nginx-Konfiguration bereits vorhanden.')
    enabled=False
    try:
        atomic('/etc/systemd/system/kiagent-services-agent.service',agent.encode())
        atomic('/etc/systemd/system/kiagent-services-web.service',web.encode())
        atomic('/etc/systemd/system/kiagent-services-auth.path',auth_path.encode())
        atomic('/etc/systemd/system/kiagent-services-auth-refresh.service',auth_refresh.encode())
        atomic(nginx_file,(proxy(9898,8787,ip,cert,key)+proxy(9999,9990,ip,cert,key)).encode())
        run(['/usr/sbin/nginx','-t'])
        # Change only the management origin; preserve all provider settings and credentials.
        lines=before.decode().splitlines()
        updated='\n'.join('CONFIG_ORIGIN=https://'+ip+':9898' if line.startswith('CONFIG_ORIGIN=') else line for line in lines)+'\n'
        atomic(env_path,updated.encode(),0o600)
        run(['/usr/bin/systemctl','daemon-reload'])
        run(['/usr/bin/systemctl','enable','--now','kiagent-services-agent.service','kiagent-services-web.service','kiagent-services-auth.path']);enabled=True
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','120','config-web'],timeout=150)
        run(['/usr/bin/systemctl','reload','nginx'])
        for port,path in ((9898,'/login'),(9999,'/login')):
            run(['/usr/bin/curl','--resolve',f'{ip}:{port}:127.0.0.1','--fail','--silent','--show-error','--max-time','15',f'https://{ip}:{port}{path}'],stdout=subprocess.DEVNULL)
    except BaseException:
        atomic(env_path,before,0o600)
        nginx_file.unlink(missing_ok=True)
        if enabled:subprocess.run(['/usr/bin/systemctl','disable','--now','kiagent-services-web','kiagent-services-agent'],capture_output=True,timeout=30)
        run(['/usr/sbin/nginx','-t']);run(['/usr/bin/systemctl','reload','nginx'])
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','config-web'])
        raise
    print('Sicherung: '+str(backup))
    print(f'Serversteuerung: https://{ip}:9898')
    print(f'Dienste, Container und Weblinks: https://{ip}:9999')
    print('Anmeldung mit dem bestehenden Serversteuerungs-Passwort. Keine Dienste/Container zu Testzwecken gestoppt.')

if __name__=='__main__':main()
