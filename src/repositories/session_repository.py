# src/repositories/session_repository.py
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.session")


def get_session(clinic_id: int, phone: str) -> Optional[Dict[str, Any]]:
    """
    Retorna a sessão ativa de um paciente ou None se não existir.
    O campo 'data' é sempre retornado como dict (deserializado do JSON).
    """
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT step, data FROM whatsapp_sessions "
            "WHERE clinic_id = %s AND phone = %s",
            (clinic_id, phone),
        )
        row = cursor.fetchone()
        if row and isinstance(row["data"], str):
            row["data"] = json.loads(row["data"])
        return row


def upsert_session(clinic_id: int, phone: str, step: str, data: dict) -> None:
    """
    Cria ou atualiza a sessão de um paciente (ON CONFLICT DO UPDATE).
    Idempotente: pode ser chamado a cada mensagem sem duplicar linhas.
    """
    with db_cursor() as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO whatsapp_sessions (clinic_id, phone, step, data)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (clinic_id, phone) DO UPDATE SET
                step = EXCLUDED.step,
                data = EXCLUDED.data
            """,
            (clinic_id, phone, step, json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()
    logger.debug("Sessão atualizada: clinic=%d phone=%s step=%s", clinic_id, phone, step)


def delete_session(clinic_id: int, phone: str) -> None:
    """Remove a sessão após conclusão ou erro terminal."""
    with db_cursor() as (conn, cursor):
        cursor.execute(
            "DELETE FROM whatsapp_sessions WHERE clinic_id = %s AND phone = %s",
            (clinic_id, phone),
        )
        conn.commit()
    logger.debug("Sessão removida: clinic=%d phone=%s", clinic_id, phone)
