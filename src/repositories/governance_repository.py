"""Repository do dominio governance (F1.3 do docs/BACKLOG_SCC.md).

Operacoes CRUD sobre as 4 tabelas criadas pela migration 025:

- ``institutional_documents``  (doc 25 §4.4)
- ``technical_responsibles``   (doc 25 §4.3)
- ``associations``             (doc 25 §4.2)
- ``technical_operational_capacity`` (doc 25 §4.5)

Sem regras de negocio — validacao de elegibilidade fica em
``governance_service`` (F1.4). Aqui so existe acesso a dados.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Iterable, Optional

from src.infra.database import db_cursor


# =====================================================================
# institutional_documents  (doc 25 §4.4)
# =====================================================================

def create_institutional_document(
    *,
    tenant_id: int,
    document_type: str,
    title: str,
    version: str,
    file_uri: str,
    file_hash: str,
    valid_from: date,
    valid_until: Optional[date] = None,
    uploaded_by: Optional[int] = None,
) -> dict[str, Any]:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO institutional_documents (
                tenant_id, document_type, title, version,
                file_uri, file_hash, valid_from, valid_until, uploaded_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                tenant_id,
                document_type,
                title,
                version,
                file_uri,
                file_hash,
                valid_from,
                valid_until,
                uploaded_by,
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def get_institutional_document(doc_id: int) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT * FROM institutional_documents WHERE id = %s",
            (doc_id,),
        )
        return cursor.fetchone()


def list_institutional_documents(
    *,
    tenant_id: int,
    document_type: Optional[str] = None,
    active_only: bool = True,
    limit: Optional[int] = None,
    offset: int = 0,
    include_total: bool = False,
):
    """Lista documentos institucionais do tenant.

    Sprint 3 Page-Migration Tier-2:
      - `limit=None` -> compat path (retorna `list[dict]`, sem envelope).
        Mantido para callers internos (governance_service, dossier).
      - `limit=int`  -> retorna dict `{items, total, has_more}`.
    """
    conditions = ["tenant_id = %s"]
    params: list[Any] = [tenant_id]

    if document_type is not None:
        conditions.append("document_type = %s")
        params.append(document_type)
    if active_only:
        conditions.append("is_active = TRUE")

    where = " AND ".join(conditions)
    base_sql = (
        f"SELECT * FROM institutional_documents "
        f"WHERE {where} "
        f"ORDER BY valid_from DESC, id DESC"
    )

    with db_cursor(dictionary=True) as (_, cursor):
        if limit is None:
            cursor.execute(base_sql, tuple(params))
            return list(cursor.fetchall())

        # Modo paginado.
        total = None
        if include_total:
            count_sql = (
                f"SELECT COUNT(*) AS n FROM institutional_documents WHERE {where}"
            )
            cursor.execute(count_sql, tuple(params))
            total = int(cursor.fetchone()["n"])

        fetch_n = limit if include_total else limit + 1
        paged_sql = base_sql + " LIMIT %s OFFSET %s"
        cursor.execute(paged_sql, tuple(params) + (fetch_n, offset))
        rows = cursor.fetchall()

    if include_total:
        items = list(rows)
        has_more = (offset + len(items)) < (total or 0)
    else:
        from src.web.pagination import apply_limit_plus_one
        items, has_more = apply_limit_plus_one(rows, limit)

    return {"items": items, "total": total, "has_more": has_more}


def deactivate_institutional_document(doc_id: int) -> None:
    with db_cursor() as (conn, cursor):
        cursor.execute(
            "UPDATE institutional_documents SET is_active = FALSE WHERE id = %s",
            (doc_id,),
        )
        conn.commit()


# =====================================================================
# technical_responsibles  (doc 25 §4.3)
# =====================================================================

_TR_UPDATABLE_COLUMNS = {
    "full_name",
    "professional_council",
    "council_number",
    "council_state",
    "habilitation_valid_until",
    "document_ids",
    "is_active",
    "user_id",
}


def create_technical_responsible(
    *,
    tenant_id: int,
    full_name: str,
    professional_council: str,
    council_number: str,
    council_state: str,
    user_id: Optional[int] = None,
    habilitation_valid_until: Optional[date] = None,
    document_ids: Optional[Iterable[int]] = None,
) -> dict[str, Any]:
    """Cria um RT. Viola ``uq_tr_council`` se o trio conselho/numero/estado
    ja existir (repassa ``psycopg2.IntegrityError`` para a camada superior)."""
    doc_ids_list = list(document_ids) if document_ids else []
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO technical_responsibles (
                tenant_id, user_id, full_name,
                professional_council, council_number, council_state,
                habilitation_valid_until, document_ids
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                tenant_id,
                user_id,
                full_name,
                professional_council,
                council_number,
                council_state,
                habilitation_valid_until,
                doc_ids_list,
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def get_technical_responsible(rt_id: int) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT * FROM technical_responsibles WHERE id = %s",
            (rt_id,),
        )
        return cursor.fetchone()


def list_technical_responsibles(
    *,
    tenant_id: int,
    active_only: bool = True,
    limit: Optional[int] = None,
    offset: int = 0,
    include_total: bool = False,
):
    """Lista RTs do tenant.

    Sprint 3 Page-Migration Tier-2:
      - `limit=None` -> compat path (`list[dict]`).
      - `limit=int`  -> dict `{items, total, has_more}`.
    """
    conditions = ["tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if active_only:
        conditions.append("is_active = TRUE")

    where = " AND ".join(conditions)
    base_sql = (
        f"SELECT * FROM technical_responsibles WHERE {where} ORDER BY id ASC"
    )

    with db_cursor(dictionary=True) as (_, cursor):
        if limit is None:
            cursor.execute(base_sql, tuple(params))
            return list(cursor.fetchall())

        total = None
        if include_total:
            count_sql = (
                f"SELECT COUNT(*) AS n FROM technical_responsibles WHERE {where}"
            )
            cursor.execute(count_sql, tuple(params))
            total = int(cursor.fetchone()["n"])

        fetch_n = limit if include_total else limit + 1
        cursor.execute(
            base_sql + " LIMIT %s OFFSET %s",
            tuple(params) + (fetch_n, offset),
        )
        rows = cursor.fetchall()

    if include_total:
        items = list(rows)
        has_more = (offset + len(items)) < (total or 0)
    else:
        from src.web.pagination import apply_limit_plus_one
        items, has_more = apply_limit_plus_one(rows, limit)

    return {"items": items, "total": total, "has_more": has_more}


def update_technical_responsible(rt_id: int, **fields: Any) -> Optional[dict[str, Any]]:
    unknown = set(fields) - _TR_UPDATABLE_COLUMNS
    if unknown:
        raise ValueError(f"Colunas nao atualizaveis: {sorted(unknown)}")
    if not fields:
        return get_technical_responsible(rt_id)

    assignments = [f"{col} = %s" for col in fields]
    assignments.append("updated_at = NOW()")
    params = [
        list(v) if col == "document_ids" and v is not None else v
        for col, v in fields.items()
    ]
    params.append(rt_id)

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            f"""
            UPDATE technical_responsibles
               SET {", ".join(assignments)}
             WHERE id = %s
            RETURNING *
            """,
            tuple(params),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def deactivate_technical_responsible(rt_id: int) -> None:
    with db_cursor() as (conn, cursor):
        cursor.execute(
            """
            UPDATE technical_responsibles
               SET is_active = FALSE,
                   updated_at = NOW()
             WHERE id = %s
            """,
            (rt_id,),
        )
        conn.commit()


# =====================================================================
# associations  (doc 25 §4.2) — 1:1 com tenants
# =====================================================================

def upsert_association(
    *,
    tenant_id: int,
    statute_document_id: Optional[int] = None,
    directive_board: Optional[list[dict[str, Any]]] = None,
    members_count: int = 0,
    is_judicial_operation: bool = False,
    judicial_authorization: Optional[str] = None,
) -> dict[str, Any]:
    """Insere ou atualiza a linha 1:1 de ``associations`` para o tenant.

    Nao mexe em ``sandbox_application_status`` nem em
    ``eligibility_validated_at`` — esses sao governados por operacoes
    dedicadas que refletem transicoes do ciclo de vida regulatorio.
    """
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO associations (
                tenant_id, statute_document_id, directive_board,
                members_count, is_judicial_operation, judicial_authorization
            )
            VALUES (%s, %s, %s::jsonb, %s, %s, %s)
            ON CONFLICT (tenant_id) DO UPDATE SET
                statute_document_id    = EXCLUDED.statute_document_id,
                directive_board        = EXCLUDED.directive_board,
                members_count          = EXCLUDED.members_count,
                is_judicial_operation  = EXCLUDED.is_judicial_operation,
                judicial_authorization = EXCLUDED.judicial_authorization,
                updated_at             = NOW()
            RETURNING *
            """,
            (
                tenant_id,
                statute_document_id,
                json.dumps(directive_board or []),
                members_count,
                is_judicial_operation,
                judicial_authorization,
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def get_association(tenant_id: int) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT * FROM associations WHERE tenant_id = %s",
            (tenant_id,),
        )
        return cursor.fetchone()


