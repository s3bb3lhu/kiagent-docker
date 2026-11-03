"""Fresh Compose services portal: bounded web container and fixed host action broker."""
import argparse
import hashlib
import json
import os
import pwd
import secrets
import subprocess
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_web import SOURCE,PROJECT,CONFIG,COMPOSE,atomic
import parallel_https

ROOT=Path('/etc/kiagent-services')
LIB=Path('/usr/local/lib/kiagent-services')
STATE=Path('/var/lib/kiagent-services')

def run(args,timeout=90):return subprocess.run(args,check=True,timeout=timeout,cwd=PROJECT)

def owned():
    for path in (ROOT,ROOT/'owner'):
        info=path.lstat()
        if path.is_symlink() or info.st_uid!=0 or info.st_mode & 0o077:raise ValueError('Unsafe services owner record')
    if (ROOT/'owner').read_text()!='compose-services-v1':raise ValueError('Unrelated services portal exists')

def environment(values):
    path=CONFIG/'deployment.env';before=path.read_bytes()
    env=dict(line.split('=',1) for line in before.decode().splitlines() if line and not line.startswith('#'))
    env.update(values)
    after=('\n'.join(k+'='+v for k,v in env.items())+'\n').encode()
    if after!=before:
        backup=Path('/var/backups/kiagent-config')/('services-env-'+secrets.token_hex(8));backup.mkdir(mode=0o700)
        atomic(backup/'deployment.env',before,0o600);atomic(path,after,0o600)

def prepare():
    if ROOT.exists():owned();return
    if LIB.exists() or STATE.exists() or Path('/etc/systemd/system/kiagent-services-agent.service').exists():raise ValueError('Existing services installation requires explicit review')
    try:account=pwd.getpwnam('kiagent-services')
    except KeyError:
        run(['/usr/sbin/useradd','--system','--user-group','--no-create-home','--shell','/usr/sbin/nologin','kiagent-services'])
        account=pwd.getpwnam('kiagent-services')
    if account.pw_uid<=0 or account.pw_shell not in ('/usr/sbin/nologin','/sbin/nologin','/bin/false'):raise ValueError('Unexpected services account')
    ROOT.mkdir(mode=0o700);atomic(ROOT/'owner',b'compose-services-v1',0o600)
    atomic(ROOT/'session',secrets.token_hex(48).encode(),0o440,account.pw_gid)
    STATE.mkdir(mode=0o700);atomic(STATE/'local-auth-enabled',b'local-browser-setup-v1',0o600)
    LIB.mkdir(mode=0o755,parents=True);LIB.chmod(0o755)
    atomic(LIB/'host_agent.py',(SOURCE/'services/host_agent.py').read_bytes(),0o644)
    unit='''[Unit]
Description=Server control service and container action broker
After=network.target
[Service]
User=root
Group=kiagent-services
ExecStart=/usr/bin/python3 -I -B /usr/local/lib/kiagent-services/host_agent.py
RuntimeDirectory=kiagent-services
RuntimeDirectoryMode=0750
RuntimeDirectoryPreserve=yes
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
CPUQuota=25%
TasksMax=32
[Install]
WantedBy=multi-user.target
'''
    atomic(Path('/etc/systemd/system/kiagent-services-agent.service'),unit.encode())
    atomic(Path('/etc/systemd/system/kiagent-docker.service.d/30-services.conf'),b'[Unit]\nWants=kiagent-services-agent.service\nAfter=kiagent-services-agent.service\n')
    environment({'SERVICES_UID':str(account.pw_uid),'SERVICES_GID':str(account.pw_gid)})
    run(['/usr/bin/systemctl','daemon-reload']);run(['/usr/bin/systemctl','enable','--now','kiagent-services-agent'])

def copy_tls(source,address):
    certificate,key=parallel_https.validate(source,address)
    account=pwd.getpwnam('kiagent-services');tls=ROOT/'tls'
    tls.mkdir(mode=0o750,exist_ok=True);os.chown(tls,0,account.pw_gid);tls.chmod(0o750)
    changed=not (tls/'fullchain.pem').exists() or (tls/'fullchain.pem').read_bytes()!=certificate or (tls/'privkey.pem').read_bytes()!=key
    if changed:
        atomic(tls/'privkey.pem',key,0o440,account.pw_gid);atomic(tls/'fullchain.pem',certificate,0o440,account.pw_gid)
        atomic(ROOT/'reload-pending',b'pending',0o600)
    return changed

def activate(address,control_port):
    owned()
    if (ROOT/'deployment.json').exists():
        record=json.loads((ROOT/'deployment.json').read_text())
        if record['address']!=address:raise ValueError('Services address mismatch')
        run(COMPOSE+['up','-d','--no-build','--pull','never','--wait','--wait-timeout','90','services-web'],timeout=120)
        return record['origin']
    source=parallel_https.discover(address)
    port=parallel_https.free_port(9999,excluded=(control_port,))
    origin='https://'+address+':'+str(port)
    copy_tls(source,address)
    environment({'SERVICES_BIND':'0.0.0.0','SERVICES_PORT':str(port),'SERVICES_ORIGIN':origin})
    run(COMPOSE+['config','--quiet'])
    run(COMPOSE+['up','-d','--no-build','--pull','never','--wait','--wait-timeout','90','services-web','config-web'],timeout=120)
    record={'kind':'compose-services-v1','address':address,'origin':origin,'source':source}
    atomic(ROOT/'deployment.json',json.dumps(record).encode(),0o600)
    atomic(CONFIG/'services-ready',b'compose-services-v1',0o600)
    (ROOT/'reload-pending').unlink(missing_ok=True)
    timer='''[Unit]
Description=Refresh services portal TLS copies
[Timer]
OnBootSec=10min
OnUnitActiveSec=6h
Persistent=true
[Install]
WantedBy=timers.target
'''
    service='''[Unit]
Description=Refresh services portal TLS without changing its source
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 -I -B /opt/kiagent-docker/project/tools/provision_services.py --sync
UMask=0077
'''
    atomic(Path('/etc/systemd/system/kiagent-services-tls.service'),service.encode())
    atomic(Path('/etc/systemd/system/kiagent-services-tls.timer'),timer.encode())
    run(['/usr/bin/systemctl','daemon-reload']);run(['/usr/bin/systemctl','enable','--now','kiagent-services-tls.timer'])
    return origin

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--sync',action='store_true');args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('Root required')
    if args.prepare:prepare();return
    owned()
    if args.sync:
        record=json.loads((ROOT/'deployment.json').read_text())
        changed=copy_tls(record['source'],record['address'])
        if changed or (ROOT/'reload-pending').exists():
            run(COMPOSE+['kill','-s','HUP','services-web']);(ROOT/'reload-pending').unlink(missing_ok=True)
        return
    record=json.loads((CONFIG/'compose-install.json').read_text())
    print('Dienstemanager bereit: '+activate(record['address'],record['port'])+'/setup')

if __name__=='__main__':main()
