# src/repositories/evidence_repository.py
"""
Repositorio do Evidence Engine (F4.1 do docs/BACKLOG_SCC.md).

Acesso SQL pre-agregado as tabelas de telemetria pos-consulta e diario
clinico, para alimentar `src/services/evidence_service.py`. Sem regras
de negocio aqui — so SELECTs.

Tabelas consultadas:
  - scheduled_followups (D+3/D+7/D+15 com response_text/responded_at)
  - symptom_diary (overall_score, pain_level, sleep_quality, mood)
  - iot_telemetry (metricas continuas)
  - treatment_plans (dose, ratio, plan_name) — para condition matching
  - patients (contexto demografico)

Por convencao SCC, funcoes recebem `tenant_id`. As tabelas
transacionais usam `clinic_id`; assumimos `tenant_id == clinic_id`
conforme docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md secao 11.3
("clinic_id = tenant_id" preservado durante a evolucao).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.repo.evidence")


# ---------------------------------------------------------------------------
# Follow-ups respondidos com contexto clinico
# ---------------------------------------------------------------------------

def list_responded_followups(
    tenant_id: int,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    plan_name_like: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Follow-ups com `responded_at IS NOT NULL` no escopo do tenant.

    Quando `plan_name_like` e informado, restringe a pacientes com
    pelo menos um treatment_plan ativo cujo plan_name OU
    plan_description contenha o termo (ILIKE).

    Retorna por linha: followup_id, patient_id, patient_name,
    followup_type, scheduled_at, responded_at, response_text,
    plan_name (do plano mais recente do paciente, se houver).
    """
    sql_where = ["sf.clinic_id = %s", "sf.responded_at IS NOT NULL"]
    params: list[Any] = [tenant_id]

    if since is not None:
        sql_where.append("sf.responded_at >= %s")
        params.append(since)
    if until is not None:
        sql_where.append("sf.responded_at < %s")
        params.append(until)
    if plan_name_like:
        sql_where.append(
            "EXISTS ("
            "  SELECT 1 FROM treatment_plans tp "
            "  WHERE tp.patient_id = sf.patient_id"
            "    AND tp.clinic_id = sf.clinic_id"
            "    AND ("
            "      tp.plan_name ILIKE %s OR tp.plan_description ILIKE %s"
            "    )"
            ")"
        )
        like = f"%{plan_name_like}%"
        params.extend([like, like])

    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT
          sf.id            AS followup_id,
          sf.patient_id,
          p.name           AS patient_name,
          sf.followup_type,
          sf.scheduled_at,
          sf.responded_at,
          sf.response_text,
          sf.report_id,
          (SELECT tp.plan_name
             FROM treatment_plans tp
            WHERE tp.patient_id = sf.patient_id
              AND tp.clinic_id  = sf.clinic_id
            ORDER BY tp.created_at DESC
            LIMIT 1)       AS latest_plan_name
        FROM scheduled_followups sf
        LEFT JOIN patients p ON p.id = sf.patient_id
        WHERE {where_clause}
        ORDER BY sf.responded_at DESC
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        return list(cur.fetchall())