def set_sandbox_application_status(
    tenant_id: int,
    status: Optional[str],
) -> Optional[dict[str, Any]]:
    """Atualiza ``sandbox_application_status``. O CHECK do schema valida
    a whitelist — passar valor invalido gera ``IntegrityError``."""
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            UPDATE associations
               SET sandbox_application_status = %s,
                   updated_at = NOW()
             WHERE tenant_id = %s
            RETURNING *
            """,
            (status, tenant_id),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def mark_eligibility_validated(tenant_id: int) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            UPDATE associations
               SET eligibility_validated_at = NOW(),
                   updated_at = NOW()
             WHERE tenant_id = %s
            RETURNING *
            """,
            (tenant_id,),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


# =====================================================================
# technical_operational_capacity  (doc 25 §4.5)
# =====================================================================

def create_capacity_assessment(
    *,
    tenant_id: int,
    assessment_date: date,
    infrastructure_score: dict[str, Any],
    human_resources_score: dict[str, Any],
    process_maturity_score: dict[str, Any],
    proposed_scale: dict[str, Any],
    overall_readiness: Optional[float] = None,
    assessed_by: Optional[int] = None,
) -> dict[str, Any]:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO technical_operational_capacity (
                tenant_id, assessment_date,
                infrastructure_score, human_resources_score,
                process_maturity_score, proposed_scale,
                overall_readiness, assessed_by
            )
            VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
            RETURNING *
            """,
            (
                tenant_id,
                assessment_date,
                json.dumps(infrastructure_score),
                json.dumps(human_resources_score),
                json.dumps(process_maturity_score),
                json.dumps(proposed_scale),
                overall_readiness,
                assessed_by,
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def get_latest_capacity_assessment(tenant_id: int) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT * FROM technical_operational_capacity
             WHERE tenant_id = %s
             ORDER BY assessment_date DESC, id DESC
             LIMIT 1
            """,
            (tenant_id,),
        )
        return cursor.fetchone()


