"""Blueprint /api/v1/org/acompanhamento.

Snapshot de cuidado continuo da clinica: 4 KPIs do dia + atividade
dos 4 agentes IA nas ultimas 24h. Read-only, escopado ao tenant
do usuario autenticado.

Roles permitidas: Admin (global), AdminClinica, Medico, Recepcao.
Financeiro nao precisa desse painel — sua home e /org/financeiro.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, g

from src.services import acompanhamento_service
from src.services.acompanhamento_service import (
    AcompanhamentoOverview,
    AgentActivity,
    KpiSnapshot,
)
from src.web.routes.api_v1 import _error, _success, api_role_required

logger = logging.getLogger("cannabia.acompanhamento_routes")

acompanhamento_bp = Blueprint(
    "acompanhamento", __name__, url_prefix="/api/v1/org/acompanhamento"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_tenant_id() -> Optional[int]:
    tenant_id = getattr(g, "tenant_id", None)
    if tenant_id is None:
        tenant_id = getattr(g, "clinic_id", None)
    return int(tenant_id) if tenant_id is not None else None


def _serialize_kpis(k: KpiSnapshot) -> dict[str, int]:
    return {
        "patients_at_risk": k.patients_at_risk,
        "followups_pending": k.followups_pending,
        "triages_in_progress": k.triages_in_progress,
        "adverse_events_open": k.adverse_events_open,
    }


def _serialize_agent(a: AgentActivity) -> dict[str, Any]:
    return {
        "agent": a.agent,
        "actions": a.actions,
        "last_action_at": a.last_action_at,
    }


def _serialize_overview(o: AcompanhamentoOverview) -> dict[str, Any]:
    return {
        "tenant_id": o.tenant_id,
        "generated_at": o.generated_at.isoformat(),
        "kpis": _serialize_kpis(o.kpis),
        "agents_activity_24h": [_serialize_agent(a) for a in o.agents_activity_24h],
    }


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@acompanhamento_bp.get("/overview")
@api_role_required("Admin", "AdminClinica", "Medico", "Recepcao")
def overview_endpoint():
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        return _error(
            "tenant_context_missing",
            "Contexto de tenant nao resolvido para o usuario autenticado.",
            400,
        )
    overview = acompanhamento_service.get_overview(tenant_id)
    return _success(_serialize_overview(overview))
