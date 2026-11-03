"""Default Compose first-install flow. Own existing installs are started, never updated."""
import fcntl
import json
import os
import re
import secrets
import stat
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

RESULT=Path('/installation-result')
HOST_CONFIG=Path('/host/etc/kiagent-docker')
HOST_PROJECT='/opt/kiagent-docker/project'

def protected_file(path):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o077:raise ValueError('Unsicherer Installationsnachweis.')
    return path.read_text()

def write(path,value,mode=0o600):
    fd,temporary=tempfile.mkstemp(prefix='.install-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write(value);stream.flush();os.fchmod(stream.fileno(),mode);os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:Path(temporary).unlink(missing_ok=True)

def status(state,url=None):
    data={'state':state}
    if url:data['url']=url
    write(RESULT/'status.json',json.dumps(data)+'\n',0o644)
    message=url+'\n' if url else 'Installation '+state+'. Siehe Container-Protokoll von setup.\n'
    write(RESULT/'WEBADRESSE.txt',message,0o644)

def matches(owner):
    try:return protected_file(HOST_CONFIG/'first-install-owner')==owner
    except FileNotFoundError:return False

def protected_directory(path):
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022:raise ValueError('Installationsordner muss rootgeschuetzt sein.')

def ready_url():
    record=json.loads(protected_file(HOST_CONFIG/'compose-install.json'))
    if record.get('kind')!='compose-host-install-v1' or record.get('network_ready') is not True:raise ValueError('HTTPS-Einrichtung nicht abgeschlossen.')
    origin=record['origin'];parsed=urlsplit(origin)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:raise ValueError('Ungueltiger Webzugang.')
    return origin+'/setup'

def ensure_ollama(stage_payload,namespace,child_env):
    helper=Path('/host/usr/local/lib/kiagent-ai/install_ollama.py')
    if helper.exists():
        protected_file(helper)
        path='/usr/local/lib/kiagent-ai/install_ollama.py'
    else:path=stage_payload()+'/tools/install_ollama.py'
    subprocess.run(namespace+['/usr/bin/python3','-I','-B',path],check=True,env=child_env())

def run(probe,stage_payload,namespace,child_env,select_source=None,check_ai=None):
    protected_directory(RESULT)
    lock=os.open(RESULT/'install.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX)
        owner_path=RESULT/'owner'
        owner=protected_file(owner_path) if owner_path.exists() else secrets.token_hex(32)
        if not re.fullmatch('[0-9a-f]{64}',owner):raise ValueError('Ungueltige Installationskennung.')
        if not owner_path.exists():write(owner_path,owner)
        status('installing')
        source_info=None
        facts=probe()
        if facts['installed'] or facts['configured']:
            if not matches(owner):raise ValueError('Andere oder bisherige Installation erkannt. Kein Update und kein Ueberschreiben.')
            marker=HOST_CONFIG/'compose-install.json'
            if not marker.exists():raise ValueError('Unvollstaendige Grundeinrichtung. Manuelle Pruefung erforderlich.')
            record=json.loads(protected_file(marker))
            if not record.get('network_ready'):
                command=namespace+['/usr/bin/python3','-I','-B',HOST_PROJECT+'/tools/host_compose_install.py','--resume-network']
                subprocess.run(command,check=True,env=child_env())
            else:
                subprocess.run(namespace+['/usr/bin/systemctl','start','kiagent-config.service','kiagent-docker.service'],check=True,env=child_env())
            print('Vorhandene eigene Installation gestartet; keine Dateien aktualisiert.',flush=True)
        else:
            if select_source is None:
                from latest_release import source
                select_source=source
            print('Ermittle den neuesten veroeffentlichten Stable-Release direkt von GitHub.',flush=True)
            with select_source() as release:
                source_info=release['metadata']
                print('Installiere aktuellen Stable-Release '+source_info['tag']+' ('+source_info['commit']+').',flush=True)
                stage=stage_payload(payload=release['path'])
                command=namespace+['/usr/bin/python3','-I','-B',stage+'/tools/host_compose_install.py','--install-owner',owner,'--port',os.environ.get('SERVER_WEB_PORT','9898')]
                connection=os.environ.get('INSTALL_SSH_CONNECTION','')
                if connection:command+=['--ssh-connection',connection]
                subprocess.run(command,check=True,env=child_env())
        if check_ai:check_ai()
        else:ensure_ollama(stage_payload,namespace,child_env)
        url=ready_url()
        if source_info:write(RESULT/'version.json',json.dumps(source_info,sort_keys=True)+'\n',0o644)
        status('ready',url)
        installed=json.loads(protected_file(HOST_CONFIG/'compose-install.json'))
        if installed.get('services_origin'):
            services_url=installed['services_origin']+'/setup'
            write(RESULT/'DIENSTEMANAGER.txt',services_url+'\n',0o644)
            print('DIENSTEMANAGER: '+services_url,flush=True)
        print('\nWEBADRESSE: '+url+'\nPasswort und alle Dienstzugriffe ausschliesslich dort einrichten.\nKein Update bestehender Installationen ausgefuehrt.',flush=True)
    except BaseException:
        status('failed')
        raise
    finally:os.close(lock)