def get_followup_by_id(followup_id: int) -> Optional[dict[str, Any]]:
    """Single row de scheduled_followups, com patient_name."""
    sql = """
        SELECT
          sf.id            AS followup_id,
          sf.clinic_id,
          sf.patient_id,
          p.name           AS patient_name,
          sf.followup_type,
          sf.scheduled_at,
          sf.responded_at,
          sf.response_text,
          sf.status
        FROM scheduled_followups sf
        LEFT JOIN patients p ON p.id = sf.patient_id
        WHERE sf.id = %s
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (followup_id,))
        return cur.fetchone()


def count_followups_by_status(
    tenant_id: int,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> dict[str, int]:
    """
    Contagem por (followup_type, status) no escopo. Usado para calcular
    response rate (responded / sent) por tipo.
    """
    sql_where = ["sf.clinic_id = %s"]
    params: list[Any] = [tenant_id]
    if since is not None:
        sql_where.append("sf.scheduled_at >= %s")
        params.append(since)
    if until is not None:
        sql_where.append("sf.scheduled_at < %s")
        params.append(until)

    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT
          sf.followup_type,
          sf.status,
          COUNT(*) AS n
        FROM scheduled_followups sf
        WHERE {where_clause}
        GROUP BY sf.followup_type, sf.status
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    out: dict[str, int] = {}
    for r in rows:
        out[f"{r['followup_type']}::{r['status']}"] = int(r["n"])
    return out


# ---------------------------------------------------------------------------
# Treatment plans por condicao
# ---------------------------------------------------------------------------

def list_treatment_plans_by_condition(
    tenant_id: int,
    condition_name: str,
    *,
    only_active: bool = True,
    limit: Optional[int] = None,
    offset: int = 0,
    include_total: bool = False,
):
    """
    Treatment_plans cujo plan_name OU plan_description contem
    `condition_name` (ILIKE). Inclui patient context.

    Sprint 3 Page-Migration Tier-2:
      - `limit=None` -> compat path (`list[dict]`). Mantido para
        `evidence_service.aggregate_condition_outcomes` (caller interno).
      - `limit=int`  -> dict `{items, total, has_more}`.

    Quando `only_active=True`, filtra status='ativo'.
    """
    sql_where = [
        "tp.clinic_id = %s",
        "(tp.plan_name ILIKE %s OR tp.plan_description ILIKE %s)",
    ]
    params: list[Any] = [tenant_id, f"%{condition_name}%", f"%{condition_name}%"]
    if only_active:
        sql_where.append("tp.status = 'ativo'")

    where_clause = " AND ".join(sql_where)
    base_sql = f"""
        SELECT
          tp.id            AS plan_id,
          tp.patient_id,
          p.name           AS patient_name,
          tp.plan_name,
          tp.dosage,
          tp.cbd_thc_ratio,
          tp.frequency,
          tp.route,
          tp.status,
          tp.created_at    AS plan_started_at
        FROM treatment_plans tp
        LEFT JOIN patients p ON p.id = tp.patient_id
        WHERE {where_clause}
        ORDER BY tp.created_at DESC
    """

    with db_cursor(dictionary=True) as (_, cur):
        if limit is None:
            cur.execute(base_sql, tuple(params))
            return list(cur.fetchall())

        total = None
        if include_total:
            count_sql = f"""
                SELECT COUNT(*) AS n
                FROM treatment_plans tp
                WHERE {where_clause}
            """
            cur.execute(count_sql, tuple(params))
            total = int(cur.fetchone()["n"])

        fetch_n = limit if include_total else limit + 1
        cur.execute(
            base_sql + " LIMIT %s OFFSET %s",
            tuple(params) + (fetch_n, offset),
        )
        rows = cur.fetchall()

    if include_total:
        items = list(rows)
        has_more = (offset + len(items)) < (total or 0)
    else:
        from src.web.pagination import apply_limit_plus_one
        items, has_more = apply_limit_plus_one(rows, limit)

    return {"items": items, "total": total, "has_more": has_more}


# ---------------------------------------------------------------------------
# Diario de sintomas (baseline e post-treatment)
# ---------------------------------------------------------------------------

def aggregate_diary_metric(
    patient_id: int,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    metric: str = "pain_level",
) -> dict[str, Any]:
    """
    Mean/min/max/count de uma metrica do symptom_diary num intervalo.

    `metric` deve ser uma das colunas numericas: pain_level, overall_score,
    sleep_quality. Whitelist enforced para evitar SQL injection.
    """
    allowed = {"pain_level", "overall_score", "sleep_quality"}
    if metric not in allowed:
        raise ValueError(f"metric invalida: {metric!r} (esperado um de {allowed})")

    sql_where = ["sd.patient_id = %s", f"sd.{metric} IS NOT NULL"]
    params: list[Any] = [patient_id]
    if since is not None:
        sql_where.append("sd.created_at >= %s")
        params.append(since)
    if until is not None:
        sql_where.append("sd.created_at < %s")
        params.append(until)

    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT
          AVG(sd.{metric})::float AS mean,
          MIN(sd.{metric})        AS min,
          MAX(sd.{metric})        AS max,
          COUNT(*)                AS n
        FROM symptom_diary sd
        WHERE {where_clause}
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        row = cur.fetchone() or {}

    return {
        "mean": row.get("mean"),
        "min": row.get("min"),
        "max": row.get("max"),
        "n": int(row.get("n", 0) or 0),
    }


def count_distinct_patients_with_plan(
    tenant_id: int,
    condition_name: str,
    *,
    only_active: bool = True,
) -> int:
    """N de pacientes distintos com pelo menos 1 plan_name matching."""
    sql_where = [
        "tp.clinic_id = %s",
        "(tp.plan_name ILIKE %s OR tp.plan_description ILIKE %s)",
    ]
    params: list[Any] = [tenant_id, f"%{condition_name}%", f"%{condition_name}%"]
    if only_active:
        sql_where.append("tp.status = 'ativo'")

    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT COUNT(DISTINCT tp.patient_id) AS n
        FROM treatment_plans tp
        WHERE {where_clause}
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        row = cur.fetchone() or {}
    return int(row.get("n", 0) or 0)
