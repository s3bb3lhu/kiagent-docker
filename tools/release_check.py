#!/usr/bin/env python3
"""Offline release checks, no credentials, deployment, GitHub writes or live actions."""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/app'))
from release_version import VERSION

def main():
    assert re.fullmatch(r'\d+\.\d+\.\d+\.\d+',VERSION)
    assert (ROOT/'VERSION').read_text().strip()==VERSION
    if (ROOT/'installer-manifest.json').exists():
        assert json.loads((ROOT/'installer-manifest.json').read_text())=={'kind':'server-control-first-install','protocol':1,'version':VERSION}
    for name in ('Dockerfile','Dockerfile.portable','Dockerfile.installer'):
        assert 'org.opencontainers.image.version="'+VERSION+'"' in (ROOT/name).read_text()
    for path in ROOT.rglob('*.py'):
        if '.git' not in path.parts:ast.parse(path.read_text(encoding='utf-8'),filename=str(path.relative_to(ROOT)))
    subprocess.run([sys.executable,'-B',str(ROOT/'tools/scan_secrets.py')],check=True)
    subprocess.run([sys.executable,'-B',str(ROOT/'tools/export_docs.py'),'--check'],check=True)
    print('Release source checks: OK · '+VERSION)
    print('No tag, release or visibility change performed.')
if __name__=='__main__':main()
