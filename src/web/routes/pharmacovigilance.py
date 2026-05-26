"""Pharmacovigilance API (F3.6 do docs/BACKLOG_SCC.md).

Blueprint do painel medico/clinica para eventos adversos. Costura as
camadas F3.3 (`adverse_event_service`), F3.4 (skill `triage_adverse_event`)
e F3.5 (`integrations.vigimed`) atraves do orquestrador
`pharmacovigilance_service`.

Prefixo: `/api/v1/pharmacovigilance`. Todas as operacoes sao escopadas
ao tenant do usuario autenticado (`g.tenant_id`). Reads aceitam roles
Admin/Medico; writes exigem Admin/Medico + CSRF.

Webhook do WhatsApp NAO usa este blueprint — chama
`adverse_event_service.capture_adverse_event` direto, com sua propria
auth HMAC.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from flask import Blueprint, g, request

from src.services import (
    adverse_event_service,
    pharmacovigilance_service,
)
from src.services.adverse_event_service import (
    AdverseEvent,
    AdverseEventValidationError,
)
from src.services.pharmacovigilance_service import (
    AdverseEventNotFoundError,
    DashboardSummary,
    NotificationRecord,
)
from src.integrations.vigimed import (
    PharmacovigilanceError,
    UnknownProviderError,
)
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _require_json_csrf,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.pharmacovigilance_routes")

pharmacovigilance_bp = Blueprint(
    "pharmacovigilance", __name__, url_prefix="/api/v1/pharmacovigilance"
)


# =====================================================================
# Helpers
# =====================================================================


def _current_tenant_id() -> Optional[int]:
    tenant_id = getattr(g, "tenant_id", None)
    if tenant_id is None:
        tenant_id = getattr(g, "clinic_id", None)
    return int(tenant_id) if tenant_id is not None else None


def _require_tenant_context():
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        return None, _error(
            "tenant_context_missing",
            "Contexto de tenant nao resolvido para o usuario autenticado.",
            400,
        )
    return tenant_id, None


def _current_user_id() -> Optional[int]:
    """Para gravacao de `triaged_by` etc."""
    try:
        from flask_login import current_user

        if current_user.is_authenticated:
            return int(current_user.id)
    except RuntimeError:
        # flask_login levanta RuntimeError fora do request context (jobs, CLI)
        return None
    return None


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"datetime invalido: {value!r}") from exc


def _serialize_event(event: AdverseEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "tenant_id": event.tenant_id,
        "member_id": event.member_id,
        "preparation_id": event.preparation_id,
        "reported_at": event.reported_at.isoformat() if event.reported_at else None,
        "event_onset_at": (
            event.event_onset_at.isoformat() if event.event_onset_at else None
        ),
        "severity": event.severity,
        "description": event.description,
        "reported_via": event.reported_via,
        "ai_triage_result": event.ai_triage_result,
        "triaged_by": event.triaged_by,
        "clinical_assessment": event.clinical_assessment,
        "outcome": event.outcome,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
        "requires_regulatory_notification": event.requires_regulatory_notification,
    }


def _serialize_notification(record: NotificationRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "adverse_event_id": record.adverse_event_id,
        "notification_target": record.notification_target,
        "notified_at": record.notified_at.isoformat() if record.notified_at else None,
        "notification_reference": record.notification_reference,
        "response_received_at": (
            record.response_received_at.isoformat()
            if record.response_received_at
            else None
        ),
        "response_payload": record.response_payload,
    }


def _serialize_dashboard(s: DashboardSummary) -> dict[str, Any]:
    return {
        "tenant_id": s.tenant_id,
        "period_days": s.period_days,
        "generated_at": s.generated_at.isoformat(),
        "total_events": s.total_events,
        "events_by_severity": s.events_by_severity,
        "events_requiring_notification": s.events_requiring_notification,
        "notifications_by_target": s.notifications_by_target,
    }


# =====================================================================
# Adverse events — captura e listagem
# =====================================================================


@pharmacovigilance_bp.post("/adverse-events")
@api_role_required("Admin", "Medico")
def capture_adverse_event_endpoint():
    """Captura manual de evento adverso pelo painel."""
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    description = (payload.get("description") or "").strip()
    severity = payload.get("severity")
    reported_via = payload.get("reported_via")

    if not description:
        return _error("validation_error", "description e obrigatorio.", 422)
    if not severity:
        return _error("validation_error", "severity e obrigatorio.", 422)
    if not reported_via:
        return _error("validation_error", "reported_via e obrigatorio.", 422)

    member_id = payload.get("member_id")
    preparation_id = payload.get("preparation_id")
    try:
        reported_at = _parse_iso_datetime(payload.get("reported_at"))
        event_onset_at = _parse_iso_datetime(payload.get("event_onset_at"))
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)

    try:
        event = adverse_event_service.capture_adverse_event(
            tenant_id=tenant_id,
            description=description,
            severity=severity,
            reported_via=reported_via,
            member_id=int(member_id) if member_id is not None else None,
            preparation_id=int(preparation_id) if preparation_id is not None else None,
            reported_at=reported_at,
            event_onset_at=event_onset_at,
        )
    except AdverseEventValidationError as exc:
        return _error("validation_error", str(exc), 422)

    return _success({"adverse_event": _serialize_event(event)}, status=201)


@pharmacovigilance_bp.get("/adverse-events")
@api_role_required("Admin", "Medico")
def list_adverse_events_endpoint():
    """Lista eventos do tenant com filtros opcionais.

    Query params: severity, reported_via, member_id, has_triage,
    since (ISO), until (ISO), limit (1..500, default 100), offset.
    """
    tenant_id, err = _require_tenant_context()
    if err:
        return err

    args = request.args
    severity = args.get("severity") or None
    reported_via = args.get("reported_via") or None
    member_id = args.get("member_id")
    has_triage_raw = args.get("has_triage")

    try:
        since = _parse_iso_datetime(args.get("since"))
        until = _parse_iso_datetime(args.get("until"))
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)

    try:
        limit = max(1, min(int(args.get("limit", 100)), 500))
    except (TypeError, ValueError):
        limit = 100
    try:
        offset = max(0, int(args.get("offset", 0)))
    except (TypeError, ValueError):
        offset = 0

    has_triage: Optional[bool]
    if has_triage_raw is None:
        has_triage = None
    elif has_triage_raw.lower() in ("true", "1", "yes"):
        has_triage = True
    elif has_triage_raw.lower() in ("false", "0", "no"):
        has_triage = False
    else:
        return _error(
            "validation_error",
            "has_triage deve ser true|false (omitido = sem filtro).",
            422,
        )

    try:
        events = adverse_event_service.list_events(
            tenant_id,
            severity=severity,
            reported_via=reported_via,
            member_id=int(member_id) if member_id else None,
            has_triage=has_triage,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )
    except AdverseEventValidationError as exc:
        return _error("validation_error", str(exc), 422)

    return _success(
        {"adverse_events": [_serialize_event(e) for e in events]},
        meta={"limit": limit, "offset": offset, "count": len(events)},
    )


@pharmacovigilance_bp.get("/adverse-events/<int:event_id>")
@api_role_required("Admin", "Medico")
def get_adverse_event_endpoint(event_id: int):
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    event = adverse_event_service.get_event(event_id, tenant_id=tenant_id)
    if event is None:
        return _error("not_found", f"Evento {event_id} nao encontrado.", 404)
    return _success({"adverse_event": _serialize_event(event)})


# =====================================================================
# Atualizacoes clinicas (parecer / outcome)
# =====================================================================


@pharmacovigilance_bp.put("/adverse-events/<int:event_id>/clinical-assessment")
@api_role_required("Admin", "Medico")
def set_clinical_assessment_endpoint(event_id: int):
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    assessment = payload.get("assessment", "")
    try:
        updated = adverse_event_service.set_clinical_assessment(
            event_id, tenant_id=tenant_id, assessment=assessment
        )
    except AdverseEventValidationError as exc:
        return _error("validation_error", str(exc), 422)
    if updated is None:
        return _error("not_found", f"Evento {event_id} nao encontrado.", 404)
    return _success({"adverse_event": _serialize_event(updated)})


@pharmacovigilance_bp.put("/adverse-events/<int:event_id>/outcome")
@api_role_required("Admin", "Medico")
def set_outcome_endpoint(event_id: int):
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    outcome = payload.get("outcome", "")
    try:
        updated = adverse_event_service.set_outcome(
            event_id, tenant_id=tenant_id, outcome=outcome
        )
    except AdverseEventValidationError as exc:
        return _error("validation_error", str(exc), 422)
    if updated is None:
        return _error("not_found", f"Evento {event_id} nao encontrado.", 404)
    return _success({"adverse_event": _serialize_event(updated)})


# =====================================================================
# Triagem IA (F3.4) e Notificacao regulatoria (F3.5)
# =====================================================================


@pharmacovigilance_bp.post("/adverse-events/<int:event_id>/triage")
@api_role_required("Admin", "Medico")
def triage_event_endpoint(event_id: int):
    """Invoca a skill heuristica e grava `ai_triage_result`."""
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    triaged_by = _current_user_id()
    try:
        result = pharmacovigilance_service.triage_event(
            event_id, tenant_id=tenant_id, triaged_by=triaged_by
        )
    except AdverseEventNotFoundError as exc:
        return _error("not_found", str(exc), 404)

    response: dict[str, Any] = {
        "ok": result.get("ok", False),
        "severity_reported": result.get("severity_reported"),
        "severity_suggested": result.get("severity_suggested"),
        "escalated": result.get("escalated"),
        "notify_required": result.get("notify_required"),
        "red_flags": result.get("red_flags"),
        "matched_by_level": result.get("matched_by_level"),
        "reasoning": result.get("reasoning"),
        "model_version": result.get("model_version"),
    }
    refreshed = result.get("event")
    if isinstance(refreshed, AdverseEvent):
        response["adverse_event"] = _serialize_event(refreshed)
    if "persist_error" in result:
        response["persist_error"] = result["persist_error"]
    return _success(response)


@pharmacovigilance_bp.post("/adverse-events/<int:event_id>/notify")
@api_role_required("Admin", "Medico")
def notify_event_endpoint(event_id: int):
    """Submete a notificacao regulatoria e grava em
    `pharmacovigilance_notifications`.

    Body opcional: `{"provider": "mock|vigimed|notivisa"}`. Sem provider,
    usa env `ANVISA_NOTIFICATION_PROVIDER` ou default 'mock'.
    """
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    provider = payload.get("provider")

    try:
        record = pharmacovigilance_service.notify_event(
            event_id, tenant_id=tenant_id, provider=provider
        )
    except AdverseEventNotFoundError as exc:
        return _error("not_found", str(exc), 404)
    except UnknownProviderError as exc:
        return _error("validation_error", str(exc), 422)
    except PharmacovigilanceError as exc:
        return _error("notification_failed", str(exc), 502)

    return _success(
        {"notification": _serialize_notification(record)}, status=201
    )


@pharmacovigilance_bp.get("/adverse-events/<int:event_id>/notifications")
@api_role_required("Admin", "Medico")
def list_notifications_endpoint(event_id: int):
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    try:
        records = pharmacovigilance_service.list_notifications_for_event(
            event_id, tenant_id=tenant_id
        )
    except AdverseEventNotFoundError as exc:
        return _error("not_found", str(exc), 404)
    return _success(
        {"notifications": [_serialize_notification(r) for r in records]},
        meta={"count": len(records)},
    )


# =====================================================================
# Dashboard epidemiologico
# =====================================================================


@pharmacovigilance_bp.get("/dashboard")
@api_role_required("Admin", "Medico")
def dashboard_endpoint():
    """Snapshot agregado: counts por severidade + counts por target.

    Query param `period_days` (default 30, max 365).
    """
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    try:
        period_days = max(1, min(int(request.args.get("period_days", 30)), 365))
    except (TypeError, ValueError):
        period_days = 30

    summary = pharmacovigilance_service.dashboard_summary(
        tenant_id, period_days=period_days
    )
    return _success(_serialize_dashboard(summary))
