# src/app.py

from src.tenancy import init_tenancy
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
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from src.infra.logging import setup_logging
from src.infra.metrics import record as record_metric
from src.config import (
    SECRET_KEY,
    SESSION_COOKIE_SECURE,
    SESSION_COOKIE_SAMESITE,
    LOGIN_RATE_LIMIT,
    LOGIN_RATE_WINDOW_S,
    FRONTEND_ORIGINS,
)

from src.web.routes.auth import limit_or_429, generate_csrf_token, validate_csrf_from_form
from src.web.auth_identity import AppUser

# Blueprints
from src.web.routes.historico_atendimento import historico_bp
from src.web.routes.realtime_notifications import realtime_bp, socketio
from src.web.routes.scheduling_chain import scheduling_bp
from src.web.routes.dashboard import dashboard_bp
from src.web.routes.ai_admin import ai_admin_bp
from src.web.routes.atendimentos import atendimentos_bp
from src.web.routes.api_v1 import api_v1_bp
from src.web.routes.system import system_bp
from src.web.routes.tenant_admin import tenant_admin_bp
from src.web.routes.campaigns import campaigns_bp
from src.web.routes.chat_intake import chat_bp, ChatNamespace, ChatMonitorNamespace
from src.web.routes.telemetry import telemetry_bp
from src.web.routes.prescriptions import prescriptions_bp
from src.web.routes.patient_portal import patient_portal_bp
from src.web.routes.returns import returns_bp
from src.web.routes.org_management import org_management_bp
from src.web.routes.admin_users import admin_users_bp
from src.web.routes.admin_case_aggregates import admin_case_aggregates_bp
from src.web.routes.clinic_config import clinic_config_bp
from src.web.routes.reports import reports_bp
from src.web.routes.compliance import compliance_bp
from src.web.routes.clinical_intelligence import clinical_intel_bp
from src.web.routes.regulatory import regulatory_bp
from src.web.routes.governance import governance_bp
from src.web.routes.document_reviews import document_reviews_bp
from src.web.routes.pharmacovigilance import pharmacovigilance_bp
from src.web.routes.acompanhamento import acompanhamento_bp
from src.web.routes.regulatory_reporting import regulatory_reporting_bp
from src.web.routes.public_anchors import public_anchors_bp
from src.web.routes.knowledge import knowledge_bp
from src.web.routes.admin_agents import admin_agents_bp
from src.web.routes.conversations import conversations_bp
from src.web.routes.payments import payments_bp

from src.ai.service import CannabIAService
from src.repositories.user_repository import (
    get_user_by_username,
    get_user_by_id,
    verify_password,
)

logger = logging.getLogger("cannabia.app")

def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Correção para proxy reverso (ex: Render) confiar no protocolo HTTPS
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # 🔐 Multi-tenant
    init_tenancy(app)

    # Logging estruturado
    setup_logging()

    # ==============================
    # CONFIG
    # ==============================
    app.config["SECRET_KEY"] = SECRET_KEY or "dev-secret-key-fallback"
    app.config["SESSION_COOKIE_SECURE"] = SESSION_COOKIE_SECURE   # True em produção (HTTPS)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = SESSION_COOKIE_SAMESITE
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

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
            is_clinic_admin=bool(user.get("is_clinic_admin", False)),
        )

    # ==============================
    # REQUEST LOG / CONTEXTO
    # ==============================
    @app.before_request
    def before_request():
        g._request_start = time.time()
        g.request_id = str(uuid.uuid4())

        if current_user.is_authenticated:
            g.user_id = getattr(current_user, "id", None)
        else:
            g.user_id = None

    @app.after_request
    def after_request(response):
        elapsed_ms = int((time.time() - g.get("_request_start", time.time())) * 1000)

        record_metric("http.request", elapsed_ms)
        record_metric(f"http.endpoint.{request.endpoint or 'unknown'}", elapsed_ms)

        logger.info(
            "%s %s %s %dms",
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
            extra={
                "request_id": getattr(g, "request_id", None),
                "user_id": getattr(g, "user_id", None),
                "tenant_id": getattr(g, "tenant_id", None),
                "clinic_id": getattr(g, "clinic_id", None),
                "path": request.path,
                "method": request.method,
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )
        return response

    # ==============================
    # SOCKETIO
    # ==============================
    socketio.init_app(app, cors_allowed_origins=FRONTEND_ORIGINS)

    # Namespaces de chat (intake dinâmico via WebSocket)
    socketio.on_namespace(ChatNamespace("/chat"))
    socketio.on_namespace(ChatMonitorNamespace("/chat-monitor"))

    # ==============================
    # BLUEPRINTS
    # ==============================
    app.register_blueprint(realtime_bp, url_prefix="/realtime")
    app.register_blueprint(scheduling_bp, url_prefix="/scheduling")
    app.register_blueprint(historico_bp, url_prefix="/historico")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(ai_admin_bp)
    app.register_blueprint(atendimentos_bp)
    app.register_blueprint(api_v1_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(tenant_admin_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(telemetry_bp)
    app.register_blueprint(prescriptions_bp)
    app.register_blueprint(patient_portal_bp)
    app.register_blueprint(returns_bp)
    app.register_blueprint(org_management_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(admin_case_aggregates_bp)
    app.register_blueprint(clinic_config_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(compliance_bp)
    app.register_blueprint(clinical_intel_bp)
    app.register_blueprint(regulatory_bp)
    app.register_blueprint(governance_bp)
    app.register_blueprint(document_reviews_bp)
    app.register_blueprint(pharmacovigilance_bp)
    app.register_blueprint(acompanhamento_bp)
    app.register_blueprint(regulatory_reporting_bp)
    app.register_blueprint(public_anchors_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(admin_agents_bp)
    app.register_blueprint(conversations_bp)
    app.register_blueprint(payments_bp)

    # ==============================
    # CSRF HELPERS
    # ==============================
    def _new_csrf() -> str:
        token = generate_csrf_token()
        session["csrf_token"] = token
        return token

    def _validate_csrf_from_form_compat() -> bool:
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
        return redirect(url_for("dashboard.dashboard"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.method == "POST":
            limit_or_429("login", LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_S)

            if not _validate_csrf_from_form_compat():
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

            user = get_user_by_username(username)
            if user and verify_password(password, user["password_hash"]):
                login_user(
                    AppUser(
                        user_id=user["id"],
                        username=user["username"],
                        role=user["role"],
                    )
                )
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
                "global_role": getattr(current_user, "global_role", None),
                "clinic_role": getattr(g, "clinic_role", None),
                "tenant_id": getattr(g, "tenant_id", None),
                "tenant_role": getattr(g, "tenant_role", None),
                "tenant_type": getattr(g, "tenant_type", None),
            }
        )

    @app.route("/clinic-debug")
    @login_required
    def clinic_debug():
        return {
            "clinic_id": getattr(g, "clinic_id", None),
            "clinic_role": getattr(g, "clinic_role", None),
            "tenant_id": getattr(g, "tenant_id", None),
            "tenant_role": getattr(g, "tenant_role", None),
            "tenant_type": getattr(g, "tenant_type", None),
        }

    @app.route("/ai/test", methods=["POST"])
    @login_required
    def ai_test():

        if not hasattr(g, "clinic_id"):
            abort(403)

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
