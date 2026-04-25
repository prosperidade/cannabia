# src/services/pharmacovigilance_service.py
"""
Servico orquestrador de pharmacovigilance — F3.6 do docs/BACKLOG_SCC.md.

Costura as 3 pecas anteriores da F3:
  - F3.3 `adverse_event_service` (captura/get/list/updates)
  - F3.4 `regulatorio.triage_adverse_event` (skill IA, heuristica)
  - F3.5 `integrations.vigimed.submit_notification` (dispatcher)

E persiste o resultado da notificacao em
`pharmacovigilance_notifications` (responsabilidade que F3.5 deixou
deliberadamente para esta camada).

Tres casos de uso publicos:
  - `triage_event`        — invoca skill IA + grava ai_triage_result
  - `notify_event`        — submete via vigimed + grava notificacao
  - `dashboard_summary`   — counts por severidade + counts por target

Erros tipados para o blueprint mapear em codigos HTTP estaveis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from src.integrations import vigimed
from src.integrations.vigimed import (
    NotificationReceipt,
    PharmacovigilanceError,
)
from src.repositories import pharmacovigilance_notification_repository as notif_repo
from src.services import adverse_event_service
from src.services.adverse_event_service import AdverseEvent

logger = logging.getLogger("cannabia.svc.pharmacovigilance")


# ===========================================================================
# Erros tipados
# ===========================================================================


class PharmacovigilanceServiceError(Exception):
    """Base para erros do orquestrador."""


class AdverseEventNotFoundError(PharmacovigilanceServiceError):
    """Evento adverso nao existe ou esta fora do tenant."""


# ===========================================================================
# Dataclasses de saida
# ===========================================================================


@dataclass(frozen=True)
class NotificationRecord:
    """Notificacao persistida (linha de pharmacovigilance_notifications)."""

    id: int
    adverse_event_id: int
    notification_target: str
    notified_at: datetime
    notification_reference: Optional[str]
    response_received_at: Optional[datetime]
    response_payload: Optional[dict[str, Any]]
    created_at: datetime


@dataclass(frozen=True)
class DashboardSummary:
    """Snapshot agregado para painel epidemiologico."""

    tenant_id: int
    period_days: int
    generated_at: datetime
    total_events: int
    events_by_severity: dict[str, int]
    events_requiring_notification: int
    notifications_by_target: dict[str, int]


# ===========================================================================
# Helpers
# ===========================================================================


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_notification(row: Optional[dict[str, Any]]) -> Optional[NotificationRecord]:
    if row is None:
        return None
    return NotificationRecord(
        id=int(row["id"]),
        adverse_event_id=int(row["adverse_event_id"]),
        notification_target=str(row["notification_target"]),
        notified_at=row["notified_at"],
        notification_reference=row.get("notification_reference"),
        response_received_at=row.get("response_received_at"),
        response_payload=row.get("response_payload"),
        created_at=row["created_at"],
    )


# ===========================================================================
# Orquestracao — triagem
# ===========================================================================


def triage_event(
    event_id: int,
    *,
    tenant_id: int,
    triaged_by: Optional[int] = None,
) -> dict[str, Any]:
    """
    Carrega o evento, invoca a skill heuristica do AgenteRegulatorio e
    grava o resultado em `adverse_events.ai_triage_result`.

    Retorna o dict da skill com `event` (estado pos-update) anexo.

    Raises:
        AdverseEventNotFoundError: evento inexistente ou fora do tenant.
    """
    event = adverse_event_service.get_event(event_id, tenant_id=tenant_id)
    if event is None:
        raise AdverseEventNotFoundError(
            f"adverse_event {event_id} nao encontrado para tenant {tenant_id}"
        )

    # Lazy import para evitar acoplamento de inicializacao do agente
    # quando a peca de pharmacovigilance e o unico consumidor da skill.
    from src.ai.agents.regulatorio import AgenteRegulatorio

    agent = AgenteRegulatorio()
    triage_output = agent.invoke_skill(
        "triage_adverse_event",
        report=event,
        persist=True,
        event_id=event.id,
        tenant_id=tenant_id,
        triaged_by=triaged_by,
    )

    if not triage_output.get("ok"):
        # Skill rejeitou input (ex.: severity invalida) — nao deveria
        # acontecer para evento ja persistido com whitelist do schema,
        # mas mantem fail-safe.
        return {**triage_output, "event": event}

    refreshed = adverse_event_service.get_event(event_id, tenant_id=tenant_id)
    triage_output["event"] = refreshed
    logger.info(
        "triage_event tenant=%s event_id=%s severity_suggested=%s",
        tenant_id, event_id, triage_output.get("severity_suggested"),
    )
    return triage_output


# ===========================================================================
# Orquestracao — notificacao regulatoria
# ===========================================================================


def notify_event(
    event_id: int,
    *,
    tenant_id: int,
    provider: Optional[str] = None,
) -> NotificationRecord:
    """
    Submete uma notificacao do evento ao orgao via dispatcher F3.5 e
    persiste a linha em `pharmacovigilance_notifications`.

    Args:
        provider: override explicito (`mock|vigimed|notivisa`). Se None,
            usa env `ANVISA_NOTIFICATION_PROVIDER` ou default 'mock'.

    Raises:
        AdverseEventNotFoundError: evento inexistente.
        PharmacovigilanceError: falha de submissao (re-erguida do F3.5).
    """
    event = adverse_event_service.get_event(event_id, tenant_id=tenant_id)
    if event is None:
        raise AdverseEventNotFoundError(
            f"adverse_event {event_id} nao encontrado para tenant {tenant_id}"
        )

    receipt: NotificationReceipt = vigimed.submit_notification(
        event, provider=provider
    )

    row = notif_repo.insert_notification(
        adverse_event_id=event.id,
        notification_target=receipt.notification_target,
        notified_at=receipt.submitted_at,
        notification_reference=receipt.notification_reference,
        response_payload=dict(receipt.response_payload),
    )
    record = _row_to_notification(row)
    assert record is not None
    logger.info(
        "notify_event tenant=%s event_id=%s target=%s ref=%s",
        tenant_id, event_id, record.notification_target,
        record.notification_reference,
    )
    return record


def list_notifications_for_event(
    event_id: int, *, tenant_id: int
) -> list[NotificationRecord]:
    """
    Lista notificacoes de um evento (escopagem por tenant via JOIN).

    Raises:
        AdverseEventNotFoundError: se o evento nao pertencer ao tenant.
    """
    event = adverse_event_service.get_event(event_id, tenant_id=tenant_id)
    if event is None:
        raise AdverseEventNotFoundError(
            f"adverse_event {event_id} nao encontrado para tenant {tenant_id}"
        )
    rows = notif_repo.list_for_event(event_id, tenant_id=tenant_id)
    return [r for r in (_row_to_notification(row) for row in rows) if r is not None]


def record_notification_response(
    notification_id: int,
    *,
    tenant_id: int,
    response_payload: Optional[dict[str, Any]] = None,
    response_received_at: Optional[datetime] = None,
) -> Optional[NotificationRecord]:
    """
    Registra a resposta do orgao regulador a uma notificacao previa.
    Util quando a confirmacao chega de forma assincrona (ex.: webhook
    Vigimed posterior).
    """
    received = response_received_at or _utcnow()
    row = notif_repo.record_response(
        notification_id,
        tenant_id=tenant_id,
        response_received_at=received,
        response_payload=response_payload,
    )
    return _row_to_notification(row)


# ===========================================================================
# Dashboard epidemiologico
# ===========================================================================


def dashboard_summary(
    tenant_id: int, *, period_days: int = 30
) -> DashboardSummary:
    """
    Snapshot agregado para a UI: contagem total/severidade + numero de
    eventos com severidade notificavel + counts por target de notificacao.

    Janela inclusiva: `[now - period_days, now)`.
    """
    now = _utcnow()
    since = now - timedelta(days=period_days)

    by_severity = adverse_event_service.count_by_severity(
        tenant_id, since=since, until=now
    )
    total = sum(by_severity.values())

    notifiable = sum(
        n
        for sev, n in by_severity.items()
        if sev in adverse_event_service.NOTIFIABLE_SEVERITIES
    )

    by_target = notif_repo.count_for_tenant(tenant_id, since=since, until=now)

    return DashboardSummary(
        tenant_id=tenant_id,
        period_days=period_days,
        generated_at=now,
        total_events=total,
        events_by_severity=by_severity,
        events_requiring_notification=notifiable,
        notifications_by_target=by_target,
    )


__all__ = [
    "AdverseEventNotFoundError",
    "PharmacovigilanceServiceError",
    "NotificationRecord",
    "DashboardSummary",
    "triage_event",
    "notify_event",
    "list_notifications_for_event",
    "record_notification_response",
    "dashboard_summary",
]
