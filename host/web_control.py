"""Fixed, audited web actions bridged to existing peer-authenticated host agents."""
import grp
import json
import os
import pwd
import re
import secrets
import subprocess
import threading
import time
from pathlib import Path
from web_status import Telemetry
from package_policy import valid_package

EXEC='/run/kiagent-executor/control.sock'
PKG='/run/kiagent-packages/control.sock'
ACTIONS=frozenset({'raid_monitor_start','automatik_an','automatik_aus','uebung_neustart','testaktion','install_htop','install_tree','server_restart'})

def peer_rpc(path,packet):
    account=pwd.getpwnam('kiagent')
    timeout=150 if packet.get('op')=='confirm' else 25 if packet.get('op')=='new' else 5
    code="import json,socket,sys;s=socket.socket(socket.AF_UNIX);s.settimeout("+str(timeout)+");s.connect("+repr(path)+");s.sendall(sys.stdin.buffer.read()+bytes([10]));d=bytearray()\nwhile bytes([10]) not in d:\n b=s.recv(4096)\n if not b:raise ValueError()\n d.extend(b)\n if len(d)>1048576:raise ValueError()\nprint(d.decode(),end='')"
    result=subprocess.run(['/usr/bin/setpriv','--reuid='+str(account.pw_uid),'--regid='+str(grp.getgrnam('kiagent').gr_gid),'--clear-groups','--','/usr/bin/python3','-I','-c',code],input=json.dumps(packet),text=True,capture_output=True,timeout=timeout+3,check=True)
    return json.loads(result.stdout)

