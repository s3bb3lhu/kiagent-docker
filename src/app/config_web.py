"""Loopback/SSH-tunnel configuration UI. Saved tokens never leave the host broker."""
import collections
import functools
import hashlib
import hmac
import json
import os
import secrets
import socket
import threading
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

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
        sock.settimeout(10)
        sock.connect('/run/kiagent-config/control.sock')
        sock.sendall(json.dumps(payload).encode()+b'\n')
        raw = bytearray()
        while b'\n' not in raw and len(raw)<32000:
            part = sock.recv(4096)
            if not part:
                break
            raw.extend(part)
        if not raw.endswith(b'\n') or len(raw)>=32000:
            raise ValueError('Invalid response')
        return json.loads(raw)

def password_hash(password,salt):
    return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()

def create_app(credentials=None,backend=exchange,origin=None):
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
    failures = collections.deque()
    rate_lock = threading.Lock()

    def csrf():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)
        return session['csrf']

    @app.before_request
    def check_request():
        # The TLS proxy passes a fixed Host. Never trust client-supplied forwarded headers.
        if request.host != parsed.netloc:
            abort(400)
        if request.method not in {'GET','HEAD','POST'}:
            abort(405)
        if request.method == 'POST':
            supplied = request.headers.get('X-CSRF-Token') or request.form.get('csrf','')
            if (request.headers.get('Origin') != origin or not session.get('csrf')
                or not hmac.compare_digest(supplied,session['csrf'])):
                abort(403)

    @app.after_request
    def headers(response):
        if public_tls:
            response.headers['Strict-Transport-Security'] = 'max-age=86400'
        response.headers.update({'Cache-Control':'no-store','Pragma':'no-cache',
            'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"})
        return response

    def authenticated(function):
        @functools.wraps(function)
        def wrapper(*args,**kwargs):
            if session.get('authenticated') is not True:
                if request.path.startswith('/api/'):
                    return jsonify(ok=False,message='Bitte anmelden.'),401
                return redirect(url_for('login'))
            return function(*args,**kwargs)
        return wrapper

    def rpc(payload):
        try:
            reply = backend(payload)
        except Exception:
            return {'ok':False,'message':'Die Konfiguration ist derzeit nicht erreichbar.'}
        if not reply.get('ok'):
            return {'ok':False,'message':MESSAGES.get(reply.get('code'),MESSAGES['internal'])}
        return reply

    @app.route('/login',methods=['GET','POST'])
    def login():
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
            if 1 <= len(password)<=256 and hmac.compare_digest(password_hash(password,salt),expected):
                with rate_lock:
                    failures.clear()
                session.clear()
                session.permanent = True
                session['authenticated'] = True
                csrf()
                return redirect(url_for('index'))
            error = 'Das Passwort stimmt nicht.'
        return render_template('config_login.html',csrf=csrf(),error=error)

    @app.post('/logout')
    @authenticated
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.get('/')
    @authenticated
    def index():
        return render_template('config_index.html',csrf=csrf())

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
        return jsonify(ok=False,message='Anfrage nicht erlaubt oder nicht verfügbar.'),code
    return app
