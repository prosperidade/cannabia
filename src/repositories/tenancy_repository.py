# src/repositories/tenancy_repository.py

from src.infra.database import db_cursor


def get_user_membership(user_id: int, clinic_id: int):
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT clinic_id, role, is_default
            FROM user_clinics
            WHERE user_id=%s AND clinic_id=%s
            LIMIT 1
            """,
            (user_id, clinic_id),
        )
        return cursor.fetchone()


def resolve_default_clinic_id(user_id: int):
    with db_cursor(dictionary=True) as (_, cursor):

        # 1️⃣ tenta default
        cursor.execute(
            """
            SELECT clinic_id
            FROM user_clinics
            WHERE user_id=%s AND is_default=1
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return row["clinic_id"]

        # 2️⃣ senão pega primeira
        cursor.execute(
            """
            SELECT clinic_id
            FROM user_clinics
            WHERE user_id=%s
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()

        return row["clinic_id"] if row else None