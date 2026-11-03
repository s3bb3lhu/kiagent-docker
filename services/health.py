"""Local HTTPS liveness without disabling certificate validation."""
import os
import socket
import ssl
from urllib.parse import urlsplit
origin=urlsplit(os.environ['SERVICES_ORIGIN'])
context=ssl.create_default_context()
context.load_verify_locations('/run/services-tls/fullchain.pem')
with socket.create_connection(('127.0.0.1',8080),timeout=4) as plain:
    with context.wrap_socket(plain,server_hostname=origin.hostname) as connection:
        connection.sendall(('GET /health HTTP/1.1\r\nHost: '+origin.netloc+'\r\nConnection: close\r\n\r\n').encode())
        result=connection.makefile('rb').read(32768)
assert b'200 OK' in result and b'"ok":true' in result
