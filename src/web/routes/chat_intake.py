# src/web/routes/chat_intake.py
"""
Rotas REST + Namespace SocketIO para o Chat Dinâmico de Intake.

Fluxo:
  1. Clínica cria sessão via POST /api/v1/chat/sessions  (autenticado)
  2. Paciente recebe link com patient_token
  3. Frontend chama POST /api/v1/chat/handshake  (token → session_id efêmero)
  4. Frontend abre WebSocket no namespace /chat com session_id
  5. Eventos bidirecionais: step_data, typing, complete
  6. Dados sensíveis são cifrados via Fernet (crypto.py) em trânsito e em store

Latência: Sem polling — tudo via push WebSocket.
Segurança: Token opaco + Fernet para campos PII + audit trail.
"""

from __future__ import annotations

import json
import logging
import time
from functools import wraps
from typing import Any

from flask import Blueprint, g, request, jsonify
from flask_login import current_user, login_required
from flask_socketio import Namespace, emit, disconnect, join_room, leave_room

from src.infra.crypto import encrypt_value
from src.infra.audit import log_audit_event
from src.infra.metrics import record as record_metric
from src.services.chat_session_service import (
    ChatSession,
    SessionState,
    create_session,
    get_session,
    get_session_by_token,
    bind_socket,
    update_session_data,
    complete_session,
    disconnect_socket,
    get_active_sessions_count,
)

logger = logging.getLogger("cannabia.chat_intake")

chat_bp = Blueprint("chat_intake", __name__)

# Campos que DEVEM ser cifrados antes de armazenar/transmitir
_SENSITIVE_FIELDS = frozenset({
    "cpf", "rg", "phone", "email", "address",
    "medication_details", "diagnosis_history",
})


# ──────────────────────────────────────────────
# REST: CRIAÇÃO DE SESSÃO (lado clínica)
# ──────────────────────────────────────────────

@chat_bp.route("/api/v1/chat/sessions", methods=["POST"])
@login_required
def create_intake_session():
    """
    Cria uma sessão de intake para um paciente.
    Retorna o patient_token que vai no link enviado pela clínica.

    Body (JSON):
        patient_name:  str (opcional)
        patient_phone: str (opcional)

    Requer: login + clinic_id no contexto.
    """
    clinic_id = getattr(g, "clinic_id", None)
    if not clinic_id:
        return jsonify({"error": "Contexto de clínica ausente."}), 403

    data = request.get_json(silent=True) or {}
    patient_name = (data.get("patient_name") or "").strip() or None
    patient_phone = (data.get("patient_phone") or "").strip() or None

    sess = create_session(
        clinic_id=clinic_id,
        patient_name=patient_name,
        patient_phone=patient_phone,
    )

    log_audit_event(
        action="chat_session_created",
        resource_type="chat_session",
        resource_id=sess.session_id,
        details={"patient_name": patient_name is not None},
    )

    record_metric("chat.session_created", 1)

    return jsonify({
        "session_id": sess.session_id,
        "patient_token": sess.patient_token,
        "state": sess.state.value,
        "created_at": sess.created_at,
    }), 201


# ──────────────────────────────────────────────
# REST: HANDSHAKE (lado paciente)
# ──────────────────────────────────────────────

@chat_bp.route("/api/v1/chat/handshake", methods=["POST"])
def chat_handshake():
    """
    Troca patient_token por session_id efêmero para abrir o WebSocket.
    Não requer login — o token É a autenticação do paciente.

    Body (JSON):
        token: str  (patient_token recebido no link)

    Response:
        session_id: str
        clinic_id:  int
        state:      str
        ws_path:    str  (namespace do SocketIO para conectar)
    """
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()

    if not token:
        return jsonify({"error": "Token ausente."}), 400

    sess = get_session_by_token(token)
    if not sess:
        return jsonify({"error": "Sessão inválida ou expirada."}), 404

    if sess.state == SessionState.COMPLETED:
        return jsonify({"error": "Sessão já foi finalizada."}), 410

    sess.touch()

    log_audit_event(
        action="chat_handshake",
        resource_type="chat_session",
        resource_id=sess.session_id,
        details={"clinic_id": sess.clinic_id},
        clinic_id=sess.clinic_id,
    )

    record_metric("chat.handshake", 1)

    return jsonify({
        "session_id": sess.session_id,
        "clinic_id": sess.clinic_id,
        "state": sess.state.value,
        "ws_path": "/chat",
    }), 200


