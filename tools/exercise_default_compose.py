"""Disposable CI: the exact plain Compose command, TLS readiness, and no-update restart."""
import hashlib
import json
import os
import re
import socket
import ssl
import subprocess
import time
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
    try:
        run('docker','compose','up','-d',env=environment,timeout=600)
        wait_setup()
        result=json.loads((ROOT/'.installation/status.json').read_text());assert result['state']=='ready'
        assert result['url']=='https://8.8.8.8:9443/setup',result
        assert (ROOT/'.installation/WEBADRESSE.txt').read_text().strip()==result['url']
        assert (Path('/etc/kiagent-docker/first-install-owner').read_text())==(ROOT/'.installation/owner').read_text()
        for name in ('telegram-token','discord-token','openai-api-key','hc-bot','hc-server'):
            assert not (Path('/etc/kiagent-docker/secrets')/name).read_bytes().strip()
        context=ssl.create_default_context(cafile=str(cert))
        with socket.create_connection(('127.0.0.1',9443),timeout=10) as raw:
            with context.wrap_socket(raw,server_hostname='8.8.8.8') as connection:
                connection.sendall(b'GET /health HTTP/1.1\r\nHost: 8.8.8.8:9443\r\nConnection: close\r\n\r\n')
                response=connection.makefile('rb').read()
        assert b'200 OK' in response and b'"ok":true' in response
        paths=[Path('/opt/kiagent-docker/project/compose.yaml'),Path('/etc/kiagent-docker/deployment.env'),cert,key]
        before=[hashlib.sha256(path.read_bytes()).digest() for path in paths]
        run('docker','compose','up','-d',env=environment,timeout=60);wait_setup()
        assert before==[hashlib.sha256(path.read_bytes()).digest() for path in paths]
        print('Plain docker compose up -d: first installation, trusted TLS, URL file, empty provider keys, repeat without update: OK')
    finally:
        subprocess.run(['systemctl','disable','--now','kiagent-docker','kiagent-config','kiagent-executor','kiagent-packages','kiagent-tls-sync.timer'],capture_output=True,timeout=120)
        subprocess.run(['docker','compose','down'],cwd=ROOT,capture_output=True,timeout=60)
        trust.unlink(missing_ok=True);run('update-ca-certificates',capture_output=True)

if __name__=='__main__':main()
