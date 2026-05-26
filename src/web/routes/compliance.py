# src/web/routes/compliance.py
"""
ANVISA Compliance API — Prefix: /api/v1/org

Dois endpoints:

  GET /compliance           — checklist legado (5 itens pre-SCC,
                              mantido por retrocompatibilidade com o
                              frontend atual).

  GET /compliance/overview  — F6.4 do docs/BACKLOG_SCC.md: agregador
                              dos 7 submodulos do Sandbox Compliance
                              Core (doc 23 §7). Cada submodulo tem
                              seu proprio score (0-100) e detalhes,
                              e o overall_score e a media simples.

  GET /compliance/submodule/<name> — mesma logica, so um submodulo.

Per HANDOFF_VALIDATION_REPORT §4.2 opcao B, este blueprint age como
fachada agregadora: consome as tabelas SCC diretamente (e a view
`v_sandbox_indicator_dashboard`) em vez de depender de blueprints
dedicados por submodulo — que ainda nao existem.

tenant_id == clinic_id conforme docs/25 §11.3.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, g
from psycopg2 import DatabaseError, OperationalError

from src.infra.database import db_cursor
from src.web.routes.api_v1 import _error, _success, api_role_required

logger = logging.getLogger("cannabia.compliance")
compliance_bp = Blueprint("compliance", __name__, url_prefix="/api/v1/org")


# ===========================================================================
# Helpers comuns
# ===========================================================================


def _score_from_checks(checks: list[dict[str, Any]]) -> int:
    """Dada uma lista de checks (cada um com `status` 'ok'|'warning'|'fail'),
    retorna score 0-100 como % de checks 'ok'."""
    if not checks:
        return 0
    ok_count = sum(1 for c in checks if c.get("status") == "ok")
    return round(ok_count / len(checks) * 100)


def _check(name: str, status: str, detail: str) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail}


# ===========================================================================
# Submodulos — cada funcao retorna (score, checks[]) para um tenant
# ===========================================================================


def governance_summary(tenant_id: int) -> dict[str, Any]:
    """Submodulo 1: governance (doc 23 §7.1).

    Checks:
      - Tenant com legal_name, CNPJ e incorporation_date preenchidos
      - Tipo do tenant definido (clinic/association/doctor)
      - Pelo menos 1 RT ativo com habilitacao valida hoje
      - Statute document presente em institutional_documents
    """
    checks: list[dict[str, Any]] = []

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT legal_name, cnpj, incorporation_date, tenant_type "
            "FROM tenants WHERE id = %s",
            (tenant_id,),
        )
        tenant = cursor.fetchone() or {}

        tenant_fields_filled = all([
            tenant.get("legal_name"),
            tenant.get("cnpj"),
            tenant.get("incorporation_date"),
        ])
        checks.append(_check(
            "Identificacao institucional completa",
            "ok" if tenant_fields_filled else "warning",
            "legal_name/cnpj/incorporation_date preenchidos"
            if tenant_fields_filled
            else "um ou mais campos em falta",
        ))
        checks.append(_check(
            "Tipo de tenant definido",
            "ok" if tenant.get("tenant_type") else "fail",
            f"tipo: {tenant.get('tenant_type') or '[nao definido]'}",
        ))

        cursor.execute(
            """
            SELECT COUNT(*) AS n FROM technical_responsibles
             WHERE tenant_id = %s AND is_active = TRUE
               AND (habilitation_valid_until IS NULL
                    OR habilitation_valid_until >= CURRENT_DATE)
            """,
            (tenant_id,),
        )
        active_rt = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "RT ativo com habilitacao vigente",
            "ok" if active_rt >= 1 else "fail",
            f"{active_rt} RT(s) ativos elegiveis",
        ))

        cursor.execute(
            """
            SELECT COUNT(*) AS n FROM institutional_documents
             WHERE tenant_id = %s AND is_active = TRUE
               AND document_type = 'statute'
            """,
            (tenant_id,),
        )
        statute_count = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "Estatuto social registrado",
            "ok" if statute_count >= 1 else "warning",
            f"{statute_count} documento(s) de estatuto ativo",
        ))

    return {"score": _score_from_checks(checks), "checks": checks}


def members_summary(tenant_id: int) -> dict[str, Any]:
    """Submodulo 2: members (doc 23 §7.2)."""
    checks: list[dict[str, Any]] = []
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT COUNT(*) AS n FROM association_members "
            "WHERE tenant_id = %s AND membership_status = 'active' "
            "AND terminated_at IS NULL",
            (tenant_id,),
        )
        active_members = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "Associados ativos",
            "ok" if active_members > 0 else "warning",
            f"{active_members} associado(s) ativo(s)",
        ))

        cursor.execute(
            "SELECT COUNT(*) AS n FROM v_member_active_prescriptions "
            "WHERE tenant_id = %s",
            (tenant_id,),
        )
        with_rx = int(cursor.fetchone()["n"] or 0)
        pct_rx = (with_rx / active_members * 100) if active_members else 0.0
        checks.append(_check(
            "Associados com prescricao valida",
            "ok" if active_members == 0 or pct_rx >= 80.0 else "warning",
            f"{with_rx}/{active_members} com prescricao ativa"
            f" ({pct_rx:.0f}%)",
        ))

        cursor.execute(
            """
            SELECT COUNT(DISTINCT mc.member_id) AS n
              FROM member_consents mc
              JOIN association_members am ON am.id = mc.member_id
             WHERE am.tenant_id = %s
               AND mc.revoked_at IS NULL
            """,
            (tenant_id,),
        )
        with_consent = int(cursor.fetchone()["n"] or 0)
        pct_consent = (with_consent / active_members * 100) if active_members else 0.0
        checks.append(_check(
            "Associados com consentimento informado vigente",
            "ok" if active_members == 0 or pct_consent >= 90.0 else "warning",
            f"{with_consent}/{active_members} com consentimento ativo"
            f" ({pct_consent:.0f}%)",
        ))

    return {"score": _score_from_checks(checks), "checks": checks}


def quality_summary(tenant_id: int) -> dict[str, Any]:
    """Submodulo 3: quality (SOPs, evidencias, CAPAs)."""
    checks: list[dict[str, Any]] = []
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT COUNT(*) AS n FROM sops "
            "WHERE tenant_id = %s AND is_active = TRUE",
            (tenant_id,),
        )
        total_sops = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "SOPs ativos cadastrados",
            "ok" if total_sops >= 5 else ("warning" if total_sops > 0 else "fail"),
            f"{total_sops} SOP(s) ativo(s)",
        ))

        cursor.execute(
            "SELECT COUNT(*) AS n FROM sops "
            "WHERE tenant_id = %s AND is_active = TRUE "
            "AND current_version_id IS NOT NULL",
            (tenant_id,),
        )
        versioned = int(cursor.fetchone()["n"] or 0)
        pct_ver = (versioned / total_sops * 100) if total_sops else 0.0
        checks.append(_check(
            "SOPs com versao aprovada",
            "ok" if total_sops == 0 or pct_ver >= 80.0 else "warning",
            f"{versioned}/{total_sops} com current_version_id"
            f" ({pct_ver:.0f}%)",
        ))

        # CAPAs abertas: count informativo — presenca de CAPAs indica
        # quality system em uso. "Aberto" = completed_at IS NULL.
        # Join via sop_versions porque sop_deviations referencia versao.
        cursor.execute(
            """
            SELECT COUNT(*) AS n FROM capa_actions ca
             JOIN sop_deviations sd ON sd.id = ca.deviation_id
             WHERE sd.tenant_id = %s
               AND ca.completed_at IS NULL
            """,
            (tenant_id,),
        )
        open_capas = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "Sistema de CAPAs em operacao",
            "ok",
            f"{open_capas} CAPA(s) em andamento",
        ))

    return {"score": _score_from_checks(checks), "checks": checks}


def traceability_summary(tenant_id: int) -> dict[str, Any]:
    """Submodulo 4: traceability."""
    checks: list[dict[str, Any]] = []
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT COUNT(*) AS n FROM traceability_events "
            "WHERE tenant_id = %s",
            (tenant_id,),
        )
        total_events = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "Eventos de rastreabilidade registrados",
            "ok" if total_events > 0 else "warning",
            f"{total_events} evento(s) na trilha",
        ))

        cursor.execute(
            "SELECT COUNT(DISTINCT chain_id) AS n FROM traceability_events "
            "WHERE tenant_id = %s",
            (tenant_id,),
        )
        chains = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "Cadeias de rastreabilidade ativas",
            "ok" if chains > 0 else "warning",
            f"{chains} cadeia(s) distinta(s)",
        ))

        # Ultimo evento — freshness
        cursor.execute(
            "SELECT MAX(occurred_at) AS last_at FROM traceability_events "
            "WHERE tenant_id = %s",
            (tenant_id,),
        )
        last_at = cursor.fetchone()["last_at"]
        fresh = False
        if last_at is not None:
            age = datetime.now(timezone.utc) - last_at
            fresh = age < timedelta(days=30)
        checks.append(_check(
            "Rastreabilidade com eventos recentes",
            "ok" if fresh else ("warning" if last_at else "fail"),
            f"ultimo evento: {last_at.isoformat() if last_at else '[nunca]'}",
        ))

    return {"score": _score_from_checks(checks), "checks": checks}


def pharmacovigilance_summary(tenant_id: int) -> dict[str, Any]:
    """Submodulo 5: pharmacovigilance."""
    checks: list[dict[str, Any]] = []
    with db_cursor(dictionary=True) as (_, cursor):
        # Eventos adversos nos ultimos 90 dias
        cursor.execute(
            """
            SELECT COUNT(*) AS n FROM adverse_events
             WHERE tenant_id = %s
               AND reported_at >= NOW() - INTERVAL '90 days'
            """,
            (tenant_id,),
        )
        recent_ae = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "Captura de eventos adversos (90d)",
            "ok",
            f"{recent_ae} evento(s) reportado(s)",
        ))

        # Severidade alta/fatal — presenca indica sistema capturando, e uma
        # janela >0 disso EXIGE notificacao
        cursor.execute(
            """
            SELECT COUNT(*) AS n FROM adverse_events
             WHERE tenant_id = %s
               AND severity IN ('severe', 'life_threatening', 'fatal')
               AND reported_at >= NOW() - INTERVAL '30 days'
            """,
            (tenant_id,),
        )
        severe_ae = int(cursor.fetchone()["n"] or 0)

        # Notificados via VigiMed ou Notivisa
        cursor.execute(
            """
            SELECT COUNT(DISTINCT pn.adverse_event_id) AS n
              FROM pharmacovigilance_notifications pn
              JOIN adverse_events ae ON ae.id = pn.adverse_event_id
             WHERE ae.tenant_id = %s
               AND ae.severity IN ('severe', 'life_threatening', 'fatal')
               AND ae.reported_at >= NOW() - INTERVAL '30 days'
               AND pn.notification_target IN ('vigimed', 'notivisa')
            """,
            (tenant_id,),
        )
        notified_severe = int(cursor.fetchone()["n"] or 0)

        if severe_ae == 0:
            checks.append(_check(
                "Notificacao obrigatoria de eventos graves",
                "ok",
                "nenhum evento grave no periodo — sem obrigacao",
            ))
        else:
            compliance_pct = (notified_severe / severe_ae) * 100
            checks.append(_check(
                "Notificacao obrigatoria de eventos graves",
                "ok" if compliance_pct >= 100.0 else "fail",
                f"{notified_severe}/{severe_ae} eventos graves notificados"
                f" ({compliance_pct:.0f}%)",
            ))

        # Riscos sanitarios catalogados
        cursor.execute(
            "SELECT COUNT(*) AS n FROM sanitary_risks "
            "WHERE tenant_id = %s AND is_active = TRUE",
            (tenant_id,),
        )
        risks = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "Mapa de riscos sanitarios",
            "ok" if risks >= 5 else ("warning" if risks > 0 else "fail"),
            f"{risks} risco(s) sanitario(s) cadastrado(s)",
        ))

    return {"score": _score_from_checks(checks), "checks": checks}


def regulatory_summary(tenant_id: int) -> dict[str, Any]:
    """Submodulo 6: regulatory (sandbox_projects + indicators)."""
    checks: list[dict[str, Any]] = []
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT COUNT(*) AS n FROM sandbox_projects "
            "WHERE tenant_id = %s AND status IN ('active', 'approved', 'submitted')",
            (tenant_id,),
        )
        active_projects = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "Projetos de sandbox em andamento",
            "ok" if active_projects > 0 else "warning",
            f"{active_projects} projeto(s) ativos/aprovados/submetidos",
        ))

        # Indicadores mandatorios com pelo menos 1 valor recente
        cursor.execute(
            """
            SELECT COUNT(*) AS n
              FROM sandbox_indicators si
              JOIN sandbox_projects sp ON sp.id = si.project_id
             WHERE sp.tenant_id = %s AND si.is_mandatory = TRUE
            """,
            (tenant_id,),
        )
        mandatory = int(cursor.fetchone()["n"] or 0)

        cursor.execute(
            """
            SELECT COUNT(DISTINCT si.id) AS n
              FROM sandbox_indicators si
              JOIN sandbox_projects sp ON sp.id = si.project_id
              JOIN sandbox_indicator_values siv ON siv.indicator_id = si.id
             WHERE sp.tenant_id = %s AND si.is_mandatory = TRUE
               AND siv.period_start >= NOW() - INTERVAL '90 days'
            """,
            (tenant_id,),
        )
        with_recent = int(cursor.fetchone()["n"] or 0)
        pct_reported = (with_recent / mandatory * 100) if mandatory else 0.0

        if mandatory == 0:
            checks.append(_check(
                "Indicadores mandatorios reportados (90d)",
                "warning",
                "nenhum indicador mandatorio definido",
            ))
        else:
            checks.append(_check(
                "Indicadores mandatorios reportados (90d)",
                "ok" if pct_reported >= 80.0 else "warning",
                f"{with_recent}/{mandatory} com valor recente"
                f" ({pct_reported:.0f}%)",
            ))

        # Indicadores on_target via view
        cursor.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN on_target IS TRUE THEN 1 ELSE 0 END) AS ok
              FROM v_sandbox_indicator_dashboard
             WHERE tenant_id = %s AND target_value IS NOT NULL
            """,
            (tenant_id,),
        )
        dash = cursor.fetchone() or {}
        total_w_target = int(dash.get("total") or 0)
        on_target = int(dash.get("ok") or 0)
        pct_target = (on_target / total_w_target * 100) if total_w_target else 0.0

        if total_w_target == 0:
            checks.append(_check(
                "Indicadores dentro do target",
                "warning",
                "nenhum indicador com target definido",
            ))
        else:
            checks.append(_check(
                "Indicadores dentro do target",
                "ok" if pct_target >= 70.0 else "warning",
                f"{on_target}/{total_w_target} on_target"
                f" ({pct_target:.0f}%)",
            ))

    return {"score": _score_from_checks(checks), "checks": checks}


