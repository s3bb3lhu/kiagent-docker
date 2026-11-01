#!/usr/bin/env python3
"""Private local backup with an online SQLite snapshot and isolated restore check.

No restore-to-production operation is provided. Archives include credentials and
must stay root-only. Existing archives are never deleted by this program.
"""
import ast
import email.parser
import hashlib
import io
import json
import os
import platform
import shutil
import sqlite3
import stat
import sys
import tarfile
import tempfile
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

BACKUPS=Path('/var/backups/kiagent-daily')
STATE=Path('/var/lib/kiagent-backup')
WORK=STATE/'work'
STATUS=STATE/'status.json'
DATABASE=Path('/var/lib/kiagent-executor/history.sqlite3')
DIRECTORIES=(Path('/opt/kiagent-docker/project/src/app'),Path('/opt/kiagent/executor'),
             Path('/etc/kiagent-docker'),Path('/usr/local/lib/kiagent-heartbeat'),Path('/usr/local/lib/kiagent-config'))
OPTIONAL_RAID_FILES=(Path('/etc/mdadm/mdadm.conf'),Path('/usr/local/sbin/kiagent-mdadm-alert'))
REQUIRED_FILES=(Path('/opt/kiagent-docker/project/compose.yaml'),Path('/opt/kiagent-docker/project/requirements.lock'),Path('/opt/kiagent-docker/project/Dockerfile'),Path('/etc/os-release'),
                Path('/usr/local/lib/kiagent-backup/backup.py'))
MAX_FILE=32*1024*1024
MAX_TOTAL=256*1024*1024
MAX_MEMBERS=10000
TABLES={'events','settings','auto_repairs','auto_delivery'}


def timestamp():return datetime.now(timezone.utc).isoformat()


def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):result.update(block)
    return result.hexdigest()


def atomic_json(path,data,mode):
    fd,temporary=tempfile.mkstemp(prefix='.status-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(data,stream,ensure_ascii=False,indent=2);stream.write('\n')
            stream.flush();os.fsync(stream.fileno())
        os.chmod(temporary,mode);os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def secure(path,directory=False):
    information=path.lstat()
    expected=stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(information.st_mode) or information.st_uid!=0 or information.st_mode & 0o022:
        raise ValueError('Unsafe source or storage: '+str(path))
    return information


def copy_regular(source,target):
    import grp
    import pwd
    information=secure(source)
    if information.st_size>MAX_FILE:raise ValueError('Source exceeds file limit: '+str(source))
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        opened=os.fstat(fd)
        if (opened.st_ino,opened.st_dev)!=(information.st_ino,information.st_dev):
            raise ValueError('Source changed before read')
        with os.fdopen(fd,'rb',closefd=False) as incoming,target.open('xb') as outgoing:
            shutil.copyfileobj(incoming,outgoing,1024*1024)
        after=os.fstat(fd)
        if (opened.st_size,opened.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise ValueError('Source changed during read')
    finally:os.close(fd)
    os.chmod(target,information.st_mode & 0o777)
    return {'source':str(source),'uid':information.st_uid,'gid':information.st_gid,
            'owner':pwd.getpwuid(information.st_uid).pw_name,'group':grp.getgrgid(information.st_gid).gr_name,
            'mode':information.st_mode & 0o777,'mtime_ns':information.st_mtime_ns,
            'size':target.stat().st_size,'sha256':digest(target)}


def sources():
    selected=set()
    optional=tuple(path for path in (Path('/etc/letsencrypt/accounts'),Path('/etc/letsencrypt/archive'),Path('/etc/letsencrypt/renewal')) if path.exists())
    for directory in DIRECTORIES+optional:
        secure(directory,directory=True)
        for root,dirs,files in os.walk(directory,followlinks=False):
            base=Path(root);secure(base,directory=True)
            dirs[:]=[name for name in dirs if name!='__pycache__']
            for name in dirs:secure(base/name,directory=True)
            for name in files:
                if not name.endswith(('.pyc','.pyo')):selected.add(base/name)
    for path in REQUIRED_FILES:
        # os-release is commonly an OS-managed symlink. Store its resolved file
        # contents at the conventional name, with the real source in the manifest.
        selected.add(path.resolve(strict=True) if path==Path('/etc/os-release') else path)
    raid_env=Path('/etc/kiagent-docker/deployment.env').read_text()
    raid_required=any(line.startswith('KIAGENT_RAID_DEVICES=') and line.split('=',1)[1].strip() for line in raid_env.splitlines())
    for path in OPTIONAL_RAID_FILES:
        if path.exists() or raid_required:selected.add(path)
    for path in (Path('/etc/nginx/sites-available/kiagent-config'),Path('/etc/letsencrypt/cli.ini')):
        if path.exists():selected.add(path)
    systemd=Path('/etc/systemd/system')
    for pattern in ('kiagent*.service','kiagent*.timer','kiagent*.service.d/*.conf','kiagent*.timer.d/*.conf'):
        selected.update(systemd.glob(pattern))
    return sorted(selected,key=str)


def online_database(source,target):
    started=time.monotonic()
    def progress(*args):
        if time.monotonic()-started>40:raise TimeoutError('SQLite backup time limit')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=5)) as live:
        live.execute('PRAGMA query_only=ON')
        with closing(sqlite3.connect(target)) as saved:
            live.backup(saved,pages=128,progress=progress,sleep=0.1)
    os.chmod(target,0o600)


