from typing import List, Dict
from flask import g
from src.infra.database import db_cursor


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

def list_appointments() -> List[Dict]:

    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        raise RuntimeError("clinic_id não encontrado no contexto da request")

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
