# src/repositories/pharmacovigilance_notification_repository.py
"""
Repositorio de notificacoes regulatorias (F3.6 do docs/BACKLOG_SCC.md).

Acesso SQL puro a tabela `pharmacovigilance_notifications` (schema em
migration 031). Sem regras de negocio — orquestracao fica em
`src/services/pharmacovigilance_service.py`.

Tabela consultada:
  - pharmacovigilance_notifications (doc 25 secao 8.2)

Por convencao SCC, escopagem por tenant e feita via JOIN com
`adverse_events.tenant_id` — a tabela de notificacoes nao tem
`tenant_id` proprio.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.repo.pv_notification")


_COLUMNS = """
    id, adverse_event_id,
    notification_target, notified_at, notification_reference,
    response_received_at, response_payload, created_at
"""

# Versao qualificada para SELECTs com JOIN — evita ambiguidade em
# colunas como `id` que existem em adverse_events tambem.
_COLUMNS_N = """
    n.id, n.adverse_event_id,
    n.notification_target, n.notified_at, n.notification_reference,
    n.response_received_at, n.response_payload, n.created_at
"""


# ---------------------------------------------------------------------------
# INSERT
# ---------------------------------------------------------------------------

def insert_notification(
    *,
    adverse_event_id: int,
    notification_target: str,
    notified_at: datetime,
    notification_reference: Optional[str],
    response_payload: Optional[dict[str, Any]],
    response_received_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    Insere uma notificacao regulatoria. Retorna a linha inserida.

    O caller (service) e responsavel por garantir que `adverse_event_id`
    pertence ao tenant correto.
    """
    sql = f"""
        INSERT INTO pharmacovigilance_notifications (
          adverse_event_id, notification_target, notified_at,
          notification_reference, response_payload, response_received_at
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, %s)
        RETURNING {_COLUMNS}
    """
    payload_json = (
        json.dumps(response_payload) if response_payload is not None else None
    )
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            sql,
            (
                adverse_event_id,
                notification_target,
                notified_at,
                notification_reference,
                payload_json,
                response_received_at,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return row


# ---------------------------------------------------------------------------
# SELECT
# ---------------------------------------------------------------------------

def get_notification(notification_id: int, *, tenant_id: int) -> Optional[dict[str, Any]]:
    """
    Busca uma notificacao por id; valida o escopo via JOIN com
    adverse_events.tenant_id. Retorna None se nao existir ou for de
    outro tenant.
    """
    sql = f"""
        SELECT {_COLUMNS_N}
        FROM pharmacovigilance_notifications n
        JOIN adverse_events ae ON ae.id = n.adverse_event_id
        WHERE n.id = %s AND ae.tenant_id = %s
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (notification_id, tenant_id))
        return cur.fetchone()


def list_for_event(
    adverse_event_id: int, *, tenant_id: int
) -> list[dict[str, Any]]:
    """
    Lista todas as notificacoes de um evento adverso, escopadas por
    tenant via JOIN.
    """
    sql = f"""
        SELECT {_COLUMNS_N}
        FROM pharmacovigilance_notifications n
        JOIN adverse_events ae ON ae.id = n.adverse_event_id
        WHERE n.adverse_event_id = %s AND ae.tenant_id = %s
        ORDER BY n.notified_at DESC, n.id DESC
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (adverse_event_id, tenant_id))
        return list(cur.fetchall())


def count_for_tenant(
    tenant_id: int,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> dict[str, int]:
    """
    Contagem por `notification_target` no escopo do tenant (e janela
    opcional). Usado pelo dashboard. Targets sem notificacoes nao
    aparecem no dict.
    """
    sql_where = ["ae.tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if since is not None:
        sql_where.append("n.notified_at >= %s")
        params.append(since)
    if until is not None:
        sql_where.append("n.notified_at < %s")
        params.append(until)
    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT n.notification_target, COUNT(*) AS n
        FROM pharmacovigilance_notifications n
        JOIN adverse_events ae ON ae.id = n.adverse_event_id
        WHERE {where_clause}
        GROUP BY n.notification_target
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        return {r["notification_target"]: int(r["n"]) for r in cur.fetchall()}


# ---------------------------------------------------------------------------
# UPDATE — registro de resposta do orgao regulador
# ---------------------------------------------------------------------------

def record_response(
    notification_id: int,
    *,
    tenant_id: int,
    response_received_at: datetime,
    response_payload: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """
    Atualiza uma notificacao com a resposta recebida do orgao regulador.

    Escopagem por tenant via subquery — UPDATE so aplica se a
    notificacao pertence a um adverse_event do tenant.
    """
    sql = f"""
        UPDATE pharmacovigilance_notifications
        SET response_received_at = %s,
            response_payload     = COALESCE(%s::jsonb, response_payload)
        WHERE id = %s
          AND adverse_event_id IN (
            SELECT id FROM adverse_events WHERE tenant_id = %s
          )
        RETURNING {_COLUMNS}
    """
    payload_json = (
        json.dumps(response_payload) if response_payload is not None else None
    )
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            sql,
            (response_received_at, payload_json, notification_id, tenant_id),
        )
        row = cur.fetchone()
        conn.commit()
        return row
