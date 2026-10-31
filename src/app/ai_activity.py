"""Bounded phase-only AI activity. Never records prompts, answers or secrets."""
import json
import math
import os
import tempfile
import time
from pathlib import Path

PATHS={'telegram':Path('/tmp/kiagent-ai-activity.json'),'discord':Path('/run/kiagent-discord/ai-activity.json')}
PHASES={'ai_started','ai_plan','ai_finished','ai_failed'}

def read(platform):
    path=PATHS[platform]
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:raw=stream.read(32769)
        if len(raw)>32768:return []
        data=json.loads(raw)
        if not isinstance(data,list):return []
        return [{'time':row['time'],'event':row['event'],'platform':platform} for row in data[-32:]
                if isinstance(row,dict) and row.get('event') in PHASES and type(row.get('time')) in (int,float) and math.isfinite(row['time'])]
    except (OSError,ValueError,KeyError):return []

def record(platform,event):
    if platform not in PATHS or event not in PHASES:return
    name=None
    try:
        path=PATHS[platform];events=read(platform)[-31:]+[{'time':time.time(),'event':event,'platform':platform}]
        fd,name=tempfile.mkstemp(prefix='.ai-',dir=path.parent)
        with os.fdopen(fd,'w') as stream:json.dump(events,stream)
        os.replace(name,path)
    except OSError:pass
    finally:
        if name and os.path.exists(name):os.unlink(name)

if __name__=='__main__':
    import sys
    print(json.dumps(read(sys.argv[1] if len(sys.argv)==2 and sys.argv[1] in PATHS else 'telegram')))
