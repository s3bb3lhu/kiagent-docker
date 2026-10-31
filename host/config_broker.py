"""Authenticated UNIX peer, fixed config operations, backup and restart transaction."""
import grp
import json
import os
import pwd
import secrets
import socket
import sqlite3
import struct
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from config_store import Store, Invalid, MANAGED

ROOT = Path('/etc/kiagent-docker')
STATE = Path('/var/lib/kiagent-config/jobs')
BACKUPS = Path('/var/backups/kiagent-config')
SOCKET = '/run/kiagent-config/control.sock'
COMPOSE = ['/usr/bin/docker','compose','--env-file',str(ROOT/'deployment.env'),'-f','/opt/kiagent-docker/project/compose.yaml']
SERVICES = ['telegram','discord','server-heartbeat']
AGENTS = ['kiagent-executor.service','kiagent-packages.service']

class PublicError(RuntimeError):
    pass

def run(command,timeout=240):
    result = subprocess.run(command,capture_output=True,text=True,timeout=timeout,stdin=subprocess.DEVNULL)
    if result.returncode:
        raise PublicError('apply')
    return result.stdout

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def check_logins(prepared):
    before,new = prepared['before'],prepared['desired']
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def get(url,headers=None):
        request = urllib.request.Request(url,headers={'User-Agent':'Kiagent-Config/1',**(headers or {})})
        with opener.open(request,timeout=20) as response:
            return json.load(response)
    if new['secrets/telegram-token'] != before['secrets/telegram-token']:
        try:
            token = new['secrets/telegram-token'].decode().strip()
            result = get('https://api.telegram.org/bot'+token+'/getMe')
            if result.get('ok') is not True or result.get('result',{}).get('is_bot') is not True:
                raise ValueError()
        except Exception:
            raise PublicError('telegram_login') from None
    changed = any(new[name] != before[name] for name in ('secrets/discord-token','secrets/discord-access.json'))
    old_env = dict(line.split('=',1) for line in before['deployment.env'].decode().splitlines() if line)
    env = dict(line.split('=',1) for line in new['deployment.env'].decode().splitlines() if line)
    if changed or old_env['DISCORD_APPLICATION_ID'] != env['DISCORD_APPLICATION_ID']:
        try:
            token = new['secrets/discord-token'].decode().strip()
            headers = {'Authorization':'Bot '+token}
            bot = get('https://discord.com/api/v10/users/@me',headers)
            access = json.loads(new['secrets/discord-access.json'])
            channel = get('https://discord.com/api/v10/channels/'+str(access['channel_id']),headers)
            if (bot.get('bot') is not True or bot.get('id') != env['DISCORD_APPLICATION_ID']
                or channel.get('guild_id') != str(access['guild_id']) or channel.get('type') != 0):
                raise ValueError()
        except Exception:
            raise PublicError('discord_login') from None

def durable_state():
    with sqlite3.connect('file:/var/lib/kiagent-executor/history.sqlite3?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        if (db.execute("SELECT 1 FROM auto_repairs WHERE result='pending'").fetchone()
            or db.execute("SELECT 1 FROM package_jobs WHERE state IN ('started','checking','uncertain')").fetchone()):
            raise PublicError('active_action')
        return {name:db.execute('SELECT * FROM '+name+' ORDER BY rowid').fetchall()
                for name in ('settings','auto_repairs','auto_delivery','package_jobs')}

def barrier(path,packet):
    account = pwd.getpwnam('kiagent')
    gid = grp.getgrnam('kiagent').gr_gid
    code = "import socket,json; s=socket.socket(socket.AF_UNIX); s.settimeout(60); s.connect("+repr(path)+"); s.sendall(json.dumps("+repr(packet)+").encode()+bytes([10])); d=bytearray()\nwhile bytes([10]) not in d:\n b=s.recv(4096)\n if not b: raise ValueError()\n d.extend(b)\n if len(d)>24000: raise ValueError()\nassert json.loads(d).get('ok') is True"
    run(['/usr/bin/setpriv','--reuid='+str(account.pw_uid),'--regid='+str(gid),'--clear-groups','--','/usr/bin/python3','-I','-c',code],timeout=70)

def apply_configuration(store,prepared,progress):
    check_logins(prepared)
    if store.revision() != prepared['revision']:
        raise Invalid('stale')
    durable_state()
    backup = BACKUPS/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(4))
    backup.mkdir(mode=0o700)
    for name in MANAGED:
        path = backup/name
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(prepared['before'][name])
            stream.flush()
            os.fsync(stream.fileno())
    changed = False
    stopped = False
    try:
        progress('stopping')
        stopped = True
        run(COMPOSE+['stop',*SERVICES])
        user = int(prepared['before']['secrets/allowed-users'].splitlines()[0])
        barrier('/run/kiagent-executor/control.sock',{'op':'health'})
        barrier('/run/kiagent-packages/control.sock',{'op':'status','user_id':user,'chat_id':user,'message_id':1})
        before = durable_state()
        if store.revision() != prepared['revision']:
            raise Invalid('stale')
        changed = True
        run(['/usr/bin/systemctl','stop',*AGENTS])
        store.write(prepared['desired'])
        progress('starting')
        run(['/usr/bin/systemctl','start',*AGENTS])
        time.sleep(1)
        user = int(prepared['desired']['secrets/allowed-users'].splitlines()[0])
        barrier('/run/kiagent-executor/control.sock',{'op':'health'})
        barrier('/run/kiagent-packages/control.sock',{'op':'status','user_id':user,'chat_id':user,'message_id':1})
        if before != durable_state():
            raise PublicError('state_changed')
        progress('checking')
        run(COMPOSE+['up','-d','--no-build','--pull','never','--force-recreate','--wait','--wait-timeout','180',*SERVICES])
        return 'success'
    except Exception:
        if changed:
            progress('restoring')
            try:
                run(['/usr/bin/systemctl','stop',*AGENTS])
                store.write(prepared['before'])
                run(['/usr/bin/systemctl','start',*AGENTS])
                run(COMPOSE+['up','-d','--no-build','--pull','never','--force-recreate','--wait','--wait-timeout','180',*SERVICES])
            except Exception:
                raise PublicError('rollback_failed') from None
            return 'rolled_back'
        if stopped:
            run(COMPOSE+['up','-d','--no-build','--pull','never','--no-recreate','--wait','--wait-timeout','180',*SERVICES])
        raise

