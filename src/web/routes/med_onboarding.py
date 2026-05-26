# src/web/routes/med_onboarding.py
"""Sprint C MVP: endpoints do onboarding medico.

Wraps simples sobre `medical_profile_repository`. Restrito a Medico
(e Admin global) pois o perfil pertence ao proprio medico autenticado.

Upload real de documentos ainda nao existe (onda 2 desta sprint). O
endpoint aceita URLs nos campos *_url se fornecidas, mas o frontend
hoje envia apenas os dados textuais.
"""

from __future__ import annotations

import logging

from flask import Blueprint
from flask_login import current_user

from src.repositories import medical_profile_repository as profile_repo
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _require_json_csrf,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.med_onboarding")

med_onboarding_bp = Blueprint("med_onboarding", __name__, url_prefix="/api/v1/med")


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
