"""Only the web service may start before browser onboarding has committed."""
import subprocess
from pathlib import Path
ROOT=Path('/etc/kiagent-docker')
COMPOSE=['/usr/bin/docker','compose','--env-file',str(ROOT/'deployment.env'),'-f','/opt/kiagent-docker/project/compose.yaml']

def services(root=ROOT):
    web=['config-web']+(['services-web'] if (root/'services-ready').is_file() else [])
    return web if (root/'pending-setup').exists() or not (root/'runtime-ready').is_file() else web+['telegram','discord','server-heartbeat']

def main():
    subprocess.run(COMPOSE+['up','-d','--no-build','--pull','never','--wait','--wait-timeout','180',*services()],check=True,timeout=210)
if __name__=='__main__':main()
