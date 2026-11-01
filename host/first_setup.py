"""First browser configuration: validated credentials, gated agents, durable commit."""
import json
import os
import secrets
import time
from pathlib import Path
from config_store import MANAGED,Invalid,validate_secret

def durable_file(path,data):
    temporary=path.with_name('.'+path.name+'-'+secrets.token_hex(8))
    fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        sync_parent(path)
    finally:temporary.unlink(missing_ok=True)

def sync_parent(path):
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def apply_first_configuration(store,prepared,progress,*,run,login_check,state_read,barrier,compose,backup_root=Path('/var/backups/kiagent-config')):
    from config_broker import PublicError
    pending=store.root/'pending-setup';ready=store.root/'runtime-ready'
    if not pending.is_file() or pending.is_symlink():raise Invalid('schema')
    # Never reuse this path to replace an already configured installation.
    if prepared['before']['secrets/allowed-users'].strip() or any(prepared['before']['secrets/'+name].strip() for name in ('telegram-token','discord-token')):raise Invalid('schema')
    for key,name in (('telegram','telegram-token'),('discord','discord-token')):validate_secret(key,prepared['desired']['secrets/'+name].decode().strip())
    login_check(prepared)
    if store.revision()!=prepared['revision']:raise Invalid('stale')
    before=state_read()
    backup=backup_root/('first-setup-'+str(time.time_ns())+'-'+secrets.token_hex(4));backup.mkdir(mode=0o700)
    for name in MANAGED:
        path=backup/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);durable_file(path,prepared['before'][name])
    changed=False
    agents=['kiagent-executor.service','kiagent-packages.service']
    bots=['telegram','discord','server-heartbeat']
    try:
        progress('starting');changed=True
        store.write(prepared['desired'])
        durable_file(ready,b'{"kind":"validated-browser-configuration-v1"}\n')
        run(['/usr/bin/systemctl','enable','--now',*agents])
        user=int(prepared['desired']['secrets/allowed-users'].splitlines()[0])
        barrier('/run/kiagent-executor/control.sock',{'op':'health'})
        barrier('/run/kiagent-packages/control.sock',{'op':'status','user_id':user,'chat_id':user,'message_id':1})
        if state_read()!=before:raise PublicError('state_changed')
        progress('checking')
        run(compose+['up','-d','--no-build','--pull','never','--no-deps','--force-recreate','--wait','--wait-timeout','180',*bots])
        run(['/usr/bin/systemctl','enable','--now','kiagent-backup.timer'])
        run(['/usr/bin/systemctl','start','kiagent-backup.service'])
        pending.unlink();sync_parent(pending)
        return 'success'
    except Exception:
        if changed:
            progress('restoring')
            try:
                if not pending.exists():durable_file(pending,b'{"kind":"browser-setup-pending-v1"}\n')
                ready.unlink(missing_ok=True);sync_parent(ready)
                run(compose+['stop',*bots])
                run(['/usr/bin/systemctl','disable','--now',*agents,'kiagent-backup.timer'])
                store.write(prepared['before'])
            except Exception:raise PublicError('rollback_failed') from None
            return 'rolled_back'
        raise
