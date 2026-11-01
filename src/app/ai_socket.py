"""Bounded local AI IPC; no network address or credential supplied by clients."""
import json
import socket
SOCKET='/run/kiagent-ai/control.sock'

def request(data,timeout=5):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(timeout);connection.connect(SOCKET)
        raw=json.dumps(data,ensure_ascii=True).encode()+b'\n'
        if len(raw)>32768:raise ValueError('AI request too large')
        connection.sendall(raw);response=bytearray()
        while b'\n' not in response:
            chunk=connection.recv(4096)
            if not chunk or len(response)+len(chunk)>65536:raise ValueError('Invalid AI response')
            response.extend(chunk)
        result=json.loads(response)
        if not result.get('ok'):raise RuntimeError(result.get('code','ai_unavailable'))
        return result
