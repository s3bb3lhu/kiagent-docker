"""Disposable CI: the exact plain Compose command, TLS readiness, and no-update restart."""
import hashlib
import json
import os
import re
import socket
import ssl
import subprocess
import time
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def run(*args,**kwargs):return subprocess.run(args,check=True,cwd=ROOT,**kwargs)

def wait_setup():
    identifier=subprocess.check_output(['docker','compose','ps','-a','-q','setup'],cwd=ROOT,text=True).strip()
    if not identifier:raise AssertionError('Setup container missing')
    deadline=time.monotonic()+600
    while time.monotonic()<deadline:
        state=json.loads(subprocess.check_output(['docker','inspect','--format','{{json .State}}',identifier],text=True))
        if state['Status']=='exited':
            if state['ExitCode']!=0:
                # Export exception class names only, never log text, paths or environment.
                logs=subprocess.check_output(['docker','logs',identifier],text=True,stderr=subprocess.STDOUT)
                classes=sorted(set(re.findall(r'^([A-Za-z]+Error|SystemExit):',logs,re.MULTILINE)))
                raise AssertionError({'setup_exit_code':state['ExitCode'],'exception_classes':classes})
            return
        time.sleep(2)
    raise AssertionError('Setup did not finish')

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.geteuid()!=0:raise SystemExit('Disposable CI root only.')
    if Path('/etc/kiagent-docker').exists() or Path('/opt/kiagent-docker').exists():raise SystemExit('Fresh CI host required.')
    root=Path('/etc/letsencrypt/live/kiagent-ci-first');root.mkdir(parents=True,mode=0o755)
    cert=root/'fullchain.pem';key=root/'privkey.pem'
    run('openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','3','-subj','/CN=CI first install only','-addext','subjectAltName=IP:8.8.8.8','-addext','basicConstraints=critical,CA:TRUE','-keyout',str(key),'-out',str(cert),capture_output=True)
    trust=Path('/usr/local/share/ca-certificates/kiagent-first-ci.crt');trust.write_bytes(cert.read_bytes());trust.chmod(0o644)
    run('update-ca-certificates',capture_output=True)
    environment={**os.environ,'SSH_CONNECTION':'203.0.113.5 55000 8.8.8.8 22'}
    from ollama_ci_fixture import Fixture
    ollama=Fixture()
    try:
        run('docker','compose','up','-d',env=environment,timeout=600)
        wait_setup()
        result=json.loads((ROOT/'.installation/status.json').read_text());assert result['state']=='ready'
        assert result['url']=='https://8.8.8.8:9443/setup',result
        assert (ROOT/'.installation/WEBADRESSE.txt').read_text().strip()==result['url']
        version=json.loads((ROOT/'.installation/version.json').read_text())
        assert version['channel']=='stable' and version['version']==Path('/opt/kiagent-docker/project/VERSION').read_text().strip()
        assert version==json.loads(Path('/opt/kiagent-docker/project/release-source.json').read_text())
        assert (Path('/etc/kiagent-docker/first-install-owner').read_text())==(ROOT/'.installation/owner').read_text()
        for name in ('telegram-token','discord-token','openai-api-key','hc-bot','hc-server'):
            assert not (Path('/etc/kiagent-docker/secrets')/name).read_bytes().strip()
        context=ssl.create_default_context(cafile=str(cert))
        with socket.create_connection(('127.0.0.1',9443),timeout=10) as raw:
            with context.wrap_socket(raw,server_hostname='8.8.8.8') as connection:
                connection.sendall(b'GET /health HTTP/1.1\r\nHost: 8.8.8.8:9443\r\nConnection: close\r\n\r\n')
                response=connection.makefile('rb').read()
        assert b'200 OK' in response and b'"ok":true' in response
        paths=[Path('/opt/kiagent-docker/project/compose.yaml'),Path('/etc/kiagent-docker/deployment.env'),ROOT/'.installation/version.json',cert,key]
        before=[hashlib.sha256(path.read_bytes()).digest() for path in paths]
        run('docker','compose','up','-d',env=environment,timeout=60);wait_setup()
        assert before==[hashlib.sha256(path.read_bytes()).digest() for path in paths]
        print('Plain docker compose up -d: latest published stable release, trusted TLS, URL/version files, empty provider keys, repeat without update: OK')
        # Explicitly activate new frontend code on this disposable host, preserving its port/history.
        run('/usr/bin/python3','-I','-B',str(ROOT/'tools/activate_ollama.py'),timeout=900)
        sys.path.insert(0,str(ROOT/'src/app'))
        from ai_socket import request
        info=request({'op':'info'});assert info['provider']=='ollama' and info['ready'] and info['managed'] is False
        result=request({'op':'generate','instructions':'Fixture','input':'Read-only question','schema':None,'max_tokens':512},timeout=20)
        assert 'Local CI answer' in result['text']
        ollama.verify()
        assert subprocess.run(['docker','container','inspect','server-control-ollama'],capture_output=True).returncode!=0
        print('Ollama: existing API preserved, no model pull or new Ollama container, unprivileged gateway, local completion without API key, explicit activation: OK')
    finally:
        subprocess.run(['systemctl','disable','--now','kiagent-docker','kiagent-config','kiagent-executor','kiagent-packages','kiagent-tls-sync.timer','kiagent-ai'],capture_output=True,timeout=120)
        subprocess.run(['docker','compose','down'],cwd=ROOT,capture_output=True,timeout=60)
        ollama.close()
        trust.unlink(missing_ok=True);run('update-ca-certificates',capture_output=True)

if __name__=='__main__':main()
