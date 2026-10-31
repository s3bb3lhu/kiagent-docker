#!/usr/bin/env python3
"""Expose only the authenticated UI through nginx HTTPS with an IP certificate."""
import argparse
import ipaddress
import json
import os
import pwd
import subprocess
import urllib.request
from datetime import datetime,timezone
from pathlib import Path
from install_web import SOURCE,PROJECT,CONFIG,COMPOSE,atomic,run

MARKER = '# Kiagent managed HTTPS v1\n'
SITE = Path('/etc/nginx/sites-available/kiagent-config')
ENABLED = Path('/etc/nginx/sites-enabled/kiagent-config')
CERTBOT = '/opt/kiagent-certbot/bin/certbot'

def nginx_config(address,tls=False,setup_ip=None):
    address=str(ipaddress.IPv4Address(address))
    if setup_ip is not None:setup_ip=str(ipaddress.ip_address(setup_ip))
    text = MARKER+'''limit_req_zone $binary_remote_addr zone=kiagent_login:10m rate=5r/m;
server {
    listen 80 default_server;
    server_name '''+address+''';
    access_log off;
    location ^~ /.well-known/acme-challenge/ { root /var/lib/kiagent-acme; }
    location / { return 308 https://'''+address+'''$request_uri; }
}
'''
    if tls:
        text += '''server {
    listen 443 ssl default_server;
    server_name '''+address+''';
    ssl_certificate /etc/letsencrypt/live/'''+address+'''/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/'''+address+'''/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_tickets off;
    proxy_hide_header Referrer-Policy;
    add_header Referrer-Policy same-origin always;
    client_max_body_size 32k;
    access_log off;
    if ($host != "'''+address+'''") { return 444; }
    location = /login {
        limit_req zone=kiagent_login burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host '''+address+''';
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host "";
        proxy_set_header Connection "";
        proxy_read_timeout 30s;
    }
    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host '''+address+''';
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host "";
        proxy_set_header Connection "";
        proxy_read_timeout 30s;
    }
}
'''
    if tls:
        text=text.replace('proxy_set_header X-Forwarded-Proto https;','proxy_set_header X-Forwarded-Proto https;\n        proxy_set_header X-Kiagent-Setup-IP $remote_addr;')
        setup=('allow '+setup_ip+'; deny all;' if setup_ip else 'deny all;')
        text=text.replace('    location / {\n        proxy_pass', '''    location = /setup {
        '''+setup+'''
        limit_req zone=kiagent_login burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host '''+address+''';
        proxy_set_header X-Kiagent-Setup-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }
    location / {
        proxy_pass''')
    return text

