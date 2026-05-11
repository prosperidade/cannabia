import json
from flask import g
from src.ai.audit_redaction import sanitize_clinical_payload
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
    prescription_time_ms=None,
    prescription_input_tokens=None,
    prescription_output_tokens=None,
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
                estimated_cost_usd,
                prescription_time_ms,
                prescription_input_tokens,
                prescription_output_tokens
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                patient_id,
                clinic_id,
                request_id,
                user_id,
                endpoint,
                # A.3: sanitiza PII estruturalmente antes do json.dumps.
                # Single point of intervention — toda call site (5+ em
                # service.py, prescription_service, futuras) herda protecao.
                # Sanitizer eh fail-safe (nunca raise), audit log nunca
                # desaparece por causa de erro de redaction.
                json.dumps(sanitize_clinical_payload(input_payload), ensure_ascii=False),
                json.dumps(sanitize_clinical_payload(output_payload), ensure_ascii=False)
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
                prescription_time_ms,
                prescription_input_tokens,
                prescription_output_tokens,
            ),
        )

        connection.commit()


# =====================================================
# SUMMARY
# =====================================================

def get_ai_audit_summary():
    return get_ai_audit_summary_filtered()


def _build_audit_filters(clinic_id, status=None, days=None):
    clauses = ["clinic_id = %s"]
    params = [clinic_id]

    if status:
        clauses.append("status = %s")
        params.append(status)

    if days is not None:
        clauses.append("created_at >= CURRENT_TIMESTAMP - (%s * INTERVAL '1 day')")
        params.append(days)

    return " AND ".join(clauses), params


def get_ai_audit_summary_filtered(status=None, days=None):

    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        raise RuntimeError("clinic_id não encontrado no contexto da request")

    where_clause, params = _build_audit_filters(clinic_id, status=status, days=days)

    with db_cursor(dictionary=True) as (_, cursor):

        cursor.execute(
            f"""
            SELECT
                COUNT(*) AS total_execucoes,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(estimated_cost_usd), 0) AS total_cost_usd,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS sucessos,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS erros,
                SUM(CASE WHEN status = 'security_blocked' THEN 1 ELSE 0 END) AS bloqueios,
                COALESCE(AVG(total_time_ms), 0) AS tempo_medio_ms
            FROM ai_audit_logs
            WHERE {where_clause}
            """,
            params,
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
    return get_recent_ai_logs_filtered(limit=limit)


def get_recent_ai_logs_filtered(
    limit=10,
    status=None,
    days=None,
    *,
    offset: int = 0,
    include_total: bool = False,
    paginated: bool = False,
):
    """Retorna logs de auditoria de IA da clinica corrente.

    Compat (default): retorna `list[dict]` (Sprint 1).
    Sprint 2 Track Page: passe `paginated=True` pra receber dict
    {items, total, has_more}.
    """
    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        raise RuntimeError("clinic_id não encontrado no contexto da request")

    where_clause, base_params = _build_audit_filters(clinic_id, status=status, days=days)

    if not paginated:
        # Compat path Sprint 1.
        params = base_params + [limit]
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                f"""
                SELECT
                    id,
                    patient_id,
                    status,
                    endpoint,
                    model,
                    total_tokens,
                    estimated_cost_usd,
                    error_message,
                    created_at
                FROM ai_audit_logs
                WHERE {where_clause}
                ORDER BY id DESC
                LIMIT %s
                """,
                params,
            )
            return cursor.fetchall()

    # Modo paginado.
    total = None
    with db_cursor(dictionary=True) as (_, cursor):
        if include_total:
            cursor.execute(
                f"SELECT COUNT(*) AS n FROM ai_audit_logs WHERE {where_clause}",
                base_params,
            )
            total = int(cursor.fetchone()["n"])

        fetch_n = limit if include_total else limit + 1
        params = base_params + [fetch_n, offset]
        cursor.execute(
            f"""
            SELECT
                id,
                patient_id,
                status,
                endpoint,
                model,
                total_tokens,
                estimated_cost_usd,
                error_message,
                created_at
            FROM ai_audit_logs
            WHERE {where_clause}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
            """,
            params,
        )
        rows = cursor.fetchall()

    if include_total:
        items = list(rows)
        has_more = (offset + len(items)) < (total or 0)
    else:
        from src.web.pagination import apply_limit_plus_one
        items, has_more = apply_limit_plus_one(rows, limit)

    return {"items": items, "total": total, "has_more": has_more}
