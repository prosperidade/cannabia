"""Regulatory Reporting API (F3.7 do docs/BACKLOG_SCC.md).

Dashboards ANVISA-ready com indicadores calculados em tempo real sobre
as 6 tabelas regulatorias (migration 032) e a view
`v_sandbox_indicator_dashboard` (migration 036 / F6.2).

Read-only. Tudo escopado ao tenant do usuario autenticado
(`g.tenant_id`). Roles: Admin/Medico (mesmo padrao de governance/
compliance/pharmacovigilance).

NAO confundir com `regulatory.py` (legislation files via Google Files
API). Este blueprint tem prefixo distinto: `/api/v1/regulatory-reporting`.

Conteudo:
  GET /projects                     — lista sandbox_projects
  GET /projects/<id>                — projeto + protocolo vigente
  GET /indicators                   — view dashboard (filtros opcionais)
  GET /indicators/<id>              — detalhe + history para grafico
  GET /submissions                  — regulatory_submissions filtraveis
  GET /reports                      — regulatory_reports filtraveis
  GET /overview                     — KPIs top-level para painel
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from flask import Blueprint, g, request

from src.repositories import regulatory_reporting_repository as repo
from src.web.routes.api_v1 import (
    _error,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.regulatory_reporting")

regulatory_reporting_bp = Blueprint(
    "regulatory_reporting",
    __name__,
    url_prefix="/api/v1/regulatory-reporting",
)


# Whitelists espelhando os CHECKs da migration 032 — usadas para validar
# filtros antes de tocar o DB.
_PROJECT_STATUSES = (
    "draft", "submitted", "under_review", "approved",
    "active", "suspended", "concluded", "discontinued",
)
_REPORT_TYPES = (
    "work_plan", "communication_plan", "discontinuity_plan",
    "monitoring_plan", "risk_management_plan",
    "final_monitoring_opinion", "eligibility_dossier",
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


def _parse_iso(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"datetime invalido: {value!r}") from exc


def _parse_bool(raw: Optional[str]) -> Optional[bool]:
    if raw is None:
        return None
    low = raw.lower()
    if low in ("true", "1", "yes"):
        return True
    if low in ("false", "0", "no"):
        return False
    raise ValueError(f"booleano invalido: {raw!r}")


def _bounded_int(value: Any, *, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(int(value), hi))
    except (TypeError, ValueError):
        return default


# =====================================================================
# Aggregations (puras, testaveis)
# =====================================================================


def compute_indicators_score(counts: dict[str, int]) -> int:
    """
    Score 0-100 = % de indicadores mandatorios `on_target`.

    Sem indicadores mandatorios, retorna 0 (overview ainda renderiza
    sinalizando ausencia, e a UI decide se exibe N/A).
    """
    total = int(counts.get("mandatory_total") or 0)
    if total <= 0:
        return 0
    on_target = int(counts.get("mandatory_on_target") or 0)
    return round(on_target / total * 100)


def compute_overview(
    *,
    tenant_id: int,
    projects_by_status: dict[str, int],
    indicator_counts: dict[str, int],
    submissions_pending: int,
    reports_by_type: dict[str, int],
) -> dict[str, Any]:
    """
    Empacota KPIs top-level. Funcao pura — recebe os 4 agregados
    pre-calculados pelo repo, devolve dict serializavel.
    """
    active_projects = sum(
        n for s, n in projects_by_status.items()
        if s in ("submitted", "under_review", "approved", "active")
    )
    return {
        "tenant_id": tenant_id,
        "projects": {
            "total": sum(projects_by_status.values()),
            "active_or_pending": active_projects,
            "by_status": projects_by_status,
        },
        "indicators": {
            **indicator_counts,
            "score": compute_indicators_score(indicator_counts),
        },
        "submissions": {
            "awaiting_anvisa_response": submissions_pending,
        },
        "reports": {
            "total": sum(reports_by_type.values()),
            "by_type": reports_by_type,
        },
    }


# =====================================================================
# Serializers
# =====================================================================


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if isinstance(dt, datetime) else None


def _serialize_project(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "project_code": row["project_code"],
        "title": row["title"],
        "status": row["status"],
        "submitted_at": _iso(row.get("submitted_at")),
        "approved_at": _iso(row.get("approved_at")),
        "started_at": _iso(row.get("started_at")),
        "concluded_at": _iso(row.get("concluded_at")),
        "anvisa_reference": row.get("anvisa_reference"),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


def _serialize_protocol(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "protocol_version": row["protocol_version"],
        "scope": row.get("scope"),
        "applicable_norms": row.get("applicable_norms"),
        "modulated_norms": row.get("modulated_norms"),
        "monitoring_parameters": row.get("monitoring_parameters"),
        "discontinuity_plan": row.get("discontinuity_plan"),
        "quality_requirements": row.get("quality_requirements"),
        "data_sharing_obligations": row.get("data_sharing_obligations"),
        "effective_from": _iso(row.get("effective_from")),
        "effective_until": _iso(row.get("effective_until")),
        "created_at": _iso(row.get("created_at")),
        "is_active": row.get("effective_until") is None,
    }


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _serialize_indicator(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "indicator_id": row["indicator_id"],
        "project_id": row["project_id"],
        "tenant_id": row["tenant_id"],
        "indicator_code": row["indicator_code"],
        "indicator_name": row["indicator_name"],
        "unit": row.get("unit"),
        "target_value": _to_float(row.get("target_value")),
        "reporting_frequency": row.get("reporting_frequency"),
        "is_mandatory": row.get("is_mandatory"),
        "latest_value": _to_float(row.get("latest_value")),
        "latest_period_start": _iso(row.get("latest_period_start")),
        "latest_period_end": _iso(row.get("latest_period_end")),
        "latest_calculated_at": _iso(row.get("latest_calculated_at")),
        "n_periods": int(row.get("n_periods") or 0),
        "on_target": row.get("on_target"),
    }


def _serialize_indicator_value(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "indicator_id": row["indicator_id"],
        "period_start": _iso(row.get("period_start")),
        "period_end": _iso(row.get("period_end")),
        "calculated_value": _to_float(row.get("calculated_value")),
        "calculation_details": row.get("calculation_details"),
        "calculated_at": _iso(row.get("calculated_at")),
    }


def _serialize_submission(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "project_id": row.get("project_id"),
        "submission_type": row["submission_type"],
        "submitted_at": _iso(row.get("submitted_at")),
        "submitted_by": row.get("submitted_by"),
        "payload_uri": row.get("payload_uri"),
        "payload_hash": row.get("payload_hash"),
        "anvisa_response_uri": row.get("anvisa_response_uri"),
        "anvisa_response_at": _iso(row.get("anvisa_response_at")),
        "awaiting_response": row.get("anvisa_response_at") is None,
        "created_at": _iso(row.get("created_at")),
    }


def _serialize_report(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "project_id": row.get("project_id"),
        "report_type": row["report_type"],
        "version": row["version"],
        "content_uri": row.get("content_uri"),
        "content_hash": row.get("content_hash"),
        "generated_at": _iso(row.get("generated_at")),
        "approved_by": row.get("approved_by"),
        "approved_at": _iso(row.get("approved_at")),
        "is_approved": row.get("approved_at") is not None,
    }


# =====================================================================
# Endpoints — Projects
# =====================================================================


@regulatory_reporting_bp.get("/projects")
@api_role_required("Admin", "Medico")
def list_projects_endpoint():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    args = request.args
    status = args.get("status") or None
    if status is not None and status not in _PROJECT_STATUSES:
        return _error(
            "validation_error",
            f"status invalido: {status!r}. Esperado um de {_PROJECT_STATUSES}.",
            422,
        )
    limit = _bounded_int(args.get("limit", 200), default=200, lo=1, hi=500)
    offset = _bounded_int(args.get("offset", 0), default=0, lo=0, hi=10_000_000)

    rows = repo.list_projects(
        tenant_id, status=status, limit=limit, offset=offset
    )
    return _success(
        {"projects": [_serialize_project(r) for r in rows]},
        meta={"limit": limit, "offset": offset, "count": len(rows)},
    )


@regulatory_reporting_bp.get("/projects/<int:project_id>")
@api_role_required("Admin", "Medico")
def get_project_endpoint(project_id: int):
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    project = repo.get_project(project_id, tenant_id=tenant_id)
    if project is None:
        return _error(
            "not_found", f"Projeto {project_id} nao encontrado.", 404
        )
    protocol = repo.get_active_protocol(project_id, tenant_id=tenant_id)
    return _success({
        "project": _serialize_project(project),
        "active_protocol": (
            _serialize_protocol(protocol) if protocol else None
        ),
    })


# =====================================================================
# Endpoints — Indicators
# =====================================================================


@regulatory_reporting_bp.get("/indicators")
@api_role_required("Admin", "Medico")
def list_indicators_endpoint():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    args = request.args
    project_id = args.get("project_id")
    try:
        only_mandatory = _parse_bool(args.get("only_mandatory")) or False
        only_off_target = _parse_bool(args.get("only_off_target")) or False
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)

    rows = repo.list_indicator_dashboard(
        tenant_id,
        project_id=int(project_id) if project_id else None,
        only_mandatory=only_mandatory,
        only_off_target=only_off_target,
    )
    return _success(
        {"indicators": [_serialize_indicator(r) for r in rows]},
        meta={"count": len(rows)},
    )


@regulatory_reporting_bp.get("/indicators/<int:indicator_id>")
@api_role_required("Admin", "Medico")
def get_indicator_endpoint(indicator_id: int):
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    args = request.args

    row = repo.get_indicator_dashboard_row(
        indicator_id, tenant_id=tenant_id
    )
    if row is None:
        return _error(
            "not_found", f"Indicador {indicator_id} nao encontrado.", 404
        )

    try:
        since = _parse_iso(args.get("since"))
        until = _parse_iso(args.get("until"))
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)
    history_limit = _bounded_int(
        args.get("history_limit", 365), default=365, lo=1, hi=2000
    )

    history = repo.list_indicator_history(
        indicator_id,
        tenant_id=tenant_id,
        since=since,
        until=until,
        limit=history_limit,
    )
    return _success({
        "indicator": _serialize_indicator(row),
        "history": [_serialize_indicator_value(h) for h in history],
    })


# =====================================================================
# Endpoints — Submissions
# =====================================================================


@regulatory_reporting_bp.get("/submissions")
@api_role_required("Admin", "Medico")
def list_submissions_endpoint():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    args = request.args
    try:
        since = _parse_iso(args.get("since"))
        until = _parse_iso(args.get("until"))
        awaiting_response = _parse_bool(args.get("awaiting_response"))
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)
    project_id = args.get("project_id")
    submission_type = args.get("submission_type") or None
    limit = _bounded_int(args.get("limit", 100), default=100, lo=1, hi=500)
    offset = _bounded_int(args.get("offset", 0), default=0, lo=0, hi=10_000_000)

    rows = repo.list_submissions(
        tenant_id,
        project_id=int(project_id) if project_id else None,
        submission_type=submission_type,
        since=since,
        until=until,
        awaiting_response=awaiting_response,
        limit=limit,
        offset=offset,
    )
    return _success(
        {"submissions": [_serialize_submission(r) for r in rows]},
        meta={"limit": limit, "offset": offset, "count": len(rows)},
    )


# =====================================================================
# Endpoints — Reports
# =====================================================================


@regulatory_reporting_bp.get("/reports")
@api_role_required("Admin", "Medico")
def list_reports_endpoint():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    args = request.args
    project_id = args.get("project_id")
    report_type = args.get("report_type") or None
    if report_type is not None and report_type not in _REPORT_TYPES:
        return _error(
            "validation_error",
            f"report_type invalido: {report_type!r}. "
            f"Esperado um de {_REPORT_TYPES}.",
            422,
        )
    try:
        only_approved = _parse_bool(args.get("only_approved"))
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)
    limit = _bounded_int(args.get("limit", 100), default=100, lo=1, hi=500)
    offset = _bounded_int(args.get("offset", 0), default=0, lo=0, hi=10_000_000)

    rows = repo.list_reports(
        tenant_id,
        project_id=int(project_id) if project_id else None,
        report_type=report_type,
        only_approved=only_approved,
        limit=limit,
        offset=offset,
    )
    return _success(
        {"reports": [_serialize_report(r) for r in rows]},
        meta={"limit": limit, "offset": offset, "count": len(rows)},
    )


# =====================================================================
# Endpoint — Overview
# =====================================================================


@regulatory_reporting_bp.get("/overview")
@api_role_required("Admin", "Medico")
def overview_endpoint():
    """KPIs top-level — agregadores de projects/indicators/submissions/reports."""
    tenant_id, err = _require_tenant_context()
    if err:
        return err

    projects_by_status = repo.count_projects_by_status(tenant_id)
    indicator_counts = repo.count_indicators_status(tenant_id)
    submissions_pending = repo.count_submissions_pending(tenant_id)
    reports_by_type = repo.count_reports_by_type(tenant_id)

    return _success(compute_overview(
        tenant_id=tenant_id,
        projects_by_status=projects_by_status,
        indicator_counts=indicator_counts,
        submissions_pending=submissions_pending,
        reports_by_type=reports_by_type,
    ))
