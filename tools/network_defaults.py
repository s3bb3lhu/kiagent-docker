"""Discover installation addresses without asking for or persisting user input."""
import ipaddress
import json
import subprocess

def ip(value):
    address=ipaddress.ip_address(value)
    if address.is_unspecified or address.is_multicast or address.is_loopback:
        raise ValueError('Keine verwendbare Netzwerkadresse.')
    return str(address)

def discover(connection='',run=subprocess.check_output):
    peer=server=None
    fields=connection.split()
    if fields:
        if len(fields)!=4:raise ValueError('Ungueltige SSH-Verbindungsdaten.')
        peer=ip(fields[0]);server=ip(fields[2])
        if not all(value.isdigit() and 0<int(value)<65536 for value in (fields[1],fields[3])):
            raise ValueError('Ungueltige SSH-Verbindungsdaten.')
    if peer is None:
        # Root reads the host login database, including when sudo removed SSH_CONNECTION.
        peers=set()
        for line in run(['/usr/bin/who','--ips'],text=True,timeout=10).splitlines():
            last=line.split()[-1] if line.split() else ''
            if last.startswith('(') and last.endswith(')'):
                try:peers.add(ip(last[1:-1]))
                except ValueError:pass
        if len(peers)!=1:
            raise ValueError('Ersteinrichtung nicht eindeutig zuordenbar. Installation aus einer einzigen direkten SSH-Sitzung starten; Browser und SSH muessen denselben Internetzugang verwenden. Keine Dateien geaendert.')
        peer=peers.pop()
    if server is None or ipaddress.ip_address(server).version!=4 or not ipaddress.ip_address(server).is_global:
        candidates=set()
        for interface in json.loads(run(['/usr/sbin/ip','-j','-4','address','show','scope','global'],text=True,timeout=10)):
            for entry in interface.get('addr_info',[]):
                value=entry.get('local','')
                try:
                    address=ipaddress.IPv4Address(value)
                    if address.is_global:candidates.add(str(address))
                except ValueError:pass
        if len(candidates)!=1:
            raise ValueError('Keine eindeutige oeffentliche IPv4-Adresse erkannt. Dieser automatische Installationsweg benoetigt einen direkt erreichbaren Server ohne NAT. Keine Dateien geaendert.')
        server=candidates.pop()
    return server,peer
