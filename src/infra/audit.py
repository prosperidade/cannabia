# src/infra/audit.py
"""
Trilha de auditoria transversal para ações clínicas e administrativas.

Registra quem fez o quê, quando, de onde, e detalhes opcionais (antes/depois).
Complementa ai_audit_logs com cobertura de login, prontuário, agendamentos etc.

Uso:
    from src.infra.audit import log_audit_event

    log_audit_event(
        action="login_success",
        resource_type="session",
        resource_id=str(user_id),
        details={"username": username},
    )
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import g, request

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.audit")


def log_audit_event(
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    *,
    clinic_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> None:
    """
    Registra um evento na trilha de auditoria transversal.

    Campos de contexto (clinic_id, tenant_id, user_id, ip, user_agent)
    são extraídos automaticamente do Flask g/request quando disponíveis,
    mas podem ser sobrescritos via parâmetros explícitos.

    Args:
        action:        Identificador da ação (ex: login_success, medical_record_created)
        resource_type: Tipo do recurso afetado (ex: session, medical_record, patient)
        resource_id:   ID do recurso afetado (opcional)
        details:       Dicionário com detalhes adicionais (antes/depois, campos alterados)
        clinic_id:     Sobrescreve clinic_id do contexto Flask
        tenant_id:     Sobrescreve tenant_id do contexto Flask
        user_id:       Sobrescreve user_id do contexto Flask
    """
    # Resolução de contexto: parâmetro explícito > Flask g > None
    resolved_clinic_id = clinic_id or getattr(g, "clinic_id", None)
    resolved_tenant_id = tenant_id or getattr(g, "tenant_id", None)
    resolved_user_id = user_id or getattr(g, "user_id", None)

    # Extrai IP e User-Agent do request atual
    ip_address = None
    user_agent = None
    try:
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip_address and "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()
        user_agent = request.headers.get("User-Agent", "")[:500]
    except RuntimeError:
        # Fora de contexto de request (ex: jobs async)
        pass

    import json

    try:
        with db_cursor() as (connection, cursor):
            cursor.execute(
                """
                INSERT INTO audit_trail
                    (clinic_id, tenant_id, user_id, action, resource_type,
                     resource_id, details, ip_address, user_agent)
                VALUES
                    (COALESCE(%s, 0), %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    resolved_clinic_id,
                    resolved_tenant_id,
                    resolved_user_id,
                    action,
                    resource_type,
                    resource_id,
                    json.dumps(details or {}, default=str),
                    ip_address,
                    user_agent,
                ),
            )
            connection.commit()
    except Exception:
        # Auditoria nunca deve derrubar a operação principal.
        # Loga o erro e segue — o registro ficará ausente, mas a operação não falha.
        logger.exception(
            "Falha ao registrar evento de auditoria: action=%s resource_type=%s",
            action,
            resource_type,
        )
