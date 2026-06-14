# src/services/payment_service.py
"""
Servico financeiro: emitir cobrancas Pix, confirmar pagamentos e conciliar
via webhook.

O provedor padrao e `manual` — gera um BR Code Pix estatico usando chave/nome
configurados em tenant_integrations. Integracao com provedores externos
(Mercado Pago, Gerencianet, PagBank) pode ser plugada substituindo o
provider no build do payload.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from src.infra.audit import log_audit_event
from src.integrations.pix import build_pix_payload
from src.repositories import payment_repository as repo
from src.repositories.tenant_settings_repository import get_integrations
from src.repositories.tenancy_repository import get_clinic_public_label

logger = logging.getLogger("cannabia.payments")

DEFAULT_EXPIRATION_HOURS = 24


def _resolve_pix_config(tenant_id: int) -> dict[str, Any]:
    """
    Resolve chave Pix + nome recebedor para o tenant.
    Usa tenant_integrations.provider_metadata quando disponivel
    (fallback para nome do tenant).
    """
    integ = get_integrations(tenant_id, decrypted=True) or {}
    label = get_clinic_public_label(integ.get("tenant_id") or tenant_id)

    # Pix key e nome podem ser customizados via tenant_integrations.
    # Nao temos colunas dedicadas ainda; usamos verify_token_encrypted? Nao.
    # Aqui leitura direta nao existe -> retornar estrutura vazia forca fallback.
    return {
        "pix_key": integ.get("pix_key") if isinstance(integ, dict) else None,
        "merchant_name": (integ.get("merchant_name") if isinstance(integ, dict) else None) or label,
        "merchant_city": (integ.get("merchant_city") if isinstance(integ, dict) else None) or "BRASIL",
    }


def issue_pix_charge(
    *,
    tenant_id: int,
    clinic_id: int,
    amount_cents: int,
    description: Optional[str] = None,
    patient_id: Optional[int] = None,
    prescription_id: Optional[int] = None,
    subscription_id: Optional[int] = None,
    pix_key: Optional[str] = None,
    merchant_name: Optional[str] = None,
    merchant_city: Optional[str] = None,
    expiration_hours: int = DEFAULT_EXPIRATION_HOURS,
    created_by: Optional[int] = None,
) -> dict[str, Any]:
    """
    Emite uma cobranca Pix (manual) para o tenant.

    Retorna o payment_request com o BR Code (pix_payload) pronto para copia e cola.
    """
    if amount_cents is None or int(amount_cents) <= 0:
        raise ValueError("amount_cents deve ser positivo.")

    cfg = _resolve_pix_config(tenant_id)
    pix_key = pix_key or cfg["pix_key"]
    merchant_name = (merchant_name or cfg["merchant_name"] or "CANNABIA").upper()
    merchant_city = (merchant_city or cfg["merchant_city"] or "BRASIL").upper()

    if not pix_key:
        raise ValueError(
            "Chave Pix nao configurada para este tenant. "
            "Defina pix_key em tenant_integrations ou informe explicitamente."
        )

    # txid e alfanumerico, 1..25; usamos uuid hex sem hifens truncado
    txid = uuid.uuid4().hex[:25]
    external_id = f"cbn-{txid}"

    pix_payload = build_pix_payload(
        pix_key=pix_key,
        merchant_name=_sanitize_ascii(merchant_name),
        merchant_city=_sanitize_ascii(merchant_city),
        amount_cents=int(amount_cents),
        txid=txid,
        description=_sanitize_ascii(description) if description else None,
    )

    expires_at = datetime.now(timezone.utc) + timedelta(hours=int(expiration_hours))

    request = repo.create_payment_request(
        tenant_id=tenant_id,
        clinic_id=clinic_id,
        amount_cents=int(amount_cents),
        description=description,
        patient_id=patient_id,
        prescription_id=prescription_id,
        subscription_id=subscription_id,
        method="pix",
        provider="manual",
        external_id=external_id,
        pix_payload=pix_payload,
        pix_key=pix_key,
        expires_at=expires_at,
        created_by=created_by,
        provider_metadata={
            "merchant_name": merchant_name,
            "merchant_city": merchant_city,
            "txid": txid,
        },
    )

    log_audit_event(
        action="payment_charge_issued",
        resource_type="payment_request",
        resource_id=str(request["id"]),
        details={
            "tenant_id": tenant_id,
            "amount_cents": int(amount_cents),
            "method": "pix",
            "patient_id": patient_id,
        },
    )

    return request


def confirm_payment(
    request_id: int,
    *,
    amount_cents: Optional[int] = None,
    provider: str = "manual",
    provider_event_id: Optional[str] = None,
    payer_name: Optional[str] = None,
    payer_document: Optional[str] = None,
    raw_payload: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Confirma recebimento manual de uma cobranca. Marca status=paid e registra
    uma payment_transaction associada.
    """
    payment = repo.get_payment_request(request_id)
    if not payment:
        raise ValueError(f"Cobranca {request_id} nao encontrada.")
    if payment["status"] == "paid":
        return payment
    if payment["status"] in ("cancelled", "refunded"):
        raise ValueError(
            f"Cobranca {request_id} esta {payment['status']}; nao pode ser confirmada."
        )

    paid_amount = int(amount_cents) if amount_cents is not None else int(payment["amount_cents"])

    updated = repo.mark_payment_paid(
        request_id,
        paid_amount_cents=paid_amount,
        provider_ref=provider_event_id,
    )

    repo.record_transaction(
        payment_request_id=request_id,
        tenant_id=payment["tenant_id"],
        provider=provider,
        provider_event_id=provider_event_id or f"manual-{uuid.uuid4().hex[:12]}",
        event_type="charge.paid",
        status="succeeded",
        amount_cents=paid_amount,
        payer_name=payer_name,
        payer_document=payer_document,
        raw_payload=raw_payload,
    )

    log_audit_event(
        action="payment_confirmed",
        resource_type="payment_request",
        resource_id=str(request_id),
        details={
            "paid_amount_cents": paid_amount,
            "provider": provider,
            "provider_event_id": provider_event_id,
        },
    )

    # R10: trilha financeira transversal (confirmacao manual tambem recebe).
    _emit_payment_billing_event(
        payment,
        "payment_received",
        {
            "provider": provider,
            "provider_event_id": provider_event_id,
            "amount_cents": paid_amount,
            "source": "manual_confirm",
        },
    )

    return updated or payment


