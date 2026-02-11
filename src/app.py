import logging
import secrets
import time

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user

from config import APP_AUTH_PASSWORD, APP_AUTH_USERNAME, SECRET_KEY
from historico_atendimento import historico_bp
from realtime_notifications import realtime_bp, socketio
from scheduling_chain import scheduling_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar esta página.'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)


class AppUser(UserMixin):
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username


AUTH_USER_ID = 'default-user'



LOGIN_RATE_LIMIT = 5
LOGIN_RATE_WINDOW_SECONDS = 60
_login_rate_attempts = {}


def _get_client_ip():
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def _is_login_rate_limited(client_ip):
    now = time.time()
    attempts = _login_rate_attempts.get(client_ip, [])
    attempts = [attempt for attempt in attempts if now - attempt < LOGIN_RATE_WINDOW_SECONDS]
    if len(attempts) >= LOGIN_RATE_LIMIT:
        _login_rate_attempts[client_ip] = attempts
        return True
    attempts.append(now)
    _login_rate_attempts[client_ip] = attempts
    return False

@login_manager.user_loader
def load_user(user_id):
    if user_id == AUTH_USER_ID:
        return AppUser(AUTH_USER_ID, APP_AUTH_USERNAME)
    return None


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
    logging.info(
        'request path=%s method=%s status=%s elapsed_ms=%s',
        request.path,
        request.method,
        response.status_code,
        elapsed_ms,
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net https://cdn.socket.io; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    return response


@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        if _is_login_rate_limited(_get_client_ip()):
            abort(429)

        csrf_token = request.form.get('csrf_token', '')
        session_csrf_token = session.get('login_csrf_token')
        if not session_csrf_token or not csrf_token or not secrets.compare_digest(csrf_token, session_csrf_token):
            abort(400)

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        if username == APP_AUTH_USERNAME and password == APP_AUTH_PASSWORD:
            login_user(AppUser(AUTH_USER_ID, APP_AUTH_USERNAME), remember=remember)
            next_url = request.args.get('next')
            return redirect(next_url or url_for('index'))

        flash('Usuário ou senha inválidos.', 'danger')

    session['login_csrf_token'] = secrets.token_urlsafe(32)
    return render_template('login.html', csrf_token=session['login_csrf_token'])


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso.', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)
