"""Strict configuration schema and atomic files; never returns saved secrets."""
import hashlib
import hmac
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

SECRET_FILES = {'telegram':'telegram-token','discord':'discord-token','openai':'openai-api-key',
                'hc_bot':'hc-bot','hc_server':'hc-server'}
PUBLIC_FIELDS = {'telegram_users','discord_application','discord_users','discord_guild','discord_channel','raid_devices'}
MANAGED = ['deployment.env','secrets/allowed-users','secrets/discord-access.json',
           *['secrets/'+name for name in SECRET_FILES.values()]]

class Invalid(ValueError):
    pass

def number(value):
    if not isinstance(value,str) or not value.isdecimal() or not 0 < int(value) < 2**63:
        raise Invalid('ids')
    return int(value)

def users(value):
    if not isinstance(value,str) or len(value)>500:
        raise Invalid('ids')
    values = [number(x.strip()) for x in value.split(',')]
    if not 1 <= len(values) <= 20 or len(set(values)) != len(values):
        raise Invalid('ids')
    return values

def validate_secret(name,value):
    if not isinstance(value,str) or not value.isascii() or len(value)>2048 or any(c.isspace() for c in value):
        raise Invalid('token')
    if not value:
        if name in {'telegram','discord'}:
            raise Invalid('required')
        return value
    if name == 'telegram' and re.fullmatch(r'[0-9]{5,15}:[A-Za-z0-9_-]{20,150}',value) is None:
        raise Invalid('telegram_format')
    if name == 'discord' and re.fullmatch(r'[A-Za-z0-9_.-]{30,2048}',value) is None:
        raise Invalid('discord_format')
    if name == 'openai' and (not value.startswith('sk-') or len(value)<24):
        raise Invalid('openai_format')
    if name in {'hc_bot','hc_server'}:
        prefix = 'https://hc-ping.com/'
        try:
            if not value.startswith(prefix) or str(uuid.UUID(value[len(prefix):])) != value[len(prefix):].lower():
                raise ValueError()
        except ValueError:
            raise Invalid('ping_format') from None
    return value

class Store:
    def __init__(self,root,gid,signing_key,owner=0):
        self.root,self.gid,self.signing_key = Path(root),gid,signing_key
        self.owner=owner

    def read(self):
        result = {}
        for name in MANAGED:
            path = self.root/name
            if path.is_symlink() or not path.is_file():
                raise Invalid('storage')
            data = path.read_bytes()
            if len(data)>16000:
                raise Invalid('storage')
            result[name] = data
        return result

    def revision(self,raw=None):
        raw = raw if raw is not None else self.read()
        canonical = b''.join(name.encode()+b'\0'+raw[name]+b'\0' for name in MANAGED)
        return hmac.new(self.signing_key,canonical,hashlib.sha256).hexdigest()

    def overview(self):
        raw = self.read()
        env = dict(line.split('=',1) for line in raw['deployment.env'].decode().splitlines() if line and not line.startswith('#'))
        access = json.loads(raw['secrets/discord-access.json'])
        return {'revision':self.revision(raw),'public':{
            'telegram_users':','.join(raw['secrets/allowed-users'].decode().split()),
            'discord_application':env['DISCORD_APPLICATION_ID'],
            'discord_users':','.join(str(x) for x in access['users']),
            'discord_guild':str(access['guild_id']),'discord_channel':str(access['channel_id']),
            'raid_devices':env.get('KIAGENT_RAID_DEVICES','')},
            'configured':{key:bool(raw['secrets/'+name].strip()) for key,name in SECRET_FILES.items()}}

    def prepare(self,request):
        if not isinstance(request,dict) or set(request) != {'revision','public','secrets'}:
            raise Invalid('schema')
        raw = self.read()
        if not isinstance(request['revision'],str) or not hmac.compare_digest(request['revision'],self.revision(raw)):
            raise Invalid('stale')
        public,secret_specs = request['public'],request['secrets']
        if not isinstance(public,dict) or set(public) != PUBLIC_FIELDS or not isinstance(secret_specs,dict) or set(secret_specs) != set(SECRET_FILES):
            raise Invalid('schema')
        telegram_users = users(public['telegram_users'])
        discord_users = users(public['discord_users'])
        application,guild,channel = [number(public[k]) for k in ('discord_application','discord_guild','discord_channel')]
        raids = public['raid_devices']
        if not isinstance(raids,str) or len(raids)>200 or (raids and any(re.fullmatch(r'md[0-9]+',x) is None for x in raids.split(','))):
            raise Invalid('raid')
        desired = dict(raw)
        for key,name in SECRET_FILES.items():
            spec = secret_specs[key]
            if not isinstance(spec,dict):
                raise Invalid('schema')
            mode = spec.get('mode')
            if mode == 'keep' and set(spec) == {'mode'}:
                continue
            if mode == 'clear' and set(spec) == {'mode'} and key not in {'telegram','discord'}:
                value = ''
            elif mode == 'replace' and set(spec) == {'mode','value'}:
                value = validate_secret(key,spec['value'])
            else:
                raise Invalid('schema')
            desired['secrets/'+name] = (value+'\n').encode()
        env = dict(line.split('=',1) for line in raw['deployment.env'].decode().splitlines() if line and not line.startswith('#'))
        for key in ('telegram','discord'):
            validate_secret(key,desired['secrets/'+SECRET_FILES[key]].decode().strip())
        env['DISCORD_APPLICATION_ID'] = str(application)
        env['KIAGENT_RAID_DEVICES'] = raids
        desired['deployment.env'] = ('\n'.join(k+'='+v for k,v in env.items())+'\n').encode()
        desired['secrets/allowed-users'] = ('\n'.join(str(x) for x in telegram_users)+'\n').encode()
        desired['secrets/discord-access.json'] = (json.dumps({'users':discord_users,'guild_id':guild,'channel_id':channel})+'\n').encode()
        # Legacy files may have harmless whitespace differences; canonicalize only after confirmation.
        return {'before':raw,'desired':desired,'revision':self.revision(raw),
                'changed':any(raw[name] != desired[name] for name in MANAGED)}

    def write(self,raw):
        for name in MANAGED:
            path = self.root/name
            if path.is_symlink():
                raise Invalid('storage')
            fd,temporary = tempfile.mkstemp(prefix='.config-',dir=path.parent)
            try:
                with os.fdopen(fd,'wb') as stream:
                    stream.write(raw[name])
                    stream.flush()
                    os.fsync(stream.fileno())
                    os.fchmod(stream.fileno(),0o600 if name == 'deployment.env' else 0o440)
                    os.fchown(stream.fileno(),self.owner,self.gid if name != 'deployment.env' or self.owner!=0 else 0)
                os.replace(temporary,path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        for directory in (self.root,self.root/'secrets'):
            fd = os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
