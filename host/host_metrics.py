"""Fixed read-only host metrics; never runs in a chat container."""
import os
import re
import shutil
import subprocess
from pathlib import Path

def collect():
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        memory[key] = int(value.split()[0])
    disk = shutil.disk_usage('/')
    raid = {}
    for name in filter(None, os.environ.get('KIAGENT_RAID_DEVICES', 'md1,md2,md3,md4').split(',')):
        if re.fullmatch(r'md[0-9]+', name) is None:
            raise ValueError('Invalid configured RAID device')
        values = {}
        for field in ('degraded', 'sync_action', 'sync_completed'):
            try:
                values[field] = (Path('/sys/block') / name / 'md' / field).read_text().strip()[:160]
            except OSError:
                values[field] = 'unavailable'
        raid[name] = values
    try:
        mdstat = Path('/proc/mdstat').read_text()[:4096]
    except OSError:
        mdstat = 'unavailable'
    try:
        result = subprocess.run(['/usr/bin/systemctl', '--failed', '--no-pager', '--no-legend', '--plain', '--full', '--all', '--type=service'], capture_output=True, text=True, timeout=5, env={'PATH':'/usr/bin:/bin', 'LC_ALL':'C', 'SYSTEMD_COLORS':'0'})
        failed = {'available': result.returncode == 0, 'units': [line.split()[0] for line in result.stdout.splitlines() if line.strip()][:100] if result.returncode == 0 else []}
    except (OSError, subprocess.TimeoutExpired):
        failed = {'available': False, 'units': []}
    return {'raid': raid, 'raid_status': mdstat, 'failed_services': failed,
        'cpu_count': os.cpu_count(), 'load_1_5_15_minutes': list(os.getloadavg()),
        'ram_total_mib': round(memory['MemTotal']/1024), 'ram_available_mib': round(memory['MemAvailable']/1024),
        'root_disk_total_gib': round(disk.total/1024**3, 1), 'root_disk_used_percent': round(100*disk.used/disk.total, 1),
        'uptime_seconds': int(float(Path('/proc/uptime').read_text().split()[0]))}
