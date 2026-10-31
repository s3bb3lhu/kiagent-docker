"""Bounded read-only host telemetry with rate deltas; no external IP service."""
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

class Telemetry:
    def __init__(self):self.previous=None;self.cached=None;self.at=0
    def read(self):
        now=time.monotonic()
        if self.cached and now-self.at<2:return self.cached
        cpu=[int(x) for x in Path('/proc/stat').read_text().splitlines()[0].split()[1:9]]
        counters={}
        for line in Path('/proc/net/dev').read_text().splitlines()[2:]:
            name,values=line.split(':',1);name=name.strip();values=values.split()
            if name!='lo' and not name.startswith(('veth','br-','docker')):
                counters[name]=(int(values[0]),int(values[8]))
        percent=None;net=[]
        for name,(rx,tx) in counters.items():
            previous=self.previous[2].get(name) if self.previous else None
            elapsed=now-self.previous[0] if self.previous else 0
            net.append({'name':name,'received_bytes':rx,'sent_bytes':tx,
                        'receive_bps':max(0,(rx-previous[0])/elapsed) if previous and elapsed>0 else None,
                        'send_bps':max(0,(tx-previous[1])/elapsed) if previous and elapsed>0 else None})
        if self.previous:
            old=self.previous[1];total=sum(cpu)-sum(old);idle=cpu[3]+cpu[4]-old[3]-old[4]
            if total>0:percent=round(max(0,min(100,100*(total-idle)/total)),1)
        self.previous=(now,cpu,counters)
        memory={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))}
        disks=[]
        try:
            output=subprocess.check_output(['/usr/bin/findmnt','--json','--list','--real','--output','TARGET,SOURCE,FSTYPE'],timeout=3,text=True)
            seen=set()
            for row in sorted(json.loads(output).get('filesystems',[]),key=lambda row:len(row.get('target') or ''))[:96]:
                if row['fstype'] in {'overlay','squashfs','tmpfs','devtmpfs'}:continue
                try:
                    device=os.stat(row['target']).st_dev
                    if device in seen:continue
                    seen.add(device)
                    disk=shutil.disk_usage(row['target'])
                    disks.append({'mount':row['target'],'device':row['source'],'filesystem':row['fstype'],
                                  'total_bytes':disk.total,'used_bytes':disk.used,'free_bytes':disk.free,
                                  'used_percent':round(100*disk.used/disk.total,1) if disk.total else 0})
                except OSError:pass
        except (OSError,ValueError,subprocess.SubprocessError):pass
        addresses=[]
        devices=[]
        try:
            listing=json.loads(subprocess.check_output(['/usr/bin/lsblk','--json','--bytes','--nodeps','--output','NAME,SIZE,TYPE,MODEL'],timeout=3,text=True))
            devices=[{'name':'/dev/'+d['name'],'model':d.get('model') or '', 'total_bytes':int(d['size'])} for d in listing.get('blockdevices',[])[:64] if d.get('type')=='disk']
        except (OSError,ValueError,subprocess.SubprocessError):pass
        try:
            for row in json.loads(subprocess.check_output(['/usr/sbin/ip','-j','address','show'],timeout=3,text=True)):
                if row.get('ifname') in counters:
                    for value in row.get('addr_info',[]):
                        if value.get('scope')=='global':addresses.append({'interface':row['ifname'],'address':value['local'],'family':value['family']})
        except (OSError,ValueError,subprocess.SubprocessError):pass
        self.cached={'available':True,'scope':'host','sampled_at':time.time(),'hostname':socket.gethostname(),
                     'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                     'uptime_seconds':int(float(Path('/proc/uptime').read_text().split()[0])),
                     'cpu_percent':percent,'cpu_count':os.cpu_count(),'load':list(os.getloadavg()),
                     'memory':{'total_bytes':memory['MemTotal'],'available_bytes':memory['MemAvailable'],
                               'used_bytes':memory['MemTotal']-memory['MemAvailable'],
                               'used_percent':round(100*(1-memory['MemAvailable']/memory['MemTotal']),1)},
                     'disks':disks,'devices':devices,'network':net,'addresses':addresses}
        self.at=now
        return self.cached
