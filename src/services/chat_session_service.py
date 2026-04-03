# src/services/chat_session_service.py
"""
Gerencia sessões de chat de intake (anamnese via frontend).

Cada sessão representa um paciente que clicou no link enviado pela clínica
e está preenchendo o formulário dinâmico em tempo real via WebSocket.

A sessão é armazenada em memória (dict thread-safe) com TTL configurável.
Para escalar horizontalmente, migrar para Redis pub/sub.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.infra.crypto import encrypt_value, decrypt_value
from src.config import CHAT_SESSION_TTL_S, CHAT_CLEANUP_INTERVAL_S

logger = logging.getLogger("cannabia.chat_session")

# ──────────────────────────────────────────────
# MODELOS
# ──────────────────────────────────────────────

class SessionState(str, Enum):
    WAITING = "waiting"          # Token criado, aguardando conexão WS
    CONNECTED = "connected"      # WebSocket ativo
    IN_PROGRESS = "in_progress"  # Preenchimento em andamento
    COMPLETED = "completed"      # Intake finalizado
    EXPIRED = "expired"          # TTL expirou sem completar


@dataclass
class ChatSession:
    session_id: str
    clinic_id: int
    patient_token: str           # Token opaco para o paciente (no link)
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    state: SessionState = SessionState.WAITING
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    sid: Optional[str] = None    # SocketIO session id
    collected_data: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_activity = time.time()

    def is_expired(self, ttl_s: int) -> bool:
        return (time.time() - self.last_activity) > ttl_s

    def to_safe_dict(self) -> dict[str, Any]:
        """Representação segura (sem dados sensíveis) para telemetria."""
        return {
            "session_id": self.session_id,
            "clinic_id": self.clinic_id,
            "state": self.state.value,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "has_data": bool(self.collected_data),
        }


# ──────────────────────────────────────────────
# STORE (in-memory, thread-safe)
# ──────────────────────────────────────────────

_SESSION_TTL_S = CHAT_SESSION_TTL_S
_CLEANUP_INTERVAL_S = CHAT_CLEANUP_INTERVAL_S

_lock = threading.Lock()
_sessions: dict[str, ChatSession] = {}
_token_index: dict[str, str] = {}  # patient_token -> session_id
_last_cleanup: float = time.time()


def _maybe_cleanup() -> None:
    """Remove sessões expiradas se o intervalo de limpeza passou."""
    global _last_cleanup
    now = time.time()
    if (now - _last_cleanup) < _CLEANUP_INTERVAL_S:
        return
    _last_cleanup = now

    expired_ids = [
        sid for sid, sess in _sessions.items()
        if sess.is_expired(_SESSION_TTL_S)
    ]
    for sid in expired_ids:
        sess = _sessions.pop(sid, None)
        if sess:
            _token_index.pop(sess.patient_token, None)
            logger.info("Sessão expirada removida: %s", sid)


# ──────────────────────────────────────────────
# API PÚBLICA
# ──────────────────────────────────────────────

def create_session(
    clinic_id: int,
    patient_name: Optional[str] = None,
    patient_phone: Optional[str] = None,
) -> ChatSession:
    """
    Cria uma sessão de intake e retorna o objeto com o patient_token.
    O token é o que vai no link enviado pela clínica ao paciente.
    """
    session_id = secrets.token_urlsafe(24)
    patient_token = secrets.token_urlsafe(32)

    sess = ChatSession(
        session_id=session_id,
        clinic_id=clinic_id,
        patient_token=patient_token,
        patient_name=patient_name,
        patient_phone=patient_phone,
    )

    with _lock:
        _maybe_cleanup()
        _sessions[session_id] = sess
        _token_index[patient_token] = session_id

    logger.info(
        "Sessão de intake criada: session_id=%s clinic_id=%d",
        session_id, clinic_id,
    )
    return sess


def get_session(session_id: str) -> Optional[ChatSession]:
    """Retorna a sessão pelo ID interno (uso do backend)."""
    with _lock:
        sess = _sessions.get(session_id)
        if sess and sess.is_expired(_SESSION_TTL_S):
            _sessions.pop(session_id, None)
            _token_index.pop(sess.patient_token, None)
            return None
        return sess


def get_session_by_token(patient_token: str) -> Optional[ChatSession]:
    """Resolve sessão pelo token público (uso do paciente via link)."""
    with _lock:
        session_id = _token_index.get(patient_token)
        if not session_id:
            return None
        return get_session(session_id)


def bind_socket(session_id: str, sid: str) -> bool:
    """Vincula um SocketIO sid à sessão de intake."""
    with _lock:
        sess = _sessions.get(session_id)
        if not sess or sess.is_expired(_SESSION_TTL_S):
            return False
        sess.sid = sid
        sess.state = SessionState.CONNECTED
        sess.touch()
        return True


def update_session_data(
    session_id: str,
    step_key: str,
    value: Any,
    *,
    encrypt_sensitive: bool = False,
) -> bool:
    """
    Armazena dados coletados em um step do intake.
    Se encrypt_sensitive=True, o valor é cifrado via Fernet antes do store.
    """
    with _lock:
        sess = _sessions.get(session_id)
        if not sess or sess.state in (SessionState.COMPLETED, SessionState.EXPIRED):
            return False

        stored_value = encrypt_value(str(value)) if encrypt_sensitive else value
        sess.collected_data[step_key] = stored_value
        sess.state = SessionState.IN_PROGRESS
        sess.touch()
        return True


def complete_session(session_id: str) -> Optional[dict[str, Any]]:
    """
    Marca a sessão como completa e retorna os dados coletados.
    Valores cifrados são descriptografados no retorno.
    """
    with _lock:
        sess = _sessions.get(session_id)
        if not sess:
            return None
        sess.state = SessionState.COMPLETED
        sess.touch()

        # Retorna cópia dos dados (descriptografa campos cifrados)
        result = {}
        for k, v in sess.collected_data.items():
            if isinstance(v, str):
                try:
                    result[k] = decrypt_value(v)
                except (ValueError, Exception):
                    result[k] = v
            else:
                result[k] = v
        return result


def disconnect_socket(sid: str) -> Optional[str]:
    """Chamado no evento disconnect do SocketIO. Retorna session_id se encontrou."""
    with _lock:
        for session_id, sess in _sessions.items():
            if sess.sid == sid:
                sess.sid = None
                if sess.state == SessionState.CONNECTED:
                    sess.state = SessionState.WAITING
                return session_id
    return None


def get_active_sessions_count(clinic_id: Optional[int] = None) -> int:
    """Conta sessões ativas (para métricas de telemetria)."""
    with _lock:
        _maybe_cleanup()
        if clinic_id is None:
            return len(_sessions)
        return sum(
            1 for s in _sessions.values()
            if s.clinic_id == clinic_id and not s.is_expired(_SESSION_TTL_S)
        )