class Broker:
    def __init__(self,store,state=STATE,apply=apply_configuration):
        self.store,self.state,self.apply = store,Path(state),apply
        self.lock = threading.Lock()
        self.active = None
        self.previous = None
        self.blocked = False
        self.state.mkdir(mode=0o700,parents=True,exist_ok=True)
        # A prior interrupted transaction is reported, never replayed.
        for path in self.state.glob('*.json'):
            data = json.loads(path.read_text())
            if data.get('state') not in {'success','rolled_back','failed','unchanged','interrupted'}:
                data.update(state='interrupted',code='interrupted')
                path.write_text(json.dumps(data))
            if data.get('state') == 'interrupted' or data.get('code') == 'rollback_failed':
                self.blocked = True

    def record(self,job,state,code=None):
        data = {'job':job,'state':state,'code':code,'updated_at':time.time()}
        target = self.state/(job+'.json')
        temporary = target.with_suffix('.tmp')
        fd = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump(data,stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary,target)
        fd = os.open(self.state,os.O_RDONLY|os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        if code == 'rollback_failed':
            self.blocked = True

    def handle(self,request):
        if not isinstance(request,dict):
            raise Invalid('schema')
        if request.get('op') in {'web_status','web_activity','web_prepare','web_decide','web_job','web_read'}:
            if not hasattr(self,'control'):return {'ok':False,'code':'unsupported'}
            return self.control.handle(request)
        if request == {'op':'health'}:
            return {'ok':True}
        if request == {'op':'overview'}:
            data = self.previous if self.active and self.previous else self.store.overview()
            return {'ok':True,**data,'busy':self.active is not None,'job':self.active,'blocked':self.blocked}
        if set(request) == {'op','job'} and request['op'] == 'job':
            job = request['job']
            if not isinstance(job,str) or len(job)!=32 or any(c not in '0123456789abcdef' for c in job):
                raise Invalid('schema')
            path = self.state/(job+'.json')
            if not path.is_file():
                raise Invalid('unknown_job')
            return {'ok':True,**json.loads(path.read_text())}
        if set(request) != {'op','data'} or request['op'] != 'save':
            raise Invalid('schema')
        if (self.state.parent/'maintenance').exists():raise Invalid('busy')
        if self.blocked:
            raise Invalid('interrupted')
        if not self.lock.acquire(blocking=False):
            raise Invalid('busy')
        try:
            prepared = self.store.prepare(request['data'])
            if not prepared['changed']:
                self.lock.release()
                return {'ok':True,'state':'unchanged'}
            job = secrets.token_hex(16)
            self.previous = self.store.overview()
            self.active = job
            self.record(job,'queued')
            def work():
                try:
                    result = self.apply(self.store,prepared,lambda state:self.record(job,state))
                    self.record(job,result)
                except (Invalid,PublicError) as error:
                    self.record(job,'failed',str(error))
                except Exception:
                    self.record(job,'failed','internal')
                finally:
                    prepared.clear()
                    self.active = None
                    self.previous = None
                    self.lock.release()
            threading.Thread(target=work,daemon=False).start()
            return {'ok':True,'state':'queued','job':job}
        except Exception:
            if self.lock.locked():
                self.lock.release()
            raise

def main():
    os.umask(0o077)
    account = pwd.getpwnam('kiagent-config')
    os.chown(Path(SOCKET).parent,0,account.pw_gid)
    os.chmod(Path(SOCKET).parent,0o750)
    key = (Path(os.environ['CREDENTIALS_DIRECTORY'])/'web-session-key').read_bytes()
    broker = Broker(Store(ROOT,grp.getgrnam('kiagent').gr_gid,key))
    from web_control import WebControl
    broker.control=WebControl(ROOT,STATE.parent/'actions',broker.lock,guard=durable_state)
    Path(SOCKET).unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(SOCKET)
        os.chown(SOCKET,0,account.pw_gid)
        os.chmod(SOCKET,0o660)
        server.listen(8)
        while True:
            connection,_ = server.accept()
            with connection:
                connection.settimeout(5)
                try:
                    _,uid,_ = struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    if uid != account.pw_uid:
                        continue
                    raw = bytearray()
                    while b'\n' not in raw and len(raw)<=32000:
                        data = connection.recv(4096)
                        if not data:
                            break
                        raw.extend(data)
                    if len(raw)>32000 or not raw.endswith(b'\n') or raw.count(b'\n') != 1:
                        raise Invalid('schema')
                    reply = broker.handle(json.loads(raw))
                except Invalid as error:
                    reply = {'ok':False,'code':str(error)}
                except Exception:
                    reply = {'ok':False,'code':'internal'}
                try:
                    connection.sendall(json.dumps(reply).encode()+b'\n')
                except OSError:
                    pass

if __name__ == '__main__':
    main()
