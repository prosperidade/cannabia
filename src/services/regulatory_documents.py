"""Context providers para os templates regulatorios ativados em F4.6.

Cada ``build_*_data(...)`` retorna o dict de contexto esperado pelo
respectivo template Jinja2 catalogado em ``data/templates/registry.yaml``:

- ``final/monitoring_opinion``          ← :func:`build_monitoring_opinion_data`
- ``final/regulatory_report``           ← :func:`build_regulatory_report_data`
- ``operational/consent_form``          ← :func:`build_consent_form_data`
- ``operational/label_warning``         ← :func:`build_label_warning_data`
- ``operational/sop_template``          ← :func:`build_sop_template_data`
- ``project_plans/work_plan``           ← :func:`build_work_plan_data`
- ``project_plans/communication_plan``  ← :func:`build_communication_plan_data`
- ``project_plans/discontinuity_plan``  ← :func:`build_discontinuity_plan_data`
- ``project_plans/monitoring_plan``     ← :func:`build_monitoring_plan_data`
- ``project_plans/risk_management_plan`` ← :func:`build_risk_management_plan_data`

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
# 4. Relatorio Tecnico-Regulatorio Consolidado  (final/regulatory_report)
# ---------------------------------------------------------------------

def build_regulatory_report_data(
    project_id: int,
    tenant_id: int,
    *,
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Consolida o ciclo SCC do projeto em contexto para o template
    final/regulatory_report (doc 27 §3.1).

    Puxa dados em 4 queries curtas:
      - tenant + RT + projeto (via helpers existentes)
      - regulatory_reports com status='approved' do projeto
      - contadores de farmacovigilancia
      - agregado de blockchain_anchors

    overrides permite o caller injetar indicators_summary,
    operational_summary, recommendations, limitations, next_steps,
    attachments — campos que dependem de agregados ainda nao
    disponiveis no schema (Evidence Engine em F4.1).
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

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT r.id, r.report_type, r.version, r.status,
                   r.content_hash, r.approved_at, r.approved_by,
                   u.username AS approved_by_name
              FROM regulatory_reports r
         LEFT JOIN users u ON u.id = r.approved_by
             WHERE r.tenant_id = %s
               AND (r.project_id = %s OR r.project_id IS NULL)
               AND r.status IN ('approved', 'rejected', 'legal_review',
                                'rt_review', 'draft')
             ORDER BY r.approved_at DESC NULLS LAST, r.id ASC
            """,
            (tenant_id, project_id),
        )
        report_rows = [dict(r) for r in cursor.fetchall()]

    # Contadores de farmacovigilancia + anchors no tenant
    with db_cursor(dictionary=True) as (_, cursor):
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

    linked_documents = [
        {
            "type": r["report_type"],
            "title": r["report_type"].replace("_", " ").title(),
            "version": r["version"],
            "status": r["status"],
            "content_hash": r["content_hash"],
            "approved_at": r["approved_at"],
            "approved_by_name": r.get("approved_by_name"),
        }
        for r in report_rows
    ]

    context: dict[str, Any] = {
        "project": {
            "id": int(project_row["id"]),
            "title": project_row["title"],
            "objective": None,
            "start_date": project_row["started_at"],
            "end_date": project_row["concluded_at"],
            "status": project_row["status"],
            "anvisa_reference": project_row["anvisa_reference"],
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
        "linked_documents": linked_documents,
        "indicators_summary": {
            "mandatory_count": 0,
            "complementary_count": 0,
            "periods_reported": 0,
        },
        "operational_summary": {
            "sops_count": 0,
            "sop_deviations": 0,
            "capa_actions": 0,
            "lab_analyses_count": 0,
            "dispensations_count": 0,
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
        "recommendations": [],
        "limitations": [],
        "next_steps": [],
        "attachments": [],
        "generated_at": _iso_now(),
        "document_version": DOCUMENT_VERSION,
    }

    if overrides:
        context.update(overrides)
    return context


# ---------------------------------------------------------------------
# Helpers dos 5 planos obrigatorios  (F4.5 — doc 27 §4)
# ---------------------------------------------------------------------

def _fetch_project(project_id: int, tenant_id: int) -> dict[str, Any]:
    """Projeto basico + validacao de tenant. Compartilhado pelos 5 planos."""
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, project_code, title, status,
                   submitted_at, approved_at, started_at, concluded_at,
                   anvisa_reference
              FROM sandbox_projects
             WHERE id = %s AND tenant_id = %s
            """,
            (project_id, tenant_id),
        )
        row = cursor.fetchone()
    if row is None:
        raise ValueError(
            f"Projeto {project_id} nao encontrado para tenant {tenant_id}."
        )
    return dict(row)


def _fetch_association(tenant_id: int) -> Optional[dict[str, Any]]:
    """Linha de ``associations`` do tenant, se existir."""
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT tenant_id, statute_document_id, directive_board,
                   members_count, is_judicial_operation,
                   sandbox_application_status
              FROM associations
             WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        row = cursor.fetchone()
    return dict(row) if row else None


def _project_basics(project_row: dict[str, Any]) -> dict[str, Any]:
    """Shape do ``project`` usado por todos os 5 templates de planos."""
    return {
        "id": int(project_row["id"]),
        "title": project_row["title"],
        "objective": None,  # sandbox_projects nao tem objetivo textual ainda
        "start_date": project_row["started_at"],
        "end_date": project_row["concluded_at"],
        "status": project_row["status"],
    }


def _rt_shape(rt: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Shape consistente de technical_responsible para os templates."""
    if rt is None:
        return None
    return {
        "full_name": rt["full_name"],
        "professional_council": rt["professional_council"],
        "council_number": rt["council_number"],
        "council_state": rt["council_state"],
    }


# ---------------------------------------------------------------------
# 6. Plano de Trabalho  (project_plans/work_plan)  — doc 27 §4.1
# ---------------------------------------------------------------------

def build_work_plan_data(
    project_id: int,
    tenant_id: int,
    *,
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Contexto do Plano de Trabalho (doc 27 §4.1).

    Agregados que dependem de dados operacionais profundos (metodologia,
    criterios de qualidade, RH detalhado, cronograma) chegam via
    ``overrides``; os providers consultam apenas o que ja esta persistido
    estruturalmente: tenant + associacao + RT + projeto + resumo de POPs.
    """
    tenant = _fetch_tenant(tenant_id)
    rt = _fetch_primary_rt(tenant_id)
    project_row = _fetch_project(project_id, tenant_id)
    association = _fetch_association(tenant_id)

    # Resumo de POPs ativos por area
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT area, COUNT(*) AS n
              FROM sops
             WHERE tenant_id = %s AND is_active = TRUE
             GROUP BY area
            """,
            (tenant_id,),
        )
        sop_rows = [dict(r) for r in cursor.fetchall()]

    by_area = {r["area"]: int(r["n"]) for r in sop_rows}
    sops_total = sum(by_area.values())

    context: dict[str, Any] = {
        "tenant": {
            "id": tenant["id"],
            "legal_name": tenant["legal_name"],
            "trade_name": tenant["trade_name"],
            "cnpj": tenant["cnpj"],
            "incorporation_date": tenant["incorporation_date"],
        },
        "association": (
            {
                "members_count": int(association["members_count"] or 0),
                "directive_board": association["directive_board"] or [],
                "is_judicial_operation": bool(association["is_judicial_operation"]),
                "statute_document_id": association["statute_document_id"],
            }
            if association else None
        ),
        "technical_responsible": _rt_shape(rt),
        "project": _project_basics(project_row),
        "scope": {"activities": []},
        "methodology": [],
        "quality_criteria": [],
        "infrastructure": {"summary": None, "components": []},
        "human_resources": [],
        "scale": {
            "members_benefited": None,
            "production_volume": None,
            "dispensation_target": None,
        },
        "schedule": [],
        "interdependencies": [],
        "sops_summary": {"total": sops_total, "by_area": by_area},
        "generated_at": _iso_now(),
        "document_version": DOCUMENT_VERSION,
    }

    if overrides:
        context.update(overrides)
    return context


# ---------------------------------------------------------------------
# 7. Plano de Comunicacao  (project_plans/communication_plan) — §4.2
# ---------------------------------------------------------------------

def build_communication_plan_data(
    project_id: int,
    tenant_id: int,
    *,
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Contexto do Plano de Comunicacao (doc 27 §4.2).

    Sem tabela dedicada de canais/politicas hoje — o provider monta o
    esqueleto com defaults regulatorios (vedacoes, principios genericos),
    e a associacao complementa via ``overrides`` ou via edicao manual
    no ciclo de aprovacao.
    """
    tenant = _fetch_tenant(tenant_id)
    rt = _fetch_primary_rt(tenant_id)
    project_row = _fetch_project(project_id, tenant_id)

    context: dict[str, Any] = {
        "tenant": {
            "id": tenant["id"],
            "legal_name": tenant["legal_name"],
            "trade_name": tenant["trade_name"],
            "cnpj": tenant["cnpj"],
        },
        "technical_responsible": _rt_shape(rt),
        "project": _project_basics(project_row),
        "principles": [],
        "prohibitions": [],
        "official_channels": [],
        "moderation_policy": {
            "summary": None,
            "responsible_role": "Responsavel Tecnico",
            "review_sla_hours": None,
            "escalation": None,
        },
        "member_comms": {
            "frequency": None,
            "channels": [],
            "content_types": [],
        },
        "anvisa_comms": {
            "submission_types": [],
            "cadence": None,
            "responsible": rt["full_name"] if rt else None,
        },
        "public_comms": {
            "allowed_topics": [],
            "forbidden_topics": [],
        },
        "press_response": {
            "spokesperson": None,
            "approval_flow": None,
        },
        "review_cycle": {
            "frequency": None,
            "responsible": None,
            "last_review": None,
            "next_review": None,
        },
        "generated_at": _iso_now(),
        "document_version": DOCUMENT_VERSION,
    }

    if overrides:
        context.update(overrides)
    return context


# ---------------------------------------------------------------------
# 8. Plano de Descontinuidade  (project_plans/discontinuity_plan) — §4.3
# ---------------------------------------------------------------------

def build_discontinuity_plan_data(
    project_id: int,
    tenant_id: int,
    *,
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Contexto do Plano de Descontinuidade (doc 27 §4.3).

    Le ``sandbox_protocols.discontinuity_plan`` (JSONB) do protocolo
    vigente do projeto, se houver, e expoe como dados-base. Tudo demais
    pode ser sobrescrito por ``overrides`` — plano tipicamente editado
    manualmente antes da aprovacao final.
    """
    tenant = _fetch_tenant(tenant_id)
    rt = _fetch_primary_rt(tenant_id)
    project_row = _fetch_project(project_id, tenant_id)

    # Protocolo vigente (effective_until IS NULL significa em vigor).
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT protocol_version, discontinuity_plan, effective_from
              FROM sandbox_protocols
             WHERE project_id = %s
               AND (effective_until IS NULL OR effective_until >= NOW())
             ORDER BY effective_from DESC NULLS LAST, id DESC
             LIMIT 1
            """,
            (project_id,),
        )
        protocol_row = cursor.fetchone()

    protocol_disc = (
        dict(protocol_row)["discontinuity_plan"]
        if protocol_row else {}
    ) or {}

    context: dict[str, Any] = {
        "tenant": {
            "legal_name": tenant["legal_name"],
            "cnpj": tenant["cnpj"],
        },
        "technical_responsible": _rt_shape(rt),
        "project": _project_basics(project_row),
        "scenarios": protocol_disc.get("scenarios") or [],
        "triggers": protocol_disc.get("triggers") or [],
        "cultivation_shutdown": protocol_disc.get("cultivation_shutdown") or {
            "steps": [],
            "timeframe_days": None,
            "responsible": None,
        },
        "disposal": protocol_disc.get("disposal") or {
            "procedures": [],
            "oversight": None,
            "regulatory_reference": None,
        },
        "transition": protocol_disc.get("transition") or {
            "description": None,
            "target_regime": None,
            "steps": [],
        },
        "member_communication": protocol_disc.get("member_communication") or {
            "channels": [],
            "notice_period_days": None,
            "message_template": None,
        },
        "care_continuity": protocol_disc.get("care_continuity") or {
            "description": None,
            "referral_partners": [],
        },
        "records_preservation": protocol_disc.get("records_preservation") or {
            "retention_years": None,
            "storage_method": None,
            "access_policy": None,
        },
        "responsibilities": protocol_disc.get("responsibilities") or [],
        "schedule": protocol_disc.get("schedule") or [],
        "generated_at": _iso_now(),
        "document_version": DOCUMENT_VERSION,
    }

    if overrides:
        context.update(overrides)
    return context


# ---------------------------------------------------------------------
# 9. Plano de Monitoramento  (project_plans/monitoring_plan) — §4.4
# ---------------------------------------------------------------------

def build_monitoring_plan_data(
    project_id: int,
    tenant_id: int,
    *,
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Contexto do Plano de Monitoramento (doc 27 §4.4).

    Le ``sandbox_indicators`` do projeto e separa por ``is_mandatory``.
    A metodologia de calculo vem de ``calculation_formula`` (texto livre
    no schema). Agregados complementares ficam em ``overrides``.
    """
    tenant = _fetch_tenant(tenant_id)
    rt = _fetch_primary_rt(tenant_id)
    project_row = _fetch_project(project_id, tenant_id)

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT indicator_code, indicator_name, calculation_formula,
                   unit, target_value, reporting_frequency, is_mandatory
              FROM sandbox_indicators
             WHERE project_id = %s
             ORDER BY is_mandatory DESC, indicator_code ASC
            """,
            (project_id,),
        )
        indicator_rows = [dict(r) for r in cursor.fetchall()]

    mandatory: list[dict[str, Any]] = []
    complementary: list[dict[str, Any]] = []
    for row in indicator_rows:
        entry = {
            "code": row["indicator_code"],
            "name": row["indicator_name"],
            "unit": row["unit"],
            "formula": row["calculation_formula"],
            "frequency": row["reporting_frequency"],
            "target": row["target_value"],
            "data_source": None,
        }
        if row["is_mandatory"]:
            mandatory.append(entry)
        else:
            complementary.append(
                {k: entry[k] for k in ("code", "name", "unit", "frequency")}
            )

    context: dict[str, Any] = {
        "tenant": {
            "legal_name": tenant["legal_name"],
            "cnpj": tenant["cnpj"],
        },
        "technical_responsible": _rt_shape(rt),
        "project": _project_basics(project_row),
        "mandatory_indicators": mandatory,
        "complementary_indicators": complementary,
        "collection_infrastructure": {
            "systems": [],
            "ingestion_cadence": None,
        },
        "validation_process": {
            "steps": [],
            "responsible": rt["full_name"] if rt else None,
            "frequency": None,
        },
        "delivery_format": {
            "to_anvisa": None,
            "to_internal": None,
            "reporting_template": None,
        },
        "deviation_criteria": [],
        "governance": {
            "review_committee": [],
            "review_cadence": None,
        },
        "generated_at": _iso_now(),
        "document_version": DOCUMENT_VERSION,
    }

    if overrides:
        context.update(overrides)
    return context


# ---------------------------------------------------------------------
# 10. Plano de Riscos  (project_plans/risk_management_plan) — §4.5
# ---------------------------------------------------------------------

def build_risk_management_plan_data(
    project_id: int,
    tenant_id: int,
    *,
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Contexto do Plano de Gerenciamento de Riscos (doc 27 §4.5).

    Consome matriz de riscos ativa em ``sanitary_risks`` + controles em
    ``risk_controls``, agrega contadores de farmacovigilancia (adverse
    events) e CAPAs (capa_actions via sop_deviations). Campos descritivos
    (metodologia, politica) ficam com defaults textuais.
    """
    tenant = _fetch_tenant(tenant_id)
    rt = _fetch_primary_rt(tenant_id)
    project_row = _fetch_project(project_id, tenant_id)

    # Matriz de riscos ativa + controles
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, risk_code, category, description,
                   probability, impact, risk_level, is_active
              FROM sanitary_risks
             WHERE tenant_id = %s AND is_active = TRUE
             ORDER BY risk_level DESC, risk_code ASC
            """,
            (tenant_id,),
        )
        risk_rows = [dict(r) for r in cursor.fetchall()]

    risks: list[dict[str, Any]] = [
        {
            "id": int(r["id"]),
            "code": r["risk_code"],
            "category": r["category"],
            "description": r["description"],
            "probability": r["probability"],
            "impact": r["impact"],
            "risk_level": r["risk_level"],
            "is_active": bool(r["is_active"]),
        }
        for r in risk_rows
    ]

    risk_code_by_id = {r["id"]: r["code"] for r in risks}

    controls: list[dict[str, Any]] = []
    if risks:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT c.risk_id, c.control_description, c.control_type,
                       c.verification_status, c.related_sop_id,
                       u.username AS responsible_name,
                       s.code AS related_sop_code
                  FROM risk_controls c
             LEFT JOIN users u ON u.id = c.responsible
             LEFT JOIN sops s ON s.id = c.related_sop_id
                 WHERE c.risk_id = ANY(%s)
                 ORDER BY c.risk_id ASC, c.id ASC
                """,
                (list(risk_code_by_id.keys()),),
            )
            for row in cursor.fetchall():
                d = dict(row)
                controls.append({
                    "risk_code": risk_code_by_id.get(d["risk_id"]),
                    "description": d["control_description"],
                    "control_type": d["control_type"],
                    "responsible": d.get("responsible_name"),
                    "related_sop": d.get("related_sop_code"),
                    "verification_status": d.get("verification_status"),
                })

    # Farmacovigilancia + CAPAs
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT COUNT(*) AS n FROM adverse_events WHERE tenant_id=%s",
            (tenant_id,),
        )
        adverse_count = int(cursor.fetchone()["n"])
        cursor.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE a.completed_at IS NULL) AS open_n,
              COUNT(*) FILTER (WHERE a.completed_at IS NOT NULL) AS resolved_n
              FROM capa_actions a
              JOIN sop_deviations d ON d.id = a.deviation_id
             WHERE d.tenant_id = %s
            """,
            (tenant_id,),
        )
        capa_row = cursor.fetchone() or {"open_n": 0, "resolved_n": 0}

    context: dict[str, Any] = {
        "tenant": {
            "legal_name": tenant["legal_name"],
            "cnpj": tenant["cnpj"],
        },
        "technical_responsible": _rt_shape(rt),
        "project": _project_basics(project_row),
        "methodology": {
            "description": None,
            "scales": {},
        },
        "risks": risks,
        "controls": controls,
        "responsibles": [
            {"risk_code": r["code"], "responsible": None} for r in risks
        ],
        "verification": {
            "method": None,
            "frequency": None,
            "last_review": None,
        },
        "review_cycle": {
            "frequency": None,
            "responsible": rt["full_name"] if rt else None,
        },
        "pharmacovigilance": {
            "adverse_events_count": adverse_count,
            "sanitary_risks_count": len(risks),
            "reporting_policy": None,
        },
        "capa_integration": {
            "open_capa_count": int(capa_row["open_n"] or 0),
            "resolved_capa_count": int(capa_row["resolved_n"] or 0),
            "policy": None,
        },
        "governance": {
            "committee": [],
            "cadence": None,
        },
        "generated_at": _iso_now(),
        "document_version": DOCUMENT_VERSION,
    }

    if overrides:
        context.update(overrides)
    return context


# ---------------------------------------------------------------------
# 11. Template-Base de POP  (operational/sop_template)
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
