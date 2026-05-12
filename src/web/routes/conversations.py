"""Endpoints para inbox clinica — conversas e mensagens."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from flask_login import current_user

from src.infra.security import get_effective_roles, normalize_role_name
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _require_json_csrf,
    _serialize,
    _success,
    api_auth_required,
    api_role_required,
)

conversations_bp = Blueprint("conversations", __name__, url_prefix="/api/v1")


@conversations_bp.get("/conversations")
@api_role_required("Admin", "Medico", "Atendente")
def list_convs():
    """Sprint 2 Track Page: envelope canonico {items, total, limit, offset, has_more}.

    `?legacy=1` -> compat path (lista nua, max=100).
    """
    from src.repositories.conversation_repository import list_conversations
    from src.web.pagination import bare_legacy_response, paginated_response, parse_pagination

    status = request.args.get("status") or None
    search = request.args.get("search") or None

    try:
        limit, offset, include_total, legacy_mode = parse_pagination(request)
    except ValueError as exc:
        from src.web.routes.api_v1 import _pagination_error
        return _pagination_error(exc)

    if legacy_mode:
        # Compat path: lista nua com cap antigo (max=100).
        # DEPRECATED Sprint 3 — Sunset 2026-08-01.
        from src.web.routes.api_v1 import _apply_deprecation_headers
        legacy_limit = max(1, min(limit, 100))
        convs = list_conversations(status=status, search=search, limit=legacy_limit)
        return _apply_deprecation_headers(
            _success(bare_legacy_response(_serialize(convs)))
        )

    result = list_conversations(
        status=status,
        search=search,
        limit=limit,
        offset=offset,
        include_total=include_total,
        paginated=True,
    )
    envelope = paginated_response(
        _serialize(result["items"]),
        limit=limit,
        offset=offset,
        total=result["total"],
        has_more=result["has_more"],
    )
    return _success(envelope)


@conversations_bp.get("/conversations/unread")
@api_role_required("Admin", "Medico", "Atendente")
def unread_count():
    from src.repositories.conversation_repository import get_unread_count

    return _success({"unread_count": get_unread_count()})


@conversations_bp.get("/conversations/<int:conversation_id>")
@api_role_required("Admin", "Medico", "Atendente")
def conv_detail(conversation_id: int):
    from src.repositories.conversation_repository import get_conversation, list_messages

    conv = get_conversation(conversation_id)
    if not conv:
        return _error("not_found", "Conversa nao encontrada.", 404)

    try:
        limit = int(request.args.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100
    before_id = request.args.get("before_id")
    before_id = int(before_id) if before_id else None

    messages = list_messages(conversation_id, limit=limit, before_id=before_id)
    return _success(_serialize({
        "conversation": conv,
        "messages": messages,
    }))


@conversations_bp.post("/conversations/<int:conversation_id>/messages")
@api_role_required("Admin", "Medico", "Atendente")
def send_message(conversation_id: int):
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    message_text = (payload.get("message") or "").strip()
    if not message_text:
        return _error("validation_error", "message e obrigatorio.", 422)

    from src.services.conversation_service import send_outbound_message

    try:
        result = send_outbound_message(
            g.clinic_id,
            conversation_id,
            message_text,
            sender_name=getattr(current_user, "username", None),
            sender_user_id=int(current_user.id),
        )
        return _success(result, status=201)
    except ValueError as exc:
        return _error("not_found", str(exc), 404)


@conversations_bp.patch("/conversations/<int:conversation_id>/read")
@api_role_required("Admin", "Medico", "Atendente")
def mark_read(conversation_id: int):
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    from src.repositories.conversation_repository import mark_conversation_read

    mark_conversation_read(conversation_id)
    return _success({"marked": True})


@conversations_bp.patch("/conversations/<int:conversation_id>/close")
@api_role_required("Admin", "Medico", "Atendente")
def close_conv(conversation_id: int):
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    from src.repositories.conversation_repository import close_conversation

    close_conversation(conversation_id)
    return _success({"closed": True})


@conversations_bp.patch("/conversations/<int:conversation_id>/assign")
@api_role_required("Admin", "Medico")
def assign_conv(conversation_id: int):
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    user_id = payload.get("user_id")
    if not user_id:
        return _error("validation_error", "user_id e obrigatorio.", 422)

    from src.repositories.conversation_repository import assign_conversation

    assign_conversation(conversation_id, int(user_id))
    return _success({"assigned": True})
