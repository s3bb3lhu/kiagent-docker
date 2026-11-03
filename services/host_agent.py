"""Peer-authenticated service manager. Never accepts shell commands or Docker options."""
import collections
import hashlib
import hmac
import json
import os
import pwd
import re
import secrets
import socket
import struct
import subprocess
import threading
import tempfile
import time
from pathlib import Path

SOCKET='/run/kiagent-services/control.sock'
STATE=Path('/var/lib/kiagent-services')
UNIT=re.compile(r'[A-Za-z0-9_.:@\\-]+\.service')
CID=re.compile(r'[a-f0-9]{64}')
VERBS={'start','stop','restart'}
AUTH=Path('/var/lib/kiagent-web/auth/auth.json')

def command(args,timeout=12):
    result=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,timeout=timeout)
    if result.returncode:raise ValueError('command_failed')
    if len(result.stdout)>4*1024*1024:raise ValueError('response_too_large')
    return result.stdout.decode(errors='replace')

def describe(name,description):
    groups=[(('ssh','sshd'),'Ermöglicht verschlüsselte Fernanmeldung und Dateiübertragung.'),
        (('docker','containerd'),'Betreibt und verwaltet Container. Ein Stop kann mehrere Anwendungen betreffen.'),
        (('nginx','apache2','caddy'),'Nimmt Webanfragen entgegen und liefert Webseiten aus oder leitet sie weiter.'),
        (('mdmonitor',),'Überwacht Linux-Software-RAID und meldet Ereignisse; prüft nicht umfassend die Festplattengesundheit.'),
        (('cron',),'Führt zeitgesteuerte Aufgaben aus.'),(('systemd-resolved',),'Löst Rechnernamen in IP-Adressen auf.'),
        (('systemd-networkd','NetworkManager','networking'),'Verwaltet Netzwerkverbindungen. Ein Stop kann den Server unerreichbar machen.'),
        (('kiagent',),'Komponente der Serversteuerung. Änderungen können Bots, Überwachung oder Bedienoberflächen unterbrechen.'),
        (('ollama',),'Stellt lokale KI-Modelle für Anfragen bereit.')]
    explanation=next((text for prefixes,text in groups if name.startswith(prefixes)),None)
    return {'description':description,'explanation':explanation or 'Die Beschreibung stammt vom installierten Dienst. Die genaue Aufgabe ist anwendungsspezifisch.'}

def inventory():
    raw=command(['/usr/bin/systemctl','list-units','--all','--type=service','--no-pager','--plain','--no-legend','--full'])
    services=[]
    for line in raw.splitlines():
        row=line.strip().lstrip('●').split(None,4)
        if len(row)<4 or not UNIT.fullmatch(row[0]):continue
        name,load,active,sub=row[:4];description=row[4] if len(row)>4 else name
        services.append({'id':name,'state':active,'substate':sub,'load':load,**describe(name,description)})
    # Include installed but currently unloaded units as well as active/transient units.
    installed=command(['/usr/bin/systemctl','list-unit-files','--type=service','--no-pager','--no-legend','--full'])
    known={row['id'] for row in services}
    for line in installed.splitlines():
        row=line.split()
        if row and UNIT.fullmatch(row[0]) and row[0] not in known:
            services.append({'id':row[0],'state':'not-loaded','substate':row[1] if len(row)>1 else '', 'load':'installed',**describe(row[0],row[0])})
    names=[row['id'] for row in services if row['state']=='not-loaded' and '@.' not in row['id']]
    if names:
        try:
            descriptions=command(['/usr/bin/systemctl','show','--property=Id,Description','--',*names])
            mapping={}
            for block in descriptions.strip().split('\n\n'):
                fields=dict(line.split('=',1) for line in block.splitlines() if '=' in line)
                if fields.get('Id') and fields.get('Description'):mapping[fields['Id']]=fields['Description']
            for row in services:
                if row['id'] in mapping:row.update(describe(row['id'],mapping[row['id']]))
        except (ValueError,subprocess.TimeoutExpired):pass
    containers=[];docker=Path('/usr/bin/docker').is_file();docker_error=False
    if docker:
        try:
            ids=command(['/usr/bin/docker','ps','-aq','--no-trunc']).splitlines()
            ids=[identifier for identifier in ids if CID.fullmatch(identifier)]
            # Deliberately exclude environment, commands, mounts and labels, which may contain secrets.
            template='{{json .Id}}\n{{json .Name}}\n{{json .State.Status}}\n{{json .HostConfig.PortBindings}}\n{{json .Config.Image}}'
            lines=command(['/usr/bin/docker','inspect','--format',template,*ids]).splitlines() if ids else []
            for offset in range(0,len(lines),5):
                values=[json.loads(line) for line in lines[offset:offset+5]]
                containers.append({'id':values[0],'name':values[1].lstrip('/'),'state':values[2],'ports':values[3] or {},'image':values[4],
                    'description':'Docker-Anwendung aus Image '+values[4]+'. Der Containername identifiziert die konkrete Anwendung; interne Einstellungen und Zugangsdaten werden nicht angezeigt.'})
        except (ValueError,subprocess.TimeoutExpired):docker_error=True
    return {'ok':True,'services':sorted(services,key=lambda row:row['id']),'containers':containers,'docker_installed':docker,'docker_error':docker_error,'time':time.time()}