def list_capacity_assessments(
    tenant_id: int,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
    include_total: bool = False,
):
    """Lista assessments de capacidade tecnico-operacional.

    Sprint 3 Page-Migration Tier-2:
      - `limit=None` -> compat path (`list[dict]`).
      - `limit=int`  -> dict `{items, total, has_more}`.
    """
    base_sql = (
        "SELECT * FROM technical_operational_capacity "
        "WHERE tenant_id = %s "
        "ORDER BY assessment_date DESC, id DESC"
    )

    with db_cursor(dictionary=True) as (_, cursor):
        if limit is None:
            cursor.execute(base_sql, (tenant_id,))
            return list(cursor.fetchall())

        total = None
        if include_total:
            cursor.execute(
                "SELECT COUNT(*) AS n FROM technical_operational_capacity "
                "WHERE tenant_id = %s",
                (tenant_id,),
            )
            total = int(cursor.fetchone()["n"])

        fetch_n = limit if include_total else limit + 1
        cursor.execute(
            base_sql + " LIMIT %s OFFSET %s",
            (tenant_id, fetch_n, offset),
        )
        rows = cursor.fetchall()

    if include_total:
        items = list(rows)
        has_more = (offset + len(items)) < (total or 0)
    else:
        from src.web.pagination import apply_limit_plus_one
        items, has_more = apply_limit_plus_one(rows, limit)

    return {"items": items, "total": total, "has_more": has_more}
