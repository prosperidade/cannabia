"""
Tests do Sprint 2 Track Obs + Sprint 3 Track Obs-Harden.

Sprint 2 cobre:
1. Soft-off: SENTRY_DSN ausente em dev → init_sentry NAO chama sentry_sdk.init.
   (Em prod agora raise — ver Sprint 3 Obs-Harden, abaixo.)
2. before_send: PII clinico (patient_name, CPF embutido) vira [REDACTED:*].
3. Fail-drop: se sanitize_clinical_payload raise, before_send retorna
   None (drop event vs vazamento PII em DSN externo).
4. tag_request: g sem user_id/clinic_id/tenant_id NAO deve raise.

Sprint 3 Obs-Harden cobre:
5. _get_sentry_config raise em prod sem DSN (Q-OH-1, supersede Q-Obs-1).
6. _get_sentry_config soft em dev sem DSN (path inalterado).
7. traces_sample_rate vem do env SENTRY_TRACES_SAMPLE_RATE (Q-OH-2),
   com fallback pro default 0.1 quando valor invalido.
8. before_send sanitiza exception.values[].stacktrace.frames[].vars
   (frames vars walk recursivo — defesa pra include_local_variables=True,
   Q-OH-3).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest


# =====================================================
# 1. Soft-off: DSN ausente (dev)
# =====================================================

def test_sentry_off_when_dsn_missing():
    """init_sentry(None) — config sem DSN — NAO deve chamar sentry_sdk.init.

    Sprint 3 Obs-Harden: forca FLASK_ENV=development pra evitar raise hard
    do _get_sentry_config em prod (Q-OH-1). O comportamento testado aqui
    e' o de init_sentry consumindo config=None, que vem do path dev.
    """
    from src.infra import observability

    with patch.dict(
        "os.environ",
        {"FLASK_ENV": "development", "SENTRY_DSN": ""},
        clear=False,
    ), patch.object(observability, "sentry_sdk") as mock_sdk:
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


# =====================================================
# Sprint 3 Track Obs-Harden
# =====================================================

# -----------------------------------------------------
# 5. Q-OH-1: raise em prod sem DSN
# -----------------------------------------------------

def test_sentry_config_raises_in_prod_without_dsn():
    """FLASK_ENV=production + SENTRY_DSN ausente → RuntimeError.

    Pattern A.4 (Q-OH-1, supersede Q-Obs-1 soft-fail). Mensagem deve
    apontar configuracao no Render dashboard.
    """
    from src.config import _get_sentry_config

    with patch.dict(
        "os.environ",
        {"FLASK_ENV": "production", "SENTRY_DSN": ""},
        clear=False,
    ):
        with pytest.raises(RuntimeError) as excinfo:
            _get_sentry_config()

    msg = str(excinfo.value)
    assert "SENTRY_DSN" in msg, (
        f"Mensagem deve mencionar SENTRY_DSN, veio: {msg!r}"
    )
    assert "production" in msg.lower() or "prod" in msg.lower(), (
        f"Mensagem deve indicar contexto de producao, veio: {msg!r}"
    )


# -----------------------------------------------------
# 6. Dev path inalterado — soft sem DSN
# -----------------------------------------------------

def test_sentry_config_soft_in_dev_without_dsn():
    """FLASK_ENV=development + SENTRY_DSN ausente → returns None (sem raise).

    Path dev intocado pelo hardening Sprint 3. Dev local nao precisa
    configurar Sentry, app sobe silent.
    """
    from src.config import _get_sentry_config

    with patch.dict(
        "os.environ",
        {"FLASK_ENV": "development", "SENTRY_DSN": ""},
        clear=False,
    ):
        result = _get_sentry_config()

    assert result is None, (
        f"Em dev sem DSN, _get_sentry_config deve retornar None, "
        f"veio: {result!r}"
    )


# -----------------------------------------------------
# 7. Q-OH-2: traces_sample_rate via env override + clamp
# -----------------------------------------------------

def test_traces_sample_rate_from_env():
    """SENTRY_TRACES_SAMPLE_RATE=0.2 → config dict.traces_sample_rate == 0.2.

    Valor invalido (nao-numerico) cai pra default 0.1. Valor fora do
    range 0..1 sofre clamp.
    """
    from src.config import _get_sentry_config

    # Caso 1: override valido (0.2)
    with patch.dict(
        "os.environ",
        {
            "FLASK_ENV": "development",
            "SENTRY_DSN": "https://foo@o0.ingest.sentry.io/0",
            "SENTRY_TRACES_SAMPLE_RATE": "0.2",
        },
        clear=False,
    ):
        result = _get_sentry_config()

    assert result is not None
    assert result["traces_sample_rate"] == pytest.approx(0.2), (
        f"traces_sample_rate deveria ser 0.2, veio: {result['traces_sample_rate']!r}"
    )

    # Caso 2: valor invalido → fallback 0.1 (default Q-OH-2)
    with patch.dict(
        "os.environ",
        {
            "FLASK_ENV": "development",
            "SENTRY_DSN": "https://foo@o0.ingest.sentry.io/0",
            "SENTRY_TRACES_SAMPLE_RATE": "naoeumnumero",
        },
        clear=False,
    ):
        result = _get_sentry_config()

    assert result is not None
    assert result["traces_sample_rate"] == pytest.approx(0.1), (
        f"Valor invalido deve cair pra default 0.1, "
        f"veio: {result['traces_sample_rate']!r}"
    )

    # Caso 3: fora do range → clamp em [0.0, 1.0]
    with patch.dict(
        "os.environ",
        {
            "FLASK_ENV": "development",
            "SENTRY_DSN": "https://foo@o0.ingest.sentry.io/0",
            "SENTRY_TRACES_SAMPLE_RATE": "2.5",
        },
        clear=False,
    ):
        result = _get_sentry_config()

    assert result is not None
    assert result["traces_sample_rate"] == pytest.approx(1.0), (
        f"Valor >1.0 deve sofrer clamp pra 1.0, "
        f"veio: {result['traces_sample_rate']!r}"
    )


# -----------------------------------------------------
# 8. Q-OH-3: walk recursivo sanitiza frames[].vars
# -----------------------------------------------------

def test_before_send_sanitizes_frames_vars():
    """exception.values[i].stacktrace.frames[j].vars deve ser sanitizado.

    Defesa pra include_local_variables=True (Q-OH-3): Sentry envia
    locals do stacktrace, mas _sentry_before_send aplica
    sanitize_clinical_payload recursivamente em frames[].vars antes do
    event sair pro DSN externo.
    """
    from src.infra.observability import _sentry_before_send

    event = {
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "alguma falha",
                    "stacktrace": {
                        "frames": [
                            {
                                "function": "process_anamnesis",
                                "vars": {
                                    "cpf": "123.456.789-00",
                                    "patient_name": "Joao Silva",
                                    "diagnosis_note": (
                                        "Paciente com dor. CPF 987.654.321-00."
                                    ),
                                    "age": 45,
                                },
                            },
                        ],
                    },
                },
            ],
        },
    }

    result = _sentry_before_send(event, hint={})

    assert result is not None, "before_send deve retornar event sanitizado, nao None"

    frame_vars = result["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]

    # `cpf` e' SENSITIVE_KEY → value-redact integral
    assert frame_vars["cpf"] == "[REDACTED:key]", (
        f"cpf (sensitive_key) deveria virar [REDACTED:key], veio: {frame_vars['cpf']!r}"
    )
    # `patient_name` idem
    assert frame_vars["patient_name"] == "[REDACTED:key]", (
        f"patient_name deveria virar [REDACTED:key], "
        f"veio: {frame_vars['patient_name']!r}"
    )
    # `diagnosis_note` nao e' sensitive_key, mas CPF embutido vira [CPF_REDACTED]
    assert "[CPF_REDACTED]" in frame_vars["diagnosis_note"], (
        f"CPF embutido em string-leaf deveria virar [CPF_REDACTED], "
        f"veio: {frame_vars['diagnosis_note']!r}"
    )
    assert "987.654.321-00" not in frame_vars["diagnosis_note"], (
        "CPF original NAO deve persistir nos locals do frame"
    )
    # campo sem PII passa intacto
    assert frame_vars["age"] == 45