def database_check(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)) as connection:
        connection.execute('PRAGMA query_only=ON')
        if connection.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:
            raise ValueError('SQLite integrity failure')
        available={row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not TABLES<=available:raise ValueError('Expected database tables missing')
        if connection.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Foreign key failure')
        return {name:connection.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in sorted(TABLES)}


def package_metadata():
    packages=[]
    lock=Path('/opt/kiagent-docker/project/requirements.lock')
    secure(lock)
    for line in lock.read_text().splitlines():
        if line.strip():
            name,version=line.split()[0].split('==',1)
            packages.append({'name':name,'version':version,'source':'container-lock'})
    links=[]
    for path in sorted(Path('/etc/systemd/system').glob('*.target.wants/kiagent*')):
        if path.is_symlink():links.append({'path':str(path),'target':os.readlink(path)})
    return {'python':sys.version,'platform':platform.platform(),'packages':packages,'enabled_links':links}


RECOVERY='''KIAGENT BACKUP - RECOVERY NOTES

This archive contains credentials. Keep the archive and extracted data root-only.
The automated test extracts into a private scratch directory, checks all hashes,
parses Python sources and runs SQLite integrity checks. It never overwrites live
files, starts restored code or proves a complete new-server deployment.

For an actual recovery, review manifest.json, metadata/packages.json and the saved
unit files first. Recreate service users/groups and a compatible Ubuntu/Python
environment. Clone the private Docker project and rebuild its pinned Dockerfile
using requirements.lock. Container images and virtual environments are not included.

Stop only the relevant kiagent services before replacing live code or the audit
database. Restore files under payload/files to reviewed original paths, applying
the original owner/group/mode recorded in the manifest. Restore the consistent
database/history.sqlite3 snapshot to /var/lib/kiagent-executor/history.sqlite3,
root-owned and mode 0600. Preserve its settings and automatic-repair history.

Review systemd units and enabled-links metadata; daemon-reload and verify service
status before enabling operation. Do not blindly restore mdadm.conf to different
hardware. No block-device/RAID member metadata, SSH configuration, SSH private
keys, or complete operating-system image is included.
'''


def build_payload(stage):
    payload=stage/'payload';payload.mkdir(mode=0o700)
    records={};total=0
    selected=sources()
    for source in selected:
        relative='files/'+source.as_posix().lstrip('/')
        records[relative]=copy_regular(source,payload/relative)
        total+=records[relative]['size']
        if total>MAX_TOTAL:raise ValueError('Backup exceeds size limit')
    secure(DATABASE)
    database=payload/'database/history.sqlite3';database.parent.mkdir(mode=0o700)
    online_database(DATABASE,database)
    database_check(database)
    records['database/history.sqlite3']={'source':str(DATABASE),'uid':0,'gid':0,'owner':'root','group':'root','mode':0o600,
        'size':database.stat().st_size,'sha256':digest(database)}
    metadata=payload/'metadata';metadata.mkdir(mode=0o700)
    atomic_json(metadata/'packages.json',package_metadata(),0o600)
    (metadata/'RECOVERY.txt').write_text(RECOVERY,encoding='utf-8')
    os.chmod(metadata/'RECOVERY.txt',0o600)
    for name in ('packages.json','RECOVERY.txt'):
        path=metadata/name
        records['metadata/'+name]={'source':None,'uid':0,'gid':0,'mode':0o600,
            'size':path.stat().st_size,'sha256':digest(path)}
    # Recheck source metadata so a simultaneous deployment cannot silently produce
    # a mixed collection of mutable code/configuration files.
    for relative,record in records.items():
        if not relative.startswith('files/'):continue
        current=Path(record['source']).lstat()
        if current.st_size!=record['size'] or current.st_mtime_ns!=record['mtime_ns']:
            raise ValueError('Source changed during collection')
    if sources()!=selected:raise ValueError('Source inventory changed during collection')
    manifest={'format':'kiagent-local-backup-v1','created_utc':timestamp(),'files':records,
              'credentials_included':True,'virtual_environment_included':False}
    atomic_json(payload/'manifest.json',manifest,0o600)
    return payload


def create_archive(payload,archive):
    with tarfile.open(archive,'w:gz',format=tarfile.PAX_FORMAT) as output:
        output.add(payload,arcname='payload',recursive=True)
    os.chmod(archive,0o600)


def verify_archive(archive,parent):
    parent=parent.resolve()
    with tempfile.TemporaryDirectory(prefix='restore-',dir=parent) as temporary:
        restore=Path(temporary)
        if not restore.resolve().is_relative_to(parent):raise ValueError('Unsafe restore directory')
        with tarfile.open(archive,'r:gz') as incoming:
            members=incoming.getmembers()
            if len(members)>MAX_MEMBERS:raise ValueError('Too many archive members')
            names=set();size=0
            for member in members:
                name=PurePosixPath(member.name)
                if name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0]!='payload':
                    raise ValueError('Unsafe archive path')
                if member.name in names:raise ValueError('Duplicate archive path')
                names.add(member.name)
                if not (member.isdir() or member.isfile()):raise ValueError('Links/special files are not permitted')
                if member.size>MAX_FILE:raise ValueError('Oversized archive member')
                size+=member.size
                if size>MAX_TOTAL:raise ValueError('Oversized archive')
            incoming.extractall(restore,filter='data')
        payload=restore/'payload'
        manifest=json.loads((payload/'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('format')!='kiagent-local-backup-v1':raise ValueError('Unknown backup format')
        records=manifest['files']
        actual={path.relative_to(payload).as_posix() for path in payload.rglob('*') if path.is_file()}
        if actual!=set(records)|{'manifest.json'}:raise ValueError('Archive inventory mismatch')
        python_files=0
        for relative,record in records.items():
            name=PurePosixPath(relative)
            if name.is_absolute() or '..' in name.parts:raise ValueError('Unsafe manifest path')
            path=payload/relative
            if path.stat().st_size!=record['size'] or digest(path)!=record['sha256']:
                raise ValueError('File hash or size mismatch')
            if path.suffix=='.py' and '.before-' not in path.name:
                ast.parse(path.read_text(encoding='utf-8'));python_files+=1
        counts=database_check(payload/'database/history.sqlite3')
        return {'verified_files':len(records),'python_sources_parsed':python_files,
                'database_integrity':'ok','database_table_rows':counts}


def update_status(result):
    previous={}
    if STATUS.exists():
        try:previous=json.loads(STATUS.read_text())
        except (OSError,ValueError):pass
    if result['result']=='success':result['last_success']=result['checked_utc']
    elif previous.get('last_success'):result['last_success']=previous['last_success']
    atomic_json(STATUS,result,0o644)


def run_backup():
    if os.geteuid()!=0:raise SystemExit('Backup requires root.')
    for path in (BACKUPS,STATE,WORK):secure(path,directory=True)
    if BACKUPS.stat().st_mode & 0o077 or WORK.stat().st_mode & 0o077:
        raise SystemExit('Private backup/work directory permissions required.')
    if shutil.disk_usage(BACKUPS).free<1024**3:raise SystemExit('Less than 1 GiB free; backup not started.')
    stage_name='collect'
    temporary_archive=None
    try:
        with tempfile.TemporaryDirectory(prefix='backup-',dir=WORK) as temporary:
            stage=Path(temporary)
            if not stage.resolve().is_relative_to(WORK.resolve()):raise ValueError('Unsafe staging directory')
            payload=build_payload(stage)
            name='kiagent-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'.tar.gz'
            temporary_archive=BACKUPS/('.'+name+'.partial')
            stage_name='archive';create_archive(payload,temporary_archive)
            stage_name='isolated_restore';verification=verify_archive(temporary_archive,WORK)
            archive=BACKUPS/name;os.replace(temporary_archive,archive);temporary_archive=None
            result={'result':'success','checked_utc':timestamp(),'archive':name,
                    'archive_bytes':archive.stat().st_size,'archive_sha256':digest(archive),
                    'root_only':(archive.stat().st_mode & 0o077)==0,**verification}
            update_status(result)
            print(json.dumps(result),flush=True)
    except Exception as error:
        result={'result':'failed','checked_utc':timestamp(),'stage':stage_name,'error_type':type(error).__name__}
        if type(error) is ValueError:result['error_detail']=str(error)
        update_status(result);print(json.dumps(result),flush=True)
        raise SystemExit(1)
    finally:
        if temporary_archive is not None and temporary_archive.exists():temporary_archive.unlink()


def self_test():
    base=Path.cwd()/'work'
    if not base.is_dir():base=Path(tempfile.gettempdir())
    with tempfile.TemporaryDirectory(prefix='backup-test-',dir=base) as temporary:
        root=Path(temporary)
        if not root.resolve().is_relative_to(base.resolve()):raise ValueError('Unsafe test directory')
        payload=root/'payload';payload.mkdir()
        db=payload/'database/history.sqlite3';db.parent.mkdir()
        source=root/'live.sqlite3'
        with closing(sqlite3.connect(source)) as connection:
            connection.executescript('CREATE TABLE events(id INTEGER PRIMARY KEY); CREATE TABLE settings(name TEXT,value TEXT); CREATE TABLE auto_repairs(id INTEGER PRIMARY KEY,result TEXT); CREATE TABLE auto_delivery(run_id INTEGER,user_id INTEGER);')
            connection.execute("INSERT INTO settings VALUES ('auto_enabled','true')")
            connection.execute("INSERT INTO auto_repairs VALUES (1,'success')");connection.commit()
            online_database(source,db)
            assert connection.execute('SELECT COUNT(*) FROM auto_repairs').fetchone()[0]==1
        code=payload/'files/opt/kiagent/app/bot.py';code.parent.mkdir(parents=True)
        code.write_text('value = 1\n',encoding='utf-8')
        records={str(path.relative_to(payload).as_posix()):{'size':path.stat().st_size,'sha256':digest(path)} for path in (db,code)}
        atomic_json(payload/'manifest.json',{'format':'kiagent-local-backup-v1','files':records},0o600)
        archive=root/'good.tar.gz';create_archive(payload,archive)
        restored=verify_archive(archive,root)
        assert restored['verified_files']==2 and restored['database_integrity']=='ok'
        code.write_text('value = 2\n',encoding='utf-8');create_archive(payload,root/'tampered.tar.gz')
        try:verify_archive(root/'tampered.tar.gz',root)
        except ValueError:pass
        else:raise AssertionError('Tampering not detected')
        for label,name,kind in (('traversal','../escape',tarfile.REGTYPE),('symlink','payload/link',tarfile.SYMTYPE)):
            bad=root/(label+'.tar.gz')
            with tarfile.open(bad,'w:gz') as output:
                item=tarfile.TarInfo(name);item.type=kind
                if kind==tarfile.SYMTYPE:item.linkname='/etc/passwd'
                output.addfile(item,io.BytesIO(b''))
            try:verify_archive(bad,root)
            except ValueError:pass
            else:raise AssertionError('Unsafe archive accepted')
        assert not (base/'escape').exists()
    print('Backup tests passed: online SQLite snapshot, isolated restore, hashes, tampering and unsafe paths/links.')


def main():
    if sys.argv[1:]==['--self-test']:self_test();return
    if sys.argv[1:]==['--run']:run_backup();return
    if len(sys.argv)==3 and sys.argv[1]=='--verify':
        if os.geteuid()!=0:raise SystemExit('Verification requires root.')
        archive=Path(sys.argv[2]).resolve(strict=True)
        if archive.parent!=BACKUPS.resolve() or archive.suffixes[-2:]!=['.tar','.gz']:
            raise SystemExit('Only archives in the private backup directory may be verified.')
        secure(archive)
        print(json.dumps(verify_archive(archive,WORK)));return
    raise SystemExit('Use --self-test, --run, or --verify <private archive>.')


if __name__=='__main__':main()
