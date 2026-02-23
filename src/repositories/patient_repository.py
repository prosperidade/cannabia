from typing import Optional
from src.infra.database import db_cursor


# =====================================================
# READ
# =====================================================

def get_patient_by_name(clinic_id: int, name: str) -> Optional[dict]:
    if clinic_id is None:
        raise RuntimeError("clinic_id é obrigatório para consulta de paciente")

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, name
            FROM patients
            WHERE clinic_id = %s
              AND name = %s
            LIMIT 1
            """,
            (clinic_id, name),
        )
        return cursor.fetchone()


# =====================================================
# CREATE
# =====================================================

def create_patient(clinic_id: int, name: str) -> int:
    if clinic_id is None:
        raise RuntimeError("clinic_id é obrigatório para criar paciente")

    with db_cursor() as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO patients (clinic_id, name)
            VALUES (%s, %s)
            RETURNING id
            """,
            (clinic_id, name),
        )
        conn.commit()
        return cursor.fetchone()[0]


# =====================================================
# GET OR CREATE
# =====================================================

def get_or_create_patient_by_name(clinic_id: int, name: str) -> int:
    patient = get_patient_by_name(clinic_id, name)

    if patient:
        return patient["id"]

    return create_patient(clinic_id, name)