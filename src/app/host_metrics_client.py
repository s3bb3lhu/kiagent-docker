"""Fixed host metrics operation; no paths or commands can be supplied."""
import json
import socket
import threading
import time
_lock = threading.Lock()
_cached = None
_updated = 0.0

def snapshot():
    global _cached, _updated
    with _lock:
        if _cached is not None and time.monotonic() - _updated < 1:
            return _cached
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(10)
            sock.connect('/run/kiagent-executor/control.sock')
            sock.sendall(b'{"op":"metrics"}\n')
            raw = bytearray()
            while b'\n' not in raw and len(raw) < 24000:
                block = sock.recv(4096)
                if not block:
                    break
                raw.extend(block)
            if not raw.endswith(b'\n') or len(raw) >= 24000:
                raise ValueError('Invalid host metrics response')
            reply = json.loads(raw)
            if reply.get('ok') is not True or reply.get('kind') != 'host_metrics_v1':
                raise ValueError('Host metrics unavailable')
            data = reply['data']
            required = {'ram_total_mib','ram_available_mib','cpu_count','load_1_5_15_minutes','root_disk_total_gib','root_disk_used_percent','uptime_seconds','raid','raid_status','failed_services'}
            if not isinstance(data, dict) or not required <= data.keys():
                raise ValueError('Incomplete host metrics')
            _cached, _updated = data, time.monotonic()
            return data
