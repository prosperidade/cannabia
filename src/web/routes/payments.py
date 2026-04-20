# src/web/routes/payments.py
"""
Endpoints do dominio financeiro: emissao de cobrancas, consulta, confirmacao
manual e webhook de provedor externo.

Autenticacao:
  - Endpoints operacionais exigem sessao autenticada (Admin, Medico, Atendente).
  - Webhook externo nao exige autenticacao; valida assinatura por provedor.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, g, request
from flask_login import current_user

from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _require_json_csrf,
    _serialize,
    _success,
    api_auth_required,
    api_role_required,
)

logger = logging.getLogger("cannabia.payments.routes")

payments_bp = Blueprint("payments", __name__, url_prefix="/api/v1")


# ═══════════════════════════════════════════════════════════════════════════
# Leitura: lista + detalhe + totais
# ═══════════════════════════════════════════════════════════════════════════

@payments_bp.get("/payments")
@api_role_required("Admin", "Medico", "Atendente")
def list_payments():
    from src.services.payment_service import list_payments as svc_list

    status = request.args.get("status") or None
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 200))

    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    patient_id = request.args.get("patient_id")
    patient_id = int(patient_id) if patient_id else None

    items = svc_list(
        tenant_id=g.tenant_id,
        status=status,
        patient_id=patient_id,
        limit=limit,
        offset=offset,
    )
    return _success(_serialize(items), meta={"limit": limit, "offset": offset, "count": len(items)})


@payments_bp.get("/payments/summary")
@api_role_required("Admin", "Medico", "Atendente")
def payment_summary():
    from src.services.payment_service import tenant_totals

    return _success(_serialize(tenant_totals(g.tenant_id)))


@payments_bp.get("/payments/<int:request_id>")
@api_role_required("Admin", "Medico", "Atendente")
def payment_detail(request_id: int):
    from src.services.payment_service import get_payment_detail

    payment = get_payment_detail(request_id)
    if not payment or payment.get("tenant_id") != g.tenant_id:
        return _error("not_found", "Cobranca nao encontrada.", 404)
    return _success(_serialize(payment))


# ═══════════════════════════════════════════════════════════════════════════
# Emissao de Pix
# ═══════════════════════════════════════════════════════════════════════════

@payments_bp.post("/payments/pix")
@api_role_required("Admin", "Medico", "Atendente")
def issue_pix():
    """
    POST /api/v1/payments/pix

    Body JSON:
        amount_cents      (int, obrigatorio)
        description       (str, opcional)
        patient_id        (int, opcional)
        prescription_id   (int, opcional)
        pix_key           (str, opcional)   — sobrescreve chave padrao do tenant
        merchant_name     (str, opcional)
        merchant_city     (str, opcional)
        expiration_hours  (int, opcional, default 24)
    """
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    from src.services.payment_service import issue_pix_charge

    payload = _json_payload()
    amount_cents = payload.get("amount_cents")
    if amount_cents is None:
        return _error("validation_error", "amount_cents e obrigatorio.", 422)

    try:
        created = issue_pix_charge(
            tenant_id=g.tenant_id,
            clinic_id=g.clinic_id,
            amount_cents=int(amount_cents),
            description=payload.get("description"),
            patient_id=payload.get("patient_id"),
            prescription_id=payload.get("prescription_id"),
            subscription_id=payload.get("subscription_id"),
            pix_key=payload.get("pix_key"),
            merchant_name=payload.get("merchant_name"),
            merchant_city=payload.get("merchant_city"),
            expiration_hours=int(payload.get("expiration_hours") or 24),
            created_by=int(current_user.id) if current_user.is_authenticated else None,
        )
        return _success(_serialize(created), status=201)
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)
    except Exception as exc:
        logger.error("Erro ao emitir Pix: %s", exc, exc_info=True)
        return _error("internal_error", "Falha ao emitir cobranca.", 500)


# ═══════════════════════════════════════════════════════════════════════════
# Confirmacao manual (fora de webhook)
# ═══════════════════════════════════════════════════════════════════════════

@payments_bp.post("/payments/<int:request_id>/confirm")
@api_role_required("Admin", "Medico", "Atendente")
def confirm_payment(request_id: int):
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    from src.services.payment_service import confirm_payment as svc_confirm, get_payment_detail

    existing = get_payment_detail(request_id)
    if not existing or existing.get("tenant_id") != g.tenant_id:
        return _error("not_found", "Cobranca nao encontrada.", 404)

    payload = _json_payload()
    try:
        updated = svc_confirm(
            request_id,
            amount_cents=payload.get("amount_cents"),
            provider="manual",
            payer_name=payload.get("payer_name"),
            payer_document=payload.get("payer_document"),
        )
        return _success(_serialize(updated))
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)


@payments_bp.post("/payments/<int:request_id>/cancel")
@api_role_required("Admin", "Atendente")
def cancel_payment(request_id: int):
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    from src.services.payment_service import cancel_payment as svc_cancel, get_payment_detail

    existing = get_payment_detail(request_id)
    if not existing or existing.get("tenant_id") != g.tenant_id:
        return _error("not_found", "Cobranca nao encontrada.", 404)

    try:
        cancelled = svc_cancel(request_id)
        return _success(_serialize(cancelled))
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)


# ═══════════════════════════════════════════════════════════════════════════
# Webhook externo (reconciliacao automatica)
# ═══════════════════════════════════════════════════════════════════════════

def _verify_payment_webhook_signature(provider_slug: str, raw_body: bytes) -> tuple[bool, str | None]:
    """
    Valida assinatura HMAC-SHA256 do webhook via cabecalho X-Signature.

    A chave e lida de PAYMENT_WEBHOOK_SECRET_<PROVIDER_UPPER> no ambiente.
    Se a chave nao estiver configurada:
      - em producao (FLASK_ENV=production) rejeita com False
      - fora de producao aceita mas marca signature_ok=False no log
    """
    import hashlib
    import hmac
    import os

    header_sig = (
        request.headers.get("X-Signature")
        or request.headers.get("X-Hub-Signature-256")
        or request.headers.get("X-Webhook-Signature")
        or ""
    ).strip()

    secret_env = f"PAYMENT_WEBHOOK_SECRET_{provider_slug.upper()}"
    secret = os.getenv(secret_env, "")

    if not secret:
        if os.getenv("FLASK_ENV") == "production":
            return False, f"Secret {secret_env} nao configurada."
        logger.warning(
            "Webhook %s sem secret configurada (%s). Aceito em modo dev.",
            provider_slug, secret_env,
        )
        return False, "dev_mode_no_secret"

    if not header_sig:
        return False, "missing_signature"

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    # Alguns provedores prefixam "sha256=", toleramos
    received = header_sig.split("=", 1)[-1] if "=" in header_sig else header_sig

    if hmac.compare_digest(expected, received):
        return True, None
    return False, "invalid_signature"


@payments_bp.post("/payments/webhook/<provider>")
def payment_webhook(provider: str):
    """
    Recebe eventos de provedor de pagamento externo.

    Validacao de assinatura:
      - Header: X-Signature (ou X-Hub-Signature-256, X-Webhook-Signature)
      - Secret: PAYMENT_WEBHOOK_SECRET_<PROVIDER_UPPER> no ambiente
      - Em FLASK_ENV=production, eventos sem assinatura valida sao REJEITADOS

    Corpo JSON obrigatorio:
        event_type         (str)
        provider_event_id  (str)
        external_id        (str)   — id ecoado pelo provedor (txid local)
        amount_cents       (int)
        status             (str)   — succeeded, failed, refunded
        payer_name         (str, opcional)
        payer_document     (str, opcional)
        payer_account      (str, opcional)
    """
    from src.repositories import payment_repository as repo
    from src.services.payment_service import process_webhook_event

    provider_slug = (provider or "manual").lower()
    raw_body = request.get_data() or b""
    signature_ok, sig_error = _verify_payment_webhook_signature(provider_slug, raw_body)

    # Em producao bloqueia quando invalido
    import os
    if not signature_ok and os.getenv("FLASK_ENV") == "production":
        try:
            repo.log_webhook(
                provider=provider_slug,
                signature_ok=False,
                status_code=401,
                body=request.get_json(silent=True) or {},
                headers=dict(request.headers),
                error_message=sig_error,
            )
        except Exception:
            pass
        return _error("invalid_signature", sig_error or "Assinatura invalida.", 401)

    body = request.get_json(silent=True) or {}
    status_code = 200
    error_message = None

    try:
        external_id = body.get("external_id")
        amount_cents = body.get("amount_cents")
        event_type = body.get("event_type") or "charge.paid"
        status = body.get("status") or "succeeded"
        if not external_id or amount_cents is None:
            status_code = 422
            error_message = "external_id e amount_cents sao obrigatorios."
            return _error("validation_error", error_message, 422)

        result = process_webhook_event(
            provider=provider_slug,
            event_type=event_type,
            provider_event_id=body.get("provider_event_id"),
            external_id=external_id,
            amount_cents=int(amount_cents),
            status=status,
            payer_name=body.get("payer_name"),
            payer_document=body.get("payer_document"),
            payer_account=body.get("payer_account"),
            raw_payload=body,
        )
        return _success(result)
    except ValueError as exc:
        status_code = 404
        error_message = str(exc)
        return _error("not_found", error_message, 404)
    except Exception as exc:
        status_code = 500
        error_message = str(exc)
        logger.error("Erro ao processar webhook %s: %s", provider_slug, exc, exc_info=True)
        return _error("internal_error", "Falha ao processar webhook.", 500)
    finally:
        try:
            repo.log_webhook(
                provider=provider_slug,
                signature_ok=signature_ok,
                status_code=status_code,
                body=body,
                headers=dict(request.headers),
                error_message=error_message or sig_error,
            )
        except Exception as log_err:
            logger.warning("Falha ao registrar webhook log: %s", log_err)
