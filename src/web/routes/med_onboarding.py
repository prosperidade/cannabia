# src/web/routes/med_onboarding.py
"""Sprint C MVP: endpoints do onboarding medico.

Wraps simples sobre `medical_profile_repository`. Restrito a Medico
(e Admin global) pois o perfil pertence ao proprio medico autenticado.

Sprint D M1 (onda 2): endpoint POST /upload/<field> aceita multipart
e grava o documento via `src.infra.storage` (provider configuravel:
noop|local|r2). A URL gerada e persistida em `medical_profiles.<field>_url`.
"""

from __future__ import annotations

import logging

from flask import Blueprint, request
from flask_login import current_user

from src.infra import storage
from src.repositories import medical_profile_repository as profile_repo
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _require_json_csrf,
    _success,
    api_role_required,
)
from src.web.routes.auth import validate_csrf_value

logger = logging.getLogger("cannabia.med_onboarding")

med_onboarding_bp = Blueprint("med_onboarding", __name__, url_prefix="/api/v1/med")

UPLOAD_FIELDS = ("photo", "crm_doc", "diploma")
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# mime -> extensao canonica (usada na key do storage)
ALLOWED_MIMES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}


@med_onboarding_bp.get("/onboarding")
@api_role_required("Admin", "Medico")
def get_onboarding():
    user_id = int(current_user.id)
    row = profile_repo.get_by_user_id(user_id)
    return _success(profile_repo.serialize(row))


@med_onboarding_bp.post("/onboarding/complete")
@api_role_required("Admin", "Medico")
def complete_onboarding():
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    user_id = int(current_user.id)

    full_name = (payload.get("full_name") or "").strip()
    crm = (payload.get("crm") or "").strip()
    specialty = (payload.get("specialty") or "").strip()

    if not full_name:
        return _error("validation_error", "Nome completo e obrigatorio.", 422)
    if not crm:
        return _error("validation_error", "CRM e obrigatorio.", 422)
    if not specialty:
        return _error("validation_error", "Especialidade e obrigatoria.", 422)

    profile_repo.upsert(user_id, payload)
    row = profile_repo.mark_completed(user_id)
    return _success(profile_repo.serialize(row))


@med_onboarding_bp.post("/onboarding/upload/<field>")
@api_role_required("Admin", "Medico")
def upload_document(field: str):
    """Sprint D M1: upload multipart de documento de credenciamento.

    field in {photo, crm_doc, diploma}. Persiste a URL em
    medical_profiles.<field>_url. Provider via STORAGE_PROVIDER.
    """
    if field not in UPLOAD_FIELDS:
        return _error(
            "validation_error",
            f"field invalido: {field}. Permitidos: {', '.join(UPLOAD_FIELDS)}.",
            422,
        )

    sent_csrf = request.headers.get("X-CSRF-Token") or ""
    if not validate_csrf_value(sent_csrf):
        return _error("csrf_invalid", "CSRF invalido.", 400)

    uploaded = request.files.get("file")
    if uploaded is None:
        return _error("validation_error", "Arquivo ausente (campo 'file').", 422)

    content = uploaded.read()
    if not content:
        return _error("validation_error", "Arquivo vazio.", 422)
    if len(content) > MAX_FILE_SIZE:
        mb = MAX_FILE_SIZE // (1024 * 1024)
        return _error("file_too_large", f"Arquivo excede {mb}MB.", 413)

    content_type = (uploaded.content_type or "").lower().strip()
    extension = ALLOWED_MIMES.get(content_type)
    if extension is None:
        return _error(
            "validation_error",
            f"Tipo nao permitido: {content_type or 'desconhecido'}. "
            "Use PDF, JPG ou PNG.",
            422,
        )

    user_id = int(current_user.id)
    key = f"onboarding/{user_id}/{field}{extension}"

    try:
        url = storage.get_backend().upload(
            key=key, content=content, content_type=content_type
        )
    except storage.StorageNotConfigured as exc:
        logger.warning("storage.not_configured field=%s reason=%s", field, exc)
        return _error("storage_not_configured", str(exc), 503)
    except storage.StorageError as exc:
        logger.exception("storage.upload_failed field=%s", field)
        return _error("storage_error", str(exc), 502)

    profile_repo.upsert(user_id, {f"{field}_url": url})
    return _success({"field": field, "url": url})
