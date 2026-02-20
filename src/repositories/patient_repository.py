# src/repositories/patient_repository.py

from typing import Optional
from src.infra.database import db_cursor


def get_patient_by_name(name: str) -> Optional[dict]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT id, name FROM patients WHERE name = %s LIMIT 1",
            (name,),
        )
        return cursor.fetchone()


def create_patient(name: str) -> int:
    with db_cursor() as (conn, cursor):
        cursor.execute(
            "INSERT INTO patients (name) VALUES (%s)",
            (name,),
        )
        conn.commit()
        return cursor.lastrowid


def get_or_create_patient_by_name(name: str) -> int:
    patient = get_patient_by_name(name)

    if patient:
        return patient["id"]

    return create_patient(name)
