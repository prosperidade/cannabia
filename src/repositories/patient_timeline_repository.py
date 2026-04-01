from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

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


def list_patient_events(clinic_id: int, patient_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    if not _timeline_schema_enabled():
        return []

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
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
            WHERE clinic_id = %s
              AND patient_id = %s
            ORDER BY event_time DESC, id DESC
            LIMIT %s
            """,
            (clinic_id, patient_id, limit),
        )
        rows = cursor.fetchall()

    for row in rows:
        if isinstance(row.get("metadata"), str):
            row["metadata"] = json.loads(row["metadata"])

    return rows
