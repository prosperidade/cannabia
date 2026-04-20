"""Governance Hub API (F1.5 do docs/BACKLOG_SCC.md — parte 1).

Endpoints REST para gestao institucional da associacao: dados
cadastrais, documentos, responsaveis tecnicos, capacidade
tecnico-operacional e validacao de elegibilidade ao Sandbox.

Prefixo: ``/api/v1/governance``. Todas as operacoes sao escopadas ao
tenant do usuario autenticado (``g.tenant_id``). Writes exigem CSRF e
role Admin; reads permitem Admin/Medico.

A geracao do Dossie de Elegibilidade fica em arquivo separado (F1.5
parte 2).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from flask import Blueprint, g

from src.repositories import governance_repository as repo
from src.services.governance_service import (
    EligibilityReport,
    check_sandbox_eligibility,
    refresh_eligibility,
)
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _require_json_csrf,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.governance_routes")

governance_bp = Blueprint("governance", __name__, url_prefix="/api/v1/governance")


# =====================================================================
# Helpers
# =====================================================================

def _current_tenant_id() -> Optional[int]:
    tenant_id = getattr(g, "tenant_id", None)
    return int(tenant_id) if tenant_id is not None else None


def _require_tenant_context():
    """Retorna (tenant_id, None) em sucesso ou (None, response) em erro."""
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        return None, _error(
            "tenant_context_missing",
            "Contexto de tenant nao resolvido para o usuario autenticado.",
            400,
        )
    return tenant_id, None


def _parse_date(value: Any, field: str) -> Optional[date]:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"Campo '{field}' invalido: {exc}") from exc


def _ensure_rt_belongs_to_tenant(rt_id: int, tenant_id: int) -> Optional[dict[str, Any]]:
    rt = repo.get_technical_responsible(rt_id)
    if rt is None or rt.get("tenant_id") != tenant_id:
        return None
    return rt


def _ensure_document_belongs_to_tenant(
    doc_id: int, tenant_id: int
) -> Optional[dict[str, Any]]:
    doc = repo.get_institutional_document(doc_id)
    if doc is None or doc.get("tenant_id") != tenant_id:
        return None
    return doc


# =====================================================================
# Association — metadados institucionais
# =====================================================================

@governance_bp.get("/association")
@api_role_required("Admin", "Medico")
def get_association():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    association = repo.get_association(tenant_id)
    return _success({"association": association})


@governance_bp.put("/association")
@api_role_required("Admin")
def upsert_association():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    try:
        members_count = int(payload.get("members_count", 0))
    except (TypeError, ValueError):
        return _error("validation_error", "members_count deve ser inteiro.", 422)
    if members_count < 0:
        return _error("validation_error", "members_count deve ser >= 0.", 422)

    directive_board = payload.get("directive_board") or []
    if not isinstance(directive_board, list):
        return _error("validation_error", "directive_board deve ser lista.", 422)

    statute_document_id = payload.get("statute_document_id")
    if statute_document_id is not None:
        try:
            statute_document_id = int(statute_document_id)
        except (TypeError, ValueError):
            return _error("validation_error", "statute_document_id deve ser inteiro.", 422)
        if _ensure_document_belongs_to_tenant(statute_document_id, tenant_id) is None:
            return _error(
                "not_found",
                "Documento de estatuto nao encontrado para este tenant.",
                404,
            )

    association = repo.upsert_association(
        tenant_id=tenant_id,
        statute_document_id=statute_document_id,
        directive_board=directive_board,
        members_count=members_count,
        is_judicial_operation=bool(payload.get("is_judicial_operation", False)),
        judicial_authorization=payload.get("judicial_authorization"),
    )
    return _success({"association": association})


# =====================================================================
# Documents — institutional_documents
# =====================================================================

@governance_bp.get("/documents")
@api_role_required("Admin", "Medico")
def list_documents():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    from flask import request  # local import mantem modulo enxuto

    document_type = request.args.get("type") or None
    active_only = request.args.get("active_only", "true").lower() != "false"
    docs = repo.list_institutional_documents(
        tenant_id=tenant_id,
        document_type=document_type,
        active_only=active_only,
    )
    return _success({"documents": docs})


@governance_bp.post("/documents")
@api_role_required("Admin")
def create_document():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    required = ["document_type", "title", "version", "file_uri", "file_hash", "valid_from"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        return _error(
            "validation_error",
            f"Campos obrigatorios ausentes: {', '.join(missing)}.",
            422,
        )

    file_hash = str(payload["file_hash"]).strip()
    if len(file_hash) != 64:
        return _error("validation_error", "file_hash deve ser SHA-256 hex (64 chars).", 422)

    try:
        valid_from = _parse_date(payload["valid_from"], "valid_from")
        valid_until = _parse_date(payload.get("valid_until"), "valid_until")
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)

    uploaded_by = getattr(g, "user_id", None)
    if uploaded_by is None:
        try:
            from flask_login import current_user  # type: ignore
            uploaded_by = int(current_user.id) if current_user.is_authenticated else None
        except Exception:
            uploaded_by = None

    doc = repo.create_institutional_document(
        tenant_id=tenant_id,
        document_type=str(payload["document_type"]).strip(),
        title=str(payload["title"]).strip(),
        version=str(payload["version"]).strip(),
        file_uri=str(payload["file_uri"]).strip(),
        file_hash=file_hash,
        valid_from=valid_from,
        valid_until=valid_until,
        uploaded_by=uploaded_by,
    )
    return _success({"document": doc}, status=201)


@governance_bp.delete("/documents/<int:doc_id>")
@api_role_required("Admin")
def deactivate_document(doc_id: int):
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    if _ensure_document_belongs_to_tenant(doc_id, tenant_id) is None:
        return _error("not_found", "Documento nao encontrado.", 404)

    repo.deactivate_institutional_document(doc_id)
    return _success({"deactivated": True, "document_id": doc_id})


# =====================================================================
# Technical Responsibles — RTs
# =====================================================================

@governance_bp.get("/rts")
@api_role_required("Admin", "Medico")
def list_rts():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    from flask import request

    active_only = request.args.get("active_only", "true").lower() != "false"
    rts = repo.list_technical_responsibles(tenant_id=tenant_id, active_only=active_only)
    return _success({"technical_responsibles": rts})


@governance_bp.post("/rts")
@api_role_required("Admin")
def create_rt():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    required = ["full_name", "professional_council", "council_number", "council_state"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        return _error(
            "validation_error",
            f"Campos obrigatorios ausentes: {', '.join(missing)}.",
            422,
        )

    council_state = str(payload["council_state"]).strip().upper()
    if len(council_state) != 2:
        return _error("validation_error", "council_state deve ter 2 caracteres (UF).", 422)

    try:
        habilitation_valid_until = _parse_date(
            payload.get("habilitation_valid_until"), "habilitation_valid_until"
        )
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)

    document_ids = payload.get("document_ids") or []
    if not isinstance(document_ids, list):
        return _error("validation_error", "document_ids deve ser lista de inteiros.", 422)
    try:
        document_ids = [int(x) for x in document_ids]
    except (TypeError, ValueError):
        return _error("validation_error", "document_ids deve conter apenas inteiros.", 422)

    try:
        rt = repo.create_technical_responsible(
            tenant_id=tenant_id,
            full_name=str(payload["full_name"]).strip(),
            professional_council=str(payload["professional_council"]).strip().upper(),
            council_number=str(payload["council_number"]).strip(),
            council_state=council_state,
            user_id=payload.get("user_id"),
            habilitation_valid_until=habilitation_valid_until,
            document_ids=document_ids,
        )
    except Exception as exc:
        # IntegrityError do UNIQUE (conselho/numero/estado)
        if "uq_tr_council" in str(exc):
            return _error(
                "conflict",
                "RT ja cadastrado neste conselho/numero/estado.",
                409,
            )
        raise
    return _success({"technical_responsible": rt}, status=201)


@governance_bp.patch("/rts/<int:rt_id>")
@api_role_required("Admin")
def update_rt(rt_id: int):
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    if _ensure_rt_belongs_to_tenant(rt_id, tenant_id) is None:
        return _error("not_found", "RT nao encontrado.", 404)

    payload = _json_payload()
    updatable = {
        "full_name",
        "professional_council",
        "council_number",
        "council_state",
        "habilitation_valid_until",
        "document_ids",
        "is_active",
        "user_id",
    }
    fields: dict[str, Any] = {}
    for key in updatable & set(payload):
        value = payload[key]
        if key == "habilitation_valid_until":
            try:
                value = _parse_date(value, key)
            except ValueError as exc:
                return _error("validation_error", str(exc), 422)
        elif key == "council_state" and value is not None:
            value = str(value).strip().upper()
            if len(value) != 2:
                return _error("validation_error", "council_state deve ter 2 caracteres.", 422)
        elif key == "document_ids" and value is not None:
            if not isinstance(value, list):
                return _error("validation_error", "document_ids deve ser lista.", 422)
            try:
                value = [int(x) for x in value]
            except (TypeError, ValueError):
                return _error("validation_error", "document_ids deve conter inteiros.", 422)
        fields[key] = value

    updated = repo.update_technical_responsible(rt_id, **fields)
    return _success({"technical_responsible": updated})


@governance_bp.delete("/rts/<int:rt_id>")
@api_role_required("Admin")
def deactivate_rt(rt_id: int):
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    if _ensure_rt_belongs_to_tenant(rt_id, tenant_id) is None:
        return _error("not_found", "RT nao encontrado.", 404)

    repo.deactivate_technical_responsible(rt_id)
    return _success({"deactivated": True, "rt_id": rt_id})


# =====================================================================
# Technical Operational Capacity
# =====================================================================

@governance_bp.get("/capacity/latest")
@api_role_required("Admin", "Medico")
def get_latest_capacity():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    assessment = repo.get_latest_capacity_assessment(tenant_id)
    return _success({"capacity_assessment": assessment})


@governance_bp.post("/capacity")
@api_role_required("Admin")
def create_capacity():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    required_jsonb = [
        "infrastructure_score",
        "human_resources_score",
        "process_maturity_score",
        "proposed_scale",
    ]
    missing = [k for k in required_jsonb if not isinstance(payload.get(k), dict)]
    if missing:
        return _error(
            "validation_error",
            f"Scores obrigatorios (dict): {', '.join(missing)}.",
            422,
        )

    try:
        assessment_date = _parse_date(
            payload.get("assessment_date") or date.today().isoformat(),
            "assessment_date",
        )
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)

    overall_readiness = payload.get("overall_readiness")
    if overall_readiness is not None:
        try:
            overall_readiness = float(overall_readiness)
        except (TypeError, ValueError):
            return _error("validation_error", "overall_readiness deve ser numerico.", 422)
        if not (0 <= overall_readiness <= 100):
            return _error("validation_error", "overall_readiness fora de [0,100].", 422)

    assessed_by = None
    try:
        from flask_login import current_user  # type: ignore
        assessed_by = int(current_user.id) if current_user.is_authenticated else None
    except Exception:
        pass

    assessment = repo.create_capacity_assessment(
        tenant_id=tenant_id,
        assessment_date=assessment_date,
        infrastructure_score=payload["infrastructure_score"],
        human_resources_score=payload["human_resources_score"],
        process_maturity_score=payload["process_maturity_score"],
        proposed_scale=payload["proposed_scale"],
        overall_readiness=overall_readiness,
        assessed_by=assessed_by,
    )
    return _success({"capacity_assessment": assessment}, status=201)


# =====================================================================
# Eligibility
# =====================================================================

def _report_payload(report: EligibilityReport) -> dict[str, Any]:
    return report.to_dict()


@governance_bp.get("/eligibility")
@api_role_required("Admin", "Medico")
def get_eligibility():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    try:
        report = check_sandbox_eligibility(tenant_id)
    except ValueError as exc:
        return _error("not_found", str(exc), 404)
    return _success(_report_payload(report))


@governance_bp.post("/eligibility/refresh")
@api_role_required("Admin")
def post_refresh_eligibility():
    tenant_id, err = _require_tenant_context()
    if err:
        return err
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error
    try:
        report = refresh_eligibility(tenant_id)
    except ValueError as exc:
        return _error("not_found", str(exc), 404)
    return _success(_report_payload(report))
