# src/repositories/tenancy_repository.py

from src.infra.database import db_cursor


def _tenant_schema_enabled():
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'clinics'
                  AND column_name = 'tenant_id'
            ) AS clinics_has_tenant_id,
            EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'tenants'
            ) AS tenants_table_exists
            """
        )
        row = cursor.fetchone() or {}
        return bool(
            row.get("clinics_has_tenant_id")
            and row.get("tenants_table_exists")
        )


def get_user_membership(user_id: int, clinic_id: int):
    if _tenant_schema_enabled():
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT
                    uc.clinic_id,
                    uc.role,
                    uc.role AS clinic_role,
                    uc.role AS tenant_role,
                    uc.is_default,
                    c.tenant_id,
                    tt.slug AS tenant_type
                FROM user_clinics uc
                JOIN clinics c
                  ON c.id = uc.clinic_id
                LEFT JOIN tenants t
                  ON t.id = c.tenant_id
                LEFT JOIN tenant_types tt
                  ON tt.id = t.tenant_type_id
                WHERE uc.user_id = %s
                  AND uc.clinic_id = %s
                LIMIT 1
                """,
                (user_id, clinic_id),
            )
            return cursor.fetchone()

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
            WHERE user_id=%s AND is_default = TRUE
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


def get_clinic_public_label(clinic_id: int) -> str:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT name
            FROM clinics
            WHERE id = %s
            LIMIT 1
            """,
            (clinic_id,),
        )
        row = cursor.fetchone()

    name = (row or {}).get("name") if isinstance(row, dict) else None
    if name:
        return str(name)
    return f"Clinica #{clinic_id}"
