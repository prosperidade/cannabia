"""Repositorio para conversations e messages de thread."""

from __future__ import annotations

from typing import Optional

from flask import g

from src.infra.database import db_cursor


def _clinic_id() -> int:
    cid = getattr(g, "clinic_id", None)
    if cid is None:
        raise RuntimeError("clinic_id nao encontrado no contexto da request")
    return int(cid)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def get_or_create_conversation(
    clinic_id: int,
    contact_phone: str,
    *,
    contact_name: Optional[str] = None,
    patient_id: Optional[int] = None,
    channel: str = "whatsapp",
) -> dict:
    """Retorna a conversa existente ou cria uma nova."""
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            SELECT * FROM conversations
            WHERE clinic_id = %s AND contact_phone = %s
            LIMIT 1
            """,
            (clinic_id, contact_phone),
        )
        row = cur.fetchone()
        if row:
            # Update contact_name / patient_id if provided
            updates = []
            args = []
            if contact_name and not row.get("contact_name"):
                updates.append("contact_name = %s")
                args.append(contact_name)
            if patient_id and not row.get("patient_id"):
                updates.append("patient_id = %s")
                args.append(patient_id)
            if updates:
                args.append(row["id"])
                cur.execute(
                    f"UPDATE conversations SET {', '.join(updates)} WHERE id = %s",
                    args,
                )
                conn.commit()
            return dict(row)

        cur.execute(
            """
            INSERT INTO conversations
                (clinic_id, contact_phone, contact_name, patient_id, channel, status)
            VALUES (%s, %s, %s, %s, %s, 'open')
            RETURNING *
            """,
            (clinic_id, contact_phone, contact_name, patient_id, channel),
        )
        conn.commit()
        return dict(cur.fetchone())


def list_conversations(
    clinic_id: Optional[int] = None,
    *,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    include_total: bool = False,
    paginated: bool = False,
):
    """Lista conversas da clinica corrente.

    Compat (default): retorna `list[dict]` (Sprint 1).
    Sprint 2 Track Page: passe `paginated=True` pra receber dict
    {items, total, has_more}. Sempre aplica LIMIT (default 50).
    """
    cid = clinic_id or _clinic_id()
    with db_cursor(dictionary=True) as (_, cur):
        base_sql = """
            SELECT c.*,
                   p.name AS patient_name_resolved
            FROM conversations c
            LEFT JOIN patients p ON p.id = c.patient_id AND p.clinic_id = c.clinic_id
            WHERE c.clinic_id = %s
        """
        base_args: list = [cid]

        if status:
            base_sql += " AND c.status = %s"
            base_args.append(status)
        if search:
            base_sql += " AND (c.contact_name ILIKE %s OR c.contact_phone ILIKE %s OR p.name ILIKE %s)"
            pat = f"%{search}%"
            base_args.extend([pat, pat, pat])

        if not paginated:
            sql = base_sql + " ORDER BY c.last_message_at DESC NULLS LAST LIMIT %s"
            args = base_args + [limit]
            cur.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]

        # Modo paginado.
        total = None
        if include_total:
            count_sql = (
                "SELECT COUNT(*) AS n FROM conversations c "
                "LEFT JOIN patients p ON p.id = c.patient_id AND p.clinic_id = c.clinic_id "
                "WHERE c.clinic_id = %s"
            )
            count_args: list = [cid]
            if status:
                count_sql += " AND c.status = %s"
                count_args.append(status)
            if search:
                count_sql += (
                    " AND (c.contact_name ILIKE %s OR c.contact_phone ILIKE %s OR p.name ILIKE %s)"
                )
                pat = f"%{search}%"
                count_args.extend([pat, pat, pat])
            cur.execute(count_sql, count_args)
            total = int(cur.fetchone()["n"])

        fetch_n = limit if include_total else limit + 1
        sql = base_sql + " ORDER BY c.last_message_at DESC NULLS LAST LIMIT %s OFFSET %s"
        args = base_args + [fetch_n, offset]
        cur.execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()]

    if include_total:
        items = rows
        has_more = (offset + len(items)) < (total or 0)
    else:
        from src.web.pagination import apply_limit_plus_one
        items, has_more = apply_limit_plus_one(rows, limit)

    return {"items": items, "total": total, "has_more": has_more}


def get_conversation(conversation_id: int, clinic_id: Optional[int] = None) -> Optional[dict]:
    cid = clinic_id or _clinic_id()
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(
            """
            SELECT c.*, p.name AS patient_name_resolved
            FROM conversations c
            LEFT JOIN patients p ON p.id = c.patient_id AND p.clinic_id = c.clinic_id
            WHERE c.id = %s AND c.clinic_id = %s
            """,
            (conversation_id, cid),
        )
        return cur.fetchone()


def update_conversation_on_message(
    conversation_id: int,
    *,
    last_message_preview: str,
    increment_unread: bool = True,
) -> None:
    with db_cursor() as (conn, cur):
        unread_sql = ", unread_count = unread_count + 1" if increment_unread else ""
        cur.execute(
            f"""
            UPDATE conversations
            SET last_message_at = NOW(),
                last_message_preview = %s,
                updated_at = NOW(),
                status = CASE WHEN status = 'closed' THEN 'open' ELSE status END
                {unread_sql}
            WHERE id = %s
            """,
            (last_message_preview[:200] if last_message_preview else "", conversation_id),
        )
        conn.commit()


def mark_conversation_read(conversation_id: int, clinic_id: Optional[int] = None) -> None:
    cid = clinic_id or _clinic_id()
    with db_cursor() as (conn, cur):
        cur.execute(
            "UPDATE conversations SET unread_count = 0, updated_at = NOW() WHERE id = %s AND clinic_id = %s",
            (conversation_id, cid),
        )
        conn.commit()


def close_conversation(conversation_id: int, clinic_id: Optional[int] = None) -> None:
    cid = clinic_id or _clinic_id()
    with db_cursor() as (conn, cur):
        cur.execute(
            "UPDATE conversations SET status = 'closed', updated_at = NOW() WHERE id = %s AND clinic_id = %s",
            (conversation_id, cid),
        )
        conn.commit()


def assign_conversation(conversation_id: int, user_id: int, clinic_id: Optional[int] = None) -> None:
    cid = clinic_id or _clinic_id()
    with db_cursor() as (conn, cur):
        cur.execute(
            "UPDATE conversations SET assigned_to = %s, updated_at = NOW() WHERE id = %s AND clinic_id = %s",
            (user_id, conversation_id, cid),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Conversation Messages
# ---------------------------------------------------------------------------

def add_message(
    conversation_id: int,
    clinic_id: int,
    *,
    direction: str = "inbound",
    sender_type: str = "patient",
    sender_name: Optional[str] = None,
    message_text: Optional[str] = None,
    message_type: str = "text",
    external_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO conversation_messages
                (conversation_id, clinic_id, direction, sender_type, sender_name,
                 message_text, message_type, external_id, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                conversation_id, clinic_id, direction, sender_type, sender_name,
                message_text, message_type, external_id,
                __import__("json").dumps(metadata) if metadata else None,
            ),
        )
        conn.commit()
        return dict(cur.fetchone())


def list_messages(
    conversation_id: int,
    clinic_id: Optional[int] = None,
    *,
    limit: int = 100,
    before_id: Optional[int] = None,
) -> list[dict]:
    cid = clinic_id or _clinic_id()
    with db_cursor(dictionary=True) as (_, cur):
        sql = """
            SELECT * FROM conversation_messages
            WHERE conversation_id = %s AND clinic_id = %s
        """
        args: list = [conversation_id, cid]

        if before_id:
            sql += " AND id < %s"
            args.append(before_id)

        sql += " ORDER BY created_at DESC LIMIT %s"
        args.append(limit)

        cur.execute(sql, args)
        rows = cur.fetchall()
        return [dict(r) for r in reversed(rows)]


def get_unread_count(clinic_id: Optional[int] = None) -> int:
    cid = clinic_id or _clinic_id()
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT COALESCE(SUM(unread_count), 0) FROM conversations WHERE clinic_id = %s AND status != 'closed'",
            (cid,),
        )
        return cur.fetchone()[0]
