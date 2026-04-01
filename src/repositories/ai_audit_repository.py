import json
from flask import g
from src.infra.database import db_cursor


# =====================================================
# INSERT AUDIT LOG
# =====================================================

def save_ai_audit_log(
    clinic_id,
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
# SUMMARY
# =====================================================

def get_ai_audit_summary():

    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        raise RuntimeError("clinic_id não encontrado no contexto da request")

    with db_cursor(dictionary=True) as (_, cursor):

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_execucoes,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(estimated_cost_usd), 0) AS total_cost_usd,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS sucessos,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS erros,
                SUM(CASE WHEN status = 'security_blocked' THEN 1 ELSE 0 END) AS bloqueios,
                COALESCE(AVG(total_time_ms), 0) AS tempo_medio_ms
            FROM ai_audit_logs
            WHERE clinic_id = %s
            """,
            (clinic_id,),
        )

        result = cursor.fetchone()

        return result or {
            "total_execucoes": 0,
            "total_tokens": 0,
            "total_cost_usd": 0,
            "sucessos": 0,
            "erros": 0,
            "bloqueios": 0,
            "tempo_medio_ms": 0,
        }


# =====================================================
# RECENT LOGS
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
