"""Detect without modifying existing Ollama; provision a bounded private instance if absent."""
import argparse
import fcntl
import json
import math
import os
import pwd
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
HERE=Path(__file__).resolve()
REPO=HERE.parents[1] if HERE.parent.name=='tools' else None
if REPO:sys.path.insert(0,str(REPO/'host'))
from ai_gateway import http,models
STATE=Path('/etc/kiagent-ai')
LIB=Path('/usr/local/lib/kiagent-ai')
PROJECT=Path('/opt/kiagent-docker/project')
NAME='server-control-ollama'

def run(args,**options):return subprocess.run(args,check=True,stdin=subprocess.DEVNULL,timeout=options.pop('timeout',120),**options)
def output(args):return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL,timeout=30)

def atomic(path,data,mode=0o644):
    path.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
    if path.is_symlink():raise ValueError('Symlink in AI installation')
    if path.is_file() and path.read_bytes()==data:return
    fd,temporary=tempfile.mkstemp(prefix='.ai-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fchmod(stream.fileno(),mode);os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:Path(temporary).unlink(missing_ok=True)

def budget(total,available,cpus,disk_free):
    memory=min(4096,total//4,available//2,max(0,available-2048))
    if memory<1536 or cpus<1 or disk_free<20*1024**3:return None
    return {'memory_mib':memory,'cpus':max(.25,min(2,cpus*.25)),'threads':max(1,min(2,math.ceil(cpus*.25))),
            'model':'qwen3:1.7b' if memory>=3072 else 'qwen3:0.6b','parallel':1,'context':2048,'max_tokens':192 if cpus<4 else 384 if cpus<8 else 512,'keep_alive':'30s'}

def probe(endpoint):
    try:
        version=http(endpoint,'/api/version')
        if not isinstance(version.get('version'),str):return None
        return models(http(endpoint,'/api/tags'))
    except Exception:return None

def existing():
    local='http://127.0.0.1:11434';found=probe(local)
    containers=output(['/usr/bin/docker','ps','-a','--format','{{.ID}} {{.Image}} {{.Names}}']).splitlines()
    candidates=[]
    for row in containers:
        fields=row.split()
        if len(fields)!=3:continue
        if 'ollama' in row.lower():candidates.append(fields)
        else:
            exposed=json.loads(output(['/usr/bin/docker','inspect','--format','{{json .Config.ExposedPorts}}',fields[0]])) or {}
            if '11434/tcp' in exposed:candidates.append(fields)
    managed=False
    for identifier,image,name in candidates:
        if name==NAME:
            running=output(['/usr/bin/docker','inspect','--format','{{.State.Running}}',identifier]).strip()=='true'
            managed=running and output(['/usr/bin/docker','inspect','--format','{{index .Config.Labels "io.server-control.ollama"}}',identifier]).strip()=='1'
            if found is not None:return {'endpoint':local,'models':found,'managed':managed,'state':'existing','note':'managed_ollama' if managed else 'existing_unchanged'}
    if found is not None:return {'endpoint':local,'models':found,'managed':False,'state':'existing','note':'existing_unchanged'}
    for identifier,image,name in candidates:
        network=json.loads(output(['/usr/bin/docker','inspect','--format','{{json .NetworkSettings}}',identifier]))
        endpoints=[]
        for binding in (network.get('Ports') or {}).get('11434/tcp') or []:
            if binding.get('HostIp') in ('127.0.0.1','0.0.0.0','') and binding.get('HostPort','').isdigit():endpoints.append('http://127.0.0.1:'+binding['HostPort'])
        for details in (network.get('Networks') or {}).values():
            if details.get('IPAddress'):endpoints.append('http://'+details['IPAddress']+':11434')
        for endpoint in endpoints:
            found=probe(endpoint)
            if found is not None:return {'endpoint':endpoint,'models':found,'managed':False,'state':'existing','note':'existing_unchanged'}
    unit=output(['/usr/bin/systemctl','show','ollama.service','-p','LoadState','--value']).strip()
    binary=shutil.which('ollama') or any(Path(path).is_file() for path in ('/usr/local/bin/ollama','/usr/bin/ollama','/opt/ollama/bin/ollama'))
    if candidates or binary or unit not in ('','not-found'):return {'endpoint':None,'models':[],'managed':managed,'state':'existing_unavailable','note':'existing_unchanged'}
    with socket.socket() as check:
        try:check.bind(('127.0.0.1',11434))
        except OSError:return {'endpoint':None,'models':[],'managed':False,'state':'port_in_use','note':'existing_unchanged'}
    return None

def resources():
    memory={line.split(':',1)[0]:int(line.split()[1])//1024 for line in Path('/proc/meminfo').read_text().splitlines()}
    docker_root=Path(output(['/usr/bin/docker','info','--format','{{.DockerRootDir}}']).strip())
    disk=min(shutil.disk_usage('/var/lib').free,shutil.disk_usage(docker_root).free)
    total,available,cpus=memory['MemTotal'],memory['MemAvailable'],os.cpu_count() or 1
    root=Path('/sys/fs/cgroup');paths=[root]
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        if line.startswith('0::'):
            current=(root/line[3:].lstrip('/')).resolve()
            if current.is_relative_to(root):
                while current!=root:paths.append(current);current=current.parent
    for path in paths:
        try:
            maximum=(path/'memory.max').read_text().strip()
            if maximum.isdecimal():
                total=min(total,int(maximum)//1024**2)
                available=min(available,max(0,(int(maximum)-int((path/'memory.current').read_text()))//1024**2))
            quota,period=(path/'cpu.max').read_text().split()
            if quota.isdecimal():cpus=min(cpus,int(quota)/int(period))
        except (OSError,ValueError):pass
    return budget(total,available,cpus,disk)

def provision(limits,data=Path('/var/lib/kiagent-ollama')):
    if data.exists():raise ValueError('Existing unmanaged Ollama data directory; no overwrite')
    run(['/usr/bin/docker','pull','ollama/ollama:latest'],timeout=900)
    digest=json.loads(output(['/usr/bin/docker','image','inspect','--format','{{json .RepoDigests}}','ollama/ollama:latest']))[0]
    if not digest.startswith('ollama/ollama@sha256:'):raise ValueError('Unexpected Ollama image')
    data.mkdir(mode=0o700)
    command=['/usr/bin/docker','run','-d','--name',NAME,'--label','io.server-control.ollama=1','--restart','unless-stopped',
      '--cpus',str(limits['cpus']),'--cpu-shares','128','--memory',str(limits['memory_mib'])+'m','--memory-swap',str(limits['memory_mib'])+'m',
      '--pids-limit','128','--oom-score-adj','500','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only',
      '--tmpfs','/tmp:rw,nosuid,noexec,size=256m','--mount','type=bind,source='+str(data)+',target=/root/.ollama',
      '--publish','127.0.0.1:11434:11434']
    for key,value in {'OLLAMA_HOST':'0.0.0.0:11434','OLLAMA_NUM_PARALLEL':'1','OLLAMA_MAX_LOADED_MODELS':'1','OLLAMA_MAX_QUEUE':'2',
                      'OLLAMA_CONTEXT_LENGTH':'2048','OLLAMA_KEEP_ALIVE':'30s','OLLAMA_NO_CLOUD':'1','OLLAMA_VULKAN':'0'}.items():command+=['--env',key+'='+value]
    run(command+[digest])
    atomic(STATE/'server.json',json.dumps({'managed':True,'limits':limits,'state':'model_pending','endpoint':'http://127.0.0.1:11434'}).encode())
    for _ in range(40):
        if probe('http://127.0.0.1:11434') is not None:break
        time.sleep(.5)
    else:raise RuntimeError('New Ollama did not become ready')
    if shutil.disk_usage(data).free<8*1024**3:raise RuntimeError('Insufficient disk headroom for model')
    run(['/usr/bin/docker','exec',NAME,'ollama','pull',limits['model']],timeout=900)
    available=probe('http://127.0.0.1:11434') or []
    if not any(row['name']==limits['model'] for row in available):raise RuntimeError('New Ollama model was not verified')
    return {'endpoint':'http://127.0.0.1:11434','models':available,'managed':True,'state':'installed','note':'managed_ollama','limits':limits,'image':digest}

def enable_mounts(text):
    if 'KIAGENT_AI_ENABLED:' not in text:
        anchor="    PYTHONDONTWRITEBYTECODE: '1'"
        if text.count(anchor)!=1:raise ValueError('Unknown runtime environment')
        text=text.replace(anchor,anchor+"\n    KIAGENT_AI_ENABLED: '1'")
    for name in ('telegram','discord'):
        start=text.index('  '+name+':\n')
        # Find the next service at exactly two spaces, not a nested YAML property.
        import re
        match=re.search(r'\n  [A-Za-z][A-Za-z0-9-]*:\n',text[start+3:])
        end=start+3+match.start() if match else len(text)
        block=text[start:end]
        if 'target: /run/kiagent-ai' not in block:
            anchor='    volumes:\n'
            if block.count(anchor)!=1:raise ValueError('Unknown bot volume layout')
            block=block.replace(anchor,anchor+'''      - type: bind
        source: /run/kiagent-ai
        target: /run/kiagent-ai
        read_only: true
        bind: {create_host_path: false}
''',1)
            text=text[:start]+block+text[end:]
    return text

def install_gateway(record):
    try:account=pwd.getpwnam('kiagent-ai')
    except KeyError:
        run(['/usr/sbin/useradd','--system','--user-group','--no-create-home','--home-dir','/nonexistent','--shell','/usr/sbin/nologin','kiagent-ai'])
        account=pwd.getpwnam('kiagent-ai')
    if account.pw_uid<=0 or account.pw_shell not in ('/usr/sbin/nologin','/sbin/nologin','/bin/false'):raise ValueError('Unexpected AI service account')
    STATE.mkdir(mode=0o755,exist_ok=True)
    STATE.chmod(0o755);LIB.mkdir(mode=0o755,parents=True,exist_ok=True);LIB.chmod(0o755)
    atomic(STATE/'server.json',json.dumps(record).encode())
    provider=Path('/var/lib/kiagent-ai/provider.json');provider.parent.mkdir(mode=0o700,exist_ok=True)
    os.chown(provider.parent,account.pw_uid,account.pw_gid);provider.parent.chmod(0o700)
    if not provider.exists():
        model=(record.get('models') or [{}])[0].get('name','')
        atomic(provider,json.dumps({'provider':'ollama' if model else 'openai','model':model}).encode(),0o600)
        os.chown(provider,account.pw_uid,account.pw_gid)
    if REPO:
        files={LIB/'ai_gateway.py':REPO/'host/ai_gateway.py',LIB/'install_ollama.py':HERE,
               LIB/'ai_socket.py':REPO/'src/app/ai_socket.py',LIB/'ai_admin.py':REPO/'host/ai_admin.py'}
        for target,source in files.items():
            if not target.exists():atomic(target,source.read_bytes(),0o600 if target.name=='install_ollama.py' else 0o644)
    broker=Path('/usr/local/lib/kiagent-config')
    for name in ('ai_socket.py','ai_admin.py'):
        if not (broker/name).exists():atomic(broker/name,(LIB/name).read_bytes())
    unit=Path('/etc/systemd/system/kiagent-ai.service')
    if not unit.exists():atomic(unit,b'''[Unit]
Description=Server Control bounded local AI bridge
After=network-online.target
[Service]
User=kiagent-ai
Group=kiagent-ai
ExecStart=/usr/bin/python3 -I -B /usr/local/lib/kiagent-ai/ai_gateway.py
RuntimeDirectory=kiagent-ai
RuntimeDirectoryMode=0755
RuntimeDirectoryPreserve=yes
StateDirectory=kiagent-ai
StateDirectoryMode=0700
ReadWritePaths=/var/lib/kiagent-ai
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
CapabilityBoundingSet=
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
MemoryMax=128M
CPUQuota=10%
TasksMax=16
Nice=10
[Install]
WantedBy=multi-user.target
''')
    ordering=Path('/etc/systemd/system/kiagent-docker.service.d/20-ai.conf')
    if not ordering.exists():atomic(ordering,b'[Unit]\nWants=kiagent-ai.service\nAfter=kiagent-ai.service\n')
    run(['/usr/bin/systemctl','daemon-reload']);run(['/usr/bin/systemctl','enable','--now','kiagent-ai.service'])
    compose=PROJECT/'compose.yaml';before=compose.read_bytes();after=enable_mounts(before.decode()).encode()
    if after!=before:
        backup=Path('/var/backups/kiagent-ai-'+str(time.time_ns()));backup.mkdir(mode=0o700)
        atomic(backup/'compose.yaml',before,0o600);atomic(compose,after)
    return record

def main():
    if os.geteuid()!=0:raise SystemExit('Root required for Ollama installation check.')
    os.chdir('/')
    if not (PROJECT/'compose.yaml').is_file():raise SystemExit('Install the Server Control web foundation first.')
    if STATE.exists():
        if STATE.is_symlink() or not (STATE/'owner').is_file() or (STATE/'owner').read_text()!='server-control-ai-v1':raise SystemExit('Unknown AI configuration directory; no changes.')
    else:
        if LIB.exists() or Path('/var/lib/kiagent-ai').exists() or Path('/etc/systemd/system/kiagent-ai.service').exists():raise SystemExit('Existing AI adapter files need manual review.')
        STATE.mkdir(mode=0o755);STATE.chmod(0o755);atomic(STATE/'owner',b'server-control-ai-v1',0o600)
    lock=os.open('/run/kiagent-ollama-install.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX)
        record=existing()
        previous=json.loads((STATE/'server.json').read_text()) if (STATE/'server.json').exists() else {}
        if record is None and Path('/var/lib/kiagent-ollama').exists():record={'endpoint':None,'models':[],'managed':False,'state':'existing_unavailable','note':'existing_unchanged'}
        if record is None:
            limits=resources()
            record=provision(limits) if limits else {'endpoint':None,'models':[],'managed':False,'state':'insufficient_resources','note':'insufficient_resources'}
        elif record.get('managed'):
            record['limits']=previous.get('limits',{})
            record['image']=previous.get('image','')
        install_gateway(record)
        print('Ollama-Pruefung: '+record['state']+'. Vorhandene Ollama-Konfigurationen und Modelle wurden nicht veraendert.' if record['state']!='installed' else 'Ollama neu installiert: CPU/RAM begrenzt, ein kleines lokales Modell, keine oeffentliche API.')
    finally:os.close(lock)

if __name__=='__main__':main()
