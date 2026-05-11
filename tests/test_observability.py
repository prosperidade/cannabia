"""
Tests do Sprint 2 Track Obs — observabilidade Sentry com sanitization PII.

Cobre:
1. Soft-off: SENTRY_DSN ausente → init_sentry NAO chama sentry_sdk.init.
2. before_send: PII clinico (patient_name, CPF embutido) vira [REDACTED:*].
3. Fail-drop: se sanitize_clinical_payload raise, before_send retorna
   None (drop event vs vazamento PII em DSN externo).
4. tag_request: g sem user_id/clinic_id/tenant_id NAO deve raise.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# =====================================================
# 1. Soft-off: DSN ausente
# =====================================================

def test_sentry_off_when_dsn_missing():
    """init_sentry(None) — config sem DSN — NAO deve chamar sentry_sdk.init.

    Pattern soft (Q-Obs-1): app sobe sem Sentry vs quebrar deploy.
    """
    from src.infra import observability

    with patch.object(observability, "sentry_sdk") as mock_sdk:
        observability.init_sentry(None)
        mock_sdk.init.assert_not_called()


# =====================================================
# 2. before_send sanitiza PII clinico
# =====================================================

def test_before_send_redacts_clinical_pii():
    """Event com PII em request.data deve sair com keys redacted.

    Cobre defense in depth (Q-Obs-2): denylist nativa Sentry +
    before_send custom reusando sanitize_clinical_payload.
    """
    from src.infra.observability import _sentry_before_send

    event = {
        "request": {
            "data": {
                "patient_name": "Joao Silva",
                "main_complaint": "Dor lombar. CPF 123.456.789-00 anotado.",
                "age": 45,
            },
        },
        "extra": {
            "clinic_context": "atendimento normal",
        },
    }
    result = _sentry_before_send(event, hint={})

    assert result is not None, "before_send deve retornar event sanitizado, nao None"
    data = result["request"]["data"]

    # patient_name e' SENSITIVE_KEY → value-redact integral
    assert data["patient_name"] == "[REDACTED:key]", (
        f"patient_name deveria virar [REDACTED:key], veio: {data['patient_name']!r}"
    )

    # main_complaint NAO e' sensitive_key, mas CPF embutido vira [CPF_REDACTED]
    assert "[CPF_REDACTED]" in data["main_complaint"], (
        f"CPF embutido deveria virar [CPF_REDACTED], veio: {data['main_complaint']!r}"
    )
    assert "123.456.789-00" not in data["main_complaint"], (
        "CPF original NAO deve persistir no event"
    )

    # campos sem PII passam intactos
    assert data["age"] == 45


# =====================================================
# 3. Fail-drop: sanitization quebra → drop event
# =====================================================

def test_before_send_drops_event_on_sanitization_failure():
    """Se sanitize_clinical_payload raise, before_send DROPA event (None).

    LGPD-critical: melhor perder telemetria do que vazar PII em DSN
    externo se o sanitizer estiver quebrado.
    """
    from src.infra import observability

    event = {
        "request": {
            "data": {"patient_name": "qualquer coisa"},
        },
    }

    with patch(
        "src.ai.audit_redaction.sanitize_clinical_payload",
        side_effect=RuntimeError("sanitizer broken"),
    ):
        result = observability._sentry_before_send(event, hint={})

    assert result is None, (
        "before_send deve retornar None quando sanitizer raise — "
        "drop event ao inves de vazamento"
    )


# =====================================================
# 4. tag_request defensivo — g parcial nao raise
# =====================================================

def test_tag_request_handles_missing_g_attrs():
    """g com apenas request_id (sem user_id/clinic_id/tenant_id) nao deve raise.

    Cobre rotas publicas (login, /healthz, webhooks) onde tenant/user
    ainda nao estao resolvidos no escopo do request.
    """
    from src.infra import observability

    # g mock com SO request_id setado
    g_mock = SimpleNamespace(request_id="req-abc-123")

    with patch.object(observability, "sentry_sdk") as mock_sdk:
        # Nao deve raise mesmo sem user_id/clinic_id/tenant_id
        observability.tag_request(g_mock)

        # request_id setado → tag chamada
        mock_sdk.set_tag.assert_any_call("request_id", "req-abc-123")

        # user_id/clinic_id/tenant_id ausentes → set_user e tags
        # correspondentes NAO devem ser chamados
        mock_sdk.set_user.assert_not_called()
        # apenas a tag request_id deveria ter sido chamada (1x)
        assert mock_sdk.set_tag.call_count == 1, (
            f"Apenas request_id deveria ser tagueado, "
            f"chamadas: {mock_sdk.set_tag.call_args_list}"
        )
