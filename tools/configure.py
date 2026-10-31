#!/usr/bin/env python3
"""Interactive local setup. No credential is accepted as a CLI argument."""
import getpass
import grp
import json
import os
import pwd
import re
import subprocess
from pathlib import Path

ROOT = Path('/etc/kiagent-docker')

def identifier(label):
    value = input(label + ': ').strip()
    if not value.isdecimal() or not 0 < int(value) < 2**63:
        raise ValueError('Ungueltige numerische ID')
    return int(value)

def credential(label, optional=False):
    value = getpass.getpass(label + (' (optional, leer zum Ueberspringen)' if optional else '') + ': ').strip()
    if (not value and not optional) or any(c.isspace() for c in value):
        raise ValueError('Leere oder ungueltige Zugangsdaten')
    return value

def write(path, value, gid=None):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o440 if gid is not None else 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(value + '\n')
        if gid is not None:
            os.fchown(stream.fileno(), 0, gid)
        stream.flush()
        os.fsync(stream.fileno())

def main():
    if os.geteuid() != 0:
        raise SystemExit('Bitte mit sudo ausfuehren.')
    if ROOT.exists() or ROOT.is_symlink():
        raise SystemExit('Konfiguration existiert bereits. Fuer Aenderungen die rootgeschuetzten Dateien lokal bearbeiten; kein automatisches Ueberschreiben.')
    print('IDs sind oeffentliche Konfiguration. Tokens und API-Schluessel werden unsichtbar eingegeben.')
    telegram_id = identifier('Deine Telegram-Benutzer-ID')
    application = identifier('Discord-Anwendungs-ID')
    user = identifier('Deine Discord-Benutzer-ID')
    guild = identifier('Discord-Server-ID')
    channel = identifier('Discord-Kanal-ID')
    raids = input('RAID-Geraete, kommagetrennt (z.B. md1,md2; leer fuer keine): ').strip()
    if raids and any(re.fullmatch(r'md[0-9]+', x) is None for x in raids.split(',')):
        raise ValueError('Ungueltige RAID-Geraetenamen')
    values = {'telegram-token': credential('Telegram Bot Token'),
              'discord-token': credential('Discord Bot Token'),
              'openai-api-key': credential('OpenAI API-Schluessel', optional=True),
              'hc-bot': credential('Healthchecks Bot Ping-URL', optional=True),
              'hc-server': credential('Healthchecks Server Ping-URL', optional=True)}
    for name in ('hc-bot','hc-server'):
        if values[name] and re.fullmatch(r'https://hc-ping\.com/[0-9a-fA-F-]{36}', values[name]) is None:
            raise ValueError('Ungueltige Healthchecks Ping-URL')
    for name in ('kiagent','kiagent-discord'):
        try:
            account = pwd.getpwnam(name)
            if account.pw_uid == 0 or account.pw_shell not in ('/usr/sbin/nologin','/sbin/nologin','/bin/false'):
                raise ValueError('Unerwarteter bestehender Dienstbenutzer')
        except KeyError:
            subprocess.run(['/usr/sbin/useradd','--system','--user-group','--no-create-home','--home-dir','/nonexistent','--shell','/usr/sbin/nologin',name], check=True)
    gid = grp.getgrnam('kiagent').gr_gid
    ROOT.mkdir(mode=0o700)
    secrets = ROOT / 'secrets'
    secrets.mkdir(mode=0o700)
    for name, value in values.items():
        write(secrets / name, value, gid)
    write(secrets / 'allowed-users', str(telegram_id), gid)
    write(secrets / 'discord-access.json', json.dumps({'users':[user],'guild_id':guild,'channel_id':channel}), gid)
    env = '\n'.join([f'KIAGENT_UID={pwd.getpwnam("kiagent").pw_uid}',
        f'DISCORD_UID={pwd.getpwnam("kiagent-discord").pw_uid}',f'KIAGENT_GID={gid}',
        f'DISCORD_APPLICATION_ID={application}',f'KIAGENT_SECRETS_DIR={secrets}',f'KIAGENT_RAID_DEVICES={raids}'])
    write(ROOT / 'deployment.env', env)
    print('Lokale Konfiguration erstellt. Keine Dienste gestartet oder umgeschaltet.')
    print('Zugangsdaten liegen ausserhalb des Git-Repositorys unter /etc/kiagent-docker/secrets/.')

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print('Einrichtung fehlgeschlagen (' + type(error).__name__ + '). Zugangsdaten werden nicht ausgegeben.')
        raise SystemExit(1)
