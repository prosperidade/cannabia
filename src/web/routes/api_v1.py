from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from functools import wraps
from typing import Any, Iterable, Optional

from flask import Blueprint, g, jsonify, request, session
from flask_login import current_user, login_user, logout_user

from src.config import FRONTEND_ORIGINS, LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_S
from src.infra.security import get_effective_roles, normalize_role_name
from src.repositories import message_repository
from src.repositories.ai_audit_repository import get_ai_audit_summary, get_recent_ai_logs
from src.repositories.anamnesis_repository import get_report, list_reports, mark_reviewed
from src.repositories.dashboard_repository import get_dashboard_metrics
from src.repositories.medical_record_repository import (
    get_consultation_entry_by_report,
    get_medical_record_by_patient,
    list_patient_record_entries,
    upsert_consultation_entry,
)
from src.repositories.patient_timeline_repository import create_event, list_patient_events
from src.repositories.tenancy_repository import get_user_membership, resolve_default_clinic_id
from src.repositories.user_repository import get_user_by_username, verify_password
from src.services.appointment_service import create_appointment_from_api, list_appointments
from src.web.auth_identity import AppUser
from src.web.routes.auth import is_rate_allowed, issue_csrf_token, validate_csrf_value

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


@api_v1_bp.after_request
def apply_cors(response):
    origin = request.headers.get("Origin")
    if origin and origin in FRONTEND_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Vary"] = "Origin"
    return response


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _success(data: Any, status: int = 200, meta: Optional[dict] = None):
    payload = {"data": _serialize(data)}
    if meta is not None:
        payload["meta"] = _serialize(meta)
    return jsonify(payload), status


def _error(code: str, message: str, status: int, details: Optional[dict] = None):
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": _serialize(details or {}),
        }
    }
    return jsonify(payload), status


def _context_payload(membership: Optional[dict] = None) -> Optional[dict]:
    if membership:
        clinic_role = membership.get("clinic_role") or membership.get("role")
        tenant_id = membership.get("tenant_id") or membership.get("clinic_id")
        tenant_role = membership.get("tenant_role") or clinic_role
        tenant_type = membership.get("tenant_type") or "clinic"
        clinic_id = membership.get("clinic_id")
    else:
        clinic_id = getattr(g, "clinic_id", None)
        if clinic_id is None and not current_user.is_authenticated:
            return None
        clinic_role = getattr(g, "clinic_role", None)
        tenant_id = getattr(g, "tenant_id", None)
        tenant_role = getattr(g, "tenant_role", None)
        tenant_type = getattr(g, "tenant_type", None)

    return {
        "clinic_id": clinic_id,
        "clinic_role": clinic_role,
        "tenant_id": tenant_id,
        "tenant_role": tenant_role,
        "tenant_type": tenant_type,
    }


def _user_payload() -> Optional[dict]:
    if not current_user.is_authenticated:
        return None
    return {
        "id": int(current_user.id),
        "username": getattr(current_user, "username", None),
        "role": getattr(current_user, "role", None),
        "global_role": getattr(current_user, "global_role", None),
    }


