"""
FIN-2 (doc 30 R2 / 29.6 R2): LGPD do trilho de pagamento.

Cobre:
1. mask_document — 3 primeiros + 2 ultimos digitos, resto mascarado.
2. record_transaction aplica o mascaramento na gravacao (unico choke point).
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest


# =====================================================
# 1. mask_document (funcao pura)
# =====================================================

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("123.456.789-01", "123******01"),       # CPF formatado, 11 digitos
        ("12345678901", "123******01"),          # CPF cru
        ("12.345.678/0001-99", "123*********99"),  # CNPJ, 14 digitos
        ("12345", "***45"),                      # curto (5) -> so 2 ultimos
        ("", ""),
        (None, None),
    ],
)
def test_mask_document(raw, expected):
    from src.infra.security import mask_document

    assert mask_document(raw) == expected


def test_mask_document_never_keeps_full_cpf():
    from src.infra.security import mask_document

    masked = mask_document("529.982.247-25")
    assert "*" in masked
    assert "52998224725" not in masked
    # 3 primeiros + 2 ultimos visiveis
    assert masked.startswith("529")
    assert masked.endswith("25")


def test_mask_document_does_not_leak_on_remask():
    from src.infra.security import mask_document

    once = mask_document("12345678901")
    twice = mask_document(once)
    # re-mascarar nunca revela os digitos do meio
    assert "456789" not in twice


# =====================================================
# 2. record_transaction mascara na gravacao
# =====================================================

def test_record_transaction_masks_payer_document(monkeypatch):
    from src.repositories import payment_repository as repo

    captured = {}

    class _FakeCursor:
        def execute(self, sql, params):
            captured["params"] = params

        def fetchone(self):
            return {"id": 1}

    @contextmanager
    def _fake_db_cursor(dictionary=False):
        yield (MagicMock(), _FakeCursor())

    monkeypatch.setattr(repo, "db_cursor", _fake_db_cursor)

    repo.record_transaction(
        payment_request_id=1,
        tenant_id=10,
        provider="mercado_pago",
        provider_event_id="evt-1",
        event_type="charge.paid",
        status="succeeded",
        amount_cents=2500,
        payer_document="123.456.789-01",
    )

    # payer_document e o 10o parametro do INSERT (indice 9)
    params = captured["params"]
    assert "123******01" in params
    assert "12345678901" not in params