class WebControl:
    def __init__(self,root,state,lock,rpc=peer_rpc,guard=None):
        self.root,self.state,self.lock,self.rpc=Path(root),Path(state),lock,rpc
        self.state.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.telemetry=Telemetry()
        self.guard=guard
        self.poll_seconds=2
        self.blocked=False
        for path in self.state.glob('*.json'):
            row=json.loads(path.read_text())
            if row['state']=='running':row['state']='uncertain';self.write(row)
            elif row['state']=='pending':row['state']='expired';self.write(row)
            if row['state']=='uncertain':self.blocked=True

    def write(self,row):
        target=self.state/(row['id']+'.json');temporary=target.with_suffix('.tmp')
        fd=os.open(temporary,os.O_CREAT|os.O_TRUNC|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(row,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
        fd=os.open(self.state,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)

    def identity(self):
        uid=int((self.root/'secrets/allowed-users').read_text().splitlines()[0])
        return {'user_id':uid,'chat_id':uid}

    def prepare(self,action,actor):
        if (self.state.parent/'maintenance').exists():return {'ok':False,'code':'busy'}
        allowed=isinstance(action,str) and (action in ACTIONS or (action.startswith('install_') and valid_package(action.removeprefix('install_'))))
        if not allowed or self.blocked:return {'ok':False,'code':'action_locked' if self.blocked else 'unsupported'}
        if not self.lock.acquire(blocking=False):return {'ok':False,'code':'busy'}
        try:
            # No new operation while another web grant remains live.
            rows=[json.loads(p.read_text()) for p in self.state.glob('*.json')]
            if any(r['state']=='pending' and r['expires']>time.time() and r.get('mono_expires',0)>time.monotonic() for r in rows):return {'ok':False,'code':'busy'}
            if action=='server_restart':
                if any(r['action']=='server_restart' and r['state']=='scheduled' and time.time()-r['created_at']<300 for r in rows):return {'ok':False,'code':'cooldown'}
                if self.guard:
                    try:self.guard()
                    except Exception:return {'ok':False,'code':'action_locked'}
            row={'id':secrets.token_hex(16),'actor':actor,'action':action,'expires':time.time()+120,'mono_expires':time.monotonic()+120,'state':'pending','created_at':time.time()}
            ident=self.identity()
            row['identity']=ident
            if action.startswith('install_'):
                packet={'op':'new',**ident,'message_id':secrets.randbelow(2**52)+1,'package':action.removeprefix('install_')}
                response=self.rpc(PKG,packet)
                if response.get('result')=='installed':return {'ok':True,'state':'installed','action':action}
                if not response.get('ok') or not re.fullmatch('[a-f0-9]{32}',response.get('token','')):return {'ok':False,'code':response.get('result','unavailable')}
                changes=[]
                for line in response.get('changes',[]):
                    match=re.match(r'^Inst (\S+) (?:\[[^\]]+\] )?\(([^\s()]+)',line)
                    if match:changes.append(match[1]+'='+match[2])
                row.update(upstream=response['token'],message=packet['message_id'],plan={'versions':changes})
            elif action in {'raid_monitor_start','uebung_neustart'}:
                response=self.rpc(EXEC,{'op':'new',**ident,'action':'repair_mdmonitor' if action=='raid_monitor_start' else 'practice_restart'})
                if not response.get('ok') or not re.fullmatch('[a-f0-9]{32}',response.get('token','')):return {'ok':False,'code':'unavailable'}
                message=secrets.randbelow(2**52)+1
                bound=self.rpc(EXEC,{'op':'bind',**ident,'token':response['token'],'message_id':message})
                if not bound.get('ok'):return {'ok':False,'code':'unavailable'}
                row.update(upstream=response['token'],message=message)
            self.write(row)
            return {'ok':True,'state':'pending','id':row['id'],'action':action,'expires':row['expires'],'versions':row.get('plan',{}).get('versions',[])}
        finally:self.lock.release()

    def handle(self,packet):
        op=packet.get('op')
        pending=(self.root/'pending-setup').exists()
        if packet=={'op':'web_status'}:
            data=self.telemetry.read()
            return {'ok':True,'data':data,'control_available':not pending,'setup_required':pending,'server_clock':{'timestamp':time.time(),'timezone':data.get('server_timezone','UTC')}}
        if pending:return {'ok':False,'code':'setup_required'}
        if packet=={'op':'web_activity'}:
            from web_activity import collect
            from config_broker import COMPOSE
            return {'ok':True,'data':collect(self.root,self.state,COMPOSE)}
        actor=packet.get('actor')
        if not isinstance(actor,str) or re.fullmatch('[a-f0-9]{64}',actor) is None:return {'ok':False,'code':'schema'}
        if op=='web_prepare' and set(packet)=={'op','actor','action'}:return self.prepare(packet['action'],actor)
        if op=='web_read' and set(packet)=={'op','actor','command'}:
            ident=self.identity();command=packet['command']
            if command=='automatik_status':
                reply=self.rpc(EXEC,{'op':'auto_overview',**ident})
                if not reply.get('ok'):return {'ok':False,'code':'unavailable'}
                return {'ok':True,'data':{key:reply.get(key) for key in ('enabled','available','unhealthy','manual_required','attempts_24h','limit_24h','hourly_seconds','daily_seconds','shared_seconds','earliest_seconds','observation_seconds','notifications_pending','history')}}
            if command=='ki_install_status':
                data=self.rpc(PKG,{'op':'status',**ident,'message_id':1})
                if not data.get('ok'):return {'ok':False,'code':'unavailable'}
                data['version']=(data.get('version') or '').removeprefix('install ok installed ')
                return {'ok':True,'data':data}
            return {'ok':False,'code':'schema'}
        if op not in {'web_decide','web_job'} or set(packet)!=({'op','actor','id','confirm'} if op=='web_decide' else {'op','actor','id'}):return {'ok':False,'code':'schema'}
        job=packet['id']
        if not isinstance(job,str) or re.fullmatch('[a-f0-9]{32}',job) is None:return {'ok':False,'code':'schema'}
        path=self.state/(job+'.json')
        if not path.is_file():return {'ok':False,'code':'unknown_job'}
        row=json.loads(path.read_text())
        if row['actor']!=actor:return {'ok':False,'code':'denied'}
        if op=='web_job':return {'ok':True,'state':'uncertain' if self.blocked and row['state']=='running' else row['state'],'action':row['action'],'result':row.get('result',{}),'created_at':row['created_at']}
        if type(packet['confirm']) is not bool:return {'ok':False,'code':'schema'}
        if row['state']!='pending':return {'ok':False,'code':'already'}
        if row['expires']<=time.time() or row.get('mono_expires',0)<=time.monotonic():row['state']='expired';self.write(row);return {'ok':False,'code':'expired'}
        if not packet['confirm']:
            row['state']='cancelled';self.write(row)
            if row.get('upstream'):self.rpc(PKG if row['action'].startswith('install_') else EXEC,{'op':'cancel',**row['identity'],'message_id':row['message'],'token':row['upstream']})
            return {'ok':True,'state':'cancelled'}
        if (self.state.parent/'maintenance').exists():return {'ok':False,'code':'busy'}
        if not self.lock.acquire(blocking=False):return {'ok':False,'code':'busy'}
        try:
            # Consume durably before any process/RPC; failure here executes nothing.
            row['state']='running';self.write(row)
            def execute():
                try:
                    action=row['action']
                    if action=='server_restart':
                        if self.guard:self.guard()
                        subprocess.run(['/usr/bin/systemd-run','--unit=kiagent-web-reboot-'+row['id'],'--on-active=10s','/usr/bin/systemctl','reboot'],capture_output=True,timeout=10,check=True)
                        result={'ok':True,'result':'scheduled'}
                    elif action=='testaktion':result={'ok':True,'result':'success'}
                    elif action in {'automatik_an','automatik_aus'}:result=self.rpc(EXEC,{'op':'auto_control',**row['identity'],'enabled':action=='automatik_an'})
                    else:
                        packet={'op':'confirm',**row['identity'],'token':row['upstream'],'message_id':row['message']}
                        result=self.rpc(PKG if action.startswith('install_') else EXEC,packet)
                        if action.startswith('install_'):
                            deadline=time.monotonic()+1800
                            while result.get('result') in {'started','checking'} and time.monotonic()<deadline:
                                time.sleep(self.poll_seconds)
                                result=self.rpc(PKG,{**packet,'op':'result'})
                            if result.get('result') in {'started','checking'}:result={'ok':False,'result':'uncertain'}
                    code=result.get('result','success' if result.get('ok') else 'uncertain')
                    row['result']={k:result[k] for k in ('result','retry_after','version','package','enabled') if k in result}
                    if 'version' in row['result']:row['result']['version']=row['result']['version'].removeprefix('install ok installed ')
                    row['state']='scheduled' if code=='scheduled' else 'success' if result.get('ok') else 'uncertain' if code in {'uncertain','unverified','rejected_or_uncertain'} else 'failed'
                except Exception:row['state']='uncertain'
                finally:
                    if row['state']=='uncertain':self.blocked=True
                    try:self.write(row)
                    except Exception:
                        self.blocked=True
                        print(json.dumps({'event':'web_audit_failed','action':row['action']}),flush=True)
                    finally:self.lock.release()
            try:threading.Thread(target=execute,daemon=False).start()
            except Exception:
                row['state']='uncertain';self.blocked=True;self.write(row);raise
            return {'ok':True,'state':'running','id':job}
        except Exception:
            if self.lock.locked():self.lock.release()
            raise
