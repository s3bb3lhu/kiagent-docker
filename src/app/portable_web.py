"""Portable web/configuration foundation; no host commands or Docker socket."""
import fcntl
import json
import os
import secrets
import tempfile
import time
import threading
from pathlib import Path
from config_store import Store,Invalid,MANAGED,SECRET_FILES
from config_web import create_app as web_app,password_hash
from web_auth import AuthStore

NOTICE='Portable Oberfläche: Einstellungen werden lokal gespeichert. Host-Reparaturen und Bot-Dienste sind hier nicht verbunden. Für echte Serveraktionen ist ein passender Betriebssystem-Adapter erforderlich.'

def atomic(path,value):
    path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.init-')
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(value);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

class PortableBackend:
    def __init__(self,root,key):
        self.root=Path(root)
        self.root.mkdir(parents=True,mode=0o700,exist_ok=True)
        self.lock=os.open(self.root/'configuration.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        self.mutex=threading.Lock()
        self.store=Store(self.root,os.getgid(),key,owner=os.getuid())
        if not (self.root/'deployment.env').exists():
            raw={'deployment.env':b'DISCORD_APPLICATION_ID=\nKIAGENT_RAID_DEVICES=\n',
                 'secrets/allowed-users':b'',
                 'secrets/discord-access.json':json.dumps({'users':[],'guild_id':'','channel_id':''}).encode()}
            raw.update({'secrets/'+name:b'' for name in SECRET_FILES.values()})
            (self.root/'secrets').mkdir(mode=0o700,exist_ok=True)
            for name in MANAGED:atomic(self.root/name,raw[name])

    def __call__(self,packet):
        # Threads share one fd, so flock is paired with a process-local mutex.
        with self.mutex:
            fcntl.flock(self.lock,fcntl.LOCK_EX)
            try:
                if packet=={'op':'web_status'}:return {'ok':True,'data':{'available':False,'scope':'portable'},'control_available':False}
                if packet.get('op','').startswith('web_'):return {'ok':False,'code':'unsupported'}
                if packet=={'op':'health'}:return {'ok':True}
                if packet=={'op':'overview'}:
                    return {'ok':True,**self.store.overview(),'busy':False,'blocked':False,'capability_notice':NOTICE}
                if set(packet)=={'op','data'} and packet['op']=='save':
                    prepared=self.store.prepare(packet['data'])
                    if not prepared['changed']:return {'ok':True,'state':'unchanged'}
                    backup=self.root/'backups'/(str(time.time_ns())+'-'+secrets.token_hex(4))
                    for name in MANAGED:atomic(backup/name,prepared['before'][name])
                    try:self.store.write(prepared['desired'])
                    except Exception:
                        self.store.write(prepared['before']);raise
                    return {'ok':True,'state':'saved','message':'Einstellungen gespeichert. Es wurden keine Host-Aktionen ausgeführt und keine Bot-Dienste gestartet.'}
                return {'ok':False,'code':'schema'}
            except Invalid as error:return {'ok':False,'code':str(error)}
            finally:fcntl.flock(self.lock,fcntl.LOCK_UN)

def create_app():
    root=Path(os.environ.get('PORTABLE_STATE','/var/lib/kiagent-web'))
    credentials=root/'credentials'
    credentials.mkdir(mode=0o700,parents=True,exist_ok=True)
    for name in ('web-session-key','web-admin-hash'):
        if not (credentials/name).exists():
            salt=secrets.token_hex(16)
            value=(salt+'$'+password_hash(secrets.token_urlsafe(48),salt) if name=='web-admin-hash' else secrets.token_hex(32))+'\n'
            atomic(credentials/name,value.encode())
    auth_dir=root/'auth'
    first=not (auth_dir/'auth.json').exists()
    legacy=(credentials/'web-admin-hash').read_text().strip().split('$',1)
    auth=AuthStore(auth_dir,legacy)
    if first:auth.reset()
    backend=PortableBackend(root/'configuration',(credentials/'web-session-key').read_bytes())
    return web_app(credentials,backend,state_dir=auth_dir)
