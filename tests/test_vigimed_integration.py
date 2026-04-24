"""Testes do wrapper de notificacao regulatoria (F3.5 do SCC).

Sem DB — todo o escopo de F3.5 e pure integration. O dispatcher,
resolucao de provider, determinismo do mock e o payload shape sao
testados com isolamento total.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pytest

from src.integrations import vigimed as vig
from src.integrations.vigimed import (
    DEFAULT_PROVIDER,
    MOCK_MODEL_VERSION,
    MockNotificationClient,
    NOTIFICATION_PROVIDER_ENV,
    NotificationReceipt,
    PharmacovigilanceError,
    UnknownProviderError,
    VALID_PROVIDERS,
    VigiMedSubmissionError,
    build_notification_payload,
    submit_notification,
)


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Garante que NAO ha env var vazando entre testes."""
    monkeypatch.delenv(NOTIFICATION_PROVIDER_ENV, raising=False)
    yield


def _sample_event(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": 101,
        "tenant_id": 7,
        "member_id": 55,
        "preparation_id": None,
        "severity": "severe",
        "reported_via": "consultation",
        "description": "Paciente internado apos dose inicial.",
        "reported_at": datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc),
        "event_onset_at": datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc),
        "clinical_assessment": None,
        "outcome": None,
        "ai_triage_result": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------
# Constantes e contratos basicos
# ---------------------------------------------------------------------


class TestContracts:
    def test_valid_providers_set(self) -> None:
        assert VALID_PROVIDERS == frozenset({"mock", "vigimed", "notivisa"})

    def test_default_provider_is_mock(self) -> None:
        assert DEFAULT_PROVIDER == "mock"

    def test_mock_model_version_is_string(self) -> None:
        assert isinstance(MOCK_MODEL_VERSION, str)
        assert MOCK_MODEL_VERSION.startswith("vigimed-mock-")


# ---------------------------------------------------------------------
# _resolve_provider
# ---------------------------------------------------------------------


class TestResolveProvider:
    def test_default_when_no_arg_no_env(self, monkeypatch) -> None:
        monkeypatch.delenv(NOTIFICATION_PROVIDER_ENV, raising=False)
        assert vig._resolve_provider(None) == "mock"

    def test_env_used_when_no_arg(self, monkeypatch) -> None:
        monkeypatch.setenv(NOTIFICATION_PROVIDER_ENV, "vigimed")
        assert vig._resolve_provider(None) == "vigimed"

    def test_arg_overrides_env(self, monkeypatch) -> None:
        monkeypatch.setenv(NOTIFICATION_PROVIDER_ENV, "vigimed")
        assert vig._resolve_provider("notivisa") == "notivisa"

    def test_case_insensitive(self, monkeypatch) -> None:
        monkeypatch.setenv(NOTIFICATION_PROVIDER_ENV, "VigiMed")
        assert vig._resolve_provider(None) == "vigimed"

    def test_invalid_raises(self) -> None:
        with pytest.raises(UnknownProviderError, match="invalido"):
            vig._resolve_provider("anvisa-direto")


# ---------------------------------------------------------------------
# build_notification_payload
# ---------------------------------------------------------------------


class TestPayloadBuilder:
    def test_extracts_all_expected_keys_from_dict(self) -> None:
        ev = _sample_event()
        payload = build_notification_payload(ev)
        for key in (
            "event_id", "tenant_id", "member_id", "preparation_id",
            "severity", "reported_via", "description",
            "reported_at", "event_onset_at",
            "clinical_assessment", "outcome", "ai_triage_result",
        ):
            assert key in payload

    def test_datetimes_serialized_to_iso(self) -> None:
        payload = build_notification_payload(_sample_event())
        assert isinstance(payload["reported_at"], str)
        assert payload["reported_at"].startswith("2026-04-24")

    def test_accepts_object_with_attributes(self) -> None:
        @dataclass
        class Stub:
            id: int = 9
            tenant_id: int = 1
            member_id: Optional[int] = None
            preparation_id: Optional[int] = None
            severity: str = "mild"
            reported_via: str = "web"
            description: str = "rash leve"
            reported_at: Optional[datetime] = datetime(
                2026, 1, 1, tzinfo=timezone.utc
            )
            event_onset_at: Optional[datetime] = None
            clinical_assessment: Optional[str] = None
            outcome: Optional[str] = None
            ai_triage_result: Optional[dict] = None

        payload = build_notification_payload(Stub())
        assert payload["event_id"] == 9
        assert payload["description"] == "rash leve"
        assert payload["reported_at"].startswith("2026-01-01")


# ---------------------------------------------------------------------
# MockNotificationClient — determinismo e shape
# ---------------------------------------------------------------------