def crypto_summary(tenant_id: int) -> dict[str, Any]:
    """Submodulo 7: crypto/anchoring."""
    checks: list[dict[str, Any]] = []
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT COUNT(*) AS n FROM blockchain_anchors "
            "WHERE tenant_id = %s AND verification_status = 'confirmed'",
            (tenant_id,),
        )
        confirmed = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "Ancoragens confirmadas na blockchain",
            "ok" if confirmed > 0 else "warning",
            f"{confirmed} ancoragem(ns) confirmada(s)",
        ))

        cursor.execute(
            "SELECT COUNT(*) AS n FROM blockchain_anchors "
            "WHERE tenant_id = %s AND verification_status = 'pending'",
            (tenant_id,),
        )
        pending = int(cursor.fetchone()["n"] or 0)
        # pending sozinho nao penaliza (job de upgrade esta rodando),
        # mas pending antigo (> 24h) sinaliza falha do job.
        cursor.execute(
            "SELECT COUNT(*) AS n FROM blockchain_anchors "
            "WHERE tenant_id = %s AND verification_status = 'pending' "
            "AND anchored_at < NOW() - INTERVAL '24 hours'",
            (tenant_id,),
        )
        stuck = int(cursor.fetchone()["n"] or 0)
        checks.append(_check(
            "Ancoragens pendentes sem backlog",
            "ok" if stuck == 0 else "fail",
            f"{pending} pendente(s) total, {stuck} travada(s) > 24h",
        ))

        cursor.execute(
            "SELECT MAX(anchored_at) AS last_at FROM blockchain_anchors "
            "WHERE tenant_id = %s AND verification_status = 'confirmed'",
            (tenant_id,),
        )
        last_at = cursor.fetchone()["last_at"]
        fresh_anchor = False
        if last_at is not None:
            age = datetime.now(timezone.utc) - last_at
            fresh_anchor = age < timedelta(days=7)
        checks.append(_check(
            "Ancoragem recente (< 7d)",
            "ok" if fresh_anchor else ("warning" if last_at else "fail"),
            f"ultima confirmada: {last_at.isoformat() if last_at else '[nunca]'}",
        ))

    return {"score": _score_from_checks(checks), "checks": checks}


