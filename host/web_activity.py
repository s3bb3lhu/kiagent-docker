"""Read-only structured activity, deliberately excludes raw shell/journal text."""
import math
import json
import os
import re
import sqlite3
import subprocess
import time
from pathlib import Path
from package_policy import valid_package
DATABASE=Path('/var/lib/kiagent-executor/history.sqlite3')
APT_LOG=Path('/var/lib/kiagent-packages/apt-last.log')

def collect(root,state,compose):
    events=[];sources={}
    for platform in ('telegram','discord'):
        try:
            result=subprocess.run(compose+['exec','-T',platform,'python','-B','/app/ai_activity.py',platform],capture_output=True,text=True,timeout=3,check=True)
            raw=json.loads(result.stdout[:32768]);sources[platform]=True
            for row in raw[-32:]:
                if isinstance(row,dict) and row.get('event') in {'ai_started','ai_plan','ai_finished','ai_failed'} and type(row.get('time')) in (int,float) and math.isfinite(row['time']):
                    events.append({'id':platform+str(row['time']),'time':row['time'],'event':row['event'],'platform':platform})
        except Exception:sources[platform]=False
    try:
        with sqlite3.connect('file:'+str(DATABASE)+'?mode=ro',uri=True,timeout=1) as db:
            rows=db.execute('SELECT rowid,uid,state,plan,expires FROM package_jobs ORDER BY rowid DESC LIMIT 25').fetchall()
        for id,uid,status,plan,expires in rows:
            data=json.loads(plan);package=data.get('package','htop')
            if not valid_package(package):continue
            events.append({'id':'package-'+str(id),'time':expires-120,'event':'package_job','state':status,'package':package,'platform':'apt','time_kind':'created'})
        # Only known APT progress prefixes and names from the latest actual plan.
        latest=next((row for row in rows if row[2] in {'started','success','uncertain'}),None)
        if latest:
            plan=json.loads(latest[3]);allowed={item.split('=',1)[0].split(':',1)[0] for item in plan.get('versions',[]) if isinstance(item,str)}
            path=APT_LOG
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(fd,'rb') as stream:
                if os.fstat(stream.fileno()).st_mtime < latest[4]-120:raise ValueError('Stale APT log')
                stream.seek(max(0,os.fstat(stream.fileno()).st_size-32768));tail=stream.read(32768).decode(errors='replace')
            for index,line in enumerate(tail.splitlines()[-150:]):
                match=re.match(r'^(Unpacking|Setting up|Processing triggers for) ([a-z0-9][a-z0-9+.-]+)(?::[a-z0-9-]+)?(?: |$)',line)
                if match and match[2] in allowed:
                    events.append({'id':'apt-'+str(latest[0])+'-'+str(index),'time':None,'event':{'Unpacking':'apt_unpack','Setting up':'apt_setup','Processing triggers for':'apt_trigger'}[match[1]],'package':match[2],'platform':'apt'})
        sources['packages']=True
    except Exception:sources['packages']=False
    for path in sorted(Path(state).glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]:
        try:
            row=json.loads(path.read_text())
            action=row.get('action','')
            if action.startswith('install_') and not valid_package(action[8:]):continue
            events.append({'id':'web-'+row['id'],'time':row['created_at'],'event':'web_job','state':row['state'],'action':action,'platform':'web','time_kind':'created'})
        except Exception:continue
    dated=sorted([e for e in events if e['time'] is not None],key=lambda e:e['time'])[-70:]
    progress=[e for e in events if e['time'] is None][-30:]
    return {'available':True,'sampled_at':time.time(),'sources':sources,'events':dated+progress}
