# src/repositories/medical_profile_repository.py
"""Sprint C MVP: persistencia do onboarding medico.

Tabela `medical_profiles` (migration 047) e 1:1 com `users`. Funcoes aqui
sao defensivas: upsert idempotente (re-edit do onboarding), get nunca
levanta para "perfil ainda nao criado", apenas retorna None.

Upload de arquivos (photo/CRM/diploma) ainda nao tem storage backend:
campos *_url ficam NULL ate a onda 2 desta sprint. O repository aceita
URLs se fornecidas para nao bloquear o futuro.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from src.infra.database import db_cursor


ALLOWED_AI_LEVELS = {"basico", "avancado", "completo"}
DEFAULT_AI_LEVEL = "avancado"


def get_by_user_id(user_id: int) -> Optional[dict]:
    """Retorna o perfil do medico ou None se ainda nao criado."""
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT * FROM medical_profiles WHERE user_id = %s",
            (user_id,),
        )
        return cursor.fetchone()


def _coerce_ai_level(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value not in ALLOWED_AI_LEVELS:
        return DEFAULT_AI_LEVEL
    return value


def _coerce_str(raw: Any, max_len: int) -> str:
    if raw is None:
        return ""
    return str(raw).strip()[:max_len]


def upsert(user_id: int, payload: dict) -> dict:
    """Cria ou atualiza o perfil. Retorna o registro final.

    Os campos *_url so sao gravados se a chave existir no payload — assim
    o front pode salvar o resto do form mesmo antes do storage estar pronto.
    """
    full_name = _coerce_str(payload.get("full_name"), 255)
    crm = _coerce_str(payload.get("crm"), 20)
    specialty = _coerce_str(payload.get("specialty"), 100)
    prefs_notifications = bool(payload.get("prefs_notifications", True))
    prefs_ai_level = _coerce_ai_level(payload.get("prefs_ai_level"))

    url_fields: dict[str, Optional[str]] = {}
    for key in ("photo_url", "crm_doc_url", "diploma_url"):
        if key in payload:
            value = payload.get(key)
            url_fields[key] = str(value).strip() if value else None

    set_url_sql = ", ".join(f"{key} = EXCLUDED.{key}" for key in url_fields)
    extra_cols_sql = ("," + ", ".join(url_fields)) if url_fields else ""
    extra_vals_sql = ("," + ", ".join(["%s"] * len(url_fields))) if url_fields else ""
    extra_update_sql = ("," + set_url_sql) if set_url_sql else ""

    sql = f"""
        INSERT INTO medical_profiles
            (user_id, full_name, crm, specialty, prefs_notifications,
             prefs_ai_level, updated_at{extra_cols_sql})
        VALUES (%s, %s, %s, %s, %s, %s, NOW(){extra_vals_sql})
        ON CONFLICT (user_id) DO UPDATE SET
            full_name           = EXCLUDED.full_name,
            crm                 = EXCLUDED.crm,
            specialty           = EXCLUDED.specialty,
            prefs_notifications = EXCLUDED.prefs_notifications,
            prefs_ai_level      = EXCLUDED.prefs_ai_level,
            updated_at          = NOW(){extra_update_sql}
        RETURNING *
    """
    params: list[Any] = [
        user_id,
        full_name,
        crm,
        specialty,
        prefs_notifications,
        prefs_ai_level,
    ]
    params.extend(url_fields.values())

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(sql, tuple(params))
        row = cursor.fetchone()
        conn.commit()
        return row


def mark_completed(user_id: int) -> Optional[dict]:
    """Marca o wizard como concluido (idempotente). Retorna o registro."""
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            UPDATE medical_profiles
               SET onboarding_completed_at = COALESCE(onboarding_completed_at, NOW()),
                   updated_at = NOW()
             WHERE user_id = %s
             RETURNING *
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def serialize(row: Optional[dict]) -> dict:
    """Forma de payload retornada ao frontend. None vira perfil vazio."""
    if not row:
        return {
            "full_name": "",
            "crm": "",
            "specialty": "",
            "photo_url": None,
            "crm_doc_url": None,
            "diploma_url": None,
            "prefs_notifications": True,
            "prefs_ai_level": DEFAULT_AI_LEVEL,
            "onboarding_completed_at": None,
        }
    completed_at = row.get("onboarding_completed_at")
    if isinstance(completed_at, datetime):
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)
        completed_at = completed_at.isoformat()
    return {
        "full_name": row.get("full_name", "") or "",
        "crm": row.get("crm", "") or "",
        "specialty": row.get("specialty", "") or "",
        "photo_url": row.get("photo_url"),
        "crm_doc_url": row.get("crm_doc_url"),
        "diploma_url": row.get("diploma_url"),
        "prefs_notifications": bool(row.get("prefs_notifications", True)),
        "prefs_ai_level": row.get("prefs_ai_level") or DEFAULT_AI_LEVEL,
        "onboarding_completed_at": completed_at,
    }
