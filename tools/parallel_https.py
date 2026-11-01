"""Isolated HTTPS for a co-located stack. Never edits or reloads an existing proxy."""
import ipaddress
import json
import os
import pwd
import socket
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_web import PROJECT,CONFIG,COMPOSE,atomic

TLS=CONFIG/'tls'
STATE=CONFIG/'parallel-https.json'

def output(args):
    return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL,timeout=30)

def free_port(start,host='0.0.0.0',excluded=()):
    for port in range(start,min(start+100,65536)):
        if port in excluded:continue
        try:
            with socket.socket() as probe:probe.bind((host,port))
            return port
        except OSError:pass
    raise ValueError('Kein freier Web-Port im reservierten Suchbereich.')

def protected(path):
    for item in (path,*path.parents):
        info=item.stat()
        if info.st_uid!=0 or info.st_mode & 0o022:raise ValueError('Unsicherer Zertifikatspfad.')

def paths(source):
    root=Path(source['root']).resolve(strict=True);protected(root)
    result=[]
    for field in ('certificate','key'):
        relative=Path(source[field])
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('Ungueltiger Zertifikatspfad.')
        path=(root/relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():raise ValueError('Zertifikat ausserhalb des freigegebenen Ordners.')
        protected(path)
        if path.stat().st_size>131072:raise ValueError('Unerwartet grosse Zertifikatsdatei.')
        result.append(path)
    return result

def validate(source,address):
    cert,key=paths(source)
    match=output(['/usr/bin/openssl','x509','-in',str(cert),'-noout','-checkip',address])
    if 'does NOT match' in match or 'does match certificate' not in match:raise ValueError('Zertifikat gilt nicht fuer die Server-IP.')
    output(['/usr/bin/openssl','x509','-in',str(cert),'-noout','-checkend','86400'])
    output(['/usr/bin/openssl','verify','-CApath','/etc/ssl/certs','-untrusted',str(cert),str(cert)])
    public=output(['/usr/bin/openssl','x509','-in',str(cert),'-pubkey','-noout'])
    if public!=output(['/usr/bin/openssl','pkey','-in',str(key),'-passin','pass:','-pubout']):raise ValueError('Zertifikat und Schluessel passen nicht zusammen.')
    return cert.read_bytes(),key.read_bytes()

def discover(address):
    roots={Path('/etc/letsencrypt')}
    identifiers=output(['/usr/bin/docker','ps','-q']).split()
    # Read mount metadata only, never container environments or application secrets.
    for identifier in identifiers:
        for mount in json.loads(output(['/usr/bin/docker','inspect','--format','{{json .Mounts}}',identifier])):
            if mount.get('Destination')=='/etc/letsencrypt' and mount.get('Type')=='bind':roots.add(Path(mount['Source']))
    for root in sorted(roots):
        if not root.is_dir():continue
        protected(root)
        for cert in sorted(root.glob('live/*/fullchain.pem'))[:100]:
            source={'root':str(root),'certificate':str(cert.relative_to(root)),'key':str(cert.relative_to(root).with_name('privkey.pem'))}
            try:validate(source,address)
            except (OSError,ValueError,subprocess.SubprocessError):continue
            return source
    raise ValueError('Kein gueltiges vorhandenes IP-Zertifikat gefunden. Bestehende Proxys wurden nicht geaendert.')

def render_compose(text,loopback_port,port):
    replacements={
      "ports: ['127.0.0.1:"+str(loopback_port)+":8080']":"ports: ['0.0.0.0:"+str(port)+":8080']",
      "'config_web:create_app()']":"--certfile, /run/kiagent-tls/fullchain.pem, --keyfile, /run/kiagent-tls/privkey.pem, 'config_web:create_app()']",
      '      CONFIG_AUTH_DIR:':'      CONFIG_DIRECT_TLS: \'1\'\n      CONFIG_AUTH_DIR:',
      '    secrets: [web-admin-hash, web-session-key]':'''    secrets: [web-admin-hash, web-session-key]
    # Dedicated read-only copies; the existing certificate source is never mounted here.''',
      '        source: /var/lib/kiagent-web/auth':'''        source: /etc/kiagent-docker/tls
        target: /run/kiagent-tls
        read_only: true
        bind: {create_host_path: false}
      - type: bind
        source: /var/lib/kiagent-web/auth'''}
    for old,new in replacements.items():
        if text.count(old)!=1:raise ValueError('Unerwarteter Compose-Stand. Keine automatische Anpassung.')
        text=text.replace(old,new)
    return text

def copy_certificate(source,address):
    certificate,key=validate(source,address)
    gid=pwd.getpwnam('kiagent-config').pw_gid
    TLS.mkdir(mode=0o750,exist_ok=True);os.chown(TLS,0,gid);TLS.chmod(0o750)
    changed=not (TLS/'fullchain.pem').exists() or (TLS/'fullchain.pem').read_bytes()!=certificate or (TLS/'privkey.pem').read_bytes()!=key
    if changed:
        atomic(TLS/'privkey.pem',key,0o440,gid);atomic(TLS/'fullchain.pem',certificate,0o440,gid)
        atomic(TLS/'reload-pending',b'pending\n',0o600)
    return changed

def configure(address,admin,port,loopback_port,source):
    address=str(ipaddress.IPv4Address(address));admin=str(ipaddress.ip_address(admin))
    if not 1024<=port<=65535:raise ValueError('Ungueltiger Port.')
    compose=PROJECT/'compose.yaml';env_path=CONFIG/'deployment.env'
    before_compose=compose.read_bytes();before_env=env_path.read_bytes()
    rendered=render_compose(before_compose.decode(),loopback_port,port)
    copy_certificate(source,address)
    env=dict(line.split('=',1) for line in before_env.decode().splitlines() if line and not line.startswith('#'))
    env.update(CONFIG_ORIGIN='https://'+address+':'+str(port),CONFIG_SETUP_ALLOWED_IP=admin,CONFIG_SETUP_PROXY='0',CONFIG_SETUP_LOCAL_ONLY='0')
    backup=Path('/var/backups/kiagent-config')/('parallel-https-'+os.urandom(8).hex());backup.mkdir(mode=0o700)
    atomic(backup/'compose.yaml',before_compose,0o600);atomic(backup/'deployment.env',before_env,0o600)
    try:
        atomic(compose,rendered.encode())
        atomic(env_path,('\n'.join(k+'='+v for k,v in env.items())+'\n').encode(),0o600)
        subprocess.run(COMPOSE+['config','--quiet'],check=True,timeout=30)
        subprocess.run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','90','config-web'],check=True,timeout=120)
        (TLS/'reload-pending').unlink(missing_ok=True)
        atomic(STATE,json.dumps({'kind':'parallel-https-v1','address':address,'port':port,'source':source}).encode(),0o600)
        service='''[Unit]
Description=Refresh Server Control certificate copies without changing the existing proxy
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 -I -B /opt/kiagent-docker/project/tools/parallel_https.py --sync
UMask=0077
'''
        timer='''[Unit]
Description=Check Server Control certificate copies every six hours
[Timer]
OnBootSec=10min
OnUnitActiveSec=6h
Persistent=true
[Install]
WantedBy=timers.target
'''
        atomic(Path('/etc/systemd/system/kiagent-tls-sync.service'),service.encode())
        atomic(Path('/etc/systemd/system/kiagent-tls-sync.timer'),timer.encode())
        subprocess.run(['/usr/bin/systemctl','daemon-reload'],check=True)
        subprocess.run(['/usr/bin/systemctl','enable','--now','kiagent-tls-sync.timer'],check=True)
    except BaseException:
        atomic(compose,before_compose);atomic(env_path,before_env,0o600)
        subprocess.run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','90','config-web'],check=False,timeout=120)
        raise

def sync():
    protected(STATE)
    state=json.loads(STATE.read_text())
    if state.get('kind')!='parallel-https-v1':raise ValueError('Unbekannter TLS-Nachweis.')
    changed=copy_certificate(state['source'],state['address'])
    if changed or (TLS/'reload-pending').exists():
        subprocess.run(COMPOSE+['kill','-s','HUP','config-web'],check=True,timeout=30)
        (TLS/'reload-pending').unlink(missing_ok=True)

if __name__=='__main__':
    if os.geteuid()!=0 or sys.argv[1:]!=['--sync']:raise SystemExit('Nur verwalteter Zertifikatsabgleich.')
    try:sync()
    except Exception as error:raise SystemExit('Zertifikatsabgleich fehlgeschlagen: '+type(error).__name__)
