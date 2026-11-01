#!/usr/bin/env python3
"""Disposable CI host only: exercise actual web-first installation without provider secrets."""
import http.cookiejar
import json
import os
import re
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.geteuid()!=0:raise SystemExit('Nur im frischen, wegwerfbaren GitHub-CI-Host ausfuehren.')
    if Path('/etc/kiagent-docker').exists() or Path('/opt/kiagent-docker').exists():raise SystemExit('CI-Host ist nicht frisch.')
    compose=['docker','compose','-f',str(ROOT/'compose.install.yaml')]
    try:
        subprocess.run(compose+['run','--rm','-T','installer','--web-only'],check=True,timeout=600)
        origin='http://127.0.0.1:8787'
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def get(path,data=None,csrf=None):
            headers={}
            if data is not None:headers.update(Origin=origin)
            if csrf:headers.update({'X-CSRF-Token':csrf,'Content-Type':'application/json'})
            raw=json.dumps(data).encode() if csrf else urllib.parse.urlencode(data).encode() if data is not None else None
            return opener.open(urllib.request.Request(origin+path,data=raw,headers=headers),timeout=15)
        html=get('/setup').read().decode();csrf=re.search(r'name="csrf" value="([^"]+)"',html)[1]
        response=get('/setup',{'csrf':csrf,'password':'Fixture1!','repeat':'Fixture1!'})
        assert response.geturl().endswith('/settings/setup')
        wizard=response.read().decode();assert 'data-provider="all"' in wizard
        for name in ('telegram','discord','openai','hc_bot','hc_server'):assert 'data-secret="'+name+'"' in wizard
        csrf=re.search(r'name="csrf-token" content="([^"]+)"',wizard)[1]
        view=json.load(get('/api/overview'));assert view['setup_required'] and not any(view['configured'].values())
        status=json.load(get('/api/server/status'));assert status['setup_required'] and status['control_available'] is False
        empty={'revision':view['revision'],'public':{'telegram_users':'42','discord_users':'42','discord_application':'90','discord_guild':'70','discord_channel':'80','raid_devices':''},'secrets':{key:{'mode':'keep'} for key in ('telegram','discord','openai','hc_bot','hc_server')}}
        try:get('/api/config',empty,csrf)
        except urllib.error.HTTPError as error:assert json.load(error)['code']=='required'
        else:raise AssertionError('Empty bot tokens must not activate anything')
        try:get('/api/control/prepare',{'action':'server_restart'},csrf)
        except urllib.error.HTTPError as error:assert json.load(error)['code']=='setup_required'
        else:raise AssertionError('Pending setup must reject server actions')
        for unit in ('kiagent-executor','kiagent-packages'):
            assert subprocess.check_output(['systemctl','show',unit,'-p','ActiveState','--value'],text=True).strip()=='inactive'
        for name in ('telegram-token','discord-token','openai-api-key','hc-bot','hc-server'):
            assert not (Path('/etc/kiagent-docker/secrets')/name).read_bytes().strip()
        containers=subprocess.check_output(['docker','ps','--filter','label=com.docker.compose.project=kiagent','--format','{{.Label "com.docker.compose.service"}}'],text=True).splitlines()
        assert containers==['config-web'],containers
        print('Actual web-first host bootstrap: password setup, combined wizard, empty provider secrets, disabled bots/agents/actions: OK')
        from exercise_parallel_https import exercise
        exercise()
    except Exception:
        # Fixed status fields only: never export application logs or environment.
        subprocess.run(['systemctl','show','kiagent-docker','kiagent-config','-p','Id','-p','ActiveState','-p','Result','-p','ExecMainStatus'],check=False)
        subprocess.run(['docker','ps','-a','--format','{{.Names}} {{.Status}}'],check=False)
        raise
    finally:
        subprocess.run(['systemctl','disable','--now','kiagent-docker','kiagent-config','kiagent-executor','kiagent-packages','kiagent-backup.timer'],capture_output=True,timeout=120)

if __name__=='__main__':main()
