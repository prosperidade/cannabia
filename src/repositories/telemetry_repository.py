# src/repositories/telemetry_repository.py
"""
Repositório para Telemetria Pós-Consulta.

Tabelas: scheduled_followups, iot_telemetry
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.repo.telemetry")


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULED FOLLOW-UPS (CRM D+3, D+7, D+15)
# ═══════════════════════════════════════════════════════════════════════════════

def create_followup(
    clinic_id: int,
    patient_id: int,
    phone: str,
    report_id: Optional[int],
    followup_type: str,
    scheduled_at: datetime,
    message_text: str,
) -> int:
    """Cria um follow-up agendado. Retorna o ID."""
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO scheduled_followups
                (clinic_id, patient_id, phone, report_id,
                 followup_type, scheduled_at, message_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (clinic_id, patient_id, phone, report_id,
             followup_type, scheduled_at, message_text),
        )
        row = cur.fetchone()
        conn.commit()
        return row["id"]


def create_followups_batch(rows: List[Dict[str, Any]]) -> List[int]:
    """Insere múltiplos follow-ups em uma transação. Retorna IDs."""
    if not rows:
        return []

    ids: List[int] = []
    with db_cursor(dictionary=True) as (conn, cur):
        for r in rows:
            cur.execute(
                """
                INSERT INTO scheduled_followups
                    (clinic_id, patient_id, phone, report_id,
                     followup_type, scheduled_at, message_text)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (r["clinic_id"], r["patient_id"], r["phone"], r.get("report_id"),
                 r["followup_type"], r["scheduled_at"], r["message_text"]),
            )
            ids.append(cur.fetchone()["id"])
        conn.commit()
    return ids


def list_pending_followups(
    before: datetime,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Retorna follow-ups pendentes cuja hora agendada já passou."""
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, clinic_id, patient_id, phone, report_id,
                   followup_type, scheduled_at, message_text, attempts
            FROM scheduled_followups
            WHERE status = 'pending'
              AND scheduled_at <= %s
            ORDER BY scheduled_at ASC
            LIMIT %s
            """,
            (before, limit),
        )
        return cur.fetchall()


def mark_followup_sent(followup_id: int) -> None:
    """Marca follow-up como enviado com sucesso."""
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            UPDATE scheduled_followups
            SET status = 'sent', sent_at = NOW(), attempts = attempts + 1,
                updated_at = NOW()
            WHERE id = %s
            """,
            (followup_id,),
        )
        conn.commit()


def mark_followup_failed(followup_id: int, error: str) -> None:
    """Marca follow-up como falha (incrementa tentativas)."""
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            UPDATE scheduled_followups
            SET status = CASE WHEN attempts >= 2 THEN 'failed' ELSE 'pending' END,
                attempts = attempts + 1,
                last_error = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (error, followup_id),
        )
        conn.commit()


def record_patient_response(
    clinic_id: int,
    phone: str,
    response_text: str,
) -> Optional[Dict[str, Any]]:
    """
    Registra resposta do paciente no follow-up 'sent' mais recente desse telefone.
    Retorna {id, patient_id, followup_type} do follow-up atualizado, ou None
    quando não há follow-up 'sent' aguardando resposta (CLI-1 / 29.2 R1).
    """
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            UPDATE scheduled_followups
            SET status = 'responded',
                response_text = %s,
                responded_at = NOW(),
                updated_at = NOW()
            WHERE id = (
                SELECT id FROM scheduled_followups
                WHERE clinic_id = %s AND phone = %s AND status = 'sent'
                ORDER BY sent_at DESC
                LIMIT 1
            )
            RETURNING id, patient_id, followup_type
            """,
            (response_text, clinic_id, phone),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None


def list_followups_for_patient(
    clinic_id: int,
    patient_id: int,
) -> List[Dict[str, Any]]:
    """Lista todos os follow-ups de um paciente (histórico CRM)."""
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, followup_type, scheduled_at, sent_at, status,
                   response_text, responded_at, message_text
            FROM scheduled_followups
            WHERE clinic_id = %s AND patient_id = %s
            ORDER BY scheduled_at ASC
            """,
            (clinic_id, patient_id),
        )
        return cur.fetchall()


# ═══════════════════════════════════════════════════════════════════════════════
# IOT TELEMETRY — SÉRIE TEMPORAL
# ═══════════════════════════════════════════════════════════════════════════════

def insert_iot_reading(
    clinic_id: int,
    patient_id: int,
    source: str,
    metric_type: str,
    value: float,
    unit: str,
    recorded_at: datetime,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """Insere uma leitura IoT. Retorna o ID."""
    import json
    meta_json = json.dumps(metadata or {})

    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO iot_telemetry
                (clinic_id, patient_id, source, metric_type,
                 value, unit, recorded_at, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (clinic_id, patient_id, source, metric_type,
             value, unit, recorded_at, meta_json),
        )
        row = cur.fetchone()
        conn.commit()
        return row["id"]


def insert_iot_readings_batch(readings: List[Dict[str, Any]]) -> List[int]:
    """Insere múltiplas leituras em uma transação. Retorna IDs."""
    import json

    if not readings:
        return []

    ids: List[int] = []
    with db_cursor(dictionary=True) as (conn, cur):
        for r in readings:
            cur.execute(
                """
                INSERT INTO iot_telemetry
                    (clinic_id, patient_id, source, metric_type,
                     value, unit, recorded_at, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (r["clinic_id"], r["patient_id"], r["source"], r["metric_type"],
                 r["value"], r["unit"], r["recorded_at"],
                 json.dumps(r.get("metadata", {}))),
            )
            ids.append(cur.fetchone()["id"])
        conn.commit()
    return ids


def query_iot_timeseries(
    clinic_id: int,
    patient_id: int,
    metric_type: str,
    start: datetime,
    end: datetime,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Consulta série temporal de uma métrica para um paciente."""
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, source, metric_type, value, unit,
                   recorded_at, received_at, metadata
            FROM iot_telemetry
            WHERE clinic_id = %s
              AND patient_id = %s
              AND metric_type = %s
              AND recorded_at BETWEEN %s AND %s
            ORDER BY recorded_at ASC
            LIMIT %s
            """,
            (clinic_id, patient_id, metric_type, start, end, limit),
        )
        return cur.fetchall()


def get_latest_readings(
    clinic_id: int,
    patient_id: int,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Últimas N leituras IoT de um paciente (qualquer métrica)."""
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            SELECT id, source, metric_type, value, unit,
                   recorded_at, received_at
            FROM iot_telemetry
            WHERE clinic_id = %s AND patient_id = %s
            ORDER BY recorded_at DESC
            LIMIT %s
            """,
            (clinic_id, patient_id, limit),
        )
        return cur.fetchall()
