"""Endpoints de revisao e aprovacao bilateral de documentos (F4.7 do SCC).

Expoe sobre ``regulatory_reports``:

    POST /api/v1/reports/<int:report_id>/review
        Body: {"action": <one of ALL_ACTIONS>, "notes": "..."}

    GET  /api/v1/reports/<int:report_id>/status
        {status atual, ultimo step, approved_by/at quando aprovado}

    GET  /api/v1/reports/<int:report_id>/history
        lista ordenada de steps

Tenant scoping: o report precisa pertencer ao tenant do usuario
autenticado (g.tenant_id). 403 quando viola.

Role policy:
  - Admin: todas as acoes.
  - Medico: submit_to_rt, rt_approve, rt_approve_final, rt_reject.
  - Atendente/Paciente: sem acesso.

Regras de negocio formais (transicoes de estado, signature_hash) vivem
em :mod:`src.services.document_review_service`. Este modulo cuida
apenas da camada HTTP: parsing, autorizacao, erros tipados -> status.
"""

from __future__ import annotations

import logging
from typing import Optional

from flask import Blueprint, g

from src.infra.database import db_cursor
from src.infra.security import get_effective_roles, normalize_role_name
from src.services.document_review_service import (
    ALL_ACTIONS,
    InvalidActionError,
    InvalidTransitionError,
    ReportNotFoundError,
    ReviewStep,
    get_report_status,
    list_workflow_steps,
    transition,
)
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _require_json_csrf,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.document_reviews")

document_reviews_bp = Blueprint(
    "document_reviews", __name__, url_prefix="/api/v1/reports"
)


# Cada acao declara qual role(s) podem executa-la. Admin sempre pode;
# Medico pode acoes RT-side; legal_* fica restrito a Admin por ora
# (papel juridico nao existe ainda como role formal).
#
# Nomes seguem get_effective_roles() apos normalize_role_name — 'Admin',
# 'Medico', etc. (case-sensitive).
_ROLE_BY_ACTION: dict[str, frozenset[str]] = {
    "submit_to_rt":     frozenset({"Admin", "Medico"}),
    "rt_approve":       frozenset({"Admin", "Medico"}),
    "rt_approve_final": frozenset({"Admin", "Medico"}),
    "rt_reject":        frozenset({"Admin", "Medico"}),
    "legal_approve":    frozenset({"Admin"}),
    "legal_reject":     frozenset({"Admin"}),
}


def _effective_actor_role() -> str:
    """Devolve o primeiro role relevante para logging no workflow."""
    roles = get_effective_roles() or []
    # Ordem de prioridade: Admin > Medico > outros
    for preferred in ("Admin", "Medico"):
        if preferred in roles:
            return preferred
    return roles[0] if roles else "unknown"


def _check_action_authorized(action: str) -> Optional:
    roles = get_effective_roles() or set()
    allowed = _ROLE_BY_ACTION.get(action, frozenset())
    if not allowed.intersection(roles):
        return _error(
            "forbidden",
            f"Role atual nao pode executar a acao '{action}'.",
            403,
        )
    return None


def _current_tenant_id() -> Optional[int]:
    tid = getattr(g, "tenant_id", None)
    return int(tid) if tid is not None else None


def _load_report_tenant(report_id: int) -> Optional[int]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT tenant_id FROM regulatory_reports WHERE id = %s",
            (report_id,),
        )
        row = cursor.fetchone()
    return int(row["tenant_id"]) if row else None


def _step_payload(step: ReviewStep) -> dict:
    return {
        "id": step.id,
        "report_id": step.report_id,
        "from_status": step.from_status,
        "to_status": step.to_status,
        "action": step.action,
        "actor_user_id": step.actor_user_id,
        "actor_role": step.actor_role,
        "notes": step.notes,
        "content_hash_at_review": step.content_hash_at_review,
        "signature_hash": step.signature_hash,
        "reviewed_at": step.reviewed_at,
    }


# =====================================================================
# GET /<id>/status
# =====================================================================

@document_reviews_bp.get("/<int:report_id>/status")
@api_role_required("Admin", "Medico")
def get_status(report_id: int):
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        return _error("tenant_context_missing",
                      "Tenant nao resolvido.", 400)

    try:
        data = get_report_status(report_id)
    except ReportNotFoundError as exc:
        return _error("report_not_found", str(exc), 404)

    if int(data["report"]["tenant_id"]) != tenant_id:
        return _error("forbidden", "Report pertence a outro tenant.", 403)

    return _success(data)


# =====================================================================
# GET /<id>/history
# =====================================================================

@document_reviews_bp.get("/<int:report_id>/history")
@api_role_required("Admin", "Medico")
def get_history(report_id: int):
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        return _error("tenant_context_missing",
                      "Tenant nao resolvido.", 400)

    owner = _load_report_tenant(report_id)
    if owner is None:
        return _error("report_not_found",
                      f"Report {report_id} nao encontrado.", 404)
    if owner != tenant_id:
        return _error("forbidden", "Report pertence a outro tenant.", 403)

    steps = list_workflow_steps(report_id)
    return _success([_step_payload(s) for s in steps])


# =====================================================================
# POST /<id>/review
# =====================================================================

@document_reviews_bp.post("/<int:report_id>/review")
@api_role_required("Admin", "Medico")
def post_review(report_id: int):
    csrf_error = _require_json_csrf()
    if csrf_error is not None:
        return csrf_error

    payload = _json_payload()
    action = (payload.get("action") or "").strip()
    notes = payload.get("notes")
    if not action:
        return _error("missing_action", "Campo 'action' e obrigatorio.", 400)
    if action not in ALL_ACTIONS:
        return _error(
            "invalid_action",
            f"'action' deve ser um de {list(ALL_ACTIONS)}.",
            422,
        )

    denied = _check_action_authorized(action)
    if denied is not None:
        return denied

    tenant_id = _current_tenant_id()
    if tenant_id is None:
        return _error("tenant_context_missing",
                      "Tenant nao resolvido.", 400)

    owner = _load_report_tenant(report_id)
    if owner is None:
        return _error("report_not_found",
                      f"Report {report_id} nao encontrado.", 404)
    if owner != tenant_id:
        return _error("forbidden", "Report pertence a outro tenant.", 403)

    actor_user_id = int(getattr(g, "user_id", 0) or 0)
    if not actor_user_id:
        # Defesa redundante — api_role_required ja exige autenticado.
        return _error("unauthenticated", "Usuario nao identificado.", 401)

    actor_role = _effective_actor_role()

    try:
        step = transition(
            report_id,
            action,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            notes=notes,
        )
    except ReportNotFoundError as exc:
        return _error("report_not_found", str(exc), 404)
    except InvalidTransitionError as exc:
        return _error("invalid_transition", str(exc), 409)
    except InvalidActionError as exc:
        return _error("invalid_action", str(exc), 422)

    logger.info(
        "review_submitted report=%s action=%s actor=%s tenant=%s",
        report_id, action, actor_user_id, tenant_id,
    )
    return _success(
        {"step": _step_payload(step), "new_status": step.to_status},
        status=201,
    )
