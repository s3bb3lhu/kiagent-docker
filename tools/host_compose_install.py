#!/usr/bin/env python3
"""Fixed host-side sequence launched by the one-shot Compose installer."""
import argparse
import hashlib
import ipaddress
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_web import SOURCE,PROJECT,CONFIG,atomic
from install_https import origin_for,web_port
MARKER=CONFIG/'compose-install.json'

def marker_read():
    info=MARKER.lstat()
    if MARKER.is_symlink() or info.st_uid!=0 or info.st_mode & 0o077:raise ValueError('Unsicherer Installationsnachweis.')
    data=json.loads(MARKER.read_text())
    if data.get('kind')!='compose-host-install-v1':raise ValueError('Unbekannter Installationsnachweis.')
    for name in ('tools/host_compose_install.py','tools/install_https.py'):
        if hashlib.sha256((SOURCE/name).read_bytes()).digest()!=hashlib.sha256((PROJECT/name).read_bytes()).digest():raise ValueError('Installierter Quellstand weicht ab; keine automatische Netzwerkwiederholung.')
    return data

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--address',required=True);parser.add_argument('--admin-ip',required=True);parser.add_argument('--port',type=web_port,default=8443);parser.add_argument('--resume-network',action='store_true');args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('Host-Installation benoetigt root.')
    address=str(ipaddress.IPv4Address(args.address));admin=str(ipaddress.ip_address(args.admin_ip));origin=origin_for(address,args.port)
    if not ipaddress.ip_address(address).is_global:raise ValueError('Oeffentliche IPv4-Adresse erforderlich.')
    if args.resume_network:
        state=marker_read()
        if state['origin']!=origin or state['admin_ip']!=admin:raise ValueError('Wiederaufnahme nur mit denselben Netzwerkparametern.')
        if state.get('network_ready'):print('Bereits eingerichtet: '+origin);return
    else:
        if PROJECT.exists() or CONFIG.exists():raise SystemExit('Bestehende Installation wird nicht ueberschrieben.')
        listeners=subprocess.check_output(['/usr/bin/ss','-H','-lnt'],text=True)
        if any(line.split()[3].endswith((':80',':'+str(args.port),':8787')) for line in listeners.splitlines()):raise SystemExit('Ein benoetigter Port ist belegt. Keine Installation gestartet.')
        if Path('/etc/nginx').exists():raise SystemExit('Bestehende nginx-Installation zuerst pruefen. Keine automatische Uebernahme.')
        # Only internal session material is generated; provider credentials come from the browser.
        subprocess.run(['/usr/bin/python3','-I','-B',str(SOURCE/'tools/install_browser_host.py')],check=True)
        state={'kind':'compose-host-install-v1','origin':origin,'admin_ip':admin,'network_ready':False}
        atomic(MARKER,(json.dumps(state)+'\n').encode(),0o600)
    try:
        subprocess.run(['/usr/bin/python3','-I','-B',str(PROJECT/'tools/install_https.py'),'--address',address,'--admin-ip',admin,'--port',str(args.port)],check=True)
    except BaseException:
        print('Die Web-Grundinstallation ist vorhanden; Bots warten weiter auf Browser-Einrichtung. HTTPS ist nicht abgeschlossen. Nach Pruefung: denselben Compose-Installer mit --resume-network starten.')
        raise
    state['network_ready']=True;atomic(MARKER,(json.dumps(state)+'\n').encode(),0o600)
    print('Vollinstallation bereit: '+origin+'/setup')
    print('Dort Passwort festlegen und danach Dienst-IDs sowie API-Keys/Bot-Tokens eingeben. Erst nach erfolgreicher Pruefung werden Bots und Host-Aktionen aktiviert.')
    print('Runtime: docker compose --env-file /etc/kiagent-docker/deployment.env -f /opt/kiagent-docker/project/compose.yaml ps')

if __name__=='__main__':main()
