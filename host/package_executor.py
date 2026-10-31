"""Allowlisted package installation, peer-authenticated and confirmed."""
import hashlib
import json
import os
import pwd
import re
import secrets
import socket
import sqlite3
import struct
import subprocess
import time
from pathlib import Path

SOCKET = '/run/kiagent-packages/control.sock'
PACKAGES = frozenset({'htop', 'tree'})
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C',
       'DEBIAN_FRONTEND': 'noninteractive', 'APT_LISTCHANGES_FRONTEND': 'none'}
BASE = ['/usr/bin/apt-get', '-o', 'APT::Get::Assume-Yes=true',
        '-o', 'Acquire::Retries=0', '-o', 'DPkg::Lock::Timeout=5',
        '--no-install-recommends', '--no-upgrade', '--no-remove']


def installed(package):
    if package not in PACKAGES:
        raise ValueError('Package not allowlisted')
    p = subprocess.run(['/usr/bin/dpkg-query', '-W',
                        '-f=${Status} ${Version}', package],
                       capture_output=True, text=True, timeout=5, env=ENV)
    return p.stdout.strip() if p.returncode == 0 and p.stdout.startswith('install ok installed ') else None


def plan(package):
    if package not in PACKAGES:
        raise ValueError('Package not allowlisted')
    if installed(package):
        return {'installed': True, 'package': package}
    p = subprocess.run(BASE + ['--simulate', 'install', package],
                       capture_output=True, text=True, timeout=20, env=ENV)
    text = p.stdout
    if p.returncode or len(text) > 16000:
        raise ValueError('Package simulation failed')
    changes = [line for line in text.splitlines() if line.startswith(('Inst ', 'Remv ', 'Conf '))]
    installs = [line for line in changes if line.startswith('Inst ')]
    if (not installs or len(installs) > 10 or
            any(line.startswith('Remv ') for line in changes) or
            any(re.match(r'^Inst \S+ \[', line) for line in installs)):
        raise ValueError('Unsafe package changes')
    versions = []
    for line in installs:
        m = re.match(r'^Inst ([a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?) \(([^\s()]+) ', line)
        if m is None:
            raise ValueError('Unknown package plan')
        versions.append(m[1] + '=' + m[2])
    if not any(v.startswith(package + '=') for v in versions):
        raise ValueError('Missing requested package')
    digest = hashlib.sha256('\n'.join(changes).encode()).hexdigest()
    return {'installed': False, 'digest': digest, 'package': package,
            'changes': changes, 'versions': versions}


