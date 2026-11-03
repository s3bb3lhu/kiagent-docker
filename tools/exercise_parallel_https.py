"""Disposable CI only: real TLS alongside an unrelated listener, with fixture certificates."""
import hashlib
import os
import socket
import ssl
import subprocess
import tempfile
from pathlib import Path
import parallel_https as tls

def exercise():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.geteuid()!=0:raise RuntimeError('Only disposable CI host.')
    trust=Path('/usr/local/share/ca-certificates/kiagent-parallel-ci.crt')
    if trust.exists():raise RuntimeError('Fixture trust file already exists.')
    with tempfile.TemporaryDirectory(prefix='kiagent-tls-ci-',dir='/var/lib') as directory,socket.socket() as existing:
        root=Path(directory);root.chmod(0o700)
        live=root/'live/fixture';live.mkdir(parents=True)
        cert=live/'fullchain.pem';key=live/'privkey.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','3','-subj','/CN=CI only','-addext','subjectAltName=IP:8.8.8.8','-addext','basicConstraints=critical,CA:TRUE','-keyout',str(key),'-out',str(cert)],check=True,capture_output=True)
        trust.write_bytes(cert.read_bytes());trust.chmod(0o644)
        try:
            subprocess.run(['update-ca-certificates'],check=True,capture_output=True)
            source={'root':str(root),'certificate':'live/fixture/fullchain.pem','key':'live/fixture/privkey.pem'}
            before=[hashlib.sha256(p.read_bytes()).digest() for p in (cert,key)]
            existing.bind(('0.0.0.0',9443));existing.listen()
            port=tls.free_port(9443);assert port!=9443
            # Reproduce an unreachable inherited cwd without touching any existing service.
            previous=os.open('.',os.O_RDONLY)
            vanished=root/'vanished';vanished.mkdir();os.chdir(vanished);vanished.rmdir()
            try:tls.configure('8.8.8.8','127.0.0.1',port,8787,source)
            finally:os.fchdir(previous);os.close(previous)
            context=ssl.create_default_context(cafile=str(cert))
            with socket.create_connection(('127.0.0.1',port),timeout=10) as raw:
                with context.wrap_socket(raw,server_hostname='8.8.8.8') as connection:
                    connection.sendall(('GET /login HTTP/1.1\r\nHost: 8.8.8.8:'+str(port)+'\r\nConnection: close\r\n\r\n').encode())
                    response=b''
                    while True:
                        chunk=connection.recv(4096)
                        if not chunk:break
                        response+=chunk
            assert response.startswith(b'HTTP/1.1 200'),response[:100]
            assert b'name="password"' in response and b'Secure' in response
            assert before==[hashlib.sha256(p.read_bytes()).digest() for p in (cert,key)]
            assert existing.getsockname()[1]==9443
            assert subprocess.check_output(['systemctl','is-active','kiagent-tls-sync.timer'],text=True).strip()=='active'
            print('Parallel HTTPS: occupied port preserved, valid TLS login, original certificate files unchanged, renewal timer active: OK')
            from exercise_services_compose import exercise as exercise_services
            exercise_services(source,cert,port)
        finally:
            subprocess.run(['systemctl','disable','--now','kiagent-services-tls.timer','kiagent-services-agent'],capture_output=True)
            subprocess.run(['systemctl','disable','--now','kiagent-tls-sync.timer'],capture_output=True)
            trust.unlink(missing_ok=True)
            subprocess.run(['update-ca-certificates'],capture_output=True)
