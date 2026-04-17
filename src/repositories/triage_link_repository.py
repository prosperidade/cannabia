"""Repositorio para persistencia de links de triagem."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.infra.database import db_cursor


def create_triage_link(
    clinic_id: int,
    token_hash: str,
    expires_at: datetime,
    *,
    appointment_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    patient_name: Optional[str] = None,
    patient_phone: Optional[str] = None,
    issued_by: Optional[int] = None,
) -> dict:
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO triage_links
                (clinic_id, appointment_id, patient_id, patient_name,
                 patient_phone, token_hash, issued_by, expires_at, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
            RETURNING id, clinic_id, appointment_id, patient_id, patient_name,
                      patient_phone, issued_at, expires_at, status
            """,
            (
                clinic_id,
                appointment_id,
                patient_id,
                patient_name,
                patient_phone,
                token_hash,
                issued_by,
                expires_at,
            ),
        )
        conn.commit()
        return dict(cur.fetchone())


def get_triage_link_by_hash(token_hash: str) -> Optional[dict]:
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(
            """
            SELECT id, clinic_id, appointment_id, patient_id, patient_name,
                   patient_phone, token_hash, issued_by, issued_at, expires_at,
                   used_at, report_id, status
            FROM triage_links
            WHERE token_hash = %s
            LIMIT 1
            """,
            (token_hash,),
        )
        return cur.fetchone()


def mark_link_used(
    link_id: int,
    *,
    report_id: Optional[int] = None,
    used_by_ip: Optional[str] = None,
) -> None:
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            UPDATE triage_links
            SET status     = 'used',
                used_at    = NOW(),
                used_by_ip = %s,
                report_id  = %s
            WHERE id = %s
            """,
            (used_by_ip, report_id, link_id),
        )
        conn.commit()


def revoke_link(link_id: int) -> None:
    with db_cursor() as (conn, cur):
        cur.execute(
            "UPDATE triage_links SET status = 'revoked' WHERE id = %s",
            (link_id,),
        )
        conn.commit()


def list_links_by_appointment(appointment_id: int) -> list[dict]:
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(
            """
            SELECT id, status, issued_at, expires_at, used_at
            FROM triage_links
            WHERE appointment_id = %s
            ORDER BY issued_at DESC
            """,
            (appointment_id,),
        )
        return [dict(row) for row in cur.fetchall()]
