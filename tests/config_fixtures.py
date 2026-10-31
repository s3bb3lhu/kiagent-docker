import json
from pathlib import Path

def files(root):
    root = Path(root)
    (root/'secrets').mkdir(parents=True,exist_ok=True)
    values = {'telegram-token':'123456'+':'+'t'*32,'discord-token':'D'*48,
              'openai-api-key':'sk-'+'x'*48,'hc-bot':'','hc-server':''}
    for name,value in values.items():
        (root/'secrets'/name).write_text(value+'\n')
    (root/'secrets/allowed-users').write_text('42\n')
    (root/'secrets/discord-access.json').write_text(json.dumps({'users':[42],'guild_id':70,'channel_id':80})+'\n')
    (root/'deployment.env').write_text('KIAGENT_UID=10001\nDISCORD_UID=10002\nKIAGENT_GID=10001\nDISCORD_APPLICATION_ID=90\nKIAGENT_RAID_DEVICES=md1,md2\n')
    return values

def request(store):
    view = store.overview()
    return {'revision':view['revision'],'public':view['public'],
            'secrets':{key:{'mode':'keep'} for key in ('telegram','discord','openai','hc_bot','hc_server')}}
