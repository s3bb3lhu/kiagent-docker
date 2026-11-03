"""Persistent administrator credentials and network-restricted first setup."""
import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import re
import tempfile
from pathlib import Path

POLICY = 'Mindestens 8 Zeichen, ein Großbuchstabe, eine Zahl und ein Sonderzeichen.'

def valid_username(value):
    return isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,31}',value) is not None

def valid_password(value):
    return (isinstance(value,str) and 8<=len(value)<=256 and not any(c.isspace() for c in value)
            and any(c.isupper() for c in value) and any(c.isdecimal() for c in value)
            and any(not c.isalnum() for c in value))

def password_hash(password,salt):
    return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()

class AuthStore:
    def __init__(self,directory,legacy=None):
        self.directory=Path(directory)
        self.directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.path=self.directory/'auth.json'
        with self.lock():
            if not self.path.exists():
                if legacy is None or (self.directory/'initialized').exists():
                    raise ValueError('Administrator setup must be initialized locally')
                salt,digest=legacy
                self.write({'mode':'ready','salt':salt,'digest':digest,'epoch':secrets.token_hex(24)})
            (self.directory/'initialized').touch(mode=0o600,exist_ok=True)

    @contextlib.contextmanager
    def lock(self):
        fd=os.open(self.directory/'auth.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd,fcntl.LOCK_UN)
            os.close(fd)

    def read(self):
        fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:
            return json.load(stream)

    def write(self,value):
        fd,name=tempfile.mkstemp(prefix='.auth-',dir=self.directory)
        try:
            with os.fdopen(fd,'w') as stream:
                json.dump(value,stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name,self.path)
            fd=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
        finally:
            if os.path.exists(name):os.unlink(name)

    def verify(self,password,data=None):
        data=data or self.read()
        return (data.get('mode')=='ready' and isinstance(password,str) and 1<=len(password)<=256
                and hmac.compare_digest(password_hash(password,data['salt']),data['digest']))

    def reset(self):
        with self.lock():
            self.write({'mode':'setup','epoch':secrets.token_hex(24)})

    def set_password(self,password,*,setup=False,current=None,username=None):
        if not valid_password(password):return None
        if username is not None and not valid_username(username):return None
        with self.lock():
            data=self.read()
            if setup:
                allowed=data.get('mode')=='setup'
            else:
                allowed=self.verify(current,data)
            if not allowed:return None
            salt=secrets.token_hex(16)
            value={'mode':'ready','salt':salt,'digest':password_hash(password,salt),'epoch':secrets.token_hex(24)}
            if setup and username is not None:value['username']=username
            elif 'username' in data:value['username']=data['username']
            self.write(value)
            return value['epoch']
