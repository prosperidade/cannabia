import logging
import secrets
import time

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    jsonify,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from src.config import APP_AUTH_PASSWORD, APP_AUTH_USERNAME, SECRET_KEY

# Blueprints (agora em src/web/routes)
from src.web.routes.historico_atendimento import historico_bp
from src.web.routes.realtime_notifications import realtime_bp, socketio
from src.web.routes.scheduling_chain import scheduling_bp

from src.ai.service import CannabIAService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Sessão / cookies
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SESSION_COOKIE_SECURE"] = False  # dev local
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Login manager
    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    class AppUser(UserMixin):
        def __init__(self, user_id: str):
            self.id = user_id

    AUTH_USER_ID = "admin"  # POC

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == AUTH_USER_ID:
            return AppUser(AUTH_USER_ID)
        return None

    # Rate limit simples (somente login)
    LOGIN_RATE_LIMIT = 10
    LOGIN_RATE_WINDOW_SECONDS = 60
    _login_rate_attempts = {}

    def _get_client_ip() -> str:
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.remote_addr or "unknown"

    def _is_login_rate_limited(client_ip: str) -> bool:
        now = time.time()
        attempts = _login_rate_attempts.get(client_ip, [])
        attempts = [t for t in attempts if now - t < LOGIN_RATE_WINDOW_SECONDS]
        if len(attempts) >= LOGIN_RATE_LIMIT:
            _login_rate_attempts[client_ip] = attempts
            return True
        attempts.append(now)
        _login_rate_attempts[client_ip] = attempts
        return False

    # Request log
    @app.before_request
    def before_request():
        g._request_start = time.time()

    @app.after_request
    def after_request(response):
        elapsed_ms = int((time.time() - g.get("_request_start", time.time())) * 1000)
        logging.info(
            "request path=%s method=%s status=%s elapsed_ms=%s",
            request.path,
            request.method,
            response.status_code,
            elapsed_ms,
        )
        return response

    # SocketIO (precisa ser inicializado com app aqui)
    socketio.init_app(app)

    # Blueprints com prefixos (sem conflito de "/")
    app.register_blueprint(realtime_bp, url_prefix="/realtime")
    app.register_blueprint(scheduling_bp, url_prefix="/scheduling")
    app.register_blueprint(historico_bp, url_prefix="/historico")

    # CSRF simples para forms (login/logout)
    def _new_csrf() -> str:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
        return token

    def _validate_csrf_from_form() -> bool:
        form_token = request.form.get("csrf_token", "")
        sess_token = session.get("csrf_token", "")
        return bool(sess_token) and bool(form_token) and secrets.compare_digest(form_token, sess_token)

    # Rotas principais
    @app.route("/")
    @login_required
    def index():
        return render_template("index.html", csrf_token=_new_csrf())

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.method == "POST":
            if _is_login_rate_limited(_get_client_ip()):
                abort(429)

            if not _validate_csrf_from_form():
                return (
                    render_template(
                        "login.html",
                        error="CSRF inválido. Recarregue a página.",
                        csrf_token=_new_csrf(),
                    ),
                    400,
                )

            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""

            if username == APP_AUTH_USERNAME and password == APP_AUTH_PASSWORD:
                login_user(AppUser(AUTH_USER_ID))
                next_url = request.args.get("next")
                return redirect(next_url or url_for("index"))

            return (
                render_template(
                    "login.html",
                    error="Usuário ou senha inválidos.",
                    csrf_token=_new_csrf(),
                ),
                401,
            )

        return render_template("login.html", csrf_token=_new_csrf())

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        if not _validate_csrf_from_form():
            return "CSRF inválido.", 400
        logout_user()
        session.pop("csrf_token", None)
        flash("Logout realizado.", "success")
        return redirect(url_for("login"))

    @app.route("/whoami")
    def whoami():
        return jsonify(
            {
                "authenticated": bool(current_user.is_authenticated),
                "user_id": getattr(current_user, "id", None),
            }
        )

    @app.route("/ai/test", methods=["POST"])
    @login_required
    def ai_test():
        if not request.is_json:
            return jsonify({"error": "Request deve ser JSON"}), 400

        data = request.get_json()
        service = CannabIAService()

        try:
            result = service.process_patient_case(data)
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


app = create_app()

if __name__ == "__main__":
    # Rodar com socketio para realtime funcionar
    socketio.run(app, port=5000, debug=True)
