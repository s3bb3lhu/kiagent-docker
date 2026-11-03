"""Real TLS, browser account setup and read-only inventory on disposable CI only."""
import http.client
import json
import os
import re
import socket
import ssl
from pathlib import Path
from unittest.mock import patch
import provision_services

def exercise(source,certificate,control_port):
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.geteuid()!=0:raise RuntimeError('Disposable CI only')
    with patch.object(provision_services.parallel_https,'discover',return_value=source):origin=provision_services.activate('8.8.8.8',control_port)
    from urllib.parse import urlsplit,urlencode
    address=urlsplit(origin);cookie='';context=ssl.create_default_context(cafile=str(certificate))
    def request(path,data=None):
        nonlocal cookie
        body=urlencode(data).encode() if data is not None else b''
        headers={'Host':address.netloc,'Connection':'close'}
        if cookie:headers['Cookie']=cookie
        if data is not None:headers.update(Origin=origin,**{'Content-Type':'application/x-www-form-urlencoded','Content-Length':str(len(body))})
        packet=(('POST' if data is not None else 'GET')+' '+path+' HTTP/1.1\r\n'+''.join(k+': '+v+'\r\n' for k,v in headers.items())+'\r\n').encode()+body
        with socket.create_connection(('127.0.0.1',address.port),timeout=20) as plain:
            with context.wrap_socket(plain,server_hostname=address.hostname) as connection:
                connection.sendall(packet);response=http.client.HTTPResponse(connection);response.begin()
                if response.getheader('Set-Cookie'):cookie=response.getheader('Set-Cookie').split(';',1)[0]
                return response.status,response.read().decode(),dict(response.getheaders())
    status,page,headers=request('/setup');assert status==200 and 'name="username"' in page and 'name="code"' not in page
    assert headers.get('Referrer-Policy')=='same-origin'
    token=re.search(r'name="csrf" value="([^"]+)"',page)[1]
    assert request('/setup',{'csrf':token,'username':'ciadmin','password':'weak','confirm':'weak'})[0]==200
    assert request('/setup',{'csrf':token,'username':'ciadmin','password':'Fixture1!','confirm':'Fixture1!'})[0]==302
    status,page,_=request('/login');assert status==200
    token=re.search(r'name="csrf" value="([^"]+)"',page)[1]
    assert request('/login',{'csrf':token,'username':'ciadmin','password':'Fixture1!'})[0]==302
    status,page,_=request('/links');assert status==200
    for text in ('Royal Blau','Dark Purple','Anthrazit','Redline','Carbon','Pulse','role="switch"'):assert text in page,text
    assert 'https://8.8.8.8:'+str(control_port) in page
    status,inventory,_=request('/api/inventory');result=json.loads(inventory)
    assert status==200 and result['docker_installed'] and result['services'] and result['containers']
    for row in result['containers']:assert 'Env' not in row and 'Mounts' not in row
    assert request('/setup')[0]==302
    assert request('/static/ui.js')[0]==200 and request('/static/style.css')[0]==200
    print('Services Compose: trusted TLS, username/password setup without token, single registration, authenticated read-only inventory, all designs/colors: OK')
