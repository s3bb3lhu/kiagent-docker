"""Separate HTTPS service portal, using the existing server-control password."""
import functools
import hmac
import json
import os
import secrets
import socket
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask,abort,jsonify,redirect,render_template,request,session

def rpc(packet):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(65);client.connect('/run/kiagent-services/control.sock');client.sendall(json.dumps(packet).encode()+b'\n')
        raw=bytearray()
        while b'\n' not in raw:
            part=client.recv(65536)
            if not part or len(raw)+len(part)>4*1024*1024:raise ValueError('unavailable')
            raw.extend(part)
        return json.loads(raw)

def create_app(backend=rpc,secret=None,origin=None):
    app=Flask(__name__)
    origin=origin or os.environ['SERVICES_ORIGIN']
    host=urlsplit(origin).netloc
    secret=secret or (Path(os.environ['CREDENTIALS_DIRECTORY'])/'session').read_text().strip()
    app.config.update(SECRET_KEY=secret,MAX_CONTENT_LENGTH=4096,SESSION_COOKIE_NAME='kiagent_services',SESSION_COOKIE_SECURE=True,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',PERMANENT_SESSION_LIFETIME=timedelta(minutes=30))
    def csrf():
        if 'csrf' not in session:session['csrf']=secrets.token_hex(24)
        return session['csrf']
    @app.before_request
    def protect():
        if request.host!=host:abort(400)
        if request.method=='POST':
            if request.headers.get('Origin')!=origin:abort(403)
            token=request.headers.get('X-CSRF-Token') or request.form.get('csrf','')
            if not hmac.compare_digest(token,session.get('csrf','!')):abort(403)
    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','Content-Security-Policy':"default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response
    @app.get('/health')
    def health():return jsonify(ok=True)
    @app.route('/login',methods=['GET','POST'])
    def login():
        error=''
        try:
            if backend({'op':'setup_state'}).get('setup_required'):return redirect('/setup')
        except Exception:abort(503)
        if request.method=='POST':
            try:result=backend({'op':'login','username':request.form.get('username',''),'password':request.form.get('password','')})
            except Exception:result={'ok':False}
            if result.get('ok'):
                session.clear();session['token']=result['token'];session.permanent=True;return redirect('/')
            error='Anmeldung nicht möglich. Passwort prüfen oder fünf Minuten warten.'
        return render_template('login.html',csrf=csrf(),error=error)
    @app.route('/setup',methods=['GET','POST'])
    def setup():
        try:required=backend({'op':'setup_state'}).get('setup_required')
        except Exception:abort(503)
        if not required:return redirect('/login')
        error=''
        if request.method=='POST':
            if request.form.get('password')!=request.form.get('confirm'):error='Die Passwörter stimmen nicht überein.'
            else:
                result=backend({'op':'setup','username':request.form.get('username',''),'password':request.form.get('password','')})
                if result.get('ok'):session.clear();return redirect('/login')
                error='Benutzernamen und Passwortanforderungen prüfen. Möglicherweise wurde die Einrichtung bereits abgeschlossen.'
        return render_template('setup.html',csrf=csrf(),error=error)
    def authenticated(function):
        @functools.wraps(function)
        def wrapped(*args,**kwargs):
            if 'token' not in session:return redirect('/login') if not request.path.startswith('/api/') else (jsonify(ok=False,error='login_required'),401)
            return function(*args,**kwargs)
        return wrapped
    @app.post('/logout')
    @authenticated
    def logout():
        try:backend({'op':'logout','token':session['token']})
        finally:session.clear()
        return redirect('/login')
    @app.get('/')
    @app.get('/containers')
    @app.get('/links')
    @authenticated
    def index():return render_template('index.html',csrf=csrf(),page='links' if request.path=='/links' else 'containers' if request.path=='/containers' else 'services',server_ip=urlsplit(origin).hostname,control_origin=os.environ.get('SERVICES_CONTROL_ORIGIN','https://'+urlsplit(origin).hostname+':9898'))
    @app.route('/api/<operation>',methods=['GET','POST'])
    @authenticated
    def api(operation):
        if operation=='inventory' and request.method=='GET':packet={'op':'inventory'}
        elif operation in ('prepare','decide') and request.method=='POST':
            data=request.get_json(silent=True)
            keys={'kind','target','verb'} if operation=='prepare' else {'id','confirm','phrase'}
            if not isinstance(data,dict) or set(data)!=keys:abort(400)
            packet={'op':operation,**data}
        else:abort(404)
        try:result=backend({**packet,'token':session['token']})
        except Exception:result={'ok':False,'error':'unavailable'}
        return jsonify(result),200 if result.get('ok') else 400
    return app

if __name__=='__main__':create_app().run()