def _paginate(items: Iterable[Any], page: int, page_size: int):
    items = list(items)
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], {
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def _pagination_args():
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1

    try:
        page_size = int(request.args.get("page_size", 20))
    except (TypeError, ValueError):
        page_size = 20

    page_size = max(1, min(page_size, 100))
    return page, page_size


def _json_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _require_json_csrf():
    payload = _json_payload()
    sent = request.headers.get("X-CSRF-Token") or payload.get("csrf_token") or ""
    if not validate_csrf_value(sent):
        return _error("csrf_invalid", "CSRF inválido.", 400)
    return None


def api_auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return _error("unauthenticated", "Autenticação necessária.", 401)
        return fn(*args, **kwargs)

    return wrapper


def api_role_required(*allowed_roles: str):
    allowed = {
        normalize_role_name(role)
        for role in allowed_roles
        if normalize_role_name(role)
    }

    def decorator(fn):
        @wraps(fn)
        @api_auth_required
        def wrapper(*args, **kwargs):
            effective_roles = get_effective_roles()
            if not effective_roles:
                return _error("forbidden", "Usuário sem role definida.", 403)
            if not allowed.intersection(effective_roles):
                return _error("forbidden", "Sem permissão para acessar este recurso.", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def _parse_requested_exams(raw_value) -> list[str]:
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    if isinstance(raw_value, str):
        return [item.strip() for item in raw_value.replace("\r", "").replace("\n", ",").split(",") if item.strip()]
    return []


def _build_attendance_detail(report: dict) -> dict:
    timeline = []
    medical_record_entries = []
    consultation_entry = None

    if report.get("patient_id"):
        timeline = list_patient_events(g.clinic_id, report["patient_id"], limit=20)
        medical_record_entries = list_patient_record_entries(g.clinic_id, report["patient_id"], limit=10)
        consultation_entry = get_consultation_entry_by_report(g.clinic_id, report["id"])

    return {
        "report": report,
        "timeline": timeline,
        "medical_record_entries": medical_record_entries,
        "consultation_entry": consultation_entry,
    }


@api_v1_bp.get("/health")
def health():
    return _success({"status": "ok"})


@api_v1_bp.get("/session/me")
def session_me():
    if not current_user.is_authenticated:
        return _success(
            {
                "authenticated": False,
                "user": None,
                "context": None,
                "csrf_token": issue_csrf_token(),
            }
        )

    return _success(
        {
            "authenticated": True,
            "user": _user_payload(),
            "context": _context_payload(),
            "csrf_token": issue_csrf_token(),
        }
    )


@api_v1_bp.post("/session/login")
def session_login():
    if current_user.is_authenticated:
        return _success(
            {
                "authenticated": True,
                "user": _user_payload(),
                "context": _context_payload(),
                "csrf_token": issue_csrf_token(),
            }
        )

    if not is_rate_allowed("api_login", LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_S):
        return _error("rate_limited", "Muitas requisições. Tente novamente em instantes.", 429)

    payload = _json_payload()
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return _error("validation_error", "username e password são obrigatórios.", 422)

    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        return _error("invalid_credentials", "Usuário ou senha inválidos.", 401)

    login_user(
        AppUser(
            user_id=user["id"],
            username=user["username"],
            role=user["role"],
        )
    )

    clinic_id = resolve_default_clinic_id(user["id"])
    membership = None
    if clinic_id is not None:
        session["active_clinic_id"] = clinic_id
        membership = get_user_membership(user["id"], clinic_id)
        if membership:
            session["active_tenant_id"] = membership.get("tenant_id") or membership.get("clinic_id")

    return _success(
        {
            "authenticated": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "global_role": user["role"],
            },
            "context": _context_payload(membership),
            "csrf_token": issue_csrf_token(force_new=True),
        }
    )


@api_v1_bp.post("/session/logout")
@api_auth_required
def session_logout():
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    logout_user()
    session.pop("csrf_token", None)
    session.pop("_csrf_token", None)
    session.pop("active_clinic_id", None)
    session.pop("active_tenant_id", None)
    return _success({"success": True})


@api_v1_bp.get("/context")
@api_auth_required
def context():
    return _success(_context_payload())


@api_v1_bp.get("/dashboard")
@api_role_required("Admin", "Medico")
def dashboard():
    charts_by_contact = [
        {"label": row.get("contact_name") or "Sem nome", "count": row.get("message_count", 0)}
        for row in message_repository.aggregate_messages_by_contact(g.clinic_id)
    ]
    charts_by_day = [
        {"date": row.get("message_date"), "count": row.get("total_messages", 0)}
        for row in message_repository.aggregate_messages_by_day(g.clinic_id)
    ]
    return _success(
        {
            "metrics": get_dashboard_metrics(),
            "charts": {
                "messages_by_contact": charts_by_contact,
                "messages_by_day": charts_by_day,
            },
        }
    )


@api_v1_bp.get("/dashboard/messages")
@api_role_required("Admin", "Medico")
def dashboard_messages():
    sender = request.args.get("sender")
    page, page_size = _pagination_args()
    messages = message_repository.list_messages(g.clinic_id, sender)
    items, meta = _paginate(messages, page, page_size)
    return _success(items, meta=meta)


@api_v1_bp.get("/messages")
@api_role_required("Admin", "Medico", "Atendente")
def messages():
    sender = request.args.get("sender")
    page, page_size = _pagination_args()
    messages_list = message_repository.list_messages(g.clinic_id, sender)
    items, meta = _paginate(messages_list, page, page_size)
    return _success(items, meta=meta)


@api_v1_bp.get("/attendances")
@api_role_required("Admin", "Medico")
def attendances():
    status = request.args.get("status") or None
    page, page_size = _pagination_args()
    reports = list_reports(g.clinic_id, status=status)
    items, meta = _paginate(reports, page, page_size)
    return _success(items, meta=meta)


@api_v1_bp.get("/attendances/<int:report_id>")
@api_role_required("Admin", "Medico")
def attendance_detail(report_id: int):
    report = get_report(g.clinic_id, report_id)
    if not report:
        return _error("not_found", "Atendimento não encontrado.", 404)
    return _success(_build_attendance_detail(report))


@api_v1_bp.post("/attendances/<int:report_id>/review")
@api_role_required("Admin", "Medico")
def attendance_review(report_id: int):
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    report = get_report(g.clinic_id, report_id)
    if not report:
        return _error("not_found", "Atendimento não encontrado.", 404)

    if report.get("status") != "revisado":
        mark_reviewed(g.clinic_id, report_id)
        if report.get("patient_id"):
            create_event(
                clinic_id=g.clinic_id,
                tenant_id=getattr(g, "tenant_id", None),
                patient_id=report["patient_id"],
                event_type="anamnesis_reviewed",
                journey_stage="caso_revisado",
                title="Atendimento revisado pelo médico",
                description="O relatório da anamnese foi validado e arquivado no painel clínico.",
                source_type="anamnesis_report",
                source_id=report_id,
                metadata={"status": "revisado"},
            )

    updated = get_report(g.clinic_id, report_id)
    return _success(
        {
            "reviewed": True,
            "report_id": report_id,
            "status": updated.get("status") if updated else "revisado",
        }
    )


@api_v1_bp.post("/attendances/<int:report_id>/medical-record")
@api_role_required("Admin", "Medico")
def attendance_medical_record(report_id: int):
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    report = get_report(g.clinic_id, report_id)
    if not report:
        return _error("not_found", "Atendimento não encontrado.", 404)

    patient_id = report.get("patient_id")
    if not patient_id:
        return _error("conflict", "Este atendimento ainda não possui paciente vinculado.", 409)

    payload = _json_payload()
    consultation_status = (payload.get("consultation_status") or "em_revisao").strip()
    medical_observations = (payload.get("medical_observations") or "").strip()
    clinical_assessment = (payload.get("clinical_assessment") or "").strip()
    conduct = (payload.get("conduct") or "").strip()
    follow_up_plan = (payload.get("follow_up_plan") or "").strip()
    requested_exams = _parse_requested_exams(payload.get("requested_exams"))

    if not any([medical_observations, clinical_assessment, conduct, follow_up_plan, requested_exams]):
        return _error("validation_error", "Preencha pelo menos um campo clínico antes de salvar o prontuário.", 422)

    result = upsert_consultation_entry(
        clinic_id=g.clinic_id,
        tenant_id=getattr(g, "tenant_id", None),
        patient_id=patient_id,
        author_user_id=int(current_user.id),
        author_name=getattr(current_user, "username", "medico"),
        source_report_id=report_id,
        consultation_status=consultation_status,
        medical_observations=medical_observations,
        clinical_assessment=clinical_assessment,
        conduct=conduct,
        requested_exams=requested_exams,
        follow_up_plan=follow_up_plan,
    )

    if not result["enabled"]:
        return _error("schema_unavailable", "O schema de prontuário ainda não foi aplicado no banco local.", 409)

    if consultation_status == "consulta_nao_realizada":
        event_type = "consultation_not_completed"
        journey_stage = "ausencia_em_consulta"
        title = "Consulta não realizada"
        description = "A consulta não foi concluída e o caso permanece em acompanhamento operacional."
    elif result["created"]:
        event_type = "conduct_registered"
        journey_stage = "conduta_registrada"
        title = "Conduta clínica registrada"
        description = "O médico registrou a decisão clínica inicial no prontuário."
    else:
        event_type = "medical_record_updated"
        journey_stage = "prontuario_atualizado"
        title = "Prontuário atualizado"
        description = "A entrada clínica vinculada ao caso foi atualizada."

    create_event(
        clinic_id=g.clinic_id,
        tenant_id=getattr(g, "tenant_id", None),
        patient_id=patient_id,
        event_type=event_type,
        journey_stage=journey_stage,
        title=title,
        description=description,
        source_type="medical_record_entry",
        source_id=result["entry_id"],
        metadata={
            "consultation_status": consultation_status,
            "requested_exams_count": len(requested_exams),
        },
    )

    return _success(
        {
            "saved": True,
            "medical_record_id": result["medical_record_id"],
            "entry_id": result["entry_id"],
            "created": result["created"],
        }
    )


@api_v1_bp.get("/patients/<int:patient_id>/timeline")
@api_role_required("Admin", "Medico")
def patient_timeline(patient_id: int):
    try:
        limit = int(request.args.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(limit, 100))
    events = list_patient_events(g.clinic_id, patient_id, limit=limit)
    return _success(events)


@api_v1_bp.get("/patients/<int:patient_id>/medical-record")
@api_role_required("Admin", "Medico")
def patient_medical_record(patient_id: int):
    record = get_medical_record_by_patient(g.clinic_id, patient_id)
    entries = list_patient_record_entries(g.clinic_id, patient_id, limit=50)
    return _success({"medical_record": record, "entries": entries})


@api_v1_bp.get("/appointments")
@api_role_required("Admin", "Medico", "Atendente")
def appointments_list():
    page, page_size = _pagination_args()
    appointments = list_appointments()
    items, meta = _paginate(appointments, page, page_size)
    return _success(items, meta=meta)


@api_v1_bp.post("/appointments")
@api_role_required("Admin", "Medico", "Atendente")
def appointments_create():
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    patient_name = (payload.get("patient_name") or "").strip()
    appointment_date = (payload.get("appointment_date") or "").strip()

    if not patient_name or not appointment_date:
        return _error("validation_error", "patient_name e appointment_date são obrigatórios.", 422)

    try:
        appointment_id = create_appointment_from_api(patient_name, appointment_date)
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)

    return _success({"created": True, "appointment_id": appointment_id}, status=201)


@api_v1_bp.get("/admin/ai-metrics")
@api_role_required("Admin", "Medico")
def ai_metrics():
    return _success(
        {
            "summary": get_ai_audit_summary(),
            "recent_logs": get_recent_ai_logs(10),
        }
    )