def cancel_payment(request_id: int) -> Optional[dict[str, Any]]:
    payment = repo.get_payment_request(request_id)
    if not payment:
        raise ValueError(f"Cobranca {request_id} nao encontrada.")
    if payment["status"] != "pending":
        raise ValueError(f"Cobranca {request_id} nao esta pendente (status={payment['status']}).")
    cancelled = repo.cancel_payment_request(request_id)
    log_audit_event(
        action="payment_cancelled",
        resource_type="payment_request",
        resource_id=str(request_id),
        details={},
    )
    return cancelled


def list_payments(
    *,
    tenant_id: int,
    status: Optional[str] = None,
    patient_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return repo.list_payment_requests(
        tenant_id=tenant_id,
        status=status,
        patient_id=patient_id,
        limit=limit,
        offset=offset,
    )


def get_payment_detail(request_id: int) -> Optional[dict[str, Any]]:
    payment = repo.get_payment_request(request_id)
    if not payment:
        return None
    payment["transactions"] = repo.list_transactions(request_id)
    return payment


def tenant_totals(tenant_id: int) -> dict[str, Any]:
    return repo.totals_by_status(tenant_id)


# ═══════════════════════════════════════════════════════════════════════════
# Webhook de provedor externo (reconciliacao automatica)
# ═══════════════════════════════════════════════════════════════════════════

def process_webhook_event(
    *,
    provider: str,
    event_type: str,
    provider_event_id: Optional[str],
    external_id: str,
    amount_cents: int,
    status: str,
    payer_name: Optional[str] = None,
    payer_document: Optional[str] = None,
    payer_account: Optional[str] = None,
    raw_payload: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Processa um evento de pagamento normalizado vindo de webhook externo.

    O `external_id` deve corresponder ao `external_id` da payment_requests
    (provedor deve receber e ecoar o valor ao criar a cobranca).

    Idempotente via (provider, provider_event_id).
    """
    payment = repo.get_payment_request_by_external_id(external_id)
    if not payment:
        raise ValueError(f"Cobranca externa {external_id} nao encontrada.")

    expected_cents = int(payment["amount_cents"])
    received_cents = int(amount_cents)

    # FIN-1 (doc 30 R1): so quita se o valor recebido cobre o valor cobrado.
    # Underpayment (valor menor que o devido) NAO marca paid; vira uma
    # transacao charge.underpaid pendente de revisao humana. Overpayment
    # (valor >= devido) quita normalmente.
    is_success_signal = status == "succeeded"
    underpaid = is_success_signal and received_cents < expected_cents

    tx_event_type = "charge.underpaid" if underpaid else event_type
    tx_status = "needs_review" if underpaid else status

    transaction = repo.record_transaction(
        payment_request_id=payment["id"],
        tenant_id=payment["tenant_id"],
        provider=provider,
        provider_event_id=provider_event_id,
        event_type=tx_event_type,
        status=tx_status,
        amount_cents=received_cents,
        payer_name=payer_name,
        payer_document=payer_document,
        payer_account=payer_account,
        raw_payload=raw_payload,
    )

    reconciled = False
    if is_success_signal and not underpaid and payment["status"] != "paid":
        repo.mark_payment_paid(
            payment["id"],
            paid_amount_cents=received_cents,
            provider_ref=provider_event_id,
        )
        reconciled = True
        log_audit_event(
            action="payment_reconciled",
            resource_type="payment_request",
            resource_id=str(payment["id"]),
            details={
                "provider": provider,
                "provider_event_id": provider_event_id,
                "amount_cents": received_cents,
            },
        )
        # R10: trilha financeira transversal.
        _emit_payment_billing_event(
            payment,
            "payment_received",
            {
                "provider": provider,
                "provider_event_id": provider_event_id,
                "amount_cents": received_cents,
                "source": "webhook",
            },
        )
    elif underpaid:
        log_audit_event(
            action="payment_underpaid",
            resource_type="payment_request",
            resource_id=str(payment["id"]),
            details={
                "provider": provider,
                "provider_event_id": provider_event_id,
                "expected_cents": expected_cents,
                "received_cents": received_cents,
            },
        )
        _emit_payment_billing_event(
            payment,
            "payment_failed",
            {
                "reason": "underpaid",
                "provider": provider,
                "provider_event_id": provider_event_id,
                "expected_cents": expected_cents,
                "received_cents": received_cents,
            },
        )
    elif status == "failed":
        log_audit_event(
            action="payment_failed",
            resource_type="payment_request",
            resource_id=str(payment["id"]),
            details={
                "provider": provider,
                "provider_event_id": provider_event_id,
                "amount_cents": received_cents,
            },
        )
        _emit_payment_billing_event(
            payment,
            "payment_failed",
            {
                "reason": "provider_failed",
                "provider": provider,
                "provider_event_id": provider_event_id,
                "amount_cents": received_cents,
            },
        )

    return {
        "payment_request_id": payment["id"],
        "transaction_id": transaction["id"] if transaction else None,
        "reconciled": reconciled,
        "underpaid": underpaid,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _emit_payment_billing_event(
    payment: dict[str, Any], event_type: str, details: dict[str, Any]
) -> None:
    """
    Emite billing_events.payment_received/payment_failed para a cobranca (R10).

    Falha de logging nunca derruba a operacao financeira principal.
    """
    clinic_id = payment.get("clinic_id")
    if not clinic_id:
        return
    try:
        from src.services.billing_service import emit_billing_event

        enriched = {"payment_request_id": payment.get("id"), **details}
        emit_billing_event(int(clinic_id), event_type, enriched)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao emitir billing event %s: %s", event_type, exc)


def _sanitize_ascii(value: str) -> str:
    """Remove acentos simples e chars fora de ASCII; Pix BR Code espera ASCII."""
    import unicodedata

    if not value:
        return value
    norm = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(ch for ch in norm if ord(ch) < 128)
    return ascii_value