class TestMockClient:
    def test_mock_reference_is_deterministic(self) -> None:
        client = MockNotificationClient(provider="mock")
        payload = {"description": "X", "severity": "severe"}
        r1 = client.submit(payload)
        r2 = client.submit(payload)
        assert r1.notification_reference == r2.notification_reference
        assert r1.notification_reference.startswith("MOCK-")

    def test_mock_reference_changes_with_payload(self) -> None:
        client = MockNotificationClient(provider="mock")
        a = client.submit({"description": "A"})
        b = client.submit({"description": "B"})
        assert a.notification_reference != b.notification_reference

    def test_mock_mock_provider_maps_to_internal_only(self) -> None:
        client = MockNotificationClient(provider="mock")
        r = client.submit({"description": "X"})
        assert r.notification_target == "internal_only"

    def test_mock_vigimed_maps_to_vigimed_target(self) -> None:
        client = MockNotificationClient(provider="vigimed")
        r = client.submit({"description": "X"})
        assert r.notification_target == "vigimed"

    def test_mock_notivisa_maps_to_notivisa_target(self) -> None:
        client = MockNotificationClient(provider="notivisa")
        r = client.submit({"description": "X"})
        assert r.notification_target == "notivisa"

    def test_mock_rejects_unknown_provider_at_init(self) -> None:
        with pytest.raises(UnknownProviderError):
            MockNotificationClient(provider="anvisa-x")

    def test_response_payload_contains_metadata(self) -> None:
        client = MockNotificationClient(provider="mock")
        r = client.submit({"description": "X"})
        assert r.response_payload["accepted"] is True
        assert r.response_payload["provider"] == "mock"
        assert r.response_payload["model_version"] == MOCK_MODEL_VERSION
        assert r.response_payload["reference"] == r.notification_reference

    def test_submitted_at_is_utc(self) -> None:
        client = MockNotificationClient(provider="mock")
        r = client.submit({"description": "X"})
        assert r.submitted_at.tzinfo is not None


# ---------------------------------------------------------------------
# submit_notification — dispatcher
# ---------------------------------------------------------------------


class TestDispatcher:
    def test_default_uses_mock_and_internal_only_target(self) -> None:
        receipt = submit_notification(_sample_event())
        assert isinstance(receipt, NotificationReceipt)
        assert receipt.notification_target == "internal_only"
        assert receipt.notification_reference.startswith("MOCK-")

    def test_env_vigimed_without_real_client_raises(self, monkeypatch) -> None:
        monkeypatch.setenv(NOTIFICATION_PROVIDER_ENV, "vigimed")
        # Stub do production client levanta VigiMedSubmissionError.
        with pytest.raises(VigiMedSubmissionError, match="VigiMed"):
            submit_notification(_sample_event())

    def test_env_notivisa_without_real_client_raises(self, monkeypatch) -> None:
        monkeypatch.setenv(NOTIFICATION_PROVIDER_ENV, "notivisa")
        with pytest.raises(VigiMedSubmissionError, match="NotiVisa"):
            submit_notification(_sample_event())

    def test_client_injection_bypasses_dispatcher_selection(self) -> None:
        # Mesmo com provider='vigimed', se passamos um client, o client
        # e que decide o target. Util para F3.6 reaproveitar mocks.
        client = MockNotificationClient(provider="vigimed")
        receipt = submit_notification(
            _sample_event(), provider="mock", client=client
        )
        # O target vem do client, nao do provider resolvido
        assert receipt.notification_target == "vigimed"

    def test_explicit_provider_arg_overrides_env(self, monkeypatch) -> None:
        monkeypatch.setenv(NOTIFICATION_PROVIDER_ENV, "vigimed")
        # Arg explicito 'mock' -> dispatcher escolhe mock client.
        receipt = submit_notification(_sample_event(), provider="mock")
        assert receipt.notification_target == "internal_only"

    def test_none_event_raises(self) -> None:
        with pytest.raises(VigiMedSubmissionError, match="obrigatorio"):
            submit_notification(None)

    def test_empty_description_raises(self) -> None:
        with pytest.raises(
            VigiMedSubmissionError, match="descricao"
        ):
            submit_notification(_sample_event(description=""))

    def test_unknown_provider_from_arg_raises(self) -> None:
        with pytest.raises(UnknownProviderError):
            submit_notification(_sample_event(), provider="fake")

    def test_client_raising_nonpharmaco_wrapped(self, monkeypatch) -> None:
        class BrokenClient:
            def submit(self, payload):
                raise RuntimeError("timeout generico")

        with pytest.raises(VigiMedSubmissionError, match="timeout"):
            submit_notification(
                _sample_event(), client=BrokenClient()
            )

    def test_client_raising_pharmaco_preserved(self) -> None:
        # Erros da hierarquia PharmacovigilanceError nao sao re-wrappeados
        class PickyClient:
            def submit(self, payload):
                raise VigiMedSubmissionError("rejeitado pelo orgao")

        with pytest.raises(VigiMedSubmissionError, match="rejeitado"):
            submit_notification(
                _sample_event(), client=PickyClient()
            )

    def test_accepts_adverse_event_dataclass(self) -> None:
        # Smoke: qualquer objeto com os atributos esperados funciona.
        from src.services.adverse_event_service import AdverseEvent

        ev = AdverseEvent(
            id=1, tenant_id=1, member_id=None, preparation_id=None,
            reported_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
            event_onset_at=None,
            severity="severe", description="Paciente internado.",
            reported_via="consultation",
            ai_triage_result=None, triaged_by=None,
            clinical_assessment=None, outcome=None,
            created_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
        )
        receipt = submit_notification(ev)
        assert receipt.notification_target == "internal_only"


# ---------------------------------------------------------------------
# Hierarquia de erros
# ---------------------------------------------------------------------


class TestErrorHierarchy:
    def test_unknown_provider_is_pharmaco_error(self) -> None:
        assert issubclass(UnknownProviderError, PharmacovigilanceError)

    def test_submission_error_is_pharmaco_error(self) -> None:
        assert issubclass(VigiMedSubmissionError, PharmacovigilanceError)
