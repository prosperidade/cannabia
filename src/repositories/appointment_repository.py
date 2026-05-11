from typing import Dict, Optional
from flask import g
from src.infra.database import db_cursor


# =====================================================
# READ APPOINTMENT BY ID (MULTI-TENANT SEGURO)
# =====================================================

def get_appointment(appointment_id: int, clinic_id: Optional[int] = None) -> Optional[Dict]:
    cid = clinic_id or getattr(g, "clinic_id", None)
    if cid is None:
        raise RuntimeError("clinic_id nao encontrado no contexto da request")

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT a.id, a.clinic_id, a.patient_id, p.name AS patient_name,
                   a.appointment_date, a.status, a.triage_link_id, a.notes,
                   a.created_at
            FROM appointments a
            JOIN patients p ON p.id = a.patient_id AND p.clinic_id = a.clinic_id
            WHERE a.id = %s AND a.clinic_id = %s
            """,
            (appointment_id, cid),
        )
        return cursor.fetchone()


def update_appointment_triage_link(appointment_id: int, triage_link_id: int) -> None:
    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        raise RuntimeError("clinic_id nao encontrado no contexto da request")

    with db_cursor() as (conn, cursor):
        cursor.execute(
            """
            UPDATE appointments
            SET triage_link_id = %s
            WHERE id = %s AND clinic_id = %s
            """,
            (triage_link_id, appointment_id, clinic_id),
        )
        conn.commit()


# =====================================================
# CREATE APPOINTMENT (MULTI-TENANT SEGURO)
# =====================================================

def create_appointment(patient_id: int, appointment_date, status: str = "Agendada") -> int:

    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        raise RuntimeError("clinic_id não encontrado no contexto da request")

    with db_cursor() as (connection, cursor):
        cursor.execute(
            """
            INSERT INTO appointments (
                clinic_id,
                patient_id,
                appointment_date,
                status
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (clinic_id, patient_id, appointment_date, status),
        )
        connection.commit()
        return cursor.fetchone()[0]


# =====================================================
# LIST APPOINTMENTS (MULTI-TENANT SEGURO)
# =====================================================

def list_appointments(
    *,
    limit: Optional[int] = None,
    offset: int = 0,
    include_total: bool = False,
):
    """Lista agendamentos da clinica corrente.

    Modo legacy (sem args): retorna `List[Dict]` (compat).
    Modo paginado: retorna `dict` com keys `items`, `total`, `has_more`.
    Sprint 2 Track Page.
    """
    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        raise RuntimeError("clinic_id não encontrado no contexto da request")

    if limit is None:
        # Compat path — sem paginacao.
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT
                    a.id,
                    a.patient_id,
                    p.name AS patient_name,
                    a.appointment_date,
                    a.status,
                    a.created_at
                FROM appointments a
                JOIN patients p ON p.id = a.patient_id
                WHERE a.clinic_id = %s
                  AND p.clinic_id = %s
                ORDER BY a.appointment_date DESC
                """,
                (clinic_id, clinic_id),
            )
            return cursor.fetchall()

    # Modo paginado.
    total = None
    with db_cursor(dictionary=True) as (_, cursor):
        if include_total:
            cursor.execute(
                """
                SELECT COUNT(*) AS n FROM appointments a
                JOIN patients p ON p.id = a.patient_id
                WHERE a.clinic_id = %s AND p.clinic_id = %s
                """,
                (clinic_id, clinic_id),
            )
            total = int(cursor.fetchone()["n"])

        # LIMIT_PLUS_ONE_TRICK: pede limit+1 pra detectar has_more sem COUNT.
        fetch_n = limit if include_total else limit + 1
        cursor.execute(
            """
            SELECT
                a.id,
                a.patient_id,
                p.name AS patient_name,
                a.appointment_date,
                a.status,
                a.created_at
            FROM appointments a
            JOIN patients p ON p.id = a.patient_id
            WHERE a.clinic_id = %s
              AND p.clinic_id = %s
            ORDER BY a.appointment_date DESC
            LIMIT %s OFFSET %s
            """,
            (clinic_id, clinic_id, fetch_n, offset),
        )
        rows = cursor.fetchall()

    if include_total:
        items = list(rows)
        has_more = (offset + len(items)) < (total or 0)
    else:
        from src.web.pagination import apply_limit_plus_one
        items, has_more = apply_limit_plus_one(rows, limit)

    return {"items": items, "total": total, "has_more": has_more}
