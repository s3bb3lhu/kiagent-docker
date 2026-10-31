#!/usr/bin/env python3
"""Install/update the loopback configuration UI without changing bot tokens."""
import getpass
import hashlib
import http.cookiejar
import json
import os
import pwd
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
PROJECT = Path('/opt/kiagent-docker/project')
CONFIG = Path('/etc/kiagent-docker')
ORIGIN = 'http://127.0.0.1:8787'
COMPOSE = ['/usr/bin/docker','compose','--env-file',str(CONFIG/'deployment.env'),'-f',str(PROJECT/'compose.yaml')]

def run(args,timeout=900):
    return subprocess.run(args,check=True,timeout=timeout)

def atomic(path,data,mode=0o644,gid=0):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name = tempfile.mkstemp(prefix='.kiagent-web-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchown(stream.fileno(),0,gid)
            os.fchmod(stream.fileno(),mode)
        os.replace(name,path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def main():
    if os.geteuid() != 0:
        raise SystemExit('Bitte mit sudo im Server-Terminal ausfuehren.')
    if not (PROJECT/'compose.yaml').is_file() or not (CONFIG/'deployment.env').is_file():
        raise SystemExit('Zuerst die Docker-Grundinstallation einrichten.')
    if sys.argv[1:] not in ([],['--before-activation']):
        raise SystemExit('Unerwartete Argumente.')
    before_activation = sys.argv[1:] == ['--before-activation']
    if not before_activation:
        # Recover the existing stack first after a prior installer rollback.
        run(['/usr/bin/systemctl','start','kiagent-docker.service'])
    for parent in (PROJECT,CONFIG,CONFIG/'secrets'):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise SystemExit('Unsicheres Installationsverzeichnis.')
    run(['/usr/bin/python3',str(SOURCE/'tools/scan_secrets.py')])
    security = subprocess.check_output(['/usr/bin/docker','info','--format','{{json .SecurityOptions}}'],text=True)
    if 'rootless' in security or 'userns' in security:
        raise SystemExit('Dieser Aufbau benoetigt Docker ohne UID-Remapping. Keine Sicherheitsoption wurde geaendert.')
    jobs = Path('/var/lib/kiagent-config/jobs')
    if jobs.exists():
        for path in jobs.glob('*.json'):
            if json.loads(path.read_text()).get('state') in {'queued','stopping','starting','checking','restoring'}:
                raise SystemExit('Eine Konfigurationsaenderung ist offen. Nicht neu starten; zuerst pruefen.')
    try:
        account = pwd.getpwnam('kiagent-config')
        if account.pw_uid == 0 or account.pw_shell not in ('/usr/sbin/nologin','/sbin/nologin','/bin/false'):
            raise SystemExit('Unerwarteter Dienstbenutzer.')
    except KeyError:
        run(['/usr/sbin/useradd','--system','--user-group','--no-create-home','--home-dir','/nonexistent','--shell','/usr/sbin/nologin','kiagent-config'])
        account = pwd.getpwnam('kiagent-config')
    admin_file = CONFIG/'secrets/web-admin-hash'
    session_file = CONFIG/'secrets/web-session-key'
    if admin_file.exists() != session_file.exists():
        raise SystemExit('Unvollstaendige Web-Anmeldung. Bitte lokal pruefen.')
    password = None
    new_auth = {}
    if not admin_file.exists():
        print('Waehle jetzt ein eigenes Web-Administratorpasswort. Die Eingabe bleibt unsichtbar.',flush=True)
        password = getpass.getpass('Web-Administratorpasswort (mindestens 16 Zeichen): ')
        if not 16 <= len(password) <= 256:
            raise SystemExit('Bitte ein Passwort mit 16 bis 256 Zeichen waehlen.')
        if password != getpass.getpass('Passwort wiederholen: '):
            raise SystemExit('Passwoerter stimmen nicht ueberein. Keine Dienste geaendert.')
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
        new_auth[admin_file] = (salt+'$'+digest+'\n').encode()
        new_auth[session_file] = (secrets.token_hex(32)+'\n').encode()
    # Build a separate UI image; running chat containers keep their existing image.
    run(['/usr/bin/docker','build','-t','kiagent-config:local',str(SOURCE)])
    library = Path('/usr/local/lib/kiagent-config')
    library.mkdir(mode=0o755,parents=True,exist_ok=True)
    if library.is_symlink() or library.stat().st_uid != 0 or library.stat().st_mode & 0o022:
        raise SystemExit('Unsicheres Programmverzeichnis.')
    run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    backup = Path('/var/backups')/('kiagent-web-install-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    saved = {}
    def replace(path,data,mode=0o644,gid=0):
        path = Path(path)
        if str(path) not in saved:
            if path.exists() or path.is_symlink():
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                    raise ValueError('Unsichere bestehende Datei.')
                previous = path.read_bytes()
                saved[str(path)] = (previous,stat.S_IMODE(info.st_mode),info.st_gid)
                target = backup/str(path).lstrip('/')
                target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                atomic(target,previous,0o600)
            else:
                saved[str(path)] = None
        atomic(path,data,mode,gid)
    payload = {}
    for path in SOURCE.rglob('*'):
        relative = path.relative_to(SOURCE)
        if '.git' in relative.parts or '__pycache__' in relative.parts:
            continue
        if path.is_symlink():
            raise SystemExit('Projekt darf keine Symlinks enthalten.')
        if path.is_file():
            if path.stat().st_size>1000000:
                raise SystemExit('Unerwartet grosse Quelldatei.')
            payload[relative] = path.read_bytes()
    was_running = subprocess.run(['/usr/bin/systemctl','is-active','--quiet','kiagent-config.service']).returncode == 0
    try:
        for relative,data in payload.items():
            replace(PROJECT/relative,data)
        for path,data in new_auth.items():
            replace(path,data,0o440,account.pw_gid)
        env_file = CONFIG/'deployment.env'
        env = dict(line.split('=',1) for line in env_file.read_text().splitlines() if line and not line.startswith('#'))
        env.update(CONFIG_UID=str(account.pw_uid),CONFIG_GID=str(account.pw_gid),CONFIG_ORIGIN=ORIGIN)
        replace(env_file,('\n'.join(k+'='+v for k,v in env.items())+'\n').encode(),0o600)
        for name in ('config_store.py','config_broker.py'):
            replace('/usr/local/lib/kiagent-config/'+name,payload[Path('host')/name])
        for name in ('kiagent-config.service','kiagent-docker.service'):
            replace('/etc/systemd/system/'+name,payload[Path('host/systemd')/name])
        replace('/usr/local/lib/kiagent-backup/backup.py',payload[Path('host/backup.py')])
        for name in ('/var/backups/kiagent-config','/var/lib/kiagent-config'):
            path = Path(name)
            path.mkdir(mode=0o700,parents=True,exist_ok=True)
            if path.is_symlink() or path.stat().st_uid != 0:
                raise ValueError('Unsicheres Statusverzeichnis.')
            path.chmod(0o700)
        run(['/usr/bin/systemd-analyze','verify','/etc/systemd/system/kiagent-config.service'])
        run(['/usr/bin/systemctl','daemon-reload'])
        run(['/usr/bin/systemctl','enable','kiagent-config.service'])
        run(['/usr/bin/systemctl','restart','kiagent-config.service'])
        for _ in range(30):
            if Path('/run/kiagent-config/control.sock').exists():
                break
            time.sleep(.5)
        run(COMPOSE+['config','--quiet'])
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--wait','--wait-timeout','90','config-web'])
        binding = subprocess.check_output(COMPOSE+['port','config-web','8080'],text=True).strip()
        if binding != '127.0.0.1:8787':
            raise ValueError('Web-Port nicht ausschliesslich an Loopback gebunden.')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        for attempt in range(10):
            try:
                with opener.open(ORIGIN+'/health',timeout=3) as response:
                    if response.status != 200:
                        raise ValueError('Web-Dienst nicht bereit.')
                break
            except OSError:
                if attempt == 9:
                    raise
                time.sleep(1)
        if password is not None:
            with opener.open(ORIGIN+'/login',timeout=10) as response:
                html = response.read().decode()
            csrf = re.search(r'name="csrf" value="([^"]+)"',html)[1]
            data = urllib.parse.urlencode({'csrf':csrf,'password':password}).encode()
            request = urllib.request.Request(ORIGIN+'/login',data=data,headers={'Origin':ORIGIN})
            with opener.open(request,timeout=10) as response:
                if response.status != 200:
                    raise ValueError('Web-Anmeldung fehlgeschlagen.')
            with opener.open(ORIGIN+'/api/overview',timeout=10) as response:
                if json.load(response).get('ok') is not True:
                    raise ValueError('Konfigurationsstatus nicht erreichbar.')
        units = ['kiagent-executor.service','kiagent-packages.service']
        if not before_activation:
            run(['/usr/bin/systemctl','start','kiagent-docker.service'])
            units.append('kiagent-docker.service')
        run(['/usr/bin/systemctl','is-active','--quiet',*units])
        run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    except BaseException:
        subprocess.run(COMPOSE+['stop','config-web'],timeout=60)
        command = ['/usr/bin/systemctl','stop','kiagent-config.service'] if was_running else ['/usr/bin/systemctl','disable','--now','kiagent-config.service']
        subprocess.run(command,timeout=60)
        for name,previous in reversed(list(saved.items())):
            if previous is None:
                Path(name).unlink(missing_ok=True)
            else:
                atomic(Path(name),previous[0],previous[1],previous[2])
        subprocess.run(['/usr/bin/systemctl','daemon-reload'])
        if was_running:
            subprocess.run(['/usr/bin/systemctl','start','kiagent-config.service'])
            subprocess.run(COMPOSE+['up','-d','--no-build','--no-deps','config-web'])
        if not before_activation:
            subprocess.run(['/usr/bin/systemctl','start','kiagent-docker.service'],timeout=240)
        raise
    report = {'result':'success','checked_utc':datetime.now(timezone.utc).isoformat(),
              'origin':ORIGIN,'login_verified':password is not None,'bot_tokens_changed':False,
              'backup':str(backup),'public_port':False}
    owner = pwd.getpwnam(os.environ.get('SUDO_USER','root'))
    if owner.pw_uid != 0:
        path = Path(owner.pw_dir)/'kiagent-config-web-install-result.json'
        if not path.exists():
            atomic(path,json.dumps(report,indent=2).encode(),0o600)
            os.chown(path,owner.pw_uid,owner.pw_gid)
    print(json.dumps(report,indent=2))
    print('Konfigurationsseite bereit. Oeffne einen SSH-Tunnel und besuche '+ORIGIN)
    print('Das Web-Passwort wurde nicht ausgegeben. Bot-Tokens wurden nicht veraendert.')

if __name__ == '__main__':
    main()
