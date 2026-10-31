#!/usr/bin/env python3
"""One bounded API diagnostic, no credential output and no package operation."""
import json
import os
import pwd
import subprocess
from pathlib import Path
from install_web import COMPOSE,atomic

PROBE=r'''
import asyncio,json,logging,os
from pathlib import Path
logging.disable(logging.CRITICAL)
import openai
from ai_install import resolve
from diagnose import snapshot
report={'sdk_version':openai.__version__,'model':'gpt-4.1-mini','installation_executed':False}
key=(Path(os.environ['CREDENTIALS_DIRECTORY'])/'openai-api-key').read_text().strip()
report['key_configured']=bool(key)
try:
    snapshot();report['measurements_ok']=True
except Exception as error:
    report['measurements_ok']=False;report['measurement_error_type']=type(error).__name__
async def probe():
    if not key:
        report.update(request_ok=False,category='missing_key');return
    try:
        decision=await asyncio.wait_for(resolve(key,'Ich moechte cowsay installieren. Bereite nur einen Plan vor.',{}),timeout=50)
        report.update(request_ok=True,intent=decision['intent'],category='ok')
    except Exception as error:
        code=getattr(error,'code',None)
        body=getattr(error,'body',None)
        if isinstance(body,dict):
            details=body.get('error',body)
            if isinstance(details,dict):code=details.get('code') or details.get('type') or code
        allowed={'invalid_api_key','insufficient_quota','billing_hard_limit_reached','rate_limit_exceeded',
                 'model_not_found','invalid_json_schema','unsupported_parameter','invalid_request_error',
                 'permission_denied','account_deactivated','unsupported_country_region_territory'}
        code=code if isinstance(code,str) and code in allowed else None
        status=getattr(error,'status_code',None)
        category=('quota' if code in {'insufficient_quota','billing_hard_limit_reached'} else
                  'authentication' if status==401 else 'permission' if status==403 else
                  'rate_limit' if status==429 else 'model' if code=='model_not_found' else
                  'schema' if code in {'invalid_json_schema','unsupported_parameter'} else
                  'timeout' if isinstance(error,(TimeoutError,openai.APITimeoutError)) else
                  'connection' if isinstance(error,openai.APIConnectionError) else
                  'response_invalid' if isinstance(error,ValueError) else 'api_error' if status else 'program_error')
        report.update(request_ok=False,category=category,error_type=type(error).__name__,http_status=status,api_code=code)
        if str(error) in {'Invalid intent','Invalid answer','Invalid package','Unexpected package','Incomplete AI answer'}:
            report['validation_reason']=str(error)
asyncio.run(probe())
print(json.dumps(report))
'''

def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausfuehren; Docker-Zugriff erforderlich.')
    result=subprocess.run(COMPOSE+['exec','-T','telegram','python','-B','-c',PROBE],capture_output=True,text=True,timeout=65)
    if result.returncode:
        report={'request_ok':False,'category':'container_probe_failed','installation_executed':False}
    else:
        try:report=json.loads(result.stdout)
        except ValueError:report={'request_ok':False,'category':'invalid_probe_result','installation_executed':False}
    user=pwd.getpwnam(os.environ.get('SUDO_USER','root'))
    if user.pw_uid!=0:
        path=Path(user.pw_dir)/'kiagent-ai-diagnosis.json';atomic(path,json.dumps(report,indent=2).encode(),0o600);os.chown(path,user.pw_uid,user.pw_gid)
    print(json.dumps(report,indent=2))
    print('Keine Zugangsdaten ausgegeben, keine Installation und kein Dienstneustart ausgefuehrt.')

if __name__=='__main__':main()
