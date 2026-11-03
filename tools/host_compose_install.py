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
from network_defaults import discover
import parallel_https
MARKER=CONFIG/'compose-install.json'

def marker_read():
    info=MARKER.lstat()
    if MARKER.is_symlink() or info.st_uid!=0 or info.st_mode & 0o077:raise ValueError('Unsicherer Installationsnachweis.')
    data=json.loads(MARKER.read_text())
    if data.get('kind')!='compose-host-install-v1':raise ValueError('Unbekannter Installationsnachweis.')
    for name in ('tools/host_compose_install.py','tools/install_https.py','tools/parallel_https.py'):
        if hashlib.sha256((SOURCE/name).read_bytes()).digest()!=hashlib.sha256((PROJECT/name).read_bytes()).digest():raise ValueError('Installierter Quellstand weicht ab; keine automatische Netzwerkwiederholung.')
    return data

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--address');parser.add_argument('--admin-ip');parser.add_argument('--ssh-connection',default='');parser.add_argument('--port',type=web_port,default=9898);parser.add_argument('--resume-network',action='store_true');parser.add_argument('--install-owner');args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('Host-Installation benoetigt root.')
    # nsenter may inherit a cwd outside the host root. Resolve a real host cwd now.
    os.chdir('/')
    if args.resume_network:
        prior=marker_read();address=prior['address'];admin=prior['admin_ip']
        args.port=prior.get('port',args.port)
    elif args.address and args.admin_ip:address,admin=args.address,args.admin_ip
    else:address,admin=discover(args.ssh_connection)
    address=str(ipaddress.IPv4Address(address));admin=str(ipaddress.ip_address(admin));origin=origin_for(address,args.port)
    if not ipaddress.ip_address(address).is_global:raise ValueError('Oeffentliche IPv4-Adresse erforderlich.')
    if args.resume_network:
        state=marker_read()
        if state['origin']!=origin or state['admin_ip']!=admin:raise ValueError('Wiederaufnahme nur mit denselben Netzwerkparametern.')
        if state.get('network_ready'):print('Bereits eingerichtet: '+origin);return
    else:
        if PROJECT.exists() or CONFIG.exists():raise SystemExit('Bestehende Installation wird nicht ueberschrieben.')
        listeners=subprocess.check_output(['/usr/bin/ss','-H','-lnt'],text=True)
        certificate=parallel_https.discover(address,required=False)
        parallel=certificate is not None or Path('/etc/nginx').exists() or any(line.split()[3].endswith((':80',':'+str(args.port),':8787')) for line in listeners.splitlines())
        if parallel and certificate is None:raise ValueError('Vorhandener Webserver ohne geeignetes IP-Zertifikat. Keine fremde Konfiguration wird zur Zertifikatsausstellung veraendert.')
        loopback=parallel_https.free_port(18787,host='127.0.0.1') if parallel else 8787
        if parallel:
            args.port=parallel_https.free_port(max(9443,args.port),excluded=(loopback,8787))
            origin=origin_for(address,args.port)
            print('Parallelbetrieb: eigener HTTPS-Port '+str(args.port)+'. Vorhandene Dienste bleiben unveraendert.')
        # Only internal session material is generated; provider credentials come from the browser.
        command=['/usr/bin/python3','-I','-B',str(SOURCE/'tools/install_browser_host.py'),'--loopback-port',str(loopback)]
        if args.install_owner:command+=['--install-owner',args.install_owner]
        subprocess.run(command,check=True)
        state={'kind':'compose-host-install-v1','origin':origin,'address':address,'admin_ip':admin,'port':args.port,'parallel':parallel,'loopback_port':loopback,'certificate':certificate,'network_ready':False}
        atomic(MARKER,(json.dumps(state)+'\n').encode(),0o600)
    try:
        if not state.get('tls_ready'):
            if state.get('parallel'):
                parallel_https.configure(address,admin,args.port,state['loopback_port'],state['certificate'])
            else:
                subprocess.run(['/usr/bin/python3','-I','-B',str(PROJECT/'tools/install_https.py'),'--address',address,'--admin-ip',admin,'--port',str(args.port),'--unattended'],check=True)
            state['tls_ready']=True;atomic(MARKER,(json.dumps(state)+'\n').encode(),0o600)
        if (PROJECT/'tools/install_ollama.py').is_file():
            subprocess.run(['/usr/bin/python3','-I','-B',str(PROJECT/'tools/install_ollama.py')],check=True)
        if (PROJECT/'tools/provision_services.py').is_file():
            subprocess.run(['/usr/bin/python3','-I','-B',str(PROJECT/'tools/provision_services.py')],check=True)
            state['services_origin']=json.loads(Path('/etc/kiagent-services/deployment.json').read_text())['origin']
    except BaseException:
        print('Die Web-Grundinstallation ist vorhanden; Bots warten weiter auf Browser-Einrichtung. HTTPS ist nicht abgeschlossen. Nach Pruefung: denselben Compose-Installer mit --resume-network starten.')
        raise
    state['network_ready']=True;atomic(MARKER,(json.dumps(state)+'\n').encode(),0o600)
    print('Vollinstallation bereit: '+origin+'/setup')
    if state.get('services_origin'):print('Dienstemanager: '+state['services_origin']+'/setup')
    print('Dort Passwort festlegen und danach Dienst-IDs sowie API-Keys/Bot-Tokens eingeben. Erst nach erfolgreicher Pruefung werden Bots und Host-Aktionen aktiviert.')
    print('Runtime: docker compose --env-file /etc/kiagent-docker/deployment.env -f /opt/kiagent-docker/project/compose.yaml ps')

if __name__=='__main__':main()
