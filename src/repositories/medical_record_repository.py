from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.medical_record")


def _medical_record_schema_enabled() -> bool:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'medical_records'
            ) AS has_records,
            EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'medical_record_entries'
            ) AS has_entries
            """
        )
        row = cursor.fetchone()
        return bool(row["has_records"] and row["has_entries"])


def get_or_create_medical_record(
    clinic_id: int,
    patient_id: int,
    tenant_id: Optional[int] = None,
    primary_doctor_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if not _medical_record_schema_enabled():
        return None

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO medical_records (
                clinic_id,
                tenant_id,
                patient_id,
                primary_doctor_id
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (clinic_id, patient_id) DO UPDATE
                SET tenant_id = COALESCE(medical_records.tenant_id, EXCLUDED.tenant_id),
                    primary_doctor_id = COALESCE(medical_records.primary_doctor_id, EXCLUDED.primary_doctor_id),
                    updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (clinic_id, tenant_id, patient_id, primary_doctor_id),
        )
        conn.commit()
        return cursor.fetchone()


def get_consultation_entry_by_report(clinic_id: int, report_id: int) -> Optional[Dict[str, Any]]:
    if not _medical_record_schema_enabled():
        return None

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT *
            FROM medical_record_entries
            WHERE clinic_id = %s
              AND source_report_id = %s
              AND entry_type = 'consultation_note'
            LIMIT 1
            """,
            (clinic_id, report_id),
        )
        row = cursor.fetchone()

    if row and isinstance(row.get("requested_exams"), str):
        row["requested_exams"] = json.loads(row["requested_exams"])

    return row


def get_medical_record_by_patient(clinic_id: int, patient_id: int) -> Optional[Dict[str, Any]]:
    if not _medical_record_schema_enabled():
        return None

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT *
            FROM medical_records
            WHERE clinic_id = %s
              AND patient_id = %s
            LIMIT 1
            """,
            (clinic_id, patient_id),
        )
        return cursor.fetchone()


def list_patient_record_entries(clinic_id: int, patient_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    if not _medical_record_schema_enabled():
        return []

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                id,
                medical_record_id,
                author_user_id,
                author_name,
                entry_type,
                source_report_id,
                title,
                status,
                medical_observations,
                clinical_assessment,
                conduct,
                requested_exams,
                follow_up_plan,
                metadata,
                created_at,
                updated_at
            FROM medical_record_entries
            WHERE clinic_id = %s
              AND patient_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (clinic_id, patient_id, limit),
        )
        rows = cursor.fetchall()

    for row in rows:
        if isinstance(row.get("requested_exams"), str):
            row["requested_exams"] = json.loads(row["requested_exams"])
        if isinstance(row.get("metadata"), str):
            row["metadata"] = json.loads(row["metadata"])

    return rows


def upsert_consultation_entry(
    clinic_id: int,
    patient_id: int,
    author_user_id: int,
    author_name: str,
    source_report_id: int,
    consultation_status: str,
    medical_observations: str,
    clinical_assessment: str,
    conduct: str,
    requested_exams: List[str],
    follow_up_plan: str,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    if not _medical_record_schema_enabled():
        logger.debug("Schema de prontuário ainda indisponível; gravação ignorada.")
        return {"enabled": False, "created": False, "entry_id": None, "medical_record_id": None}

    record = get_or_create_medical_record(
        clinic_id=clinic_id,
        patient_id=patient_id,
        tenant_id=tenant_id,
        primary_doctor_id=author_user_id,
    )
    if not record:
        return {"enabled": False, "created": False, "entry_id": None, "medical_record_id": None}

    existing = get_consultation_entry_by_report(clinic_id, source_report_id)
    payload = {
        "consultation_status": consultation_status,
        "source": "doctor_review",
    }

    with db_cursor(dictionary=True) as (conn, cursor):
        if existing:
            cursor.execute(
                """
                UPDATE medical_record_entries
                SET tenant_id = COALESCE(tenant_id, %s),
                    medical_record_id = %s,
                    author_user_id = %s,
                    author_name = %s,
                    title = %s,
                    status = %s,
                    medical_observations = %s,
                    clinical_assessment = %s,
                    conduct = %s,
                    requested_exams = %s,
                    follow_up_plan = %s,
                    metadata = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, medical_record_id
                """,
                (
                    tenant_id,
                    record["id"],
                    author_user_id,
                    author_name,
                    "Registro clínico da consulta",
                    consultation_status,
                    medical_observations,
                    clinical_assessment,
                    conduct,
                    json.dumps(requested_exams, ensure_ascii=False),
                    follow_up_plan,
                    json.dumps(payload, ensure_ascii=False),
                    existing["id"],
                ),
            )
            created = False
        else:
            cursor.execute(
                """
                INSERT INTO medical_record_entries (
                    clinic_id,
                    tenant_id,
                    medical_record_id,
                    patient_id,
                    author_user_id,
                    author_name,
                    entry_type,
                    source_report_id,
                    title,
                    status,
                    medical_observations,
                    clinical_assessment,
                    conduct,
                    requested_exams,
                    follow_up_plan,
                    metadata
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, 'consultation_note', %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id, medical_record_id
                """,
                (
                    clinic_id,
                    tenant_id,
                    record["id"],
                    patient_id,
                    author_user_id,
                    author_name,
                    source_report_id,
                    "Registro clínico da consulta",
                    consultation_status,
                    medical_observations,
                    clinical_assessment,
                    conduct,
                    json.dumps(requested_exams, ensure_ascii=False),
                    follow_up_plan,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            created = True

        row = cursor.fetchone()

        cursor.execute(
            """
            UPDATE medical_records
            SET primary_doctor_id = COALESCE(primary_doctor_id, %s),
                last_entry_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (author_user_id, row["medical_record_id"]),
        )
        conn.commit()

    return {
        "enabled": True,
        "created": created,
        "entry_id": row["id"],
        "medical_record_id": row["medical_record_id"],
    }
