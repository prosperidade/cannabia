"""Repositorio de leitura agregada da pagina /org/acompanhamento.

Contagens e medidores que alimentam os KPIs e a faixa "Atividade dos
agentes (ultimas 24h)". Sem regras de negocio — orquestracao e
classificacao de endpoint -> agente ficam em
``src/services/acompanhamento_service.py``.

Convencao de escopo:
  - ``adverse_events`` ja tem ``tenant_id`` (migration 031).
  - ``scheduled_followups`` (013), ``triage_links`` (018) e
    ``ai_audit_logs`` (001) sao escopadas por ``clinic_id`` e
    requerem JOIN em ``clinics`` para filtrar pelo ``tenant_id``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.repo.acompanhamento")


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

def count_patients_at_risk(tenant_id: int) -> int:
    """Eventos adversos graves ainda sem parecer clinico do medico.

    Severidades 'severe' e 'life_threatening' AND clinical_assessment
    NULL — caso clinico aberto que demanda atencao humana.
    """
    sql = """
        SELECT COUNT(*) AS n
        FROM adverse_events
        WHERE tenant_id = %s
          AND severity IN ('severe', 'life_threatening')
          AND clinical_assessment IS NULL
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (tenant_id,))
        row = cur.fetchone()
        return int(row["n"]) if row else 0


def count_adverse_events_open(tenant_id: int) -> int:
    """Eventos adversos sem outcome registrado (independente de severidade)."""
    sql = """
        SELECT COUNT(*) AS n
        FROM adverse_events
        WHERE tenant_id = %s
          AND outcome IS NULL
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (tenant_id,))
        row = cur.fetchone()
        return int(row["n"]) if row else 0


def count_followups_pending(tenant_id: int) -> int:
    """Follow-ups CRM (D+3/D+7/D+15) ainda sem resposta do paciente.

    Considera apenas status 'pending' (ainda nao enviado) e 'sent'
    (enviado, aguardando paciente). Cancelados, falhados e respondidos
    nao entram.
    """
    sql = """
        SELECT COUNT(*) AS n
        FROM scheduled_followups sf
        JOIN clinics c ON c.id = sf.clinic_id
        WHERE c.tenant_id = %s
          AND sf.responded_at IS NULL
          AND sf.status IN ('pending', 'sent')
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (tenant_id,))
        row = cur.fetchone()
        return int(row["n"]) if row else 0


def count_triages_in_progress(tenant_id: int) -> int:
    """Links de triagem ativos ainda nao consumidos pelo paciente.

    Aproximacao razoavel ate o agente Triagem dedicado (P5) expor
    sessoes em curso. Conta links 'active' nao usados e nao expirados.
    """
    sql = """
        SELECT COUNT(*) AS n
        FROM triage_links tl
        JOIN clinics c ON c.id = tl.clinic_id
        WHERE c.tenant_id = %s
          AND tl.status = 'active'
          AND tl.used_at IS NULL
          AND tl.expires_at > NOW()
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (tenant_id,))
        row = cur.fetchone()
        return int(row["n"]) if row else 0


# ---------------------------------------------------------------------------
# Pacientes em acompanhamento ativo
# ---------------------------------------------------------------------------

def list_active_patients(tenant_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """Pacientes com plano terapeutico ativo no tenant.

    "Ativo" = ultima entrada em ``treatment_plans`` (por paciente) com
    ``status = 'ativo'``. A lista vem ordenada pela proxima data de retorno
    (NULLS por ultimo, depois ``plan_started_at`` DESC).

    Cada item traz tambem o status do ultimo follow-up enviado/agendado
    para a tela exibir um badge "respondido"/"aguardando".

    Nota: ``adverse_events`` usa ``member_id`` (nao ``patient_id``); a
    flag de "tem evento aberto" fica para sprint que ligar
    ``association_members`` a ``patients``.
    """
    sql = """
        WITH active_plans AS (
            SELECT DISTINCT ON (tp.patient_id)
                tp.patient_id,
                tp.plan_name,
                tp.dosage,
                tp.frequency,
                tp.created_at      AS plan_started_at,
                tp.next_return_date,
                tp.status          AS plan_status
            FROM treatment_plans tp
            JOIN clinics c ON c.id = tp.clinic_id
            WHERE c.tenant_id = %(tenant)s
              AND tp.status = 'ativo'
            ORDER BY tp.patient_id, tp.created_at DESC
        ),
        last_followup AS (
            SELECT DISTINCT ON (sf.patient_id)
                sf.patient_id,
                sf.status            AS followup_status,
                sf.followup_type,
                sf.responded_at,
                sf.scheduled_at,
                sf.sent_at
            FROM scheduled_followups sf
            JOIN clinics c ON c.id = sf.clinic_id
            WHERE c.tenant_id = %(tenant)s
            ORDER BY sf.patient_id,
                     COALESCE(sf.sent_at, sf.scheduled_at, sf.responded_at) DESC NULLS LAST
        )
        SELECT
            p.id           AS patient_id,
            p.name         AS patient_name,
            p.phone        AS patient_phone,
            ap.plan_name,
            ap.dosage,
            ap.frequency,
            ap.plan_started_at,
            ap.next_return_date,
            lf.followup_status,
            lf.followup_type,
            lf.responded_at,
            lf.sent_at,
            lf.scheduled_at
        FROM patients p
        JOIN clinics c   ON c.id = p.clinic_id
        JOIN active_plans ap ON ap.patient_id = p.id
        LEFT JOIN last_followup lf ON lf.patient_id = p.id
        WHERE c.tenant_id = %(tenant)s
        ORDER BY ap.next_return_date NULLS LAST, ap.plan_started_at DESC
        LIMIT %(limit)s
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, {"tenant": tenant_id, "limit": limit})
        return list(cur.fetchall() or [])


# ---------------------------------------------------------------------------
# Atividade dos agentes (ultimas 24h)
# ---------------------------------------------------------------------------

def agent_activity_last_24h(tenant_id: int) -> list[dict[str, Any]]:
    """Agrupa ``ai_audit_logs`` por endpoint nas ultimas 24h.

    Retorna lista de ``{endpoint, n, last_at}`` para que o service
    classifique o endpoint em uma das 4 famılias de agente
    (Triagem/Anamnese/FollowUp/Regulatorio).
    """
    sql = """
        SELECT ail.endpoint AS endpoint,
               COUNT(*)     AS n,
               MAX(ail.created_at) AS last_at
        FROM ai_audit_logs ail
        JOIN clinics c ON c.id = ail.clinic_id
        WHERE c.tenant_id = %s
          AND ail.created_at >= NOW() - INTERVAL '24 hours'
        GROUP BY ail.endpoint
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (tenant_id,))
        rows = cur.fetchall() or []
        result: list[dict[str, Any]] = []
        for row in rows:
            last_at = row.get("last_at")
            if isinstance(last_at, datetime):
                last_at_iso = last_at.isoformat()
            else:
                last_at_iso = last_at
            result.append({
                "endpoint": row["endpoint"],
                "n": int(row["n"]),
                "last_at": last_at_iso,
            })
        return result
