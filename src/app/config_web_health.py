import os
import socket
import ssl
import urllib.request
from urllib.parse import urlsplit
origin = os.environ.get('CONFIG_ORIGIN','http://127.0.0.1:8787')
request = urllib.request.Request('http://127.0.0.1:8080/health',headers={'Host':urlsplit(origin).netloc})
try:
    if os.environ.get('CONFIG_DIRECT_TLS')=='1':
        context=ssl.create_default_context(cafile='/run/kiagent-tls/fullchain.pem')
        context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
        with socket.create_connection(('127.0.0.1',8080),timeout=5) as raw:
            with context.wrap_socket(raw,server_hostname=urlsplit(origin).hostname) as connection:
                connection.sendall(('GET /health HTTP/1.1\r\nHost: '+urlsplit(origin).netloc+'\r\nConnection: close\r\n\r\n').encode())
                ok=connection.recv(4096).split(b'\r\n',1)[0].split()[1]==b'200'
    else:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=5) as response:
            ok = response.status == 200
except Exception:
    ok = False
raise SystemExit(0 if ok else 1)