SERVICE = '''[Unit]
Description=Renew Kiagent HTTPS certificates
After=network-online.target nginx.service
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=/opt/kiagent-certbot/bin/certbot renew --quiet --deploy-hook "/usr/bin/systemctl reload nginx"
UMask=0077
PrivateTmp=yes
ProtectHome=yes
'''
TIMER = '''[Unit]
Description=Check Kiagent certificate renewal every six hours
[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
RandomizedDelaySec=900
Persistent=yes
[Install]
WantedBy=timers.target
'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--address',required=True)
    parser.add_argument('--admin-ip')
    args = parser.parse_args()
    address = str(ipaddress.IPv4Address(args.address))
    if not ipaddress.ip_address(address).is_global or os.geteuid()!=0:
        raise SystemExit('Mit sudo und der oeffentlichen IPv4-Adresse ausfuehren.')
    if SITE.exists() and not SITE.read_text().startswith(MARKER):
        raise SystemExit('Vorhandene nginx-Konfiguration wird nicht ueberschrieben.')
    if not SITE.exists():
        listeners = subprocess.check_output(['/usr/bin/ss','-H','-lnt'],text=True)
        if any(line.split()[3].endswith((':80',':443')) for line in listeners.splitlines()):
            raise SystemExit('Port 80/443 bereits belegt. Zuerst vorhandenen Webserver pruefen.')
        ownership=Path('/var/lib/kiagent-https/address')
        own_retry=ownership.is_file() and not ownership.is_symlink() and ownership.stat().st_uid==0 and ownership.read_text().strip()==address
        if Path('/etc/nginx').exists() and not own_retry:
            raise SystemExit('Bestehende nginx-Installation zuerst pruefen; keine automatische Uebernahme.')
    run(['/usr/bin/python3',str(SOURCE/'tools/scan_secrets.py')])
    run(['/usr/bin/systemctl','is-active','--quiet','kiagent-config.service','kiagent-docker.service'])
    for path in Path('/var/lib/kiagent-config/jobs').glob('*.json'):
        data = json.loads(path.read_text())
        if data.get('state') not in {'success','rolled_back','failed','unchanged'} or data.get('code')=='rollback_failed':
            raise SystemExit('Offene Konfigurationsaenderung: zuerst per SSH pruefen.')
    print('HTTPS fuer '+address+'. TCP-Port 80 und 443 muessen bei IONOS erreichbar sein.')
    print('Zertifikate werden bei Let\'s Encrypt angefordert und automatisch erneuert.')
    print('Nutzungsbedingungen: https://letsencrypt.org/repository/')
    if input('Diesen Bedingungen zustimmen und HTTPS einrichten? JA eingeben: ').strip()!='JA':
        raise SystemExit('Abgebrochen. Keine Aenderungen.')
    run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    backup = Path('/var/backups')/('kiagent-https-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    saved = {}
    def replace(path,data,mode=0o644):
        path=Path(path)
        if path.is_symlink():
            raise ValueError('Unerwarteter Symlink: '+str(path))
        if path not in saved:
            if path.exists():
                info=path.stat()
                if info.st_uid!=0 or info.st_mode & 0o022:
                    raise ValueError('Unsichere Zieldatei.')
                saved[path]=(path.read_bytes(),info.st_mode & 0o777,info.st_gid)
                target=backup/str(path).lstrip('/')
                atomic(target,saved[path][0],0o600)
            else:
                saved[path]=None
        atomic(path,data,mode)
    old_image=subprocess.check_output(['/usr/bin/docker','image','inspect','kiagent-config:local','--format','{{.Id}}'],text=True).strip()
    atomic(Path('/var/lib/kiagent-https/address'),(address+'\n').encode(),0o600)
    had_timer=Path('/etc/systemd/system/kiagent-certbot.timer').exists()
    default=Path('/etc/nginx/sites-enabled/default')
    default_link=None
    changed=False
    try:
        run(['/usr/bin/apt-get','update'])
        run(['/usr/bin/apt-get','install','--no-install-recommends','-y','nginx','python3-venv'])
        if default.is_symlink():
            default_link=os.readlink(default)
            default.unlink()
        root=Path('/var/lib/kiagent-acme')
        root.mkdir(mode=0o755,exist_ok=True)
        replace(SITE,nginx_config(address).encode())
        if not ENABLED.exists():
            ENABLED.symlink_to(SITE)
        elif not ENABLED.is_symlink() or ENABLED.resolve()!=SITE:
            raise ValueError('Unerwartete nginx-Verknuepfung.')
        run(['/usr/sbin/nginx','-t'])
        run(['/usr/bin/systemctl','enable','--now','nginx.service'])
        run(['/usr/bin/systemctl','reload','nginx.service'])
        venv=Path('/opt/kiagent-certbot')
        if venv.is_symlink() or (venv.exists() and (venv.stat().st_uid!=0 or venv.stat().st_mode & 0o022)):
            raise ValueError('Unsichere Certbot-Installation.')
        if not venv.exists():
            run(['/usr/bin/python3','-m','venv',str(venv)])
        run([str(venv/'bin/python'),'-m','pip','install','--index-url','https://pypi.org/simple','certbot==5.9.0'])
        run([CERTBOT,'certonly','--non-interactive','--agree-tos','--register-unsafely-without-email',
             '--preferred-profile','shortlived','--webroot','--webroot-path',str(root),
             '--ip-address',address,'--cert-name',address,'--deploy-hook','/usr/bin/systemctl reload nginx'])
        # Test renewal before exposing the application.
        run([CERTBOT,'renew','--dry-run','--cert-name',address])
        run(['/usr/bin/docker','build','-t','kiagent-config:local',str(SOURCE)])
        for relative in ('src/app/config_web.py','src/app/templates/config_login.html','src/app/templates/config_index.html','tools/install_https.py'):
            replace(PROJECT/relative,(SOURCE/relative).read_bytes())
        env_path=CONFIG/'deployment.env'
        env=dict(line.split('=',1) for line in env_path.read_text().splitlines() if line and not line.startswith('#'))
        env['CONFIG_ORIGIN']='https://'+address
        admin_ip=args.admin_ip or env.get('CONFIG_SETUP_ALLOWED_IP') or os.environ.get('SSH_CONNECTION','').split(' ')[0]
        if not admin_ip or admin_ip=='127.0.0.1':
            admin_ip=input('Oeffentliche IP deines PCs fuer die Passwort-Ersteinrichtung: ').strip()
        env.update(CONFIG_SETUP_ALLOWED_IP=str(ipaddress.ip_address(admin_ip)),CONFIG_SETUP_PROXY='1',CONFIG_SETUP_LOCAL_ONLY='0')
        replace(env_path,('\n'.join(k+'='+v for k,v in env.items())+'\n').encode(),0o600)
        changed=True
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','90','config-web'])
        replace(SITE,nginx_config(address,True,env.get('CONFIG_SETUP_ALLOWED_IP')).encode())
        run(['/usr/sbin/nginx','-t'])
        run(['/usr/bin/systemctl','reload','nginx.service'])
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('https://'+address+'/health',timeout=20) as response:
            if json.load(response).get('ok') is not True:
                raise ValueError('HTTPS-Status nicht bereit.')
        with opener.open('https://'+address+'/login',timeout=20) as response:
            if 'Secure' not in response.headers.get('Set-Cookie','') or 'Administrator-Passwort' not in response.read().decode():
                raise ValueError('Sichere Anmeldung nicht bereit.')
        replace('/etc/systemd/system/kiagent-certbot.service',SERVICE.encode())
        replace('/etc/systemd/system/kiagent-certbot.timer',TIMER.encode())
        run(['/usr/bin/systemctl','daemon-reload'])
        run(['/usr/bin/systemctl','enable','--now','kiagent-certbot.timer'])
        # Install backup support for certificates and the managed nginx config.
        replace('/usr/local/lib/kiagent-backup/backup.py',(SOURCE/'host/backup.py').read_bytes())
        replace(PROJECT/'host/backup.py',(SOURCE/'host/backup.py').read_bytes())
        run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    except BaseException:
        if not had_timer:
            subprocess.run(['/usr/bin/systemctl','disable','--now','kiagent-certbot.timer'])
        if changed:
            subprocess.run(['/usr/bin/docker','tag',old_image,'kiagent-config:local'])
        if ENABLED.is_symlink() and saved.get(SITE) is None:
            ENABLED.unlink()
        for path,previous in reversed(list(saved.items())):
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                atomic(path,*previous)
        if default_link is not None and not default.exists():
            default.symlink_to(default_link)
        subprocess.run(['/usr/bin/systemctl','daemon-reload'])
        subprocess.run(['/usr/sbin/nginx','-t'])
        subprocess.run(['/usr/bin/systemctl','reload','nginx.service'])
        if changed:
            subprocess.run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','90','config-web'])
        raise
    report={'result':'success','origin':'https://'+address,'certificate_verified':True,'renewal_tested':True,
            'backup':str(backup),'bot_tokens_changed':False,'checked_utc':datetime.now(timezone.utc).isoformat()}
    owner=pwd.getpwnam(os.environ.get('SUDO_USER','root'))
    if owner.pw_uid!=0:
        path=Path(owner.pw_dir)/'kiagent-https-install-result.json'
        atomic(path,json.dumps(report,indent=2).encode(),0o600)
        os.chown(path,owner.pw_uid,owner.pw_gid)
    print(json.dumps(report,indent=2))
    print('Jetzt '+report['origin']+' direkt im Browser oeffnen. Bisheriges Web-Passwort verwenden.')

if __name__=='__main__':
    main()
