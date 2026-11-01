"""Unprivileged, peer-authenticated Ollama bridge. One inference at a time."""
import concurrent.futures
import ipaddress
import json
import os
import pwd
import re
import socket
import struct
import threading
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path('/etc/kiagent-ai')
SOCKET=Path('/run/kiagent-ai/control.sock')
MODEL=re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,100}')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def http(endpoint,path,data=None,timeout=3):
    parsed=urlsplit(endpoint)
    address=ipaddress.ip_address(parsed.hostname)
    if parsed.scheme!='http' or not (address.is_loopback or address.is_private) or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or not 0<(parsed.port or 0)<65536:raise ValueError('Invalid local Ollama endpoint')
    if path not in ('/api/version','/api/tags','/api/ps','/api/chat'):raise ValueError('Unsupported Ollama operation')
    request=urllib.request.Request(endpoint+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(request,timeout=timeout) as response:
        raw=response.read(1048577)
        if len(raw)>1048576:raise ValueError('Ollama response too large')
        return json.loads(raw)

def models(data):
    result=[]
    for row in data.get('models',[])[:100]:
        name=row.get('name','');details=row.get('details',{})
        if not isinstance(name,str) or not MODEL.fullmatch(name) or 'cloud' in name.lower() or 'embed' in name.lower() or row.get('remote_host') or row.get('remote_model'):continue
        if details.get('family') in {'bert','nomic-bert','clip'}:continue
        size=row.get('size',0)
        if not isinstance(size,(int,float)) or size<0:continue
        result.append({'name':name,'size':size})
    return sorted(result,key=lambda row:(row['size'],row['name']))

def read(path,owner=0):
    info=path.lstat()
    if not path.is_file() or path.is_symlink() or info.st_uid!=owner or info.st_mode & 0o022 or info.st_size>16384:raise ValueError('Invalid AI configuration')
    return json.loads(path.read_text())

class Gateway:
    def __init__(self,root=ROOT,call=http):
        self.root=root;self.call=call;self.inference=threading.Lock()
        self.provider=Path('/var/lib/kiagent-ai/provider.json') if root==ROOT else root/'provider.json'
    def info(self):
        state=read(self.root/'server.json');selected=read(self.provider,owner=os.getuid())
        available=[];ready=False
        if state.get('endpoint'):
            try:available=models(self.call(state['endpoint'],'/api/tags'));ready=any(row['name']==selected.get('model') for row in available)
            except Exception:pass
        return {'ok':True,'provider':selected.get('provider','openai'),'model':selected.get('model',''),
                'ready':ready,'models':[row['name'] for row in available],'managed':state.get('managed',False),
                'limits':state.get('limits',{}),'state':state.get('state','unavailable'),'note':state.get('note',''),
                'managed_model':state.get('limits',{}).get('model','')}
    def handle(self,request,uid=None):
        if request=={'op':'info'}:return self.info()
        if request=={'op':'route'}:
            selected=read(self.provider,owner=os.getuid())
            if selected.get('provider') not in ('openai','ollama'):raise ValueError('Invalid AI provider')
            return {'ok':True,'provider':selected['provider'],'model':selected.get('model','')}
        if isinstance(request,dict) and request.get('op')=='select':
            if uid!=0 or set(request)!={'op','provider','model'} or request['provider'] not in {'openai','ollama'}:raise ValueError('Invalid provider selection')
            info=self.info();model=request['model']
            if not isinstance(model,str) or request['provider']=='ollama' and (model not in info['models'] or info['managed'] and model!=info['managed_model']):raise ValueError('Unavailable model')
            fd,temporary=tempfile.mkstemp(prefix='.provider-',dir=self.provider.parent)
            try:
                with os.fdopen(fd,'w') as stream:
                    json.dump({'provider':request['provider'],'model':model if request['provider']=='ollama' else info['model']},stream)
                    stream.flush();os.fchmod(stream.fileno(),0o600);os.fsync(stream.fileno())
                os.replace(temporary,self.provider)
            finally:Path(temporary).unlink(missing_ok=True)
            return self.info()
        if not isinstance(request,dict) or set(request)!={'op','instructions','input','schema','max_tokens'} or request['op']!='generate':raise ValueError('Invalid AI request')
        if not isinstance(request['instructions'],str) or len(request['instructions'])>8000 or not isinstance(request['input'],str) or len(request['input'])>16000:raise ValueError('Invalid AI input')
        if not isinstance(request['max_tokens'],int) or not 1<=request['max_tokens']<=1200 or request['schema'] is not None and (not isinstance(request['schema'],dict) or len(json.dumps(request['schema']))>8000):raise ValueError('Invalid AI output options')
        if not self.inference.acquire(blocking=False):return {'ok':False,'code':'ai_busy'}
        try:
            state=read(self.root/'server.json');selected=read(self.provider,owner=os.getuid())
            if selected.get('provider')!='ollama' or not selected.get('model') or not state.get('endpoint'):return {'ok':False,'code':'ai_unavailable'}
            body={'model':selected['model'],'stream':False,'think':False,'messages':[{'role':'system','content':request['instructions']},{'role':'user','content':request['input']}],
                  'options':{'num_ctx':2048,'num_predict':min(512,request['max_tokens']),'temperature':0.2}}
            if request['schema'] is not None:body['format']=request['schema']
            if state.get('managed'):
                body['keep_alive']='30s';body['options']['num_thread']=state.get('limits',{}).get('threads',1)
                body['options']['num_predict']=min(body['options']['num_predict'],state.get('limits',{}).get('max_tokens',512))
            response=self.call(state['endpoint'],'/api/chat',body,timeout=75)
            text=response.get('message',{}).get('content','')
            if response.get('done') is not True or not isinstance(text,str) or not text.strip():raise ValueError('Incomplete Ollama answer')
            return {'ok':True,'text':text.strip()[:12000]}
        finally:self.inference.release()

def main():
    gateway=Gateway();allowed={0,pwd.getpwnam('kiagent').pw_uid,pwd.getpwnam('kiagent-discord').pw_uid}
    connections=threading.BoundedSemaphore(4)
    def handle(connection):
        try:
            with connection:
                connection.settimeout(5)
                uid=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]
                if uid not in allowed:return
                raw=bytearray()
                while b'\n' not in raw:
                    chunk=connection.recv(4096)
                    if not chunk or len(raw)+len(chunk)>32768:return
                    raw.extend(chunk)
                try:result=gateway.handle(json.loads(raw),uid)
                except Exception:result={'ok':False,'code':'ai_unavailable'}
                connection.sendall(json.dumps(result).encode()+b'\n')
        except OSError:pass
        finally:connections.release()
    SOCKET.unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX) as server,concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        server.bind(str(SOCKET));SOCKET.chmod(0o666);server.listen(8)
        while True:
            connection,_=server.accept()
            if connections.acquire(blocking=False):pool.submit(handle,connection)
            else:connection.close()

if __name__=='__main__':main()
