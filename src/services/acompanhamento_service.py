"""Service que monta o snapshot da pagina /org/acompanhamento.

Une as 4 contagens-chave (KPIs do dia) com o resumo de atividade dos
4 agentes IA nas ultimas 24h. Retorna um ``AcompanhamentoOverview``
imutavel pronto para serializar no blueprint correspondente.

Fonte dos dados:
  - adverse_events (tenant_id)        — patients_at_risk, adverse_events_open
  - scheduled_followups (clinic_id)   — followups_pending
  - triage_links (clinic_id)          — triages_in_progress
  - ai_audit_logs (clinic_id)         — agents_activity (24h)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.repositories import acompanhamento_repository

logger = logging.getLogger("cannabia.acompanhamento")


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KpiSnapshot:
    patients_at_risk: int
    followups_pending: int
    triages_in_progress: int
    adverse_events_open: int


@dataclass(frozen=True)
class AgentActivity:
    """Atividade agregada de uma das 4 familias de agente nas ultimas 24h."""

    agent: str          # "Triagem" | "Anamnese" | "FollowUp" | "Regulatorio"
    actions: int        # quantidade de execucoes registradas em ai_audit_logs
    last_action_at: Optional[str]  # ISO 8601, None se sem atividade


@dataclass(frozen=True)
class AcompanhamentoOverview:
    tenant_id: int
    generated_at: datetime
    kpis: KpiSnapshot
    agents_activity_24h: tuple[AgentActivity, ...]


# ---------------------------------------------------------------------------
# Classificacao endpoint -> agente
# ---------------------------------------------------------------------------

# Os 4 agentes IA fixos da plataforma. Ordem aqui define a ordem da UI.
_AGENT_ORDER = ("Triagem", "Anamnese", "FollowUp", "Regulatorio")


def _classify_endpoint(endpoint: Optional[str]) -> Optional[str]:
    """Mapeia o endpoint registrado em ``ai_audit_logs`` para um dos 4 agentes.

    Heuristica conservadora baseada em substrings — nomes de rotas
    podem variar (ex.: ``/triage`` vs ``/triagem``). Endpoints fora do
    mapa sao ignorados (retorna ``None``).
    """
    if not endpoint:
        return None
    e = endpoint.lower()
    if "triage" in e or "triagem" in e:
        return "Triagem"
    if "anamnes" in e or "intake" in e or "conversation" in e:
        return "Anamnese"
    if "follow" in e:
        return "FollowUp"
    if (
        "regulator" in e
        or "vigimed" in e
        or "pharmacovigil" in e
        or "anvisa" in e
        or "notivisa" in e
    ):
        return "Regulatorio"
    return None


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def get_overview(tenant_id: int) -> AcompanhamentoOverview:
    """Snapshot agregado de cuidado continuo do tenant.

    Faz 5 queries em sequencia (4 contagens + 1 agregacao por endpoint).
    Custo aceitavel para uma pagina de dashboard chamada uma vez por
    visualizacao.
    """
    if tenant_id is None:
        raise ValueError("tenant_id e obrigatorio.")
    tenant_id = int(tenant_id)

    kpis = KpiSnapshot(
        patients_at_risk=acompanhamento_repository.count_patients_at_risk(tenant_id),
        followups_pending=acompanhamento_repository.count_followups_pending(tenant_id),
        triages_in_progress=acompanhamento_repository.count_triages_in_progress(tenant_id),
        adverse_events_open=acompanhamento_repository.count_adverse_events_open(tenant_id),
    )

    raw_activity = acompanhamento_repository.agent_activity_last_24h(tenant_id)

    aggregated: dict[str, dict[str, object]] = {
        agent: {"actions": 0, "last_action_at": None} for agent in _AGENT_ORDER
    }
    for row in raw_activity:
        agent = _classify_endpoint(row.get("endpoint") if isinstance(row, dict) else None)
        if agent is None:
            continue
        bucket = aggregated[agent]
        bucket["actions"] = int(bucket["actions"]) + int(row.get("n", 0))
        last_at = row.get("last_at")
        prev = bucket["last_action_at"]
        if last_at and (prev is None or str(last_at) > str(prev)):
            bucket["last_action_at"] = last_at

    activity_tuple = tuple(
        AgentActivity(
            agent=agent,
            actions=int(aggregated[agent]["actions"]),
            last_action_at=(
                aggregated[agent]["last_action_at"]
                if isinstance(aggregated[agent]["last_action_at"], str)
                or aggregated[agent]["last_action_at"] is None
                else str(aggregated[agent]["last_action_at"])
            ),
        )
        for agent in _AGENT_ORDER
    )

    return AcompanhamentoOverview(
        tenant_id=tenant_id,
        generated_at=datetime.now(tz=timezone.utc),
        kpis=kpis,
        agents_activity_24h=activity_tuple,
    )
