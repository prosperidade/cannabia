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
CONVERSATION_ROLES = ("Admin", "AdminClinica", "Medico", "Recepcao")


@conversations_bp.get("/conversations")
@api_role_required(*CONVERSATION_ROLES)
def list_convs():
    """Envelope canonico {items, total, limit, offset, has_more}.

    Sprint D Q2: removido `?legacy=1` (Sunset 2026-08-01).
    """
    from src.repositories.conversation_repository import list_conversations
    from src.web.pagination import paginated_response, parse_pagination

    status = request.args.get("status") or None
    search = request.args.get("search") or None

    try:
        limit, offset, include_total = parse_pagination(request)
    except ValueError as exc:
        from src.web.routes.api_v1 import _pagination_error
        return _pagination_error(exc)

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
@api_role_required(*CONVERSATION_ROLES)
def unread_count():
    from src.repositories.conversation_repository import get_unread_count

    return _success({"unread_count": get_unread_count()})


@conversations_bp.get("/conversations/<int:conversation_id>")
@api_role_required(*CONVERSATION_ROLES)
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
@api_role_required(*CONVERSATION_ROLES)
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
@api_role_required(*CONVERSATION_ROLES)
def mark_read(conversation_id: int):
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    from src.repositories.conversation_repository import mark_conversation_read

    mark_conversation_read(conversation_id)
    return _success({"marked": True})


@conversations_bp.patch("/conversations/<int:conversation_id>/close")
@api_role_required(*CONVERSATION_ROLES)
def close_conv(conversation_id: int):
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    from src.repositories.conversation_repository import close_conversation

    close_conversation(conversation_id)
    return _success({"closed": True})


@conversations_bp.patch("/conversations/<int:conversation_id>/assign")
@api_role_required("Admin", "AdminClinica", "Medico")
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
