"""Context providers para os templates regulatorios ativados em F4.6.

Cada ``build_*_data(...)`` retorna o dict de contexto esperado pelo
respectivo template Jinja2 catalogado em ``data/templates/registry.yaml``:

- ``final/monitoring_opinion``   ← :func:`build_monitoring_opinion_data`
- ``operational/consent_form``   ← :func:`build_consent_form_data`
- ``operational/label_warning``  ← :func:`build_label_warning_data`
- ``operational/sop_template``   ← :func:`build_sop_template_data`

O Dossie de Elegibilidade (``eligibility/dossier``) continua com builder
proprio em :mod:`src.services.governance_dossier` por ter l\u00f3gica de
validacao de elegibilidade especifica.

Princ\u00edpios:

- Todos os providers respeitam StrictUndefined — retornam dicts completos
  com todas as chaves que o template referenciar. Campos que dependem de
  dados ainda nao presentes no schema retornam ``None``, ``''`` ou ``[]``,
  e o template usa ``{% if %}`` / fallback ``[pendencia: ...]`` para
  sinalizar lacuna explicitamente (doc 27 §11.2).
- Queries sao curtas e independentes. Agregacoes complexas (indicadores,
  farmacovigilancia, anchors) vem por parametro ``overrides`` para evitar
  acoplamento prematuro ao Evidence Engine (F4.1).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.regulatory_documents")


DOCUMENT_VERSION = "v1"


# ---------------------------------------------------------------------
# Helpers comuns
# ---------------------------------------------------------------------

def _fetch_tenant(tenant_id: int) -> dict[str, Any]:
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
        row = cursor.fetchone()
    if row is None:
        raise ValueError(f"Tenant {tenant_id} nao encontrado.")
    return dict(row)


def _fetch_primary_rt(tenant_id: int, *, today: Optional[date] = None) -> Optional[dict[str, Any]]:
    """RT ativo com habilitacao vigente; fallback para primeiro ativo."""
    effective = today or date.today()
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, full_name, professional_council, council_number,
                   council_state, habilitation_valid_until, is_active
              FROM technical_responsibles
             WHERE tenant_id = %s AND is_active = TRUE
             ORDER BY habilitation_valid_until DESC NULLS LAST, id ASC
            """,
            (tenant_id,),
        )
        rts = [dict(r) for r in cursor.fetchall()]
    if not rts:
        return None
    valid = [
        r for r in rts
        if r["habilitation_valid_until"] is None
        or r["habilitation_valid_until"] >= effective
    ]
    return valid[0] if valid else rts[0]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------
# 1. Parecer Final de Monitoramento  (final/monitoring_opinion)
# ---------------------------------------------------------------------

