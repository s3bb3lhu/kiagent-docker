"""Explicit, backed-up frontend activation for existing Docker hosts; agents/history stay intact."""
import hashlib
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_web import SOURCE,PROJECT,CONFIG,COMPOSE,atomic
from install_packages import idle

def run(args,**kwargs):return subprocess.run(args,check=True,cwd=PROJECT,timeout=kwargs.pop('timeout',240),**kwargs)

def snapshot():
    with sqlite3.connect('file:/var/lib/kiagent-executor/history.sqlite3?mode=ro',uri=True) as database:
        return {'settings':database.execute('SELECT * FROM settings ORDER BY name').fetchall(),
                'repairs':database.execute('SELECT id,wall,boot,mono,result,details FROM auto_repairs ORDER BY id').fetchall(),
                'packages':database.execute('SELECT * FROM package_jobs ORDER BY rowid').fetchall()}

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte auf dem Server mit sudo ausfuehren.')
    version=(PROJECT/'VERSION').read_text().strip()
    if version not in {'1.3.0.0','1.3.0.1','1.4.0.0'}:raise SystemExit('Installierten Stand zuerst pruefen. Keine automatische Uebernahme.')
    for name in ('config_broker.py','config_store.py','web_control.py'):
        actual=Path('/usr/local/lib/kiagent-config')/name;expected=PROJECT/'host'/name
        if actual.is_symlink() or actual.read_bytes()!=expected.read_bytes():raise SystemExit('Dienstcode weicht vom Projekt ab. Keine Aenderung.')
    idle();run(['/usr/bin/python3','-B',str(SOURCE/'tools/release_check.py')])
    # Browser-only installations have not necessarily run the backup service yet.
    for directory,mode in (('/var/lib/kiagent-backup',0o755),('/var/lib/kiagent-backup/work',0o700)):
        path=Path(directory)
        if not path.exists():path.mkdir(mode=mode)
        info=path.lstat()
        if path.is_symlink() or not path.is_dir() or info.st_uid!=0 or info.st_mode & 0o022 or mode==0o700 and info.st_mode & 0o077:raise ValueError('Unsafe backup directory')
    run(['/usr/bin/systemctl','start','kiagent-backup.service'])
    backup=Path('/var/backups/kiagent-ollama-'+str(time.time_ns()));backup.mkdir(mode=0o700)
    saved={}
    def replace(path,data,mode=0o644):
        path=Path(path)
        if path.is_symlink():raise ValueError('Symlink in installed source')
        if path not in saved:
            if path.exists():
                info=path.stat()
                if info.st_uid!=0 or info.st_mode & 0o022:raise ValueError('Unsafe installed file')
                saved[path]=(path.read_bytes(),info.st_mode&0o777,info.st_gid)
                atomic(backup/str(path).lstrip('/'),saved[path][0],0o600)
            else:saved[path]=None
        atomic(path,data,mode)
    # Save the original port/TLS/mount configuration before adding the AI bridge.
    runtime=PROJECT/'compose.yaml';replace(runtime,runtime.read_bytes())
    images={tag:subprocess.check_output(['/usr/bin/docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip() for tag in ('kiagent:local','kiagent-config:local')}
    running=subprocess.check_output(COMPOSE+['ps','--services','--status','running'],text=True,cwd=PROJECT).splitlines()
    services=[name for name in ('telegram','discord','config-web') if name in running]
    if 'config-web' not in services:raise SystemExit('Webdienst ist nicht aktiv. Zuerst Zustand pruefen.')
    maintenance=Path('/var/lib/kiagent-config/maintenance')
    descriptor=os.open(maintenance,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600);os.close(descriptor)
    changed=False;stopped=False;rollback_ok=True
    try:
        idle()
        run(['/usr/bin/python3','-I','-B',str(SOURCE/'tools/install_ollama.py')],timeout=2400)
        run(['/usr/bin/docker','build','-t','kiagent:ollama-candidate',str(SOURCE)],timeout=900)
        idle();run(COMPOSE+['stop',*services]);stopped=True;idle();before=snapshot();changed=True
        run(['/usr/bin/systemctl','stop','kiagent-config'])
        for path in (SOURCE/'src/app').rglob('*'):
            if path.is_symlink():raise ValueError('Symlink in source')
            if path.is_file() and '__pycache__' not in path.parts:replace(PROJECT/path.relative_to(SOURCE),path.read_bytes())
        for name in ('VERSION','Dockerfile','requirements.lock','installer-manifest.json'):replace(PROJECT/name,(SOURCE/name).read_bytes())
        for name in ('config_broker.py','ai_admin.py'):
            replace(PROJECT/'host'/name,(SOURCE/'host'/name).read_bytes())
            replace(Path('/usr/local/lib/kiagent-config')/name,(SOURCE/'host'/name).read_bytes())
        replace('/usr/local/lib/kiagent-config/ai_socket.py',(SOURCE/'src/app/ai_socket.py').read_bytes())
        for tag in images:run(['/usr/bin/docker','tag','kiagent:ollama-candidate',tag])
        run(['/usr/bin/systemctl','start','kiagent-config'])
        run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','180','config-web'])
        if snapshot()!=before:raise ValueError('Aktionszustand hat sich waehrend der Aktivierung geaendert. Manuell pruefen.')
        bots=[name for name in services if name!='config-web']
        if bots:run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','180',*bots])
    except BaseException:
        try:
            if changed:run(['/usr/bin/systemctl','stop','kiagent-config'])
            for path,old in reversed(list(saved.items())):
                if old is None:path.unlink(missing_ok=True)
                else:atomic(path,*old)
            if changed:
                for tag,image in images.items():run(['/usr/bin/docker','tag',image,tag])
                run(['/usr/bin/systemctl','start','kiagent-config'])
            if stopped:run(COMPOSE+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','180',*services])
        except Exception:
            rollback_ok=False
            bots=[name for name in services if name!='config-web']
            if bots:subprocess.run(COMPOSE+['stop',*bots],cwd=PROJECT,check=False)
            raise RuntimeError('Ruecksetzung nicht sicher bestaetigt. Wartungssperre bleibt aktiv; Zustand manuell pruefen.') from None
        raise
    finally:
        if rollback_ok:maintenance.unlink(missing_ok=True)
    print('Ollama-Anbindung aktiviert. Backup: '+str(backup))
    print('Port, Passwort, Tokens, Aktionshistorie und Sperrzeiten erhalten. Vorhandenes Ollama unveraendert.')
    print('Im Browser neu laden: Einstellungen -> KI-Anbieter. Dort Status und Limits pruefen.')

if __name__=='__main__':main()
