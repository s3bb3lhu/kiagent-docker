"""Fetch the latest published stable application, pinned to its release commit."""
import hashlib
import io
import json
import re
import shutil
import tarfile
import tempfile
import urllib.request
from contextlib import contextmanager
from pathlib import Path,PurePosixPath
from urllib.parse import urlsplit

REPO='s3bb3lhu/kiagent-docker'
API='https://api.github.com/repos/'+REPO
HOSTS={'api.github.com','codeload.github.com'}
MAX_ARCHIVE=16*1024*1024
MAX_SOURCE=32*1024*1024
LEGACY_COMMIT='4dacf69443bc3d48a8c49f316fb311d2360bb24c'

def allowed(url):
    parsed=urlsplit(url)
    return parsed.scheme=='https' and parsed.hostname in HOSTS and not parsed.username and not parsed.password and parsed.port in (None,443)

class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,newurl):
        if not allowed(newurl):raise ValueError('Release-Weiterleitung ausserhalb von GitHub abgewiesen.')
        return super().redirect_request(request,fp,code,message,headers,newurl)

def fetch(url,limit):
    if not allowed(url):raise ValueError('Unzulaessige Release-Adresse.')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirects())
    request=urllib.request.Request(url,headers={'User-Agent':'server-control-first-install','Accept':'application/vnd.github+json'})
    with opener.open(request,timeout=40) as response:
        if not allowed(response.geturl()):raise ValueError('Unzulaessige Release-Adresse.')
        data=response.read(limit+1)
        if len(data)>limit:raise ValueError('Release-Download zu gross.')
        return data

def resolve(get):
    release=json.loads(get(API+'/releases/latest',512*1024))
    if release.get('draft') is not False or release.get('prerelease') is not False:raise ValueError('Kein stabiler veroeffentlichter Release.')
    tag=release.get('tag_name','')
    if not re.fullmatch(r'v?\d+\.\d+\.\d+\.\d+',tag):raise ValueError('Ungueltige stabile Versionsnummer.')
    target=json.loads(get(API+'/git/ref/tags/'+tag,512*1024))['object']
    for _ in range(3):
        if target.get('type')=='commit':break
        if target.get('type')!='tag' or not re.fullmatch('[0-9a-f]{40}',target.get('sha','')):raise ValueError('Ungueltiger Release-Verweis.')
        target=json.loads(get(API+'/git/tags/'+target['sha'],512*1024))['object']
    commit=target.get('sha','')
    if target.get('type')!='commit' or not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Release-Commit nicht eindeutig.')
    return {'channel':'stable','tag':tag,'version':tag.removeprefix('v'),'commit':commit,'repository':REPO}

def unpack(data,destination,commit):
    total=0;seen=set();prefix='kiagent-docker-'+commit
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
        for number,member in enumerate(archive):
            parts=PurePosixPath(member.name).parts
            if number>=5000 or not parts or parts[0]!=prefix or '\\' in member.name or '..' in parts or '.git' in parts:raise ValueError('Unsicheres Release-Archiv.')
            if not (member.isdir() or member.isfile()):raise ValueError('Links und Spezialdateien im Release abgewiesen.')
            if not 0<=member.size<=8*1024*1024:raise ValueError('Release-Datei zu gross.')
            total+=member.size
            if total>MAX_SOURCE:raise ValueError('Entpackter Release zu gross.')
            relative=Path(*parts[1:]);path=destination/relative
            if member.isdir():path.mkdir(mode=0o700,parents=True,exist_ok=True);continue
            if relative in seen:raise ValueError('Doppelte Release-Datei.')
            seen.add(relative);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            with archive.extractfile(member) as source,path.open('xb') as output:shutil.copyfileobj(source,output)
            path.chmod(0o600)

def prepare(root,metadata,bootstrap):
    if (root/'VERSION').read_text().strip()!=metadata['version']:raise ValueError('Release-Tag und Anwendungsversion stimmen nicht ueberein.')
    manifest=root/'installer-manifest.json'
    if not manifest.exists():
        # This immutable published release predates the new first-install protocol.
        # Only bootstrap helpers are adapted; src/app and dependencies stay from the release.
        if metadata['version']!='1.3.0.1' or metadata['commit']!=LEGACY_COMMIT:raise ValueError('Aktueller Stable-Release unterstuetzt diesen Erstinstaller noch nicht.')
        shutil.copyfile(root/'compose.yaml',root/'compose.runtime.yaml')
        adapted={}
        for name in ('install_browser_host.py','host_compose_install.py','parallel_https.py'):
            source=bootstrap/'tools'/name;shutil.copyfile(source,root/'tools'/name)
            adapted['tools/'+name]=hashlib.sha256(source.read_bytes()).hexdigest()
        metadata['installer_adapter']=adapted
        manifest.write_text(json.dumps({'kind':'server-control-first-install','protocol':1,'version':metadata['version']}))
    contract=json.loads(manifest.read_text())
    if contract!={'kind':'server-control-first-install','protocol':1,'version':metadata['version']}:raise ValueError('Nicht unterstuetztes Stable-Installationsprotokoll.')
    for name in ('compose.runtime.yaml','Dockerfile','tools/host_compose_install.py','tools/release_check.py','src/app/release_version.py'):
        if not (root/name).is_file():raise ValueError('Unvollstaendiger Stable-Release.')
    (root/'release-source.json').write_text(json.dumps(metadata,sort_keys=True)+'\n')

@contextmanager
def source(get=None,bootstrap=None):
    get=get or fetch;bootstrap=bootstrap or Path(__file__).resolve().parents[1]
    metadata=resolve(get)
    url='https://codeload.github.com/'+REPO+'/tar.gz/'+metadata['commit']
    data=get(url,MAX_ARCHIVE)
    if len(data)>MAX_ARCHIVE:raise ValueError('Release-Download zu gross.')
    with tempfile.TemporaryDirectory(prefix='stable-release-') as directory:
        root=Path(directory);unpack(data,root,metadata['commit']);prepare(root,metadata,bootstrap)
        yield {'path':root,'metadata':metadata}
