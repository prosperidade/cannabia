# src/repositories/anamnesis_repository.py
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.anamnesis_repo")


def _anamnesis_has_patient_id() -> bool:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'anamnesis_reports'
                  AND column_name = 'patient_id'
            ) AS has_patient_id
            """
        )
        row = cursor.fetchone()
        return bool(row["has_patient_id"])


def save_report(
    clinic_id: int,
    patient_id: int,
    patient_name: str,
    phone: str,
    anamnesis_data: dict,
    report: dict,
) -> int:
    """Persiste a anamnese completa + relatório gerado pelo pipeline."""
    has_patient_id = _anamnesis_has_patient_id()

    with db_cursor() as (conn, cursor):
        if has_patient_id:
            cursor.execute(
                """
                INSERT INTO anamnesis_reports
                  (clinic_id, patient_id, patient_name, phone, anamnesis_data,
                   clinical_analysis, treatment_plan, scientific_report,
                   rag_chunks_used, report_model)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    clinic_id,
                    patient_id,
                    patient_name,
                    phone,
                    json.dumps(anamnesis_data,                  ensure_ascii=False),
                    json.dumps(report.get("clinical_analysis",  {}), ensure_ascii=False),
                    json.dumps(report.get("treatment_plan",     {}), ensure_ascii=False),
                    json.dumps(report.get("scientific_report",  {}), ensure_ascii=False),
                    report.get("rag_chunks_used", 0),
                    report.get("report_model", "gpt-4o-mini"),
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO anamnesis_reports
                  (clinic_id, patient_name, phone, anamnesis_data,
                   clinical_analysis, treatment_plan, scientific_report,
                   rag_chunks_used, report_model)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    clinic_id,
                    patient_name,
                    phone,
                    json.dumps(anamnesis_data,                  ensure_ascii=False),
                    json.dumps(report.get("clinical_analysis",  {}), ensure_ascii=False),
                    json.dumps(report.get("treatment_plan",     {}), ensure_ascii=False),
                    json.dumps(report.get("scientific_report",  {}), ensure_ascii=False),
                    report.get("rag_chunks_used", 0),
                    report.get("report_model", "gpt-4o-mini"),
                ),
            )
        conn.commit()
        rid = cursor.fetchone()[0]
        logger.info("Relatório #%d salvo para '%s' (clinic=%d).", rid, patient_name, clinic_id)
        return rid


def list_reports(
    clinic_id: int,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lista relatórios da clínica, com filtro opcional de status."""
    with db_cursor(dictionary=True) as (_, cursor):
        sql  = (
            "SELECT id, patient_name, phone, status, rag_chunks_used, "
            "report_model, created_at "
            "FROM anamnesis_reports WHERE clinic_id = %s"
        )
        args: list = [clinic_id]
        if status:
            sql += " AND status = %s"
            args.append(status)
        sql += " ORDER BY created_at DESC"
        cursor.execute(sql, args)
        return cursor.fetchall()


def get_report(clinic_id: int, report_id: int) -> Optional[Dict[str, Any]]:
    """Retorna um relatório completo com campos JSON desserializados."""
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT * FROM anamnesis_reports WHERE clinic_id = %s AND id = %s",
            (clinic_id, report_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        for field in ("anamnesis_data", "clinical_analysis", "treatment_plan", "scientific_report"):
            if isinstance(row.get(field), str):
                row[field] = json.loads(row[field])
        return row


def mark_reviewed(clinic_id: int, report_id: int) -> None:
    """Marca um relatório como revisado pelo médico."""
    with db_cursor() as (conn, cursor):
        cursor.execute(
            "UPDATE anamnesis_reports SET status = 'revisado', updated_at = CURRENT_TIMESTAMP "
            "WHERE clinic_id = %s AND id = %s",
            (clinic_id, report_id),
        )
        conn.commit()
