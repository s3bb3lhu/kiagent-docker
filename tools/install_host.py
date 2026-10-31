#!/usr/bin/env python3
"""Install bounded host agents; leaves native chat services available until cutover."""
import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import stat
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
PROJECT = Path('/opt/kiagent-docker/project')
STATE = Path('/etc/kiagent-docker')

def run(*args, **kwargs):
    return subprocess.run(args, check=True, timeout=240, **kwargs)

def atomic(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.kiagent-install-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), 0, 0)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def db_state():
    path = Path('/var/lib/kiagent-executor/history.sqlite3')
    if not path.exists():
        return None
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {table: db.execute('SELECT * FROM ' + table + ' ORDER BY rowid').fetchall()
                for table in ('settings','auto_repairs','auto_delivery') if table in tables}

def barrier():
    code = "import socket,json; s=socket.socket(socket.AF_UNIX); s.settimeout(60); s.connect('/run/kiagent-executor/control.sock'); s.sendall(b'{\"op\":\"health\"}'+bytes([10])); r=s.recv(20000); assert json.loads(r).get('ok') is True"
    run('/usr/sbin/runuser','-u','kiagent','-g','kiagent','--','/usr/bin/python3','-I','-c',code)

def main():
    if os.geteuid() != 0:
        raise SystemExit('Bitte mit sudo ausfuehren.')
    if not (STATE / 'deployment.env').is_file():
        raise SystemExit('Zuerst tools/configure.py ausfuehren.')
    if PROJECT.exists():
        raise SystemExit('Installation existiert bereits; Update gezielt planen, keine automatische Ueberschreibung.')
    if PROJECT.parent.is_symlink():
        raise SystemExit('Unerwarteter Projektverzeichnis-Link')
    run('/usr/bin/python3', str(SOURCE/'tools/scan_secrets.py'))
    if subprocess.check_output(['/usr/bin/dpkg','--print-architecture'], text=True).strip() != 'amd64':
        raise SystemExit('Diese gesperrte Abhaengigkeitsliste ist fuer Linux amd64/Python 3.14.')
    security = subprocess.check_output(['/usr/bin/docker','info','--format','{{json .SecurityOptions}}'], text=True)
    if 'rootless' in security or 'userns' in security:
        raise SystemExit('Host-Peer-Authentifizierung benoetigt Docker ohne UID-Remapping. Keine Sicherheitsoption wurde geaendert.')
    native = [unit for unit in ('kiagent.service','kiagent-discord.service') if subprocess.run(['/usr/bin/systemctl','is-active','--quiet',unit]).returncode == 0]
    # A migration must keep the existing identities and queued notification recipients.
    for old, new in [(Path('/etc/kiagent/allowed-users'), STATE/'secrets/allowed-users'),
                     (Path('/etc/kiagent/discord-access.json'), STATE/'secrets/discord-access.json')]:
        if native and old.exists() and old.read_text().strip() != new.read_text().strip():
            if old.suffix == '.json' and json.loads(old.read_text()) == json.loads(new.read_text()):
                continue
            raise SystemExit('Identitaeten weichen von der laufenden Installation ab. Migration zuerst pruefen.')
    old_backup = Path('/usr/local/lib/kiagent-backup/backup.py')
    if old_backup.is_file():
        run('/usr/bin/python3','-I','-B',str(old_backup),'--run')
    backup = Path('/var/backups') / ('kiagent-docker-migration-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    saved = {}
    removed = []
    changed = False
    def replace(path, data, mode=0o644):
        path = Path(path)
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError('Unsicheres bestehendes Ziel: ' + str(path))
            saved[str(path)] = (path.read_bytes(), stat.S_IMODE(info.st_mode))
            store = backup / str(path).lstrip('/')
            store.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, store)
        else:
            saved[str(path)] = None
        atomic(path, data, mode)
    try:
        for unit in native:
            run('/usr/bin/systemctl','stop',unit)
        if subprocess.run(['/usr/bin/systemctl','is-active','--quiet','kiagent-executor.service']).returncode == 0:
            barrier()
        before = db_state()
        if Path('/var/lib/kiagent-executor/history.sqlite3').exists():
            with sqlite3.connect('file:/var/lib/kiagent-executor/history.sqlite3?mode=ro', uri=True) as db:
                if db.execute("SELECT COUNT(*) FROM auto_repairs WHERE result='pending'").fetchone()[0]:
                    raise ValueError('Offener Reparaturversuch; keine Migration.')
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'package_jobs' in tables and db.execute("SELECT 1 FROM package_jobs WHERE state IN ('started','checking','uncertain')").fetchone():
                    raise ValueError('Offener Paketauftrag; keine Migration.')
        subprocess.run(['/usr/bin/systemctl','stop','kiagent-executor.service','kiagent-packages.service'], timeout=180)
        for dirname in ('kiagent-executor.service.d','kiagent-packages.service.d'):
            directory = Path('/etc/systemd/system') / dirname
            if directory.exists():
                if directory.is_symlink():
                    raise ValueError('Unerwarteter Konfigurationslink')
                for path in directory.iterdir():
                    if not path.is_file() or path.is_symlink() or path.suffix != '.conf':
                        raise ValueError('Unerwartete Dienstanpassung')
                    target = backup / 'retired-dropins' / dirname / path.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
                    removed.append((path, path.read_bytes(), stat.S_IMODE(path.stat().st_mode)))
                    path.unlink()
        PROJECT.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        shutil.copytree(SOURCE, PROJECT, ignore=shutil.ignore_patterns('.git','__pycache__','.env','.venv'))
        for path in [PROJECT, *PROJECT.rglob('*')]:
            if path.is_symlink():
                raise ValueError('Projekt darf keine Symlinks enthalten')
            os.chown(path,0,0)
            os.chmod(path,0o755 if path.is_dir() else 0o644)
        for source, target in [('executor.py','server.py'),('package_executor.py','package_server.py'),('host_metrics.py','host_metrics.py')]:
            replace('/opt/kiagent/executor/' + target, (SOURCE/'host'/source).read_bytes(), 0o600)
        replace('/opt/kiagent/executor/package_policy.py',(SOURCE/'src/app/package_policy.py').read_bytes(),0o600)
        replace('/usr/local/lib/kiagent-heartbeat/kiagent_heartbeat.py',(SOURCE/'host/heartbeat.py').read_bytes())
        replace('/usr/local/lib/kiagent-backup/backup.py',(SOURCE/'host/backup.py').read_bytes())
        for path in (SOURCE/'host/systemd').iterdir():
            if path.name == 'kiagent-practice.service' and Path('/etc/systemd/system/kiagent-practice.service').exists():
                continue
            replace('/etc/systemd/system/' + path.name,path.read_bytes())
        Path('/opt/kiagent/executor').chmod(0o700)
        for directory in ('/var/backups/kiagent-daily','/var/lib/kiagent-executor'):
            Path(directory).mkdir(mode=0o700, parents=True, exist_ok=True)
        if before is None:
            with sqlite3.connect('/var/lib/kiagent-executor/history.sqlite3') as db:
                db.execute('CREATE TABLE IF NOT EXISTS settings(name TEXT PRIMARY KEY,value TEXT NOT NULL)')
                db.execute("INSERT OR REPLACE INTO settings VALUES('auto_enabled','false')")
        run('/usr/bin/systemctl','daemon-reload')
        run('/usr/bin/systemctl','enable','--now','kiagent-practice.service','kiagent-executor.service','kiagent-packages.service')
        time.sleep(1)
        barrier()
        after = db_state()
        if before is not None and before != after:
            raise ValueError('Gespeicherte Automatikdaten wurden veraendert')
        run('/usr/bin/systemctl','is-active','--quiet','kiagent-executor.service','kiagent-packages.service')
        changed = True
    finally:
        if not changed:
            for name, value in saved.items():
                if value is None:
                    Path(name).unlink(missing_ok=True)
                else:
                    atomic(Path(name),value[0],value[1])
            for path,data,mode in removed:
                atomic(path,data,mode)
            subprocess.run(['/usr/bin/systemctl','daemon-reload'])
            subprocess.run(['/usr/bin/systemctl','restart','kiagent-executor.service','kiagent-packages.service'])
            if PROJECT.is_dir() and not PROJECT.is_symlink():
                shutil.rmtree(PROJECT)
        for unit in native:
            subprocess.run(['/usr/bin/systemctl','start',unit])
    record = {'backup':str(backup),'legacy_frontends':native,'state_preserved':True}
    atomic(STATE/'migration.json',json.dumps(record).encode(),0o600)
    print('Host-Agenten vorbereitet. Bestehende Chat-Dienste wieder aktiv. Container noch nicht gestartet.')
    print('Naechster Schritt: sudo python3 /opt/kiagent-docker/project/tools/activate.py')

if __name__ == '__main__':
    main()