def auth_data():
    if (STATE/'local-auth-enabled').is_file():
        if not (STATE/'auth.json').exists():return {'mode':'setup','epoch':'setup'}
        return json.loads((STATE/'auth.json').read_text())
    credential=Path(os.environ['CREDENTIALS_DIRECTORY'])/'admin-auth'
    raw=credential.read_text()
    if raw.lstrip().startswith('{'):
        data=json.loads(raw)
        if data.get('mode')!='ready':raise ValueError('setup_required')
        return data
    salt,digest=raw.strip().split('$')
    return {'salt':salt,'digest':digest,'epoch':hashlib.sha256((salt+digest).encode()).hexdigest()}

def audit(event,**fields):
    # Failure to persist intent prevents execution. Never store passwords or session tokens.
    fd=os.open(STATE/'audit.jsonl',os.O_CREAT|os.O_APPEND|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a') as stream:
        stream.write(json.dumps({'time':time.time(),'event':event,**fields})+'\n');stream.flush();os.fsync(stream.fileno())

class Agent:
    def __init__(self):self.sessions={};self.pending={};self.failures=collections.deque();self.lock=threading.Lock()
    def handle(self,data):
        now=time.monotonic()
        self.sessions={k:v for k,v in self.sessions.items() if v['until']>now}
        self.pending={k:v for k,v in self.pending.items() if v['until']>now}
        if not isinstance(data,dict):raise ValueError('invalid')
        if data=={'op':'setup_state'}:return {'ok':True,'setup_required':auth_data().get('mode')=='setup'}
        if data.get('op')=='setup':
            if set(data)!={'op','username','password'} or auth_data().get('mode')!='setup':raise ValueError('setup_closed')
            username,password=data['username'],data['password']
            if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,31}',username):raise ValueError('username')
            if not isinstance(password,str) or not 8<=len(password)<=256 or not any(c.isupper() for c in password) or not any(c.isdecimal() for c in password) or not any(not c.isalnum() and not c.isspace() for c in password):raise ValueError('password_policy')
            salt=secrets.token_hex(16)
            record={'mode':'ready','username':username,'salt':salt,'digest':hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex(),'epoch':secrets.token_hex(24)}
            audit('administrator_created',username=username)
            fd,name=tempfile.mkstemp(prefix='.auth-',dir=STATE)
            try:
                with os.fdopen(fd,'w') as stream:json.dump(record,stream);stream.flush();os.fsync(stream.fileno())
                os.link(name,STATE/'auth.json')
                directory=os.open(STATE,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(directory)
                finally:os.close(directory)
            finally:Path(name).unlink(missing_ok=True)
            return {'ok':True}
        if data.get('op')=='login':
            while self.failures and self.failures[0]<now-300:self.failures.popleft()
            if len(self.failures)>=5:raise ValueError('rate_limit')
            if set(data) not in ({'op','password'},{'op','username','password'}) or not isinstance(data['password'],str) or not 1<=len(data['password'])<=256:raise ValueError('invalid')
            auth=auth_data()
            if auth.get('mode')=='setup':raise ValueError('setup_required')
            digest=hashlib.pbkdf2_hmac('sha256',data['password'].encode(),bytes.fromhex(auth['salt']),600000).hex()
            if not hmac.compare_digest(digest,auth['digest']) or auth.get('username') is not None and data.get('username')!=auth['username']:self.failures.append(now);raise ValueError('login_failed')
            token=secrets.token_hex(32);self.sessions[token]={'until':now+1800,'epoch':auth['epoch']}
            return {'ok':True,'token':token}
        token=data.get('token');session=self.sessions.get(token) if isinstance(token,str) else None
        if not session or session['epoch']!=auth_data()['epoch']:raise ValueError('login_required')
        if data=={'op':'logout','token':token}:self.sessions.pop(token,None);return {'ok':True}
        if data=={'op':'inventory','token':token}:return inventory()
        if data.get('op')=='prepare':
            if set(data)!={'op','token','kind','target','verb'} or data['kind'] not in ('service','container') or data['verb'] not in VERBS or not isinstance(data['target'],str):raise ValueError('invalid')
            kind,target,verb=data['kind'],data['target'],data['verb']
            info=inventory();rows=info['services'] if kind=='service' else info['containers']
            found=next((row for row in rows if row['id']==target),None)
            if not found:raise ValueError('target_missing')
            if kind=='service' and target in ('kiagent-services-agent.service','kiagent-services-web.service'):raise ValueError('self_protected')
            identifier=secrets.token_hex(24)
            self.pending[identifier]={'until':now+120,'token':token,'kind':kind,'target':target,'verb':verb,'before':found,'state':'pending'}
            audit('prepared',id=identifier,kind=kind,target=target,verb=verb)
            return {'ok':True,'id':identifier,'name':found.get('name',target),'warning':'Start, Stop oder Neustart kann Verbindungen und abhängige Anwendungen unterbrechen. Bei Docker-Containern können eingetragene Neustartrichtlinien oder andere Supervisoren den Zustand erneut ändern.'}
        if data.get('op')=='decide':
            if set(data)!={'op','token','id','confirm','phrase'} or type(data['confirm']) is not bool or not isinstance(data['id'],str):raise ValueError('invalid')
            record=self.pending.get(data['id'])
            if not record or record['token']!=token or record['state']!='pending':raise ValueError('expired')
            if not data['confirm']:record['state']='cancelled';audit('cancelled',id=data['id']);return {'ok':True,'result':'cancelled'}
            if data['phrase']!=record['before'].get('name',record['target']):raise ValueError('phrase')
            record['state']='consumed'
            info=inventory();rows=info['services'] if record['kind']=='service' else info['containers']
            current=next((row for row in rows if row['id']==record['target']),None)
            if current!=record['before']:raise ValueError('stale')
            audit('started',id=data['id'],kind=record['kind'],target=record['target'],verb=record['verb'])
            try:
                args=['/usr/bin/systemctl',record['verb'],'--',record['target']] if record['kind']=='service' else ['/usr/bin/docker',record['verb'],record['target']]
                command(args,timeout=45)
                # Wait briefly for oneshot services; report actual state, not an assumed success.
                if record['kind']=='service':
                    details=dict(line.split('=',1) for line in command(['/usr/bin/systemctl','show','--property=ActiveState,Result,ExecMainStatus','--',record['target']]).splitlines() if '=' in line)
                    after=details.get('ActiveState','unknown')
                    expected=after in ('inactive','failed') if record['verb']=='stop' else after in ('active','inactive') and details.get('Result')=='success' and details.get('ExecMainStatus')=='0'
                else:
                    after=command(['/usr/bin/docker','inspect','--format','{{.State.Status}}',record['target']]).strip()
                    expected=after in ('exited','created') if record['verb']=='stop' else after=='running'
                result='success' if expected else 'unverified'
                audit(result,id=data['id'],after=after)
                return {'ok':True,'result':result,'state':after}
            except Exception:
                audit('uncertain',id=data['id']);return {'ok':False,'error':'uncertain'}
        raise ValueError('invalid')

def main():
    account=pwd.getpwnam('kiagent-services');agent=Agent()
    Path(SOCKET).unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(SOCKET);os.chown(SOCKET,0,account.pw_gid);os.chmod(SOCKET,0o660);server.listen(8)
        while True:
            connection,_=server.accept()
            with connection:
                connection.settimeout(60)
                try:
                    _,uid,_=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    if uid!=account.pw_uid:raise ValueError('forbidden')
                    raw=b''
                    while b'\n' not in raw:
                        raw+=connection.recv(4096)
                        if not raw or len(raw)>8192:raise ValueError('invalid')
                    with agent.lock:response=agent.handle(json.loads(raw))
                except (ValueError,TypeError,KeyError) as error:response={'ok':False,'error':str(error) if type(error) is ValueError and re.fullmatch('[a-z_]+',str(error)) else 'invalid'}
                except Exception:response={'ok':False,'error':'unavailable'}
                try:connection.sendall(json.dumps(response).encode()+b'\n')
                except OSError:pass

if __name__=='__main__':main()
