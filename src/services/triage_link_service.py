"""Service para emissao e validacao de links de triagem.

Suporta dois modos:
  1. Link generico por clinica (sem agendamento)
  2. Link vinculado a um agendamento (pre-preenche dados do paciente, uso unico)
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.config import FRONTEND_ORIGINS, SECRET_KEY, TRIAGE_LINK_TTL_S
from src.repositories.tenancy_repository import get_clinic_public_label

logger = logging.getLogger("cannabia.triage_link")

_SALT = "triage-link"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(SECRET_KEY, salt=_SALT)


def _base_frontend_url() -> str:
    origin = FRONTEND_ORIGINS[0] if FRONTEND_ORIGINS else "http://localhost:3000"
    return origin.rstrip("/")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _try_persist(fn, *args, **kwargs):
    """Tenta persistir no banco; se a tabela ainda nao existir, ignora.

    Loga em debug porque a ausencia da tabela e esperada em alguns
    ambientes de dev/CI; em prod com schema migrado, qualquer falha
    aqui e visivel via log de debug + traceback.
    """
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.debug(
            "_try_persist: %s falhou (tabela ausente ou erro nao critico)",
            getattr(fn, "__name__", "callable"),
            exc_info=True,
        )
        return None


# ---------------------------------------------------------------------------
# Emissao
# ---------------------------------------------------------------------------

def issue_triage_link(
    clinic_id: int,
    *,
    appointment_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    patient_name: Optional[str] = None,
    patient_phone: Optional[str] = None,
    issued_by: Optional[int] = None,
) -> dict:
    """Emite um link de triagem, opcionalmente vinculado a um agendamento."""
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=TRIAGE_LINK_TTL_S)

    payload: dict[str, Any] = {
        "clinic_id": int(clinic_id),
        "kind": "triage_link",
    }
    if appointment_id is not None:
        payload["appointment_id"] = int(appointment_id)
    if patient_id is not None:
        payload["patient_id"] = int(patient_id)
    if patient_name:
        payload["patient_name"] = str(patient_name).strip()
    if patient_phone:
        payload["patient_phone"] = str(patient_phone).strip()

    token = _serializer().dumps(payload)
    clinic_label = get_clinic_public_label(clinic_id)
    url = f"{_base_frontend_url()}/triagem?token={token}"

    # Persistir no banco (graceful se tabela nao existir ainda)
    from src.repositories.triage_link_repository import create_triage_link

    link_record = _try_persist(
        create_triage_link,
        clinic_id=clinic_id,
        token_hash=_hash_token(token),
        expires_at=expires_at,
        appointment_id=appointment_id,
        patient_id=patient_id,
        patient_name=patient_name,
        patient_phone=patient_phone,
        issued_by=issued_by,
    )

    result = {
        "token": token,
        "url": url,
        "clinic_id": int(clinic_id),
        "clinic_label": clinic_label,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    if link_record:
        result["link_id"] = link_record["id"]
    if appointment_id is not None:
        result["appointment_id"] = appointment_id
    if patient_name:
        result["patient_name"] = patient_name

    return result


# ---------------------------------------------------------------------------
# Resolucao / validacao
# ---------------------------------------------------------------------------

def resolve_triage_link_token(token: str) -> dict:
    """Valida o token e retorna o contexto. Verifica uso unico se persistido."""
    if not token or not str(token).strip():
        raise ValueError("Token de triagem ausente.")

    token = str(token).strip()

    try:
        payload = _serializer().loads(token, max_age=TRIAGE_LINK_TTL_S)
    except SignatureExpired as exc:
        raise ValueError("Token de triagem expirado.") from exc
    except BadSignature as exc:
        raise ValueError("Token de triagem invalido.") from exc

    if payload.get("kind") != "triage_link":
        raise ValueError("Token de triagem invalido.")

    clinic_id = int(payload.get("clinic_id") or 0)
    if clinic_id <= 0:
        raise ValueError("Token de triagem invalido.")

    # Verificar uso unico no banco
    from src.repositories.triage_link_repository import get_triage_link_by_hash

    link_record = _try_persist(get_triage_link_by_hash, _hash_token(token))
    if link_record and link_record.get("status") == "used":
        raise ValueError("Este link de triagem ja foi utilizado.")
    if link_record and link_record.get("status") == "revoked":
        raise ValueError("Este link de triagem foi revogado.")

    result: dict[str, Any] = {
        "clinic_id": clinic_id,
        "clinic_label": get_clinic_public_label(clinic_id),
    }

    # Contexto enriquecido do agendamento
    if payload.get("appointment_id"):
        result["appointment_id"] = int(payload["appointment_id"])
    if payload.get("patient_id"):
        result["patient_id"] = int(payload["patient_id"])
    if payload.get("patient_name"):
        result["patient_name"] = payload["patient_name"]
    if payload.get("patient_phone"):
        result["patient_phone"] = payload["patient_phone"]

    if link_record:
        result["link_id"] = link_record["id"]

    return result


# ---------------------------------------------------------------------------
# Marcar como usado (chamado apos submissao da triagem)
# ---------------------------------------------------------------------------

def consume_triage_link(token: str, *, report_id: Optional[int] = None, remote_ip: Optional[str] = None) -> None:
    """Marca o link como usado apos submissao bem-sucedida da triagem."""
    from src.repositories.triage_link_repository import get_triage_link_by_hash, mark_link_used

    link_record = _try_persist(get_triage_link_by_hash, _hash_token(str(token).strip()))
    if link_record and link_record.get("status") == "active":
        _try_persist(
            mark_link_used,
            link_record["id"],
            report_id=report_id,
            used_by_ip=remote_ip,
        )
