# src/repositories/adverse_event_repository.py
"""
Repositorio de eventos adversos (F3.3 do docs/BACKLOG_SCC.md).

Acesso SQL puro a tabela `adverse_events` (schema em migration 031).
Sem regras de negocio aqui — validacao e orquestracao ficam em
`src/services/adverse_event_service.py`.

Tabela consultada:
  - adverse_events (doc 25 secao 8.1)

Por convencao SCC, funcoes recebem `tenant_id` (== clinic_id).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.repo.adverse_event")


_COLUMNS = """
    id, tenant_id, member_id, preparation_id,
    reported_at, event_onset_at,
    severity, description, reported_via,
    ai_triage_result, triaged_by,
    clinical_assessment, outcome,
    created_at, updated_at
"""


# ---------------------------------------------------------------------------
# INSERT
# ---------------------------------------------------------------------------

def insert_adverse_event(
    *,
    tenant_id: int,
    member_id: Optional[int],
    preparation_id: Optional[int],
    reported_at: datetime,
    event_onset_at: Optional[datetime],
    severity: str,
    description: str,
    reported_via: str,
) -> dict[str, Any]:
    """
    Insere um evento adverso minimalista (sem triagem IA ainda).
    Retorna a linha completa inserida.
    """
    sql = f"""
        INSERT INTO adverse_events (
          tenant_id, member_id, preparation_id,
          reported_at, event_onset_at,
          severity, description, reported_via
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING {_COLUMNS}
    """
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            sql,
            (
                tenant_id, member_id, preparation_id,
                reported_at, event_onset_at,
                severity, description, reported_via,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return row


# ---------------------------------------------------------------------------
# SELECT
# ---------------------------------------------------------------------------

def get_adverse_event(event_id: int, *, tenant_id: int) -> Optional[dict[str, Any]]:
    """Busca um evento por id escopado ao tenant (retorna None se nao existir)."""
    sql = f"""
        SELECT {_COLUMNS}
        FROM adverse_events
        WHERE id = %s AND tenant_id = %s
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (event_id, tenant_id))
        return cur.fetchone()


def list_adverse_events(
    tenant_id: int,
    *,
    member_id: Optional[int] = None,
    severity: Optional[str] = None,
    reported_via: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    has_triage: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Lista eventos adversos do tenant com filtros opcionais.

    Ordenacao: reported_at DESC (mais recentes primeiro).

    `has_triage`:
      - True  -> apenas eventos com ai_triage_result preenchido
      - False -> apenas eventos sem triagem IA
      - None  -> sem filtro
    """
    sql_where = ["tenant_id = %s"]
    params: list[Any] = [tenant_id]

    if member_id is not None:
        sql_where.append("member_id = %s")
        params.append(member_id)
    if severity is not None:
        sql_where.append("severity = %s")
        params.append(severity)
    if reported_via is not None:
        sql_where.append("reported_via = %s")
        params.append(reported_via)
    if since is not None:
        sql_where.append("reported_at >= %s")
        params.append(since)
    if until is not None:
        sql_where.append("reported_at < %s")
        params.append(until)
    if has_triage is True:
        sql_where.append("ai_triage_result IS NOT NULL")
    elif has_triage is False:
        sql_where.append("ai_triage_result IS NULL")

    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT {_COLUMNS}
        FROM adverse_events
        WHERE {where_clause}
        ORDER BY reported_at DESC, id DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        return list(cur.fetchall())


def count_by_severity(
    tenant_id: int,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> dict[str, int]:
    """
    Contagem de eventos por severidade no escopo do tenant.
    Retorna dict { severity -> n }. Severidades sem eventos nao aparecem.
    """
    sql_where = ["tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if since is not None:
        sql_where.append("reported_at >= %s")
        params.append(since)
    if until is not None:
        sql_where.append("reported_at < %s")
        params.append(until)
    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT severity, COUNT(*) AS n
        FROM adverse_events
        WHERE {where_clause}
        GROUP BY severity
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        return {r["severity"]: int(r["n"]) for r in cur.fetchall()}


# ---------------------------------------------------------------------------
# UPDATE — triagem IA, parecer clinico, outcome
# ---------------------------------------------------------------------------

def update_triage_result(
    event_id: int,
    *,
    tenant_id: int,
    ai_triage_result: dict[str, Any],
    triaged_by: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """
    Grava o resultado da triagem IA (F3.4) em ai_triage_result JSONB.
    Retorna a linha atualizada ou None se o evento nao existir.
    """
    sql = f"""
        UPDATE adverse_events
        SET ai_triage_result = %s::jsonb,
            triaged_by       = COALESCE(%s, triaged_by),
            updated_at       = NOW()
        WHERE id = %s AND tenant_id = %s
        RETURNING {_COLUMNS}
    """
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            sql,
            (json.dumps(ai_triage_result), triaged_by, event_id, tenant_id),
        )
        row = cur.fetchone()
        conn.commit()
        return row


def update_clinical_assessment(
    event_id: int,
    *,
    tenant_id: int,
    clinical_assessment: str,
) -> Optional[dict[str, Any]]:
    """
    Grava parecer clinico (texto livre do medico revisor).
    Retorna a linha atualizada ou None se o evento nao existir.
    """
    sql = f"""
        UPDATE adverse_events
        SET clinical_assessment = %s,
            updated_at          = NOW()
        WHERE id = %s AND tenant_id = %s
        RETURNING {_COLUMNS}
    """
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(sql, (clinical_assessment, event_id, tenant_id))
        row = cur.fetchone()
        conn.commit()
        return row


def update_outcome(
    event_id: int,
    *,
    tenant_id: int,
    outcome: str,
) -> Optional[dict[str, Any]]:
    """
    Atualiza o outcome clinico do evento (resolved/resolving/ongoing/worsened/unknown).
    Retorna a linha atualizada ou None se o evento nao existir.
    """
    sql = f"""
        UPDATE adverse_events
        SET outcome    = %s,
            updated_at = NOW()
        WHERE id = %s AND tenant_id = %s
        RETURNING {_COLUMNS}
    """
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(sql, (outcome, event_id, tenant_id))
        row = cur.fetchone()
        conn.commit()
        return row
