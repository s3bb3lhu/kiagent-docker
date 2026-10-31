#!/usr/bin/env python3
"""Reject credential artifacts and common secret formats; never print matches."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [re.compile(r'sk-[A-Za-z0-9_-]{20,}'),
    re.compile(r'\b\d{7,12}:[A-Za-z0-9_-]{25,}\b'),
    re.compile(r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----'),
    re.compile(r'https://hc-ping\.com/[a-fA-F0-9]{8}-[a-fA-F0-9-]{27,}'),
    re.compile(r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}')]
FORBIDDEN_NAMES = {'auth.json','deployment.env','.env','discord-token','telegram-token','openai-api-key','web-admin-hash','web-session-key'}

def findings(root=ROOT):
    result = []
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if '.git' in relative.parts or '__pycache__' in relative.parts:
            continue
        if path.is_symlink():
            result.append((str(relative), 'symlink'))
            continue
        if not path.is_file():
            continue
        if (path.name in FORBIDDEN_NAMES or path.suffix in {'.key','.pem','.sqlite3','.db','.log','.whl'}
                or any(part in {'secrets','.secrets','credentials','backups'} for part in relative.parts)):
            result.append((str(relative), 'credential or runtime artifact'))
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeError:
            result.append((str(relative), 'unexpected binary file'))
            continue
        if any(pattern.search(text) for pattern in PATTERNS):
            result.append((str(relative), 'possible secret'))
    return result

if __name__ == '__main__':
    problems = findings()
    for name, reason in problems:
        print(name + ': ' + reason)
    print('Secret scan: ' + ('FAILED' if problems else 'OK'))
    raise SystemExit(1 if problems else 0)