# ──────────────────────────────────────────────
# REST: STATUS DA SESSÃO (lado clínica)
# ──────────────────────────────────────────────

@chat_bp.route("/api/v1/chat/sessions/<session_id>", methods=["GET"])
@login_required
def get_session_status(session_id: str):
    """Retorna o estado atual de uma sessão (sem dados coletados)."""
    sess = get_session(session_id)
    if not sess:
        return jsonify({"error": "Sessão não encontrada."}), 404

    clinic_id = getattr(g, "clinic_id", None)
    if sess.clinic_id != clinic_id:
        return jsonify({"error": "Acesso negado."}), 403

    return jsonify(sess.to_safe_dict()), 200


# ──────────────────────────────────────────────
# REST: MÉTRICAS DE SESSÕES ATIVAS
# ──────────────────────────────────────────────

@chat_bp.route("/api/v1/chat/metrics", methods=["GET"])
@login_required
def chat_metrics():
    """Contagem de sessões ativas por clínica (para dashboard)."""
    clinic_id = getattr(g, "clinic_id", None)
    return jsonify({
        "active_sessions": get_active_sessions_count(clinic_id),
        "active_sessions_global": get_active_sessions_count(),
    }), 200


# ──────────────────────────────────────────────
# SOCKETIO NAMESPACE: /chat
# ──────────────────────────────────────────────