# Registry dos 7 submodulos — nome canonico → funcao
SUBMODULES = {
    "governance": governance_summary,
    "members": members_summary,
    "quality": quality_summary,
    "traceability": traceability_summary,
    "pharmacovigilance": pharmacovigilance_summary,
    "regulatory": regulatory_summary,
    "crypto": crypto_summary,
}


# ===========================================================================
# Endpoints
# ===========================================================================


@compliance_bp.get("/compliance")
@api_role_required("Admin", "Medico")
def get_compliance():
    """Checklist ANVISA legado (pre-SCC). Retrocompatibilidade."""
    clinic_id = g.clinic_id
    checks = []

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN doctor_crm IS NOT NULL AND doctor_crm != '' THEN 1 ELSE 0 END) AS with_crm
                   FROM prescriptions WHERE clinic_id = %s""",
                (clinic_id,),
            )
            rx = cursor.fetchone()
            total_rx = rx["total"] or 0
            crm_rx = rx["with_crm"] or 0
            checks.append({
                "category": "prescricoes",
                "name": "Prescricoes com CRM do medico",
                "status": "ok" if total_rx == 0 or crm_rx == total_rx else "warning",
                "detail": f"{crm_rx}/{total_rx} prescricoes com CRM preenchido",
            })

            cursor.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN status IS NOT NULL AND status != '' THEN 1 ELSE 0 END) AS with_status
                   FROM patients WHERE clinic_id = %s""",
                (clinic_id,),
            )
            pt = cursor.fetchone()
            checks.append({
                "category": "dados",
                "name": "Pacientes com status cadastral",
                "status": "ok" if (pt["total"] or 0) == 0 or pt["with_status"] == pt["total"] else "warning",
                "detail": f"{pt['with_status']}/{pt['total']} pacientes com status",
            })

            cursor.execute(
                "SELECT COUNT(*) AS total FROM audit_trail WHERE clinic_id = %s",
                (clinic_id,),
            )
            audit_count = cursor.fetchone()["total"]
            checks.append({
                "category": "rastreabilidade",
                "name": "Trilha de auditoria ativa",
                "status": "ok" if audit_count > 0 else "warning",
                "detail": f"{audit_count} eventos registrados",
            })

            cursor.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN expiry_date IS NOT NULL THEN 1 ELSE 0 END) AS with_expiry
                   FROM stock_inventory WHERE clinic_id = %s""",
                (clinic_id,),
            )
            stock = cursor.fetchone()
            checks.append({
                "category": "rastreabilidade",
                "name": "Estoque com validade registrada",
                "status": "ok" if (stock["total"] or 0) == 0 or stock["with_expiry"] == stock["total"] else "warning",
                "detail": f"{stock['with_expiry']}/{stock['total']} itens com validade",
            })

            cursor.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN clinical_assessment IS NOT NULL AND clinical_assessment != '' THEN 1 ELSE 0 END) AS complete
                   FROM medical_record_entries WHERE clinic_id = %s""",
                (clinic_id,),
            )
            mre = cursor.fetchone()
            checks.append({
                "category": "documentacao",
                "name": "Prontuarios com avaliacao clinica",
                "status": "ok" if (mre["total"] or 0) == 0 or mre["complete"] == mre["total"] else "warning",
                "detail": f"{mre['complete']}/{mre['total']} entradas com avaliacao",
            })

            ok_count = sum(1 for c in checks if c["status"] == "ok")
            score = round(ok_count / len(checks) * 100) if checks else 0

            return _success({
                "score": score,
                "checks": checks,
                "total_checks": len(checks),
                "passed": ok_count,
            })
    except OperationalError:
        logger.error("DB unavailable on compliance.get_compliance_report", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, TypeError, ValueError, KeyError):
        logger.error("Error generating compliance report", exc_info=True)
        return _success({"score": 0, "checks": [], "total_checks": 0, "passed": 0})