def build_monitoring_opinion_data(
    project_id: int,
    tenant_id: int,
    *,
    period_label: str = "Consolidacao Final",
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Constroi o contexto do Parecer Final (doc 27 §6).

    Agregados que dependem do Evidence Engine e de cronograma (F4.1/F4.5)
    chegam via ``overrides`` para evitar acoplamento. Sem overrides, os
    campos recebem valores neutros e o template renderiza ``[pendencia]``.
    """
    tenant = _fetch_tenant(tenant_id)
    rt = _fetch_primary_rt(tenant_id)

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, title, status, submitted_at, approved_at,
                   started_at, concluded_at, anvisa_reference
              FROM sandbox_projects
             WHERE id = %s AND tenant_id = %s
            """,
            (project_id, tenant_id),
        )
        project_row = cursor.fetchone()

    if project_row is None:
        raise ValueError(
            f"Projeto {project_id} nao encontrado para tenant {tenant_id}."
        )

    # Contagens basicas: fazemos SELECTs curtos; overrides podem
    # substituir com agregados do Evidence Engine quando estiver pronto.
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT COUNT(*) AS n FROM sop_evidences WHERE tenant_id=%s",
            (tenant_id,),
        )
        sops_count = int(cursor.fetchone()["n"])
        cursor.execute(
            "SELECT COUNT(*) AS n FROM adverse_events WHERE tenant_id=%s",
            (tenant_id,),
        )
        adverse_count = int(cursor.fetchone()["n"])
        cursor.execute(
            "SELECT COUNT(*) AS n FROM sanitary_risks WHERE tenant_id=%s",
            (tenant_id,),
        )
        risk_count = int(cursor.fetchone()["n"])
        cursor.execute(
            """
            SELECT COUNT(*) AS n, blockchain_network, verification_status
              FROM blockchain_anchors
             WHERE tenant_id = %s
             GROUP BY blockchain_network, verification_status
            """,
            (tenant_id,),
        )
        anchor_rows = [dict(r) for r in cursor.fetchall()]

    networks: dict[str, int] = {}
    statuses: dict[str, int] = {}
    total_anchors = 0
    for row in anchor_rows:
        n = int(row["n"])
        total_anchors += n
        networks[row["blockchain_network"]] = networks.get(row["blockchain_network"], 0) + n
        statuses[row["verification_status"]] = statuses.get(row["verification_status"], 0) + n

    context: dict[str, Any] = {
        "project": {
            "id": int(project_row["id"]),
            "title": project_row["title"],
            "objective": None,
            "start_date": project_row["started_at"],
            "end_date": project_row["concluded_at"],
            "status": project_row["status"],
        },
        "tenant": {
            "id": tenant["id"],
            "legal_name": tenant["legal_name"],
            "trade_name": tenant["trade_name"],
            "cnpj": tenant["cnpj"],
            "incorporation_date": tenant["incorporation_date"],
        },
        "technical_responsible": (
            {
                "full_name": rt["full_name"],
                "professional_council": rt["professional_council"],
                "council_number": rt["council_number"],
                "council_state": rt["council_state"],
            }
            if rt else None
        ),
        "scope": {"activities": [], "scale": None},
        "schedule": {"planned": [], "executed": []},
        "indicators": {"mandatory": [], "complementary": []},
        "operational_evidence": {
            "sops_count": sops_count,
            "sop_deviations": 0,
            "capa_actions": 0,
        },
        "clinical_evidence": {
            "consultations": 0,
            "prescriptions": 0,
            "outcomes": [],
        },
        "pharmacovigilance": {
            "adverse_events_count": adverse_count,
            "sanitary_risks_count": risk_count,
        },
        "anchors": {
            "total": total_anchors,
            "networks": networks,
            "verification_status_counts": statuses,
        },
        "findings": [],
        "recommendations": [],
        "limitations": [],
        "financial": None,
        "attachments": [],
        "generated_at": _iso_now(),
        "period_label": period_label,
        "document_version": DOCUMENT_VERSION,
    }

    if overrides:
        # Merge raso — overrides pode substituir qualquer chave de topo.
        context.update(overrides)

    return context


# ---------------------------------------------------------------------
# 2. Termo de Consentimento  (operational/consent_form)
# ---------------------------------------------------------------------

_DEFAULT_CONSENT_RIGHTS = [
    "Retirada do consentimento a qualquer momento.",
    "Apagamento de dados pessoais nao regulatorios (LGPD Art. 18).",
    "Acesso aos proprios dados clinicos e regulatorios.",
    "Portabilidade dos dados para outro prestador autorizado.",
    "Nao discriminacao por exercer qualquer desses direitos.",
]


