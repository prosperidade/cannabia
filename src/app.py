# src/app.py
import logging
import secrets
import time
import uuid

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

from src.infra.logging import setup_logging
from src.config import SECRET_KEY, LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_S

from src.web.routes.auth import limit_or_429, generate_csrf_token, validate_csrf_from_form

# Blueprints
from src.web.routes.historico_atendimento import historico_bp
from src.web.routes.realtime_notifications import realtime_bp, socketio
from src.web.routes.scheduling_chain import scheduling_bp
from src.web.routes.dashboard import dashboard_bp
from src.web.routes.ai_admin import ai_admin_bp

from src.ai.service import CannabIAService
from src.repositories.user_repository import get_user_by_username, get_user_by_id, verify_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class AppUser(UserMixin):
    def __init__(self, user_id: int, username: str, role: str):
        self.id = str(user_id)
        self.username = username
        self.role = role


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Logging estruturado (seu)
    setup_logging()

    # ==============================
    # CONFIG
    # ==============================
    app.config["SECRET_KEY"] = SECRET_KEY or "dev-secret-key-fallback"
    app.config["SESSION_COOKIE_SECURE"] = False  # local dev
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # 1MB

    # ==============================
    # LOGIN MANAGER
    # ==============================
    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            uid = int(user_id)
        except Exception:
            return None

        user = get_user_by_id(uid)
        if not user:
            return None

        return AppUser(
            user_id=user["id"],
            username=user["username"],
            role=user["role"],
        )

    # ==============================
    # REQUEST LOG / CONTEXTO
    # ==============================
    @app.before_request
    def before_request():
        g._request_start = time.time()
        g.request_id = str(uuid.uuid4())

        # facilita auditoria
        if current_user.is_authenticated:
            g.user_id = getattr(current_user, "id", None)
        else:
            g.user_id = None

    @app.after_request
    def after_request(response):
        elapsed_ms = int((time.time() - g.get("_request_start", time.time())) * 1000)

        logging.info(
            "request_id=%s path=%s method=%s status=%s elapsed_ms=%s",
            getattr(g, "request_id", None),
            request.path,
            request.method,
            response.status_code,
            elapsed_ms,
        )
        return response

    # ==============================
    # SOCKETIO
    # ==============================
    socketio.init_app(app)

    # ==============================
    # BLUEPRINTS
    # ==============================
    app.register_blueprint(realtime_bp, url_prefix="/realtime")
    app.register_blueprint(scheduling_bp, url_prefix="/scheduling")
    app.register_blueprint(historico_bp, url_prefix="/historico")
    app.register_blueprint(dashboard_bp)     # /dashboard, /ai-audit
    app.register_blueprint(ai_admin_bp)      # rotas administrativas IA (seu blueprint)

    # ==============================
    # CSRF helpers (compatível com seu template atual)
    # ==============================
    def _new_csrf() -> str:
        # mantém seu nome antigo csrf_token, mas usa o mecanismo oficial do auth.py
        token = generate_csrf_token()
        session["csrf_token"] = token
        return token

    def _validate_csrf_from_form_compat() -> bool:
        # aceita tanto csrf_token quanto _csrf_token
        sent = request.form.get("csrf_token")
        if sent is not None:
            expected = session.get("csrf_token")
            return bool(sent and expected and secrets.compare_digest(sent, expected))
        return validate_csrf_from_form()

    # ==============================
    # ROTAS
    # ==============================
    @app.route("/")
    @login_required
    def index():
        return render_template("index.html", csrf_token=_new_csrf())

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.method == "POST":
            # rate limit por IP
            limit_or_429("login", LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_S)

            if not _validate_csrf_from_form_compat():
                return (
                    render_template("login.html", error="CSRF inválido. Recarregue a página.", csrf_token=_new_csrf()),
                    400,
                )

            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""

            user = get_user_by_username(username)
            if user and verify_password(password, user["password_hash"]):
                login_user(AppUser(user_id=user["id"], username=user["username"], role=user["role"]))
                next_url = request.args.get("next")
                return redirect(next_url or url_for("index"))

            return (
                render_template("login.html", error="Usuário ou senha inválidos.", csrf_token=_new_csrf()),
                401,
            )

        # GET
        return render_template("login.html", csrf_token=_new_csrf())

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        if not _validate_csrf_from_form_compat():
            return "CSRF inválido.", 400

        logout_user()
        session.pop("csrf_token", None)
        session.pop("_csrf_token", None)
        flash("Logout realizado.", "success")
        return redirect(url_for("login"))

    @app.route("/whoami")
    def whoami():
        return jsonify(
            {
                "authenticated": bool(current_user.is_authenticated),
                "user_id": getattr(current_user, "id", None),
                "role": getattr(current_user, "role", None),
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
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception:
            return jsonify({"error": "Erro interno no processamento clínico."}), 500

    return app


app = create_app()

if __name__ == "__main__":
    socketio.run(app, port=5000, debug=True)
