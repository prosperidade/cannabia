"""Tests do acompanhamento_service.

Foco: classificacao de endpoint -> agente, agregacao com horario mais
recente vencendo, ordem fixa dos 4 agentes na saida e contagens dos
KPIs. Sem DB — repository e mockado via monkeypatch.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services import acompanhamento_service
from src.services.acompanhamento_service import (
    AcompanhamentoOverview,
    AgentActivity,
    KpiSnapshot,
)


# ---------------------------------------------------------------------------
# Fixtures: stubs do repository
# ---------------------------------------------------------------------------

class _RepoStub:
    def __init__(
        self,
        *,
        patients_at_risk: int = 0,
        followups_pending: int = 0,
        triages_in_progress: int = 0,
        adverse_events_open: int = 0,
        activity: list[dict] | None = None,
    ):
        self.patients_at_risk = patients_at_risk
        self.followups_pending = followups_pending
        self.triages_in_progress = triages_in_progress
        self.adverse_events_open = adverse_events_open
        self.activity = activity or []
        self.calls: list[tuple[str, int]] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = acompanhamento_service.acompanhamento_repository
        monkeypatch.setattr(
            repo,
            "count_patients_at_risk",
            lambda tid: (self.calls.append(("patients_at_risk", tid)) or self.patients_at_risk),
        )
        monkeypatch.setattr(
            repo,
            "count_followups_pending",
            lambda tid: (self.calls.append(("followups_pending", tid)) or self.followups_pending),
        )
        monkeypatch.setattr(
            repo,
            "count_triages_in_progress",
            lambda tid: (self.calls.append(("triages_in_progress", tid)) or self.triages_in_progress),
        )
        monkeypatch.setattr(
            repo,
            "count_adverse_events_open",
            lambda tid: (self.calls.append(("adverse_events_open", tid)) or self.adverse_events_open),
        )
        monkeypatch.setattr(
            repo,
            "agent_activity_last_24h",
            lambda tid: (self.calls.append(("agent_activity", tid)) or list(self.activity)),
        )


# ---------------------------------------------------------------------------
# Classificacao de endpoint
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "endpoint,expected",
    [
        ("/api/v1/triage/submit", "Triagem"),
        ("/triagem/foo", "Triagem"),
        ("/api/v1/anamnesis/intake", "Anamnese"),
        ("/api/v1/conversations/start", "Anamnese"),
        ("/api/v1/intake/foo", "Anamnese"),
        ("/api/v1/followup/run", "FollowUp"),
        ("/api/v1/follow_up/d3", "FollowUp"),
        ("/api/v1/regulatory/report", "Regulatorio"),
        ("/api/v1/pharmacovigilance/notify", "Regulatorio"),
        ("/api/v1/vigimed/x", "Regulatorio"),
        ("/api/v1/anvisa/y", "Regulatorio"),
        ("/api/v1/notivisa/z", "Regulatorio"),
    ],
)
def test_classify_endpoint_known(endpoint: str, expected: str) -> None:
    assert acompanhamento_service._classify_endpoint(endpoint) == expected


@pytest.mark.parametrize("endpoint", ["", None, "/api/v1/health", "/api/v1/auth/login"])
def test_classify_endpoint_unknown_returns_none(endpoint) -> None:
    assert acompanhamento_service._classify_endpoint(endpoint) is None


# ---------------------------------------------------------------------------
# get_overview — KPIs
# ---------------------------------------------------------------------------

def test_overview_propagates_kpis(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _RepoStub(
        patients_at_risk=2,
        followups_pending=7,
        triages_in_progress=3,
        adverse_events_open=4,
    )
    repo.install(monkeypatch)

    overview = acompanhamento_service.get_overview(tenant_id=42)

    assert isinstance(overview, AcompanhamentoOverview)
    assert overview.tenant_id == 42
    assert overview.kpis == KpiSnapshot(
        patients_at_risk=2,
        followups_pending=7,
        triages_in_progress=3,
        adverse_events_open=4,
    )
    # generated_at deve ser timezone-aware UTC
    assert overview.generated_at.tzinfo is not None
    assert overview.generated_at.tzinfo.utcoffset(overview.generated_at) == timezone.utc.utcoffset(
        overview.generated_at
    )


def test_overview_requires_tenant_id() -> None:
    with pytest.raises(ValueError):
        acompanhamento_service.get_overview(tenant_id=None)  # type: ignore[arg-type]


def test_overview_calls_repo_with_tenant_id(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _RepoStub()
    repo.install(monkeypatch)

    acompanhamento_service.get_overview(tenant_id=99)

    tenant_ids = {tid for _, tid in repo.calls}
    assert tenant_ids == {99}
    # Cobre todos os 5 metodos do repo
    method_names = {name for name, _ in repo.calls}
    assert method_names == {
        "patients_at_risk",
        "followups_pending",
        "triages_in_progress",
        "adverse_events_open",
        "agent_activity",
    }


# ---------------------------------------------------------------------------
# Agregacao de atividade dos agentes
# ---------------------------------------------------------------------------

def test_overview_returns_all_four_agents_even_with_no_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RepoStub(activity=[])
    repo.install(monkeypatch)

    overview = acompanhamento_service.get_overview(tenant_id=1)

    agents = [a.agent for a in overview.agents_activity_24h]
    assert agents == ["Triagem", "Anamnese", "FollowUp", "Regulatorio"]
    assert all(a.actions == 0 for a in overview.agents_activity_24h)
    assert all(a.last_action_at is None for a in overview.agents_activity_24h)


def test_overview_aggregates_activity_by_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    activity = [
        {"endpoint": "/api/v1/triage/submit", "n": 5, "last_at": "2026-04-27T10:00:00+00:00"},
        {"endpoint": "/triagem/foo",          "n": 2, "last_at": "2026-04-27T11:30:00+00:00"},
        {"endpoint": "/api/v1/anamnesis/intake", "n": 3, "last_at": "2026-04-27T09:00:00+00:00"},
        {"endpoint": "/api/v1/regulatory/report", "n": 1, "last_at": "2026-04-27T12:00:00+00:00"},
        # Endpoint nao classificavel — deve ser ignorado
        {"endpoint": "/api/v1/health", "n": 99, "last_at": "2026-04-27T12:30:00+00:00"},
    ]
    repo = _RepoStub(activity=activity)
    repo.install(monkeypatch)

    overview = acompanhamento_service.get_overview(tenant_id=1)
    by_agent = {a.agent: a for a in overview.agents_activity_24h}

    assert by_agent["Triagem"].actions == 7
    assert by_agent["Triagem"].last_action_at == "2026-04-27T11:30:00+00:00"

    assert by_agent["Anamnese"].actions == 3
    assert by_agent["Anamnese"].last_action_at == "2026-04-27T09:00:00+00:00"

    assert by_agent["FollowUp"].actions == 0
    assert by_agent["FollowUp"].last_action_at is None

    assert by_agent["Regulatorio"].actions == 1
    assert by_agent["Regulatorio"].last_action_at == "2026-04-27T12:00:00+00:00"


def test_overview_handles_datetime_last_at(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repository pode retornar datetime cru se nao normalizar — service tolera."""
    dt = datetime(2026, 4, 27, 13, 0, tzinfo=timezone.utc)
    activity = [{"endpoint": "/api/v1/triage", "n": 1, "last_at": dt}]
    repo = _RepoStub(activity=activity)
    repo.install(monkeypatch)

    overview = acompanhamento_service.get_overview(tenant_id=1)
    triagem = next(a for a in overview.agents_activity_24h if a.agent == "Triagem")
    assert triagem.actions == 1
    assert triagem.last_action_at is not None
    assert "2026-04-27" in triagem.last_action_at


def test_overview_returns_immutable_overview(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _RepoStub()
    repo.install(monkeypatch)

    overview = acompanhamento_service.get_overview(tenant_id=1)
    with pytest.raises(Exception):
        overview.kpis.patients_at_risk = 999  # type: ignore[misc]
    # tuple imutavel
    assert isinstance(overview.agents_activity_24h, tuple)


def test_agent_activity_dataclass_is_frozen() -> None:
    a = AgentActivity(agent="Triagem", actions=1, last_action_at=None)
    with pytest.raises(Exception):
        a.actions = 2  # type: ignore[misc]
