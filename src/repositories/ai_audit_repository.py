# src/repositories/ai_audit_repository.py

import json
from flask import g
from src.infra.database import db_cursor


# =====================================================
# INSERT AUDIT LOG (MULTI-TENANT SEGURO)
# =====================================================
def save_ai_audit_log(
    patient_id,
    request_id,
    endpoint,
    user_id,
    input_payload,
    output_payload,
    status,
    error_message,
    model,
    prompt_version,
    prompt_hash,
    input_tokens,
    output_tokens,
    total_tokens,
    clinical_time_ms,
    treatment_time_ms,
    report_time_ms,
    total_time_ms,
    estimated_cost_usd,
):

    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        raise RuntimeError("clinic_id não encontrado no contexto da request")

    with db_cursor() as (connection, cursor):

        cursor.execute(
            """
            INSERT INTO ai_audit_logs (
                patient_id,
                clinic_id,
                request_id,
                user_id,
                endpoint,
                input_payload,
                output_payload,
                status,
                error_message,
                model,
                prompt_version,
                prompt_hash,
                input_tokens,
                output_tokens,
                total_tokens,
                clinical_time_ms,
                treatment_time_ms,
                report_time_ms,
                total_time_ms,
                estimated_cost_usd
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                patient_id,
                clinic_id,
                request_id,
                user_id,
                endpoint,
                json.dumps(input_payload, ensure_ascii=False),
                json.dumps(output_payload, ensure_ascii=False)
                if output_payload
                else None,
                status,
                error_message,
                model,
                prompt_version,
                prompt_hash,
                input_tokens,
                output_tokens,
                total_tokens,
                clinical_time_ms,
                treatment_time_ms,
                report_time_ms,
                total_time_ms,
                estimated_cost_usd,
            ),
        )

        connection.commit()


# =====================================================
# SUMMARY PARA DASHBOARD (FILTRADO POR CLÍNICA)
# =====================================================
def get_ai_audit_summary():

    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        raise RuntimeError("clinic_id não encontrado no contexto da request")

    with db_cursor(dictionary=True) as (_, cursor):

        cursor.execute(
            """
            SELECT
                COUNT(*) as total_requests,
                SUM(total_tokens) as total_tokens,
                SUM(estimated_cost_usd) as total_cost_usd
            FROM ai_audit_logs
            WHERE status = 'success'
              AND clinic_id = %s
            """,
            (clinic_id,),
        )

        result = cursor.fetchone()

        return result or {
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost_usd": 0,
        }


# =====================================================
# LOGS RECENTES PARA DASHBOARD (FILTRADO POR CLÍNICA)
# =====================================================
def get_recent_ai_logs(limit=10):

    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        raise RuntimeError("clinic_id não encontrado no contexto da request")

    with db_cursor(dictionary=True) as (_, cursor):

        cursor.execute(
            """
            SELECT
                id,
                patient_id,
                status,
                total_tokens,
                estimated_cost_usd,
                created_at
            FROM ai_audit_logs
            WHERE clinic_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (clinic_id, limit),
        )

        return cursor.fetchall()