@compliance_bp.get("/compliance/overview")
@api_role_required("Admin", "Medico")
def get_compliance_overview():
    """Overview agregado dos 7 submodulos do SCC (F6.4 do BACKLOG_SCC).

    Retorna:
      {
        "tenant_id": 1,
        "overall_score": 78,
        "submodules": {
          "governance":       {"score": 100, "checks": [...]},
          "members":          {"score":  66, "checks": [...]},
          "quality":          {"score":  75, "checks": [...]},
          ...
        }
      }
    """
    tenant_id = g.clinic_id  # tenant_id == clinic_id (docs/25 §11.3)

    submodules: dict[str, Any] = {}
    scores: list[int] = []

    for name, fn in SUBMODULES.items():
        try:
            result = fn(tenant_id)
            submodules[name] = result
            scores.append(int(result.get("score", 0)))
        except (DatabaseError, TypeError, ValueError, KeyError):
            logger.error("compliance_submodule_failed name=%s", name, exc_info=True)
            submodules[name] = {
                "score": 0,
                "checks": [],
                "error": "falha ao calcular submodulo",
            }
            scores.append(0)

    overall = round(sum(scores) / len(scores)) if scores else 0

    return _success({
        "tenant_id": tenant_id,
        "overall_score": overall,
        "submodules": submodules,
    })


@compliance_bp.get("/compliance/submodule/<name>")
@api_role_required("Admin", "Medico")
def get_compliance_submodule(name: str):
    """Detalhe de 1 submodulo por nome. 404 se nome nao reconhecido."""
    tenant_id = g.clinic_id
    fn = SUBMODULES.get(name)
    if fn is None:
        return _success({
            "error": f"submodulo desconhecido: {name}",
            "available": list(SUBMODULES.keys()),
        }), 404

    try:
        result = fn(tenant_id)
    except OperationalError:
        logger.error("DB unavailable on compliance.get_compliance_submodule name=%s", name, exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, TypeError, ValueError, KeyError):
        logger.error("compliance_submodule_failed name=%s", name, exc_info=True)
        return _success({
            "score": 0, "checks": [], "error": "falha ao calcular submodulo",
        }), 500

    return _success({
        "tenant_id": tenant_id,
        "submodule": name,
        **result,
    })
