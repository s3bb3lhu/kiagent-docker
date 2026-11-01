"""Loopback/SSH-tunnel configuration UI. Saved tokens never leave the host broker."""
import collections
import functools
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import threading
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, abort, jsonify, redirect, render_template as original_render, request, session, url_for
from werkzeug.exceptions import HTTPException
from web_auth import AuthStore,POLICY,valid_password
from web_i18n import LANGUAGES,catalog
from release_version import VERSION
from user_docs import categories,documents

def language():
    value=request.args.get('lang',request.cookies.get('kiagent_language','de'))
    return value if value in LANGUAGES else 'de'

def render_template(name,**values):
    modes={'config_login.html':'login','config_password.html':'setup' if values.get('setup') else 'password','config_error.html':'error'}
    if name in modes:
        values['auth_mode']=modes[name]
        error=values.get('error','') or ''
        values['error_key']='too_many' if 'viele' in error else 'password_mismatch' if 'überein' in error else 'wrong_password' if 'Passwort stimmt' in error else 'password_policy' if 'Mindestens' in error else 'validation'
        values['page_active']='setup' if values['auth_mode']=='setup' else 'password_change' if values['auth_mode']=='password' else 'login'
        name='dashboard_auth.html'
    return original_render(name,**values)

MESSAGES = {
    'schema':'Die Eingabe konnte nicht gelesen werden. Bitte die Seite neu laden.',
    'ids':'Bitte gültige numerische IDs eintragen. Mehrere Benutzer-IDs mit Kommas trennen.',
    'raid':'RAID-Geräte bitte als md1,md2 angeben oder das Feld leer lassen.',
    'required':'Telegram- und Discord-Token dürfen nicht entfernt werden.',
    'token':'Der Token enthält ungültige Zeichen oder ist zu lang.',
    'telegram_format':'Das Format des Telegram-Bot-Tokens stimmt nicht.',
    'discord_format':'Das Format des Discord-Bot-Tokens stimmt nicht.',
    'openai_format':'Das Format des OpenAI-Schlüssels stimmt nicht.',
    'ping_format':'Bitte die vollständige Healthchecks Ping-URL im UUID-Format verwenden.',
    'stale':'Die Konfiguration wurde inzwischen geändert. Bitte neu laden und erneut prüfen.',
    'busy':'Eine Änderung wird bereits übernommen. Bitte deren Ergebnis abwarten.',
    'telegram_login':'Der neue Telegram-Token konnte nicht bestätigt werden. Bitte bei BotFather prüfen.',
    'discord_login':'Discord-Anmeldung oder Kanalzugriff fehlgeschlagen. Token, Anwendungs-ID und Kanal prüfen.',
    'active_action':'Ein Auftrag ist noch aktiv oder unklar. Bitte zuerst den Aktionsstatus prüfen.',
    'interrupted':'Eine frühere Änderung wurde unterbrochen. Bitte den Zustand zuerst per SSH prüfen lassen.',
    'rollback_failed':'Die vorherige Konfiguration konnte nicht vollständig wieder gestartet werden. Prüfung per SSH erforderlich.',
    'state_changed':'Gespeicherte Automatikdaten haben sich geändert. Bitte per SSH prüfen lassen.',
    'apply':'Die Dienste konnten nicht vollständig neu geladen werden.',
    'internal':'Die Änderung konnte nicht verarbeitet werden. Bitte den Zustand per SSH prüfen lassen.',
    'storage':'Die Konfigurationsdateien konnten nicht sicher gelesen werden.',
    'unknown_job':'Dieser Vorgang ist nicht mehr verfügbar.'}

def exchange(payload):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(35 if payload.get('op')=='web_prepare' else 10)
        sock.connect('/run/kiagent-config/control.sock')
        sock.sendall(json.dumps(payload).encode()+b'\n')
        raw = bytearray()
        while b'\n' not in raw and len(raw)<1048576:
            part = sock.recv(4096)
            if not part:
                break
            raw.extend(part)
        if not raw.endswith(b'\n') or len(raw)>=1048576:
            raise ValueError('Invalid response')
        return json.loads(raw)

def password_hash(password,salt):
    return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()

