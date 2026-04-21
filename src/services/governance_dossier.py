"""Gerador do Dossie de Elegibilidade ao Sandbox (F1.5 parte 2).

Coleta dados do Governance Hub (tenants + associations + RTs +
institutional_documents + technical_operational_capacity) e do
relatorio de elegibilidade, e renderiza um documento Markdown conforme
o template de doc 27 §5.

Dois formatos publicos:

- ``build_dossier_data(tenant_id)`` retorna o dict completo, util para
  frontends que queiram montar a propria renderizacao ou para debug.
- ``render_dossier_markdown(tenant_id)`` renderiza o template Jinja2 e
  devolve a string Markdown final.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any, Optional

from src.infra.database import db_cursor
from src.repositories import governance_repository as repo
from src.services.governance_service import (
    EligibilityReport,
    check_sandbox_eligibility,
)
from src.services.template_engine import RenderedDocument, render as render_template

logger = logging.getLogger("cannabia.governance_dossier")


# ---------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------

TEMPLATE_ID = "eligibility/dossier"
TEMPLATE_VERSION = "v1"


# ---------------------------------------------------------------------
# Loader de dados
# ---------------------------------------------------------------------

def _load_tenant(tenant_id: int) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, legal_name, display_name, trade_name, cnpj,
                   incorporation_date, tenant_type, status
              FROM tenants
             WHERE id = %s
            """,
            (tenant_id,),
        )
        return cursor.fetchone()


def _group_documents_by_type(
    documents: list[dict[str, Any]],
) -> "OrderedDict[str, list[dict[str, Any]]]":
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for doc in documents:
        grouped.setdefault(doc["document_type"], []).append(doc)
    return grouped


def _pick_primary_rt(rts: list[dict[str, Any]], today: date) -> Optional[dict[str, Any]]:
    """Escolhe o primeiro RT com habilitacao vigente, ou o primeiro ativo
    se nenhum com vigencia comprovada existir."""
    habilitated = [
        rt for rt in rts
        if rt.get("is_active")
        and rt.get("habilitation_valid_until") is not None
        and rt["habilitation_valid_until"] >= today
    ]
    if habilitated:
        return habilitated[0]
    actives = [rt for rt in rts if rt.get("is_active")]
    return actives[0] if actives else None


def _pick_presidente(association: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not association:
        return None
    board = association.get("directive_board") or []
    for member in board:
        if not isinstance(member, dict):
            continue
        role = str(member.get("role") or "").lower()
        if "presid" in role:
            return member
    return board[0] if board and isinstance(board[0], dict) else None


def build_dossier_data(
    tenant_id: int,
    *,
    today: Optional[date] = None,
) -> dict[str, Any]:
    """Coleta tudo que o template precisa. Se o tenant nao existir,
    levanta ``ValueError`` (nao faz sentido gerar dossie sem tenant)."""
    effective_today = today or date.today()
    tenant = _load_tenant(tenant_id)
    if tenant is None:
        raise ValueError(f"Tenant {tenant_id} nao encontrado.")

    association = repo.get_association(tenant_id)
    documents = repo.list_institutional_documents(
        tenant_id=tenant_id, active_only=True
    )
    rts = repo.list_technical_responsibles(tenant_id=tenant_id, active_only=True)
    capacity = repo.get_latest_capacity_assessment(tenant_id)
    report = check_sandbox_eligibility(tenant_id, today=effective_today)

    findings_dicts = [asdict(f) for f in report.findings]
    findings_by_code = {f["code"]: f for f in findings_dicts}
    fail_count = sum(1 for f in findings_dicts if f["status"] == "fail")
    warn_count = sum(1 for f in findings_dicts if f["status"] == "warn")

    data: dict[str, Any] = {
        "tenant": tenant,
        "association": association,
        "documents": documents,
        "documents_by_type": _group_documents_by_type(documents),
        "rts": rts,
        "primary_rt": _pick_primary_rt(rts, effective_today),
        "presidente": _pick_presidente(association),
        "capacity": capacity,
        "eligibility": {
            "is_eligible": report.is_eligible,
            "has_warnings": report.has_warnings,
            "checked_at": report.checked_at.isoformat(),
        },
        "findings": findings_dicts,
        "findings_by_code": findings_by_code,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "template_version": TEMPLATE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return data


# ---------------------------------------------------------------------
# Renderer — delega para template_engine (F4.6 do SCC)
# ---------------------------------------------------------------------

def render_dossier_document(
    tenant_id: int,
    *,
    data: Optional[dict[str, Any]] = None,
) -> RenderedDocument:
    """Renderiza o Dossie via template_engine e devolve o
    :class:`RenderedDocument` completo (com ``content_hash`` SHA-256).

    Uso tipico: persistir em ``regulatory_reports.content_hash`` ou
    ancorar em blockchain.
    """
    if data is None:
        data = build_dossier_data(tenant_id)
    document = render_template(TEMPLATE_ID, data, format="md")
    logger.info(
        "dossier_rendered tenant=%s eligible=%s length=%d hash=%s",
        tenant_id,
        data["eligibility"]["is_eligible"],
        len(document.content),
        document.content_hash[:12],
    )
    return document


def render_dossier_markdown(
    tenant_id: int,
    *,
    data: Optional[dict[str, Any]] = None,
) -> str:
    """Compat: devolve apenas o Markdown. Callers novos devem preferir
    :func:`render_dossier_document` para ter acesso ao ``content_hash``."""
    return render_dossier_document(tenant_id, data=data).content
