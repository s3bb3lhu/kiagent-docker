#!/usr/bin/env python3
"""Disposable portable image smoke test: first setup, cookies and restart persistence."""
import subprocess
import time
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def run(*args,**kwargs):return subprocess.run(args,check=True,timeout=600,**kwargs)

CHECK=r'''
import http.cookiejar,json,re,urllib.request,urllib.parse,sys
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def get(path,data=None):
 headers={'Host':'127.0.0.1:8787'}
 if data is not None:headers['Origin']='http://127.0.0.1:8787'
 req=urllib.request.Request('http://127.0.0.1:8080'+path,data=urllib.parse.urlencode(data).encode() if data else None,headers=headers)
 return opener.open(req,timeout=5)
phase=sys.argv[1]
if phase=='setup':
 page=get('/setup').read().decode()
 assert 'name="code"' not in page
 token=re.search(r'name="csrf" value="([^"]+)"',page)[1]
 get('/setup',{'csrf':token,'password':'Fixture1!','repeat':'Fixture1!'})
else:
 page=get('/login').read().decode()
 assert 'name="repeat"' not in page
 token=re.search(r'name="csrf" value="([^"]+)"',page)[1]
 get('/login',{'csrf':token,'password':'Fixture1!'})
view=json.load(get('/api/overview'))
assert view['ok'] and 'capability_notice' in view and not any(view['configured'].values())
print('Portable '+phase+': OK')
'''

def main():
    name='kiagent-portable-test-'+uuid.uuid4().hex[:12]
    volume=name+'-state'
    run('docker','build','-f',str(ROOT/'Dockerfile.portable'),'-t','kiagent-portal:review',str(ROOT))
    try:
        run('docker','run','-d','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,noexec,nosuid,size=16m,mode=1777','-e','CONFIG_SETUP_LOCAL_ONLY=1','-e','CONFIG_ORIGIN=http://127.0.0.1:8787','-v',volume+':/var/lib/kiagent-web','kiagent-portal:review')
        for phase in ('setup','restart'):
            if phase=='restart':run('docker','restart',name)
            for _ in range(40):
                probe=subprocess.run(['docker','exec',name,'python','-B','/app/config_web_health.py'],capture_output=True,timeout=10)
                if probe.returncode==0:break
                time.sleep(.5)
            else:raise RuntimeError('Portable container did not become healthy')
            run('docker','exec',name,'python','-B','-c',CHECK,phase)
        print('Portable image: first setup without code, login and durable restart: OK')
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=30)
        subprocess.run(['docker','volume','rm',volume],capture_output=True,timeout=30)

if __name__=='__main__':main()
