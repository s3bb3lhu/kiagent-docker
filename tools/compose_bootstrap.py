#!/usr/bin/env python3
"""One-shot, explicitly privileged Compose bootstrap. Never used by runtime services."""
import argparse
import ipaddress
import json
import os
import secrets
import shutil
import stat
import subprocess
from pathlib import Path

HOST=Path('/host')
PAYLOAD=Path('/payload')
NAMESPACE=['/usr/bin/nsenter','--target','1','--mount','--uts','--ipc','--net','--pid','--root=/proc/1/root','--wd=/','--']
PROBE=r'''import json,pathlib,platform,subprocess,sys
root=pathlib.Path('/')
os_release=dict(line.split('=',1) for line in pathlib.Path('/etc/os-release').read_text().splitlines() if '=' in line)
security=json.loads(subprocess.check_output(['/usr/bin/docker','info','--format','{{json .SecurityOptions}}'],text=True))
print(json.dumps({'os':os_release.get('ID','').strip('"'),'release':os_release.get('VERSION_ID','').strip('"'),'architecture':platform.machine(),'systemd':pathlib.Path('/run/systemd/system').is_dir(),'python':list(sys.version_info[:2]),'security':security,'installed':pathlib.Path('/opt/kiagent-docker/project').exists(),'configured':pathlib.Path('/etc/kiagent-docker').exists()}))
'''

def child_env():
    return {'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONUNBUFFERED':'1','PYTHONDONTWRITEBYTECODE':'1','TERM':os.environ.get('TERM','xterm')}

def validate_host(facts):
    if facts['os']!='ubuntu' or facts['release'] not in {'24.04','26.04'} or facts['architecture']!='x86_64' or not facts['systemd'] or facts['python']<[3,10]:
        raise ValueError('Vollinstallation benoetigt Ubuntu 24.04/26.04 amd64 mit systemd und Python >=3.10. Unter Windows eine Linux-VM verwenden.')
    if any('rootless' in value or 'userns' in value for value in facts['security']):raise ValueError('Rootless/UID-Remapping wird nicht unterstuetzt; keine Docker-Sicherheitsoption wurde geaendert.')
    return facts

def host_probe():
    if os.geteuid()!=0:raise ValueError('Installer benoetigt root im einmaligen Container.')
    a=HOST.stat();b=Path('/proc/1/root').stat()
    if (a.st_dev,a.st_ino)!=(b.st_dev,b.st_ino):raise ValueError('Host-Mount und Host-PID-Namensraum passen nicht zusammen.')
    result=subprocess.run(NAMESPACE+['/usr/bin/python3','-I','-B','-c',PROBE],check=True,capture_output=True,text=True,timeout=30,env=child_env())
    return validate_host(json.loads(result.stdout))

def parameters(address,admin_ip,port):
    address=str(ipaddress.IPv4Address(address));admin_ip=str(ipaddress.ip_address(admin_ip));port=int(port)
    if not ipaddress.ip_address(address).is_global:raise ValueError('Fuer vertrauenswuerdiges HTTPS wird eine oeffentliche IPv4-Adresse benoetigt.')
    if ipaddress.ip_address(admin_ip).is_unspecified or ipaddress.ip_address(admin_ip).is_multicast:raise ValueError('Ungueltige Administrator-IP.')
    if (port!=443 and not 1024<=port<=65535) or port==8787:raise ValueError('HTTPS-Port: 443 oder 1024..65535, ausser 8787.')
    return address,admin_ip,port

def stage_payload(payload=PAYLOAD,host=HOST):
    # Validate all inputs before creating anything on the host.
    paths=list(payload.rglob('*'))
    if any(path.is_symlink() or (not path.is_dir() and not path.is_file()) for path in paths):raise ValueError('Quellstand enthaelt Links oder Spezialdateien.')
    if any('.git' in path.relative_to(payload).parts for path in paths):raise ValueError('Git-Metadaten sind kein Installer-Payload.')
    total=sum(path.stat().st_size for path in paths if path.is_file())
    if total>32*1024*1024:raise ValueError('Unerwartet grosser Installer-Payload.')
    for relative in ('var','var/lib','var/lib/kiagent-compose-install'):
        path=host/relative
        if not path.exists():path.mkdir(mode=0o700)
        info=path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022:raise ValueError('Unsicheres Host-Staging-Verzeichnis.')
    parent=host/'var/lib/kiagent-compose-install'
    if parent.stat().st_mode & 0o077:raise ValueError('Installer-Staging muss root-exklusiv sein.')
    stage=parent/('source-'+secrets.token_hex(8))
    shutil.copytree(payload,stage)
    for path in [stage,*stage.rglob('*')]:os.chmod(path,0o700 if path.is_dir() else 0o600)
    return '/'+str(stage.relative_to(host))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--resume-network',action='store_true');parser.add_argument('--web-only',action='store_true',help='Loopback-only web bootstrap for isolated tests; no HTTPS or provider credentials.');args=parser.parse_args()
    os.umask(0o077)
    facts=host_probe()
    if args.check:
        print(json.dumps({'result':'ready','host':facts,'host_files_changed':False}));return
    if not args.resume_network and (facts['installed'] or facts['configured']):raise SystemExit('Vorhandene Installation erkannt. Kein Ueberschreiben; fuer Migration zuerst gesondert pruefen.')
    if args.web_only:
        if args.resume_network:raise SystemExit('Web-only und Netzwerk-Wiederaufnahme nicht kombinieren.')
        stage=stage_payload()
        subprocess.run(NAMESPACE+['/usr/bin/python3','-I','-B',stage+'/tools/install_browser_host.py'],check=True,env=child_env())
        print('Nur lokale Web-Einrichtung: http://127.0.0.1:8787/setup. Bots und Serveraktionen bleiben gesperrt.');return
    print('Einmalige Host-Installation: systemd-Agenten, Docker-Bots/Web und HTTPS. Der Installer beendet sich danach.')
    port=os.environ.get('SERVER_WEB_PORT','8443')
    stage=stage_payload()
    command=NAMESPACE+['/usr/bin/python3','-I','-B',stage+'/tools/host_compose_install.py','--port',str(port)]
    connection=os.environ.get('INSTALL_SSH_CONNECTION','')
    if connection:command+=['--ssh-connection',connection]
    if args.resume_network:command.append('--resume-network')
    print('Host-Quellstand: '+stage)
    subprocess.run(command,check=True,env=child_env())

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        raise SystemExit('Compose-Installation abgebrochen ('+type(error).__name__+'). Vor erneuter Installation den Zustand pruefen.')
