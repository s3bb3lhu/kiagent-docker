#!/usr/bin/env python3
"""Disposable portable image smoke test: first setup, cookies and restart persistence."""
import subprocess
import json
import tempfile
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
 get('/setup',{'csrf':token,'username':'admin','password':'Fixture1!','repeat':'Fixture1!'})
else:
 page=get('/login').read().decode()
 assert 'name="repeat"' not in page
 token=re.search(r'name="csrf" value="([^"]+)"',page)[1]
 get('/login',{'csrf':token,'username':'admin','password':'Fixture1!'})
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
    # Exercise the actual parsed Compose mounts, not a separately handwritten docker run.
    for source in ('compose.quickstart.yaml','compose.portable.yaml'):
        project='kiagent-compose-test-'+uuid.uuid4().hex[:12]
        model=json.loads(subprocess.check_output(['docker','compose','-f',str(ROOT/source),'config','--format','json'],text=True))
        mounts=model['services']['web']['tmpfs']
        assert mounts==['/tmp:rw,noexec,nosuid,size=16m,mode=1777'], 'Unexpected split tmpfs mounts'
        model.pop('name',None)
        web=model['services']['web'];web['ports']=[];web['image']='kiagent-portal:review';web.pop('build',None)
        for value in model.get('volumes',{}).values():
            value.pop('name',None)
            assert not value.get('external'), 'Tests require disposable private volumes'
        for value in model.get('networks',{}).values():
            value.pop('name',None)
            assert not value.get('external'), 'Tests require disposable private networks'
        with tempfile.TemporaryDirectory(prefix='kiagent-compose-test-') as directory:
            config=Path(directory)/'compose.json';config.write_text(json.dumps(model))
            compose=['docker','compose','-p',project,'-f',str(config)]
            try:
                run(*compose,'up','-d','--no-build','--wait','--wait-timeout','60')
                container=subprocess.check_output(compose+['ps','-q','web'],text=True).strip()
                assert container
                run('docker','exec',container,'python','-B','-c',CHECK,'setup')
                run(*compose,'restart','web')
                for _ in range(40):
                    probe=subprocess.run(['docker','exec',container,'python','-B','/app/config_web_health.py'],capture_output=True,timeout=10)
                    if probe.returncode==0:break
                    time.sleep(.5)
                else:raise RuntimeError('Compose container did not become healthy')
                run('docker','exec',container,'python','-B','-c',CHECK,'restart')
                print(source+': actual mounts, first setup and restart: OK')
            finally:
                subprocess.run(compose+['down','--volumes'],capture_output=True,timeout=60)

if __name__=='__main__':main()