def create_app(credentials=None,backend=exchange,origin=None,state_dir=None,setup_ip=None):
    credentials = Path(credentials or os.environ.get('CREDENTIALS_DIRECTORY','/run/secrets'))
    origin = origin or os.environ.get('CONFIG_ORIGIN','http://127.0.0.1:8787')
    parsed = urlsplit(origin)
    loopback = parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and parsed.port is not None
    public_tls = parsed.scheme == 'https' and bool(parsed.hostname) and parsed.port in (None,443)
    if not (loopback or public_tls) or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('Explicit loopback or HTTPS origin required')
    app = Flask(__name__)
    app.config.update(SECRET_KEY=(credentials/'web-session-key').read_text().strip(),
        MAX_CONTENT_LENGTH=32000,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',
        SESSION_COOKIE_NAME='kiagent_config',SESSION_COOKIE_SECURE=public_tls,
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30))
    salt,expected = (credentials/'web-admin-hash').read_text().strip().split('$',1)
    auth=AuthStore(state_dir or os.environ.get('CONFIG_AUTH_DIR','/var/lib/kiagent-web/auth'),(salt,expected))
    setup_ip=setup_ip or os.environ.get('CONFIG_SETUP_ALLOWED_IP','127.0.0.1')
    setup_ip=str(ipaddress.ip_address(setup_ip))
    setup_proxy=os.environ.get('CONFIG_SETUP_PROXY','0')=='1'
    local_setup=os.environ.get('CONFIG_SETUP_LOCAL_ONLY','0')=='1'
    if public_tls and local_setup:raise ValueError('Public HTTPS requires an administrator IP restriction')
    failures = collections.deque()
    rate_lock = threading.Lock()

    def csrf():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)
        return session['csrf']

    @app.context_processor
    def ui_context():
        lang=language();words=catalog(lang)
        return {'lang':lang,'ui':words,'t':lambda key:words.get(key,key),'languages':LANGUAGES,'version':VERSION,
                'theme':request.cookies.get('kiagent_theme','light') if request.cookies.get('kiagent_theme') in {'light','dark'} else 'light',
                'csrf':csrf(),'public_address':origin,'auth_mode':None,
                'design':request.cookies.get('kiagent_design','ruby') if request.cookies.get('kiagent_design') in {'ruby','glass'} else 'ruby',
                'accent':request.cookies.get('kiagent_accent','red') if request.cookies.get('kiagent_accent') in {'red','blue','green','purple','anthracite'} else 'red',
                'menu_collapsed':request.cookies.get('kiagent_menu')=='collapsed'}

    @app.before_request
    def check_request():
        # The TLS proxy passes a fixed Host. Never trust client-supplied forwarded headers.
        if request.host.lower() != parsed.netloc.lower():
            abort(400)
        current=auth.read()
        if session.get('authenticated') and session.get('epoch')!=current['epoch']:
            session.clear()
        if request.method not in {'GET','HEAD','POST'}:
            abort(405)
        if request.method == 'POST':
            supplied = request.headers.get('X-CSRF-Token') or request.form.get('csrf','')
            if (request.headers.get('Origin') != origin or not session.get('csrf')
                or not hmac.compare_digest(supplied,session['csrf'])):
                abort(403)

    @app.after_request
    def headers(response):
        if request.args.get('lang') in LANGUAGES:
            response.set_cookie('kiagent_language',language(),max_age=31536000,secure=public_tls,samesite='Strict')
        response.headers['Content-Language']=language()
        if public_tls:
            response.headers['Strict-Transport-Security'] = 'max-age=86400'
        response.headers.update({'Cache-Control':'no-store','Pragma':'no-cache',
            'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"})
        return response

    def authenticated(function):
        @functools.wraps(function)
        def wrapper(*args,**kwargs):
            if session.get('authenticated') is not True or auth.read()['mode']!='ready':
                if request.path.startswith('/api/'):
                    return jsonify(ok=False,message=catalog(language())['login_required']),401
                return redirect(url_for('login'))
            if 'web_actor' not in session:session['web_actor']=secrets.token_hex(32)
            return function(*args,**kwargs)
        return wrapper

    def rpc(payload):
        try:
            reply = backend(payload)
        except Exception:
            return {'ok':False,'code':'unavailable','message':catalog(language())['unavailable']}
        if not reply.get('ok'):
            code=reply.get('code','internal')
            return {'ok':False,'code':code,'message':catalog(language()).get(code,catalog(language())['error'])}
        if reply.get('state')=='saved':reply['message']=catalog(language())['saved']
        return reply

    @app.route('/login',methods=['GET','POST'])
    def login():
        if auth.read()['mode']=='setup':
            return redirect(url_for('setup'))
        error = None
        if request.method == 'POST':
            now = time.monotonic()
            with rate_lock:
                while failures and now-failures[0]>60:
                    failures.popleft()
                limited = len(failures)>=5
                if not limited:
                    failures.append(now)
            if limited:
                return render_template('config_login.html',csrf=csrf(),error='Zu viele Versuche. Bitte eine Minute warten.'),429
            password = request.form.get('password','')
            current=auth.read()
            if auth.verify(password,current):
                with rate_lock:
                    failures.clear()
                session.clear()
                session.permanent = True
                session['authenticated'] = True
                session['epoch'] = current['epoch']
                csrf()
                return redirect(url_for('index'))
            error = 'Das Passwort stimmt nicht.'
        return render_template('config_login.html',csrf=csrf(),error=error)

    def limited_attempt():
        now=time.monotonic()
        with rate_lock:
            while failures and now-failures[0]>60:failures.popleft()
            if len(failures)>=5:return True
            failures.append(now)
            return False

    @app.route('/setup',methods=['GET','POST'])
    def setup():
        if auth.read()['mode']!='setup':return redirect(url_for('login'))
        client_ip=request.headers.get('X-Kiagent-Setup-IP','') if setup_proxy else request.remote_addr
        if not local_setup and client_ip!=setup_ip:abort(403)
        error=None
        if request.method=='POST':
            if limited_attempt():
                return render_template('config_password.html',setup=True,csrf=csrf(),policy=POLICY,error='Zu viele Versuche. Bitte eine Minute warten.'),429
            password=request.form.get('password','')
            if not valid_password(password):error=POLICY
            elif password!=request.form.get('repeat'):error='Die Passwörter stimmen nicht überein.'
            else:
                epoch=auth.set_password(password,setup=True)
                if epoch:
                    session.clear()
                    session.permanent=True
                    session.update(authenticated=True,epoch=epoch)
                    csrf()
                    with rate_lock:failures.clear()
                    return redirect(url_for('index'))
                error='Die Einrichtung wurde bereits abgeschlossen. Bitte normal anmelden.'
        return render_template('config_password.html',setup=True,csrf=csrf(),policy=POLICY,error=error)

    @app.route('/password',methods=['GET','POST'])
    @authenticated
    def change_password():
        error=None
        if request.method=='POST':
            if limited_attempt():
                return render_template('config_password.html',setup=False,csrf=csrf(),policy=POLICY,error='Zu viele Versuche. Bitte eine Minute warten.'),429
            password=request.form.get('password','')
            if not valid_password(password):error=POLICY
            elif password!=request.form.get('repeat'):error='Die Passwörter stimmen nicht überein.'
            else:
                epoch=auth.set_password(password,current=request.form.get('current',''))
                if epoch:
                    session.clear()
                    session.permanent=True
                    session.update(authenticated=True,epoch=epoch)
                    csrf()
                    with rate_lock:failures.clear()
                    return redirect(url_for('index'))
                error='Das bisherige Passwort stimmt nicht.'
        return render_template('config_password.html',setup=False,csrf=csrf(),policy=POLICY,error=error)

    @app.post('/logout')
    @authenticated
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.get('/')
    @authenticated
    def index():
        if rpc({'op':'overview'}).get('setup_required'):return redirect('/settings/setup')
        return render_template('dashboard_status.html',csrf=csrf(),page_active='status')

    @app.get('/settings')
    @authenticated
    def settings_page():return render_template('dashboard_settings.html',csrf=csrf(),page_active='settings')

    @app.get('/settings/documentation')
    @authenticated
    def documentation_page():
        return render_template('dashboard_docs.html',csrf=csrf(),page_active='settings',doc_categories=categories(language()),document=None)

    @app.get('/settings/documentation/<slug>')
    @authenticated
    def documentation_article(slug):
        document=next((row for row in documents(language()) if row['slug']==slug),None)
        if document is None:abort(404)
        return render_template('dashboard_docs.html',csrf=csrf(),page_active='settings',doc_categories=categories(language()),document=document)

    @app.get('/settings/setup')
    @authenticated
    def initial_configuration_page():
        return render_template('dashboard_connections.html',csrf=csrf(),page_active='settings',selected_provider='all')

    @app.get('/settings/<provider>')
    @authenticated
    def settings_provider(provider):
        if provider not in {'telegram','discord','openai','health','monitoring'}:abort(404)
        if rpc({'op':'overview'}).get('setup_required'):return redirect('/settings/setup')
        return render_template('dashboard_connections.html',csrf=csrf(),page_active='settings',selected_provider=provider)

    @app.get('/console')
    @authenticated
    def console_page():return render_template('dashboard_console.html',csrf=csrf(),page_active='console')

    @app.get('/api/server/activity')
    @authenticated
    def server_activity():
        result=rpc({'op':'web_activity'})
        return jsonify(result),200 if result.get('ok') else 503

    @app.get('/status')
    @authenticated
    def status_page():return render_template('dashboard_status.html',csrf=csrf(),page_active='status')

    @app.get('/control')
    @authenticated
    def control_page():return render_template('dashboard_control.html',csrf=csrf(),page_active='control')

    def actor():
        if 'web_actor' not in session:session['web_actor']=secrets.token_hex(32)
        return hashlib.sha256((session['web_actor']+session['epoch']).encode()).hexdigest()

    @app.get('/api/server/status')
    @authenticated
    def server_status():
        result=rpc({'op':'web_status'})
        return jsonify(result),200 if result.get('ok') else 503

    @app.post('/api/control/read')
    @authenticated
    def control_read():
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or set(data)!={'command'}:abort(400)
        result=rpc({'op':'web_read','actor':actor(),'command':data['command']})
        return jsonify(result),200 if result.get('ok') else 400

    @app.post('/api/control/prepare')
    @authenticated
    def control_prepare():
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or set(data)!={'action'}:abort(400)
        result=rpc({'op':'web_prepare','actor':actor(),'action':data['action']})
        return jsonify(result),200 if result.get('ok') else 400

    @app.post('/api/control/decide')
    @authenticated
    def control_decide():
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or set(data)!={'id','confirm','phrase','restart'} or type(data['confirm']) is not bool or type(data['restart']) is not bool:abort(400)
        # Require the typed phrase for every confirmation. The root-bound job,
        # never the client action field, determines what will actually execute.
        if data['confirm'] and data['phrase']!=catalog(language())['restart_word']:abort(403)
        result=rpc({'op':'web_decide','actor':actor(),'id':data['id'],'confirm':data['confirm']})
        return jsonify(result),200 if result.get('ok') else 400

    @app.get('/api/control/jobs/<job>')
    @authenticated
    def control_job(job):
        result=rpc({'op':'web_job','actor':actor(),'id':job})
        return jsonify(result),200 if result.get('ok') else 400

    @app.get('/api/overview')
    @authenticated
    def overview():
        result = rpc({'op':'overview'})
        return jsonify(result),200 if result.get('ok') else 503

    @app.post('/api/config')
    @authenticated
    def save():
        if not request.is_json:
            abort(415)
        data = request.get_json(silent=True)
        if not isinstance(data,dict):
            abort(400)
        reply = rpc({'op':'save','data':data})
        return jsonify(reply),202 if reply.get('ok') else 400

    @app.get('/api/jobs/<job>')
    @authenticated
    def job_status(job):
        reply = rpc({'op':'job','job':job})
        if reply.get('ok'):
            reply['message'] = MESSAGES.get(reply.get('code'),'')
        return jsonify(reply),200 if reply.get('ok') else 400

    @app.get('/health')
    def health():
        reply = rpc({'op':'health'})
        return jsonify(ok=reply.get('ok') is True),200 if reply.get('ok') else 503

    @app.errorhandler(Exception)
    def error(error):
        code = error.code if isinstance(error,HTTPException) else 500
        if request.path in {'/login','/setup','/password','/'}:
            app.logger.warning('Web request rejected: status=%s type=%s',code,type(error).__name__)
            return render_template('config_error.html',message=('Die Sitzung ist abgelaufen oder das Sicherheits-Cookie fehlt. Öffne die Anmeldung neu und erlaube Cookies für diese Seite.' if code==403 else 'Die Anfrage konnte nicht verarbeitet werden. Bitte die Seite neu öffnen.')),code
        return jsonify(ok=False,message=catalog(language())['error']),code
    return app