class Broker:
    def __init__(self, db, allowed, planner=plan, runner=None, discord_access=None):
        self.db, self.allowed, self.planner = db, allowed, planner
        self.discord_access = discord_access
        self.runner = runner or self.install
        db.execute('CREATE TABLE IF NOT EXISTS package_jobs (token TEXT PRIMARY KEY, uid INTEGER, message INTEGER, expires REAL, state TEXT, plan TEXT, result TEXT)')
        # A prior process may have stopped after spawning apt. Never replay it.
        db.execute("UPDATE package_jobs SET state='uncertain' WHERE state='started'")

    def install(self, proposal):
        package = proposal.get('package', 'htop')
        if package not in PACKAGES:
            raise ValueError('Package not allowlisted')
        # Include every simulated package version. No model-generated arguments.
        with open('/var/lib/kiagent-packages/apt-last.log', 'w') as log:
            subprocess.run(BASE + ['install', *proposal['versions']],
                           check=True, stdin=subprocess.DEVNULL,
                           stdout=log, stderr=subprocess.STDOUT, env=ENV)
        version = installed(package)
        expected = next(v.split('=', 1)[1] for v in proposal['versions'] if v.startswith(package + '='))
        if version != 'install ok installed ' + expected:
            raise ValueError('Installation not verified')
        return version

    def handle(self, req, platform='telegram'):
        op = req.get('op')
        common = {'op', 'user_id', 'chat_id', 'message_id'}
        if platform == 'discord':
            common |= {'guild_id'}
        elif platform != 'telegram':
            raise ValueError('Unknown platform')
        expected = common if op == 'status' else common | ({'package'} if op == 'new' else {'token'})
        if set(req) != expected or op not in {'new', 'confirm', 'cancel', 'result', 'status'}:
            raise ValueError('Invalid request')
        uid, chat, message = (req[k] for k in ('user_id', 'chat_id', 'message_id'))
        if any(type(x) is not int or not 0 < x < 2**63 for x in (uid, chat, message)):
            raise ValueError('Unauthorized identity')
        if platform == 'telegram':
            if uid not in self.allowed or chat != uid:
                raise ValueError('Unauthorized Telegram identity')
        else:
            access = self.discord_access
            if (not access or uid not in access['users']
                    or type(req['guild_id']) is not int
                    or req['guild_id'] != access['guild_id']
                    or chat != access['channel_id']):
                raise ValueError('Unauthorized Discord identity')
            # Separate namespace; Discord snowflakes fit SQLite signed integers.
            uid = -uid
        if op == 'status':
            row = self.db.execute('SELECT state,result,plan FROM package_jobs WHERE uid=? ORDER BY rowid DESC LIMIT 1', (uid,)).fetchone()
            return {'ok': True, 'result': 'none' if row is None else row[0],
                    'version': '' if row is None else row[1],
                    'package': '' if row is None else json.loads(row[2]).get('package', 'htop')}
        if op == 'new':
            if type(req['package']) is not str or req['package'] not in PACKAGES:
                raise ValueError('Package not allowlisted')
            if self.db.execute("SELECT 1 FROM package_jobs WHERE state IN ('started','uncertain')").fetchone():
                return {'ok': False, 'result': 'locked'}
            proposal = self.planner(req['package'])
            if proposal.get('installed'):
                return {'ok': True, 'result': 'installed', 'package': req['package']}
            token = secrets.token_hex(16)
            self.db.execute('INSERT INTO package_jobs VALUES (?, ?, ?, ?, ?, ?, ?)',
                            (token, uid, message, time.time() + 120, 'pending',
                             json.dumps(proposal), ''))
            return {'ok': True, 'result': 'pending', 'token': token,
                    'changes': proposal['changes'], 'package': req['package']}
        token = req['token']
        if type(token) is not str or not re.fullmatch('[0-9a-f]{32}', token):
            raise ValueError('Invalid token')
        row = self.db.execute('SELECT uid,message,expires,state,plan,result FROM package_jobs WHERE token=?', (token,)).fetchone()
        if row is None or (row[0], row[1]) != (uid, message):
            raise ValueError('Unknown confirmation')
        state, proposal = row[3], json.loads(row[4])
        package = proposal.get('package', 'htop')
        if package not in PACKAGES:
            raise ValueError('Package no longer allowlisted')
        if op == 'result':
            return {'ok': state == 'success', 'result': state, 'version': row[5], 'package': package}
        if state != 'pending':
            return {'ok': False, 'result': 'consumed'}
        if time.time() > row[2]:
            self.db.execute("UPDATE package_jobs SET state='expired' WHERE token=?", (token,))
            return {'ok': False, 'result': 'expired'}
        if op == 'cancel':
            self.db.execute("UPDATE package_jobs SET state='cancelled' WHERE token=?", (token,))
            return {'ok': True, 'result': 'cancelled'}
        # Persist consumption before any execution; audit failure fails closed.
        self.db.execute("UPDATE package_jobs SET state='checking' WHERE token=? AND state='pending'", (token,))
        current = self.planner(package)
        if current.get('installed'):
            self.db.execute("UPDATE package_jobs SET state='already_installed' WHERE token=?", (token,))
            return {'ok': True, 'result': 'installed', 'package': package}
        if current['digest'] != proposal['digest']:
            self.db.execute("UPDATE package_jobs SET state='changed' WHERE token=?", (token,))
            return {'ok': False, 'result': 'changed'}
        self.db.execute("UPDATE package_jobs SET state='started' WHERE token=?", (token,))
        print(json.dumps({'event': 'started', 'package': package, 'platform': platform, 'user_id': abs(uid)}), flush=True)
        try:
            version = self.runner(proposal)
        except Exception:
            self.db.execute("UPDATE package_jobs SET state='uncertain' WHERE token=?", (token,))
            print(json.dumps({'event': 'uncertain', 'package': package}), flush=True)
            return {'ok': False, 'result': 'uncertain'}
        self.db.execute("UPDATE package_jobs SET state='success',result=? WHERE token=?", (version, token))
        print(json.dumps({'event': 'success', 'package': package}), flush=True)
        return {'ok': True, 'result': 'success', 'version': version, 'package': package}


def main():
    allowed = {int(s) for s in (Path(os.environ['CREDENTIALS_DIRECTORY']) / 'allowed-users').read_text().splitlines() if s.strip()}
    if not allowed or any(x <= 0 for x in allowed):
        raise ValueError('Invalid allowlist')
    db = sqlite3.connect('/var/lib/kiagent-executor/history.sqlite3', isolation_level=None)
    db.execute('PRAGMA synchronous=FULL')
    credentials = Path(os.environ['CREDENTIALS_DIRECTORY'])
    access = json.loads((credentials / 'discord-access').read_text())
    if (set(access) != {'users', 'guild_id', 'channel_id'} or not access['users']
            or any(type(x) is not int or not 0 < x < 2**63 for x in
                   [*access['users'], access['guild_id'], access['channel_id']])):
        raise ValueError('Invalid Discord access configuration')
    broker = Broker(db, allowed, discord_access=access)
    Path(SOCKET).unlink(missing_ok=True)
    client_uid = pwd.getpwnam('kiagent').pw_uid
    discord_uid = pwd.getpwnam('kiagent-discord').pw_uid
    if client_uid == discord_uid:
        raise ValueError('Transport identities must differ')
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(SOCKET)
        os.chmod(SOCKET, 0o660)
        server.listen(8)
        while True:
            conn, _ = server.accept()
            with conn:
                conn.settimeout(5)
                try:
                    _, uid, _ = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid not in {client_uid, discord_uid}:
                        raise ValueError('Invalid peer')
                    raw = bytearray()
                    while b'\n' not in raw and len(raw) <= 2048:
                        block = conn.recv(2048)
                        if not block:
                            break
                        raw.extend(block)
                    if len(raw) > 2048 or not raw.endswith(b'\n') or raw.count(b'\n') != 1:
                        raise ValueError('Invalid packet')
                    reply = broker.handle(json.loads(raw), platform='telegram' if uid == client_uid else 'discord')
                except Exception:
                    reply = {'ok': False, 'result': 'rejected_or_uncertain'}
                try:
                    conn.sendall(json.dumps(reply).encode() + b'\n')
                except OSError:
                    pass  # Execution is never repeated when delivery fails.


if __name__ == '__main__':
    main()
