from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional  # noqa: F401

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.patient_timeline")


def _timeline_schema_enabled() -> bool:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'patient_timeline_events'
            ) AS timeline_exists
            """
        )
        row = cursor.fetchone()
        return bool(row["timeline_exists"])


def create_event(
    clinic_id: int,
    patient_id: int,
    event_type: str,
    title: str,
    description: Optional[str] = None,
    journey_stage: Optional[str] = None,
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    event_time: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    if not _timeline_schema_enabled():
        logger.debug("Timeline ainda indisponível no schema; evento '%s' ignorado.", event_type)
        return 0

    payload = metadata or {}

    with db_cursor() as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO patient_timeline_events (
                clinic_id,
                tenant_id,
                patient_id,
                event_type,
                journey_stage,
                title,
                description,
                source_type,
                source_id,
                event_time,
                metadata
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                COALESCE(%s, CURRENT_TIMESTAMP),
                %s
            )
            RETURNING id
            """,
            (
                clinic_id,
                tenant_id,
                patient_id,
                event_type,
                journey_stage,
                title,
                description,
                source_type,
                source_id,
                event_time,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        conn.commit()
        return cursor.fetchone()[0]


def list_patient_events(
    clinic_id: int,
    patient_id: int,
    limit: Optional[int] = 20,
    *,
    before_id: Optional[int] = None,
    paginated: bool = False,
):
    """Lista eventos do timeline do paciente.

    Sprint 3 Page-Migration Tier-2 (CURSOR-BASED via `before_id`):
      - `paginated=False` (default) e `before_id=None` -> compat path,
        retorna `list[dict]` cru (Sprint 1 shape).
      - `paginated=True` ou `before_id` setado -> dict
        `{items, has_more, next_cursor: int | None}`.

    Feed temporal (timeline) usa cursor estilo `messages`:
        page 1 -> sem cursor (retorna primeiros `limit`)
        page 2 -> ?before_id=<id_do_ultimo>  (retorna proximos)

    `next_cursor` e o `id` do ultimo item retornado (use direto no
    proximo request). `None` quando `has_more=False`.
    """
    if not _timeline_schema_enabled():
        if paginated or before_id is not None:
            return {"items": [], "has_more": False, "next_cursor": None}
        return []

    effective_limit = limit if limit is not None else 20

    where_clauses = ["clinic_id = %s", "patient_id = %s"]
    params: List[Any] = [clinic_id, patient_id]
    if before_id is not None:
        where_clauses.append("id < %s")
        params.append(int(before_id))

    where_sql = " AND ".join(where_clauses)

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            f"""
            SELECT
                id,
                event_type,
                journey_stage,
                title,
                description,
                source_type,
                source_id,
                event_time,
                metadata,
                created_at
            FROM patient_timeline_events
            WHERE {where_sql}
            ORDER BY event_time DESC, id DESC
            LIMIT %s
            """,
            tuple(params) + (effective_limit + 1,),
        )
        rows = cursor.fetchall()

    for row in rows:
        if isinstance(row.get("metadata"), str):
            row["metadata"] = json.loads(row["metadata"])

    if not paginated and before_id is None:
        # Compat path: caller espera `list[dict]` cru. Aplica corte ao
        # `limit` sem expor o +1.
        return rows[:effective_limit]

    has_more = len(rows) > effective_limit
    items = rows[:effective_limit] if has_more else rows
    next_cursor = int(items[-1]["id"]) if items and has_more else None
    return {"items": items, "has_more": has_more, "next_cursor": next_cursor}
