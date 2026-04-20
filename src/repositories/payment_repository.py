# src/repositories/payment_repository.py
"""
Acesso a dados de cobrancas (payment_requests) e transacoes (payment_transactions).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from src.infra.database import db_cursor


def create_payment_request(
    *,
    tenant_id: int,
    clinic_id: int,
    amount_cents: int,
    description: Optional[str] = None,
    patient_id: Optional[int] = None,
    prescription_id: Optional[int] = None,
    subscription_id: Optional[int] = None,
    method: str = "pix",
    provider: str = "manual",
    external_id: str,
    pix_payload: Optional[str] = None,
    pix_qr_image_url: Optional[str] = None,
    pix_key: Optional[str] = None,
    expires_at: Optional[Any] = None,
    created_by: Optional[int] = None,
    provider_metadata: Optional[dict] = None,
) -> dict[str, Any]:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO payment_requests (
                tenant_id, clinic_id, patient_id, prescription_id, subscription_id,
                external_id, description, amount_cents, method, provider,
                pix_payload, pix_qr_image_url, pix_key, expires_at,
                created_by, provider_metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING *
            """,
            (
                tenant_id,
                clinic_id,
                patient_id,
                prescription_id,
                subscription_id,
                external_id,
                description,
                int(amount_cents),
                method,
                provider,
                pix_payload,
                pix_qr_image_url,
                pix_key,
                expires_at,
                created_by,
                json.dumps(provider_metadata or {}),
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def get_payment_request(request_id: int) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT * FROM payment_requests WHERE id = %s",
            (request_id,),
        )
        return cursor.fetchone()


def get_payment_request_by_external_id(external_id: str) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT * FROM payment_requests WHERE external_id = %s",
            (external_id,),
        )
        return cursor.fetchone()


def list_payment_requests(
    *,
    tenant_id: int,
    status: Optional[str] = None,
    patient_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    conditions = ["tenant_id = %s"]
    params: list[Any] = [tenant_id]

    if status:
        conditions.append("status = %s")
        params.append(status)
    if patient_id is not None:
        conditions.append("patient_id = %s")
        params.append(patient_id)

    params.extend([limit, offset])

    where = " AND ".join(conditions)
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            f"""
            SELECT *
            FROM payment_requests
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            params,
        )
        return cursor.fetchall()


def mark_payment_paid(
    request_id: int,
    *,
    paid_amount_cents: int,
    provider_ref: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            UPDATE payment_requests
            SET status = 'paid',
                paid_at = CURRENT_TIMESTAMP,
                paid_amount_cents = %s,
                provider_ref = COALESCE(%s, provider_ref),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status NOT IN ('paid', 'refunded')
            RETURNING *
            """,
            (int(paid_amount_cents), provider_ref, request_id),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def cancel_payment_request(request_id: int) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            UPDATE payment_requests
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = 'pending'
            RETURNING *
            """,
            (request_id,),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def record_transaction(
    *,
    payment_request_id: int,
    tenant_id: int,
    provider: str,
    provider_event_id: Optional[str],
    event_type: str,
    status: str,
    amount_cents: int,
    currency: str = "BRL",
    payer_name: Optional[str] = None,
    payer_document: Optional[str] = None,
    payer_account: Optional[str] = None,
    raw_payload: Optional[dict] = None,
) -> dict[str, Any]:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO payment_transactions (
                payment_request_id, tenant_id, provider, provider_event_id,
                event_type, status, amount_cents, currency,
                payer_name, payer_document, payer_account, raw_payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (provider, provider_event_id) DO NOTHING
            RETURNING *
            """,
            (
                payment_request_id,
                tenant_id,
                provider,
                provider_event_id,
                event_type,
                status,
                int(amount_cents),
                currency,
                payer_name,
                payer_document,
                payer_account,
                json.dumps(raw_payload or {}),
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def list_transactions(payment_request_id: int) -> list[dict[str, Any]]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT *
            FROM payment_transactions
            WHERE payment_request_id = %s
            ORDER BY received_at DESC
            """,
            (payment_request_id,),
        )
        return cursor.fetchall()


def log_webhook(
    *,
    provider: str,
    signature_ok: bool,
    status_code: int,
    body: Any,
    headers: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> None:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO payment_webhook_log (
                provider, signature_ok, status_code, body, headers, error_message
            )
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s)
            """,
            (
                provider,
                bool(signature_ok),
                int(status_code),
                json.dumps(body if body is not None else {}),
                json.dumps(headers or {}),
                error_message,
            ),
        )
        conn.commit()


def totals_by_status(tenant_id: int) -> dict[str, Any]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT status,
                   COUNT(*)                                AS count,
                   COALESCE(SUM(amount_cents), 0)          AS total_cents,
                   COALESCE(SUM(paid_amount_cents), 0)     AS paid_cents
            FROM payment_requests
            WHERE tenant_id = %s
            GROUP BY status
            """,
            (tenant_id,),
        )
        rows = cursor.fetchall()

    totals = {
        "pending": {"count": 0, "total_cents": 0},
        "paid": {"count": 0, "total_cents": 0, "paid_cents": 0},
        "expired": {"count": 0, "total_cents": 0},
        "cancelled": {"count": 0, "total_cents": 0},
        "refunded": {"count": 0, "total_cents": 0},
    }
    for row in rows:
        key = row["status"]
        totals[key] = {
            "count": int(row["count"]),
            "total_cents": int(row["total_cents"] or 0),
        }
        if key == "paid":
            totals[key]["paid_cents"] = int(row.get("paid_cents") or 0)
    return totals
