from src.infra.database import db_cursor


def get_tenant_by_id(tenant_id: int):
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                t.id,
                t.legal_name,
                t.display_name,
                t.slug,
                t.status,
                t.legacy_clinic_id,
                tt.slug AS tenant_type,
                tb.brand_name,
                tb.subdomain
            FROM tenants t
            JOIN tenant_types tt
              ON tt.id = t.tenant_type_id
            LEFT JOIN tenant_branding tb
              ON tb.tenant_id = t.id
            WHERE t.id = %s
            LIMIT 1
            """,
            (tenant_id,),
        )
        return cursor.fetchone()


def get_tenant_by_clinic_id(clinic_id: int):
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                t.id,
                t.legal_name,
                t.display_name,
                t.slug,
                t.status,
                t.legacy_clinic_id,
                tt.slug AS tenant_type,
                tb.brand_name,
                tb.subdomain
            FROM clinics c
            JOIN tenants t
              ON t.id = c.tenant_id
            JOIN tenant_types tt
              ON tt.id = t.tenant_type_id
            LEFT JOIN tenant_branding tb
              ON tb.tenant_id = t.id
            WHERE c.id = %s
            LIMIT 1
            """,
            (clinic_id,),
        )
        return cursor.fetchone()


def list_tenants(limit: int = 100):
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                t.id,
                t.display_name,
                t.slug,
                t.status,
                t.legacy_clinic_id,
                tt.slug AS tenant_type
            FROM tenants t
            JOIN tenant_types tt
              ON tt.id = t.tenant_type_id
            ORDER BY t.id ASC
            LIMIT %s
            """,
            (limit,),
        )
        return cursor.fetchall()