class ChatNamespace(Namespace):
    """
    Namespace /chat para comunicação bidirecional em tempo real.

    Eventos Client → Server:
        join_session  { session_id }
        step_data     { session_id, step, value, sensitive? }
        typing        { session_id, step }
        complete      { session_id }

    Eventos Server → Client:
        session_joined   { session_id, state }
        step_ack         { step, ok, encrypted? }
        intake_complete  { session_id }
        error            { message }

    Eventos Server → Room da clínica:
        patient_typing   { session_id, step }
        patient_progress { session_id, steps_completed }
        patient_connected    { session_id }
        patient_disconnected { session_id }
    """

    def _clinic_room(self, clinic_id: int) -> str:
        return f"clinic:{clinic_id}"

    # ── CONNECT ──────────────────────────────

    def on_connect(self):
        """
        Aceita qualquer conexão no namespace /chat.
        A autenticação real é feita no join_session com session_id válido.
        """
        logger.debug("WS /chat connect: sid=%s", request.sid)

    # ── JOIN SESSION ─────────────────────────

    def on_join_session(self, data: dict[str, Any]):
        """
        Vincula o socket a uma sessão de intake.
        Emitido pelo frontend logo após conectar ao namespace.
        """
        session_id = (data or {}).get("session_id", "")
        if not session_id:
            emit("error", {"message": "session_id ausente."})
            disconnect()
            return

        sess = get_session(session_id)
        if not sess:
            emit("error", {"message": "Sessão inválida ou expirada."})
            disconnect()
            return

        if sess.state == SessionState.COMPLETED:
            emit("error", {"message": "Sessão já finalizada."})
            disconnect()
            return

        if not bind_socket(session_id, request.sid):
            emit("error", {"message": "Falha ao vincular socket."})
            disconnect()
            return

        # Entra na room da clínica para que médicos acompanhem
        join_room(self._clinic_room(sess.clinic_id))

        emit("session_joined", {
            "session_id": session_id,
            "state": sess.state.value,
        })

        # Notifica a room da clínica que o paciente conectou
        emit(
            "patient_connected",
            {"session_id": session_id},
            room=self._clinic_room(sess.clinic_id),
            include_self=False,
        )

        record_metric("chat.ws_joined", 1)
        logger.info("Paciente vinculado: session=%s sid=%s", session_id, request.sid)

    # ── STEP DATA ────────────────────────────

    def on_step_data(self, data: dict[str, Any]):
        """
        Recebe dados de um step do formulário dinâmico.
        Campos sensíveis são cifrados automaticamente.
        """
        session_id = (data or {}).get("session_id", "")
        step = (data or {}).get("step", "")
        value = (data or {}).get("value")

        if not session_id or not step:
            emit("error", {"message": "session_id e step são obrigatórios."})
            return

        sess = get_session(session_id)
        if not sess or sess.sid != request.sid:
            emit("error", {"message": "Sessão inválida."})
            return

        # Determina se o campo é sensível
        is_sensitive = (
            data.get("sensitive", False)
            or step in _SENSITIVE_FIELDS
        )

        ok = update_session_data(
            session_id, step, value,
            encrypt_sensitive=is_sensitive,
        )

        if not ok:
            emit("error", {"message": f"Falha ao salvar step '{step}'."})
            return

        emit("step_ack", {
            "step": step,
            "ok": True,
            "encrypted": is_sensitive,
        })

        # Telemetria cifrada para a room da clínica
        steps_done = list(sess.collected_data.keys())
        progress_payload = {
            "session_id": session_id,
            "steps_completed": len(steps_done),
            "last_step": step,
        }

        # Cifra o payload de progresso se contém step sensível
        if is_sensitive:
            progress_payload["last_step"] = encrypt_value(step)
            progress_payload["encrypted"] = True

        emit(
            "patient_progress",
            progress_payload,
            room=self._clinic_room(sess.clinic_id),
            include_self=False,
        )

        record_metric("chat.step_received", 1)

    # ── TYPING INDICATOR ─────────────────────

    def on_typing(self, data: dict[str, Any]):
        """Indicador de digitação — ultra-leve, sem persistência."""
        session_id = (data or {}).get("session_id", "")
        step = (data or {}).get("step", "")

        sess = get_session(session_id)
        if not sess or sess.sid != request.sid:
            return

        emit(
            "patient_typing",
            {"session_id": session_id, "step": step},
            room=self._clinic_room(sess.clinic_id),
            include_self=False,
        )

    # ── COMPLETE ─────────────────────────────

    def on_complete(self, data: dict[str, Any]):
        """
        Paciente finalizou o intake.
        Descriptografa os dados e emite para a room da clínica.
        """
        session_id = (data or {}).get("session_id", "")

        sess = get_session(session_id)
        if not sess or sess.sid != request.sid:
            emit("error", {"message": "Sessão inválida."})
            return

        collected = complete_session(session_id)
        if collected is None:
            emit("error", {"message": "Falha ao finalizar sessão."})
            return

        emit("intake_complete", {"session_id": session_id})

        # Notifica a clínica com dados descriptografados (canal seguro WS)
        emit(
            "intake_submitted",
            {
                "session_id": session_id,
                "clinic_id": sess.clinic_id,
                "patient_name": sess.patient_name,
                "data": collected,
            },
            room=self._clinic_room(sess.clinic_id),
            include_self=False,
        )

        log_audit_event(
            action="chat_intake_completed",
            resource_type="chat_session",
            resource_id=session_id,
            details={"steps_count": len(collected)},
            clinic_id=sess.clinic_id,
        )

        record_metric("chat.intake_completed", 1)
        logger.info("Intake completo: session=%s steps=%d", session_id, len(collected))

    # ── DISCONNECT ───────────────────────────

    def on_disconnect(self):
        """Limpa referência de socket e notifica a clínica."""
        session_id = disconnect_socket(request.sid)
        if session_id:
            sess = get_session(session_id)
            if sess:
                leave_room(self._clinic_room(sess.clinic_id))
                emit(
                    "patient_disconnected",
                    {"session_id": session_id},
                    room=self._clinic_room(sess.clinic_id),
                )

        logger.debug("WS /chat disconnect: sid=%s session=%s", request.sid, session_id)


# ── MONITOR: Staff da clínica entra na room ──

class ChatMonitorNamespace(Namespace):
    """
    Namespace /chat-monitor para staff da clínica acompanhar intakes em tempo real.
    Requer autenticação Flask-Login.
    """

    def on_connect(self):
        if not current_user.is_authenticated:
            logger.warning("WS /chat-monitor rejeitado: não autenticado.")
            return False
        logger.debug("Staff conectado ao monitor: sid=%s", request.sid)

    def on_watch_clinic(self, data: dict[str, Any]):
        """Staff entra na room da clínica para receber eventos de progresso."""
        clinic_id = getattr(g, "clinic_id", None) or (data or {}).get("clinic_id")
        if not clinic_id:
            emit("error", {"message": "clinic_id ausente."})
            return

        room = f"clinic:{clinic_id}"
        join_room(room)
        emit("watching", {
            "clinic_id": clinic_id,
            "active_sessions": get_active_sessions_count(clinic_id),
        })
        logger.info("Staff watching clinic=%s sid=%s", clinic_id, request.sid)

    def on_disconnect(self):
        logger.debug("Staff desconectado do monitor: sid=%s", request.sid)
