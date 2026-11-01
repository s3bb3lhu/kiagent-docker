import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import latest_release as release

def archive(files,commit='a'*40,extra=()):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz') as stream:
        for name,value in files.items():
            content=value.encode();member=tarfile.TarInfo('kiagent-docker-'+commit+'/'+name);member.size=len(content)
            stream.addfile(member,io.BytesIO(content))
        for member in extra:stream.addfile(member)
    return output.getvalue()

def files(version='9.8.7.6',protocol=1):
    return {'VERSION':version+'\n','Dockerfile':'fixture\n','compose.runtime.yaml':'fixture\n',
      'tools/host_compose_install.py':'# fixture\n','tools/release_check.py':'# fixture\n','src/app/release_version.py':'VERSION='+repr(version)+'\n',
      'installer-manifest.json':json.dumps({'kind':'server-control-first-install','protocol':protocol,'version':version})}

def getter(data,version='9.8.7.6',commit='a'*40,prerelease=False):
    def get(url,limit):
        if url.endswith('/releases/latest'):return json.dumps({'tag_name':'v'+version,'draft':False,'prerelease':prerelease}).encode()
        if '/git/ref/tags/' in url:return json.dumps({'object':{'type':'commit','sha':commit}}).encode()
        if url.endswith('/'+commit):return data
        raise AssertionError('Unexpected request')
    return get

class LatestReleaseTests(unittest.TestCase):
    def test_latest_api_version_wins_over_local_payload(self):
        with release.source(get=getter(archive(files()))) as selected:
            self.assertEqual(selected['metadata']['version'],'9.8.7.6')
            self.assertEqual((selected['path']/'VERSION').read_text().strip(),'9.8.7.6')
            self.assertEqual(selected['metadata']['commit'],'a'*40)
            path=selected['path']
        self.assertFalse(path.exists())

    def test_prerelease_is_never_installed(self):
        with self.assertRaises(ValueError):
            with release.source(get=getter(archive(files()),prerelease=True)):pass

    def test_tag_and_version_must_match(self):
        with self.assertRaises(ValueError):
            with release.source(get=getter(archive(files('8.0.0.0')))):pass

    def test_unknown_install_protocol_is_rejected(self):
        with self.assertRaises(ValueError):
            with release.source(get=getter(archive(files(protocol=2)))):pass

    def test_archive_links_and_escape_paths_are_rejected(self):
        for name,kind in (('../escape',tarfile.REGTYPE),('link',tarfile.SYMTYPE)):
            member=tarfile.TarInfo('kiagent-docker-'+'a'*40+'/'+name);member.type=kind;member.linkname='/etc/passwd'
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):release.unpack(archive({},extra=[member]),Path(directory),'a'*40)

    def test_known_old_release_only_adapts_install_helpers(self):
        entries=files('1.3.0.1');entries.pop('installer-manifest.json');entries['compose.yaml']=entries.pop('compose.runtime.yaml')
        with release.source(get=getter(archive(entries,release.LEGACY_COMMIT),'1.3.0.1',release.LEGACY_COMMIT)) as selected:
            self.assertEqual((selected['path']/'src/app/release_version.py').read_text(),entries['src/app/release_version.py'])
            self.assertEqual(set(selected['metadata']['installer_adapter']),{'tools/install_browser_host.py','tools/host_compose_install.py','tools/parallel_https.py'})

    def test_unknown_old_commit_never_receives_compatibility_overlay(self):
        entries=files('1.3.0.1');entries.pop('installer-manifest.json')
        with self.assertRaises(ValueError):
            with release.source(get=getter(archive(entries),'1.3.0.1')):pass

    def test_download_hosts_are_fixed_and_https_only(self):
        for url in ('http://api.github.com/a','https://evil.invalid/a','https://api.github.com@evil.invalid/a','https://api.github.com:444/a'):
            self.assertFalse(release.allowed(url))
        self.assertTrue(release.allowed('https://codeload.github.com/s3bb3lhu/kiagent-docker/tar.gz/'+'a'*40))

if __name__=='__main__':unittest.main()
