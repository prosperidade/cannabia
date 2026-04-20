"""Testes do payment_service: emissao, confirmacao e reconciliacao via webhook."""

from unittest.mock import patch, MagicMock

import pytest


def _base_payment(**overrides):
    base = {
        "id": 1,
        "tenant_id": 10,
        "clinic_id": 1,
        "patient_id": None,
        "external_id": "cbn-abc123",
        "amount_cents": 2500,
        "status": "pending",
        "provider": "manual",
        "method": "pix",
        "paid_amount_cents": None,
        "paid_at": None,
    }
    base.update(overrides)
    return base


def test_issue_pix_charge_requires_positive_amount():
    from src.services import payment_service

    with pytest.raises(ValueError, match="positivo"):
        payment_service.issue_pix_charge(
            tenant_id=1, clinic_id=1, amount_cents=0,
        )


def test_issue_pix_charge_requires_pix_key():
    from src.services import payment_service

    with patch.object(payment_service, "_resolve_pix_config", return_value={
        "pix_key": None,
        "merchant_name": "Clinica",
        "merchant_city": "Sao Paulo",
    }):
        with pytest.raises(ValueError, match="Chave Pix"):
            payment_service.issue_pix_charge(
                tenant_id=1, clinic_id=1, amount_cents=5000,
            )


def test_issue_pix_charge_builds_payload_and_persists():
    from src.services import payment_service

    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return {**_base_payment(), **kwargs, "id": 42}

    with patch.object(payment_service, "_resolve_pix_config", return_value={
        "pix_key": "clinica@example.com",
        "merchant_name": "Clinica X",
        "merchant_city": "Sao Paulo",
    }), patch.object(payment_service.repo, "create_payment_request", side_effect=fake_create), \
         patch.object(payment_service, "log_audit_event"):
        result = payment_service.issue_pix_charge(
            tenant_id=10, clinic_id=1, amount_cents=12345,
            description="Consulta", created_by=99,
        )

    assert result["id"] == 42
    assert captured["amount_cents"] == 12345
    assert captured["external_id"].startswith("cbn-")
    assert captured["pix_payload"].startswith("000201")
    assert captured["created_by"] == 99


def test_confirm_payment_marks_paid_and_records_transaction():
    from src.services import payment_service

    payment = _base_payment()

    calls = {}

    def fake_record(**kwargs):
        calls["transaction"] = kwargs
        return {"id": 7, **kwargs}

    def fake_mark(request_id, **kwargs):
        calls["mark"] = {"id": request_id, **kwargs}
        return {**payment, "status": "paid", "paid_amount_cents": kwargs["paid_amount_cents"]}

    with patch.object(payment_service.repo, "get_payment_request", return_value=payment), \
         patch.object(payment_service.repo, "mark_payment_paid", side_effect=fake_mark), \
         patch.object(payment_service.repo, "record_transaction", side_effect=fake_record), \
         patch.object(payment_service, "log_audit_event"):
        result = payment_service.confirm_payment(
            payment["id"], amount_cents=2500, payer_name="Joao",
        )

    assert result["status"] == "paid"
    assert calls["mark"]["paid_amount_cents"] == 2500
    assert calls["transaction"]["status"] == "succeeded"
    assert calls["transaction"]["amount_cents"] == 2500


def test_confirm_payment_rejects_cancelled():
    from src.services import payment_service

    payment = _base_payment(status="cancelled")
    with patch.object(payment_service.repo, "get_payment_request", return_value=payment):
        with pytest.raises(ValueError, match="cancelled"):
            payment_service.confirm_payment(payment["id"])


def test_confirm_payment_idempotent_when_already_paid():
    from src.services import payment_service

    payment = _base_payment(status="paid", paid_amount_cents=2500)
    with patch.object(payment_service.repo, "get_payment_request", return_value=payment):
        result = payment_service.confirm_payment(payment["id"])
    assert result["status"] == "paid"


def test_process_webhook_event_reconciles_pending_to_paid():
    from src.services import payment_service

    payment = _base_payment()

    def fake_record(**kwargs):
        return {"id": 99, **kwargs}

    with patch.object(payment_service.repo, "get_payment_request_by_external_id", return_value=payment), \
         patch.object(payment_service.repo, "record_transaction", side_effect=fake_record) as rec, \
         patch.object(payment_service.repo, "mark_payment_paid", return_value={**payment, "status": "paid"}) as mark, \
         patch.object(payment_service, "log_audit_event"):
        result = payment_service.process_webhook_event(
            provider="mercado_pago",
            event_type="charge.paid",
            provider_event_id="evt-1",
            external_id=payment["external_id"],
            amount_cents=2500,
            status="succeeded",
            payer_name="Maria",
        )

    assert result["payment_request_id"] == 1
    assert result["transaction_id"] == 99
    rec.assert_called_once()
    mark.assert_called_once()


def test_process_webhook_event_missing_payment_raises():
    from src.services import payment_service

    with patch.object(payment_service.repo, "get_payment_request_by_external_id", return_value=None):
        with pytest.raises(ValueError, match="nao encontrada"):
            payment_service.process_webhook_event(
                provider="manual",
                event_type="charge.paid",
                provider_event_id="x",
                external_id="cbn-missing",
                amount_cents=100,
                status="succeeded",
            )


def test_sanitize_ascii_strips_accents():
    from src.services.payment_service import _sanitize_ascii

    assert _sanitize_ascii("São Paulo") == "Sao Paulo"
    assert _sanitize_ascii("CLÍNICA AÇAÍ") == "CLINICA ACAI"
    assert _sanitize_ascii("") == ""
