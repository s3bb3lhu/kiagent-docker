import os
import urllib.request
from urllib.parse import urlsplit
origin = os.environ.get('CONFIG_ORIGIN','http://127.0.0.1:8787')
request = urllib.request.Request('http://127.0.0.1:8080/health',headers={'Host':urlsplit(origin).netloc})
try:
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=5) as response:
        ok = response.status == 200
except Exception:
    ok = False
raise SystemExit(0 if ok else 1)
