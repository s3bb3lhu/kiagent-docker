"""Resume a rolled-back services installation on the original 1.0.0.0 host."""
import hashlib
import ipaddress
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_services_portal import SOURCE,TARGET,CONFIG,PROJECT,COMPOSE,atomic,run,proxy,auth_units

OLD="public_tls = parsed.scheme == 'https' and bool(parsed.hostname) and parsed.port in (None,443)"
NEW="public_tls = parsed.scheme == 'https' and bool(parsed.hostname) and (parsed.port in (None,443) or parsed.port in (9898,))"

def patch_port(source):
    if source.count(OLD)!=1:raise ValueError('Unbekannter Web-Quellstand; keine automatische Korrektur.')
    return source.replace(OLD,NEW)

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausfuehren.')
    if (PROJECT/'VERSION').read_text().strip()!='1.0.0.0':raise ValueError('Installierten Stand zuerst pruefen.')
    for file in (SOURCE/'services').rglob('*'):
        if file.is_file() and '__pycache__' not in file.parts and not file.name.startswith('test_'):
            target=TARGET/'app'/file.relative_to(SOURCE/'services')
            known=target.read_bytes()==file.read_bytes() or file.name=='host_agent.py' and hashlib.sha256(target.read_bytes()).hexdigest()=='19a6d3790fb1dbb48064268214f039293fd3066998597f59fab6d543ecdcf389'
            if target.is_symlink() or not known or target.stat().st_uid!=0:raise ValueError('Dienstemanager-Code weicht ab.')
    for name in ('kiagent-services-agent','kiagent-services-web'):
        unit=Path('/etc/systemd/system')/(name+'.service')
        if not unit.is_file() or unit.is_symlink() or '/opt/kiagent-services/' not in unit.read_text():raise ValueError('Unerwartete Dienstdefinition.')
        status=subprocess.check_output(['/usr/bin/systemctl','show',name,'--property=ActiveState','--value'],text=True).strip()
        if status not in ('inactive','failed'):raise ValueError('Dienst bereits aktiv. Zustand zuerst pruefen.')
    nginx_file=Path('/etc/nginx/conf.d/kiagent-services-ports.conf')
    if nginx_file.exists():raise ValueError('HTTPS-Konfiguration bereits vorhanden.')
    for port in (9898,9999,9990):
        with socket.socket() as probe:probe.bind(('0.0.0.0',port))
    env_path=CONFIG/'deployment.env';env_before=env_path.read_bytes()
    env=dict(line.split('=',1) for line in env_before.decode().splitlines() if line and not line.startswith('#'))
    origin=urlsplit(env['CONFIG_ORIGIN']);ip=str(ipaddress.ip_address(origin.hostname))
    if origin.scheme!='https' or origin.port not in (None,443):raise ValueError('Unerwarteter bisheriger Webzugang.')
    site=Path('/etc/nginx/sites-available/kiagent-config').read_text()
    cert=re.search(r'^\s*ssl_certificate\s+([^;\s]+);',site,re.M)[1]
    key=re.search(r'^\s*ssl_certificate_key\s+([^;\s]+);',site,re.M)[1]
    if any(not re.fullmatch(r'/[A-Za-z0-9_./-]+',path) or not Path(path).is_file() for path in (cert,key)):raise ValueError('TLS-Pfade pruefen.')
    run(['/usr/bin/openssl','x509','-in',cert,'-noout','-checkip',ip],capture_output=True)
    run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    source=PROJECT/'src/app/config_web.py';before=source.read_bytes();patched=patch_port(before.decode()).encode()
    old_image=subprocess.check_output(['/usr/bin/docker','image','inspect','kiagent-config:local','--format','{{.Id}}'],text=True).strip()
    backup=Path('/var/backups/kiagent-services-port-fix-'+str(time.time_ns()));backup.mkdir(mode=0o700)
    atomic(backup/'config_web.py',before,0o600);atomic(backup/'deployment.env',env_before,0o600);atomic(backup/'image-id',old_image.encode(),0o600)
    agent_file=TARGET/'app/host_agent.py';agent_before=agent_file.read_bytes()
    agent_unit=Path('/etc/systemd/system/kiagent-services-agent.service');unit_before=agent_unit.read_bytes()
    auth_source,auth_path,auth_refresh=auth_units()
    if b'LoadCredential=admin-auth:' in unit_before:raise ValueError('Anmeldung bereits eingerichtet. Zuerst Zustand pruefen.')
    atomic(backup/'host_agent.py',agent_before,0o600);atomic(backup/'agent.service',unit_before,0o600)
    enabled=False;switched=False
    try:
        atomic(source,patched)
        run(['/usr/bin/docker','build','-t','kiagent-config:services-ports-candidate',str(PROJECT)],timeout=600)
        atomic(nginx_file,(proxy(9898,8787,ip,cert,key)+proxy(9999,9990,ip,cert,key)).encode())
        run(['/usr/sbin/nginx','-t'])
        atomic(agent_file,(SOURCE/'services/host_agent.py').read_bytes())
        atomic(agent_unit,unit_before.replace(b'UMask=0077',b'UMask=0077\nLoadCredential=admin-auth:'+str(auth_source).encode()))
        atomic('/etc/systemd/system/kiagent-services-auth.path',auth_path.encode())
        atomic('/etc/systemd/system/kiagent-services-auth-refresh.service',auth_refresh.encode())
        run(['/usr/bin/systemctl','daemon-reload'])
        run(['/usr/bin/docker','tag','kiagent-config:services-ports-candidate','kiagent-config:local']);switched=True
        lines=env_before.decode().splitlines()
        atomic(env_path,('\n'.join('CONFIG_ORIGIN=https://'+ip+':9898' if line.startswith('CONFIG_ORIGIN=') else line for line in lines)+'\n').encode(),0o600)
        run(['/usr/bin/systemctl','enable','--now','kiagent-services-agent','kiagent-services-web','kiagent-services-auth.path']);enabled=True
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','120','config-web'],timeout=150)
        run(['/usr/bin/systemctl','reload','nginx'])
        for port in (9898,9999):
            run(['/usr/bin/curl','--resolve',f'{ip}:{port}:127.0.0.1','--fail','--silent','--show-error','--max-time','15',f'https://{ip}:{port}/login'],stdout=subprocess.DEVNULL)
    except BaseException:
        atomic(source,before);atomic(env_path,env_before,0o600)
        atomic(agent_file,agent_before);atomic(agent_unit,unit_before)
        if switched:run(['/usr/bin/docker','tag',old_image,'kiagent-config:local'])
        nginx_file.unlink(missing_ok=True)
        if enabled:subprocess.run(['/usr/bin/systemctl','disable','--now','kiagent-services-auth.path','kiagent-services-web','kiagent-services-agent'],capture_output=True,timeout=30)
        run(['/usr/bin/systemctl','daemon-reload'])
        run(['/usr/sbin/nginx','-t']);run(['/usr/bin/systemctl','reload','nginx'])
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','config-web'])
        raise
    print('Port-Korrektur erfolgreich. Backup: '+str(backup))
    print(f'Serversteuerung: https://{ip}:9898')
    print(f'Dienste und Container: https://{ip}:9999')
    print('Anmeldung mit bestehendem Serversteuerungs-Passwort. Bots und sonstige Container unveraendert.')

if __name__=='__main__':main()
