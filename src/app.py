import logging
import time

from flask import Flask, g, redirect, render_template, request, session, url_for

from auth import generate_csrf_token, limit_or_429, validate_csrf_from_form
from config import (
    LOGIN_RATE_LIMIT,
    LOGIN_RATE_WINDOW_S,
    MAX_CONTENT_LENGTH,
    PREFERRED_URL_SCHEME,
    SECRET_KEY,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    USERS,
)
from historico_atendimento import historico_bp
from realtime_notifications import realtime_bp, socketio
from scheduling_chain import scheduling_bp
from security import RedactingFormatter

handler = logging.StreamHandler()
handler.setFormatter(RedactingFormatter('%(asctime)s %(levelname)s %(message)s'))
logger = logging.getLogger('cannabia')
logger.setLevel(logging.INFO)
logger.handlers = [handler]
logger.propagate = False

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_COOKIE_SECURE'] = SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_HTTPONLY'] = SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SAMESITE'] = SESSION_COOKIE_SAMESITE
app.config['PREFERRED_URL_SCHEME'] = PREFERRED_URL_SCHEME
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

socketio.init_app(app)

app.register_blueprint(realtime_bp)
app.register_blueprint(scheduling_bp)
app.register_blueprint(historico_bp)


@app.before_request
def before_request():
    g._request_start = time.time()


@app.after_request
def after_request(response):
    elapsed_ms = int((time.time() - g.get('_request_start', time.time())) * 1000)
    logger.info(
        'request path=%s method=%s status=%s elapsed_ms=%s user=%s',
        request.path,
        request.method,
        response.status_code,
        elapsed_ms,
        session.get('user_id', 'anonymous'),
    )

    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://cdn.socket.io https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:;"
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


@app.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    return render_template('index.html', user=session.get('user_id'), role=session.get('role'), csrf_token=generate_csrf_token())


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        limit_or_429('login', LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_S)
        if not validate_csrf_from_form():
            return 'CSRF inválido.', 400

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        matched = next((u for u in USERS if u['username'] == username and u['password'] == password), None)
        if not matched:
            return render_template('login.html', error='Usuário ou senha inválidos.', csrf_token=generate_csrf_token()), 401

        session['user_id'] = matched['username']
        session['role'] = matched['role']
        next_url = request.args.get('next') or url_for('index')
        return redirect(next_url)

    return render_template('login.html', csrf_token=generate_csrf_token())


@app.route('/logout', methods=['POST'])
def logout():
    if not validate_csrf_from_form():
        return 'CSRF inválido.', 400
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)
