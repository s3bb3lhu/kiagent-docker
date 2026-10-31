#!/usr/bin/env python3
"""Build and isolate tests. Never installs host agents or starts live bots."""
import grp
import json
import os
import pwd
import socket
import struct
import subprocess
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'kiagent:review'

def run(*args, **kwargs):
    return subprocess.run(args,check=True,timeout=900,**kwargs)

def main():
    if os.geteuid() != 0:
        raise SystemExit('Docker-Test benoetigt sudo; keine produktiven Dienste werden veraendert.')
    run('/usr/bin/python3',str(ROOT/'tools/scan_secrets.py'))
    security = subprocess.check_output(['/usr/bin/docker','info','--format','{{json .SecurityOptions}}'],text=True)
    if 'rootless' in security or 'userns' in security:
        raise SystemExit('Dieser Transporttest ist fuer Docker ohne UID-Remapping.')
    run('/usr/bin/docker','build','-t',IMAGE,str(ROOT))
    run('/usr/bin/docker','run','--rm','--network','none','--read-only','--cap-drop','ALL',
        '--security-opt','no-new-privileges','--tmpfs','/tmp:rw,mode=1777',
        '-v',str(ROOT)+':/workspace:ro','-w','/workspace','--entrypoint','python',
        IMAGE,'-B','-m','unittest','discover','-s','tests','-v')
    uid = pwd.getpwnam('kiagent').pw_uid
    gid = grp.getgrnam('kiagent').gr_gid
    fixture = {'cpu_count':17,'ram_total_mib':64000,'ram_available_mib':63000,
               'root_disk_total_gib':3600,'root_disk_used_percent':1,'uptime_seconds':100,
               'raid':{},'raid_status':'fixture','failed_services':{'available':True,'units':[]},
               'load_1_5_15_minutes':[0,0,0]}
    with tempfile.TemporaryDirectory(prefix='kiagent-docker-test-') as temporary:
        base = Path(temporary)
        directory = base/'socket'
        directory.mkdir()
        os.chown(directory,0,gid)
        directory.chmod(0o750)
        key = base/'fixture-key'
        key.write_text('test-fixture-only')
        os.chown(key,0,gid)
        key.chmod(0o440)
        result = {}
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(str(directory/'control.sock'))
            os.chown(directory/'control.sock',0,gid)
            os.chmod(directory/'control.sock',0o660)
            listener.listen(1)
            listener.settimeout(40)
            def respond():
                try:
                    connection,_ = listener.accept()
                    with connection:
                        connection.settimeout(10)
                        _,actual_uid,_ = struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                        request = connection.recv(4096)
                        assert actual_uid == uid
                        assert json.loads(request) == {'op':'metrics'}
                        result['peer_uid_preserved'] = True
                        connection.sendall(json.dumps({'ok':True,'kind':'host_metrics_v1','data':fixture}).encode()+b'\n')
                except BaseException as error:
                    result['error'] = type(error).__name__
            worker = threading.Thread(target=respond,daemon=True)
            worker.start()
            code = "from host_metrics_client import snapshot; from pathlib import Path; assert snapshot()['cpu_count']==17; assert Path('/run/secrets/example-key').read_text()=='test-fixture-only'; print('Host-UID, Socket-Mount und Secret-Dateirechte: OK')"
            run('/usr/bin/docker','run','--rm','--network','none','--read-only','--cap-drop','ALL',
                '--security-opt','no-new-privileges','--user',f'{uid}:{gid}',
                '-v',str(directory)+':/run/kiagent-executor:ro','-v',str(key)+':/run/secrets/example-key:ro',
                '--entrypoint','python',IMAGE,'-B','-c',code)
            worker.join(2)
            if result != {'peer_uid_preserved':True}:
                raise ValueError('Transporttest fehlgeschlagen')
        env = base/'deployment.env'
        secrets = base/'secrets'
        secrets.mkdir()
        for name in ('telegram-token','discord-token','openai-api-key','allowed-users','discord-access.json','hc-bot','hc-server'):
            (secrets/name).write_text('fixture')
        env.write_text(f'KIAGENT_UID={uid}\nKIAGENT_GID={gid}\nDISCORD_UID={uid+1}\nDISCORD_APPLICATION_ID=90\nKIAGENT_SECRETS_DIR={secrets}\n')
        run('/usr/bin/docker','compose','--env-file',str(env),'-f',str(ROOT/'compose.yaml'),'config','--quiet')
    image = subprocess.check_output(['/usr/bin/docker','image','inspect',IMAGE,'--format','{{.Id}}'],text=True).strip()
    print(json.dumps({'result':'success','image':image,'unit_tests':True,'peer_uid_preserved':True,
                     'host_metrics_adapter':True,'secret_file_permissions':True,'compose_valid':True,
                     'live_bots_started':False,'host_services_changed':False},indent=2))

if __name__ == '__main__':
    main()
