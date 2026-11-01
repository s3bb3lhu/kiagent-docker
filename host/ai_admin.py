"""Root-side provider selection changes our settings only, never an Ollama instance."""
import json
import os
import pwd
import re
import stat
from pathlib import Path
from ai_socket import request as ai_request
PROVIDER=Path('/var/lib/kiagent-ai/provider.json')

def handle(request):
    if request=={'op':'ai_info'}:
        try:return ai_request({'op':'info'})
        except Exception:
            selected={'provider':'unavailable','model':''}
            try:
                descriptor=os.open(PROVIDER,os.O_RDONLY|os.O_NOFOLLOW)
                with os.fdopen(descriptor) as stream:
                    info=os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_uid!=pwd.getpwnam('kiagent-ai').pw_uid or info.st_size>16384:raise ValueError()
                    value=json.load(stream)
                if value.get('provider') in ('openai','ollama') and isinstance(value.get('model'),str) and re.fullmatch(r'[A-Za-z0-9._:/-]{0,101}',value['model']):selected={'provider':value['provider'],'model':value['model']}
            except Exception:pass
            return {'ok':True,**selected,'ready':False,'models':[],'state':'unavailable','managed':False,'limits':{},'note':'ai_unavailable'}
    if not isinstance(request,dict) or set(request)!={'op','provider','model'} or request['op']!='ai_select' or not isinstance(request['provider'],str) or request['provider'] not in {'openai','ollama'} or not isinstance(request['model'],str):return {'ok':False,'code':'schema'}
    return ai_request({'op':'select','provider':request['provider'],'model':request['model']})