def build_consent_form_data(
    *,
    tenant_id: int,
    member_id: int,
    project_id: int,
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Contexto para o Termo de Consentimento (doc 27 §7.1)."""
    tenant = _fetch_tenant(tenant_id)
    rt = _fetch_primary_rt(tenant_id)

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT m.id AS member_id, m.membership_number, m.membership_status,
                   p.full_name, p.cpf
              FROM association_members m
         LEFT JOIN patients p ON p.id = m.patient_id
             WHERE m.id = %s AND m.tenant_id = %s
            """,
            (member_id, tenant_id),
        )
        member_row = cursor.fetchone()

    if member_row is None:
        raise ValueError(
            f"Associado {member_id} nao encontrado para tenant {tenant_id}."
        )

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, title, anvisa_reference
              FROM sandbox_projects
             WHERE id = %s AND tenant_id = %s
            """,
            (project_id, tenant_id),
        )
        project_row = cursor.fetchone()

    if project_row is None:
        raise ValueError(
            f"Projeto {project_id} nao encontrado para tenant {tenant_id}."
        )

    context: dict[str, Any] = {
        "tenant": {
            "legal_name": tenant["legal_name"],
            "cnpj": tenant["cnpj"],
            "trade_name": tenant["trade_name"],
        },
        "member": {
            "full_name": member_row.get("full_name"),
            "cpf": member_row.get("cpf"),
            "rg": None,  # nao esta em patients hoje — placeholder explicito
        },
        "project": {
            "title": project_row["title"],
            "sandbox_protocol": project_row["anvisa_reference"],
        },
        "technical_responsible": (
            {
                "full_name": rt["full_name"],
                "council": (
                    f"{rt['professional_council']} "
                    f"{rt['council_number']}/{rt['council_state']}"
                ),
            }
            if rt else {"full_name": None, "council": None}
        ),
        "consent": {
            "lgpd_basis": "Consentimento especifico (LGPD Art. 7, I e Art. 11, I)",
            "data_sharing_with_anvisa": True,
            "rights": list(_DEFAULT_CONSENT_RIGHTS),
        },
        "known_risks": [],
        "known_benefits": [],
        "generated_at": _iso_now(),
        "document_version": DOCUMENT_VERSION,
    }

    if overrides:
        context.update(overrides)
    return context


# ---------------------------------------------------------------------
# 3. Rotulo de Preparado  (operational/label_warning)
# ---------------------------------------------------------------------

def build_label_warning_data(
    *,
    tenant_id: int,
    preparation_id: int,
    verification_base_url: str = "https://verify.cannabia.app",
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Contexto para o rotulo (doc 27 §7.2)."""
    tenant = _fetch_tenant(tenant_id)
    rt = _fetch_primary_rt(tenant_id)

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, preparation_code, preparation_type, produced_at,
                   unit_size_ml, qr_code
              FROM preparations
             WHERE id = %s AND tenant_id = %s
            """,
            (preparation_id, tenant_id),
        )
        prep_row = cursor.fetchone()

    if prep_row is None:
        raise ValueError(
            f"Preparacao {preparation_id} nao encontrada para tenant {tenant_id}."
        )

    verification_url = (
        f"{verification_base_url.rstrip('/')}/api/v1/public/anchors/"
        f"{tenant_id}/verify?table=preparations&event_id={preparation_id}"
    )

    context: dict[str, Any] = {
        "preparation": {
            "id": int(prep_row["id"]),
            "product_name": prep_row["preparation_type"],
            "dosage_form": prep_row["preparation_type"],
            "batch_code": prep_row["preparation_code"],
            "prepared_at": prep_row["produced_at"],
            # Perfil canabinoide vem da lab_analysis associada — nao
            # resolvemos aqui para manter o provider enxuto; overrides
            # pode injetar.
            "cannabinoid_profile": None,
        },
        "tenant": {
            "legal_name": tenant["legal_name"],
            "trade_name": tenant["trade_name"],
            "cnpj": tenant["cnpj"],
        },
        "technical_responsible": (
            {
                "full_name": rt["full_name"],
                "professional_council": rt["professional_council"],
                "council_number": rt["council_number"],
                "council_state": rt["council_state"],
            }
            if rt else {
                "full_name": "[pendencia]", "professional_council": "",
                "council_number": "", "council_state": "",
            }
        ),
        "verification_url": verification_url,
        "qr_code_data": prep_row["qr_code"] or verification_url,
        "generated_at": _iso_now(),
        "document_version": DOCUMENT_VERSION,
    }

    if overrides:
        context.update(overrides)
    return context


# ---------------------------------------------------------------------
# 4. Template-Base de POP  (operational/sop_template)
# ---------------------------------------------------------------------

def build_sop_template_data(
    *,
    tenant_id: int,
    code: str,
    title: str,
    version: str = "1.0",
    scope: Optional[str] = None,
    applicability: Optional[str] = None,
    approver: Optional[dict[str, str]] = None,
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Contexto para o template-base de POP (doc 27 §7.3).

    Diferente dos demais, este template NAO e um documento de producao;
    e um molde para instanciar novos POPs. Por isso nao depende de
    ``sop_id`` no banco — recebe os parametros diretamente.
    """
    tenant = _fetch_tenant(tenant_id)

    context: dict[str, Any] = {
        "sop": {
            "code": code,
            "title": title,
            "version": version,
            "scope": scope,
            "applicability": applicability,
        },
        "tenant": {"legal_name": tenant["legal_name"]},
        "definitions": [],
        "responsibilities": [],
        "procedure_steps": [],
        "generated_records": [],
        "references": [],
        "approver": approver or {"name": "[pendencia]", "role": "Responsavel Tecnico"},
        "revision_history": [],
        "generated_at": _iso_now(),
        "document_version": DOCUMENT_VERSION,
    }
    if overrides:
        context.update(overrides)
    return context
