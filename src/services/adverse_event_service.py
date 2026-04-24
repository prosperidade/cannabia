# src/services/adverse_event_service.py
"""
Servico de eventos adversos — F3.3 do docs/BACKLOG_SCC.md.

Captura estruturada de eventos adversos via WhatsApp/web/consulta,
listagem para dashboards e atualizacao do resultado de triagem IA
(gancho para F3.4) e parecer clinico.

Responsabilidades:
  - Validar payload (whitelists, ordem temporal, integridade referencial).
  - Preencher defaults sensatos (reported_at = now se ausente).
  - Delegar acesso ao DB para `adverse_event_repository`.
  - Expor dataclasses imutaveis para consumidores (blueprints, jobs).

NAO faz:
  - Notificacao VigiMed/NotiVisa — responsabilidade de F3.5.
  - Classificacao AI de severidade — responsabilidade de F3.4
    (skill `triage_adverse_event` do `ai/agents/regulatorio.py`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.repositories import adverse_event_repository as repo

logger = logging.getLogger("cannabia.svc.adverse_event")


# ===========================================================================
# Whitelists (alinhadas com CHECKs da migration 031)
# ===========================================================================

SEVERITY_CHOICES: tuple[str, ...] = (
    "mild",
    "moderate",
    "severe",
    "life_threatening",
    "fatal",
)

REPORTED_VIA_CHOICES: tuple[str, ...] = (
    "whatsapp",
    "web",
    "consultation",
    "phone",
    "other",
)

OUTCOME_CHOICES: tuple[str, ...] = (
    "resolved",
    "resolving",
    "ongoing",
    "worsened",
    "unknown",
)

# Severidades que merecem notificacao regulatoria automatica (gancho F3.5).
NOTIFIABLE_SEVERITIES: frozenset[str] = frozenset(
    {"severe", "life_threatening", "fatal"}
)


class AdverseEventValidationError(ValueError):
    """Erro de validacao de payload antes de persistir no banco."""


# ===========================================================================
# Dataclass de saida
# ===========================================================================

@dataclass(frozen=True)
class AdverseEvent:
    id: int
    tenant_id: int
    member_id: Optional[int]
    preparation_id: Optional[int]
    reported_at: datetime
    event_onset_at: Optional[datetime]
    severity: str
    description: str
    reported_via: str
    ai_triage_result: Optional[dict[str, Any]]
    triaged_by: Optional[int]
    clinical_assessment: Optional[str]
    outcome: Optional[str]
    created_at: datetime
    updated_at: datetime

    @property
    def requires_regulatory_notification(self) -> bool:
        """
        True quando a severidade esta na whitelist de notificacao
        obrigatoria. Usado por F3.5 para decidir dispatch automatico.
        """
        return self.severity in NOTIFIABLE_SEVERITIES


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_event(row: Optional[dict[str, Any]]) -> Optional[AdverseEvent]:
    if row is None:
        return None
    return AdverseEvent(
        id=int(row["id"]),
        tenant_id=int(row["tenant_id"]),
        member_id=row.get("member_id"),
        preparation_id=row.get("preparation_id"),
        reported_at=row["reported_at"],
        event_onset_at=row.get("event_onset_at"),
        severity=str(row["severity"]),
        description=str(row["description"]),
        reported_via=str(row["reported_via"]),
        ai_triage_result=row.get("ai_triage_result"),
        triaged_by=row.get("triaged_by"),
        clinical_assessment=row.get("clinical_assessment"),
        outcome=row.get("outcome"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ===========================================================================
# Validacao
# ===========================================================================

def _validate_payload(
    *,
    description: str,
    severity: str,
    reported_via: str,
    reported_at: datetime,
    event_onset_at: Optional[datetime],
) -> None:
    if not description or not description.strip():
        raise AdverseEventValidationError("description e obrigatorio")

    if severity not in SEVERITY_CHOICES:
        raise AdverseEventValidationError(
            f"severity invalida: {severity!r}. "
            f"Esperado um de {SEVERITY_CHOICES}"
        )

    if reported_via not in REPORTED_VIA_CHOICES:
        raise AdverseEventValidationError(
            f"reported_via invalido: {reported_via!r}. "
            f"Esperado um de {REPORTED_VIA_CHOICES}"
        )

    if event_onset_at is not None and event_onset_at > reported_at:
        raise AdverseEventValidationError(
            "event_onset_at deve ser anterior ou igual a reported_at "
            f"({event_onset_at} > {reported_at})"
        )


# ===========================================================================
# API publica
# ===========================================================================

def capture_adverse_event(
    *,
    tenant_id: int,
    description: str,
    severity: str,
    reported_via: str,
    member_id: Optional[int] = None,
    preparation_id: Optional[int] = None,
    reported_at: Optional[datetime] = None,
    event_onset_at: Optional[datetime] = None,
) -> AdverseEvent:
    """
    Registra um novo evento adverso no escopo do tenant.

    Preenche `reported_at = now()` se nao informado. Valida whitelists
    (`severity`, `reported_via`) e a ordem temporal
    (`event_onset_at <= reported_at`) antes de inserir.

    Raises:
        AdverseEventValidationError: quando o payload e invalido.
    """
    now = _utcnow()
    reported_at = reported_at or now

    _validate_payload(
        description=description,
        severity=severity,
        reported_via=reported_via,
        reported_at=reported_at,
        event_onset_at=event_onset_at,
    )

    row = repo.insert_adverse_event(
        tenant_id=tenant_id,
        member_id=member_id,
        preparation_id=preparation_id,
        reported_at=reported_at,
        event_onset_at=event_onset_at,
        severity=severity,
        description=description.strip(),
        reported_via=reported_via,
    )
    event = _row_to_event(row)
    assert event is not None  # RETURNING garante linha
    logger.info(
        "adverse_event.captured tenant=%s id=%s severity=%s via=%s",
        tenant_id, event.id, severity, reported_via,
    )
    return event


def get_event(event_id: int, *, tenant_id: int) -> Optional[AdverseEvent]:
    """Busca um evento escopado ao tenant."""
    row = repo.get_adverse_event(event_id, tenant_id=tenant_id)
    return _row_to_event(row)


def list_events(
    tenant_id: int,
    *,
    member_id: Optional[int] = None,
    severity: Optional[str] = None,
    reported_via: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    has_triage: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AdverseEvent]:
    """
    Lista eventos do tenant com filtros para dashboards.

    Valida whitelists dos filtros (`severity`, `reported_via`) para evitar
    queries silenciosamente vazias por enum invalido.
    """
    if severity is not None and severity not in SEVERITY_CHOICES:
        raise AdverseEventValidationError(
            f"filtro severity invalido: {severity!r}"
        )
    if reported_via is not None and reported_via not in REPORTED_VIA_CHOICES:
        raise AdverseEventValidationError(
            f"filtro reported_via invalido: {reported_via!r}"
        )

    rows = repo.list_adverse_events(
        tenant_id,
        member_id=member_id,
        severity=severity,
        reported_via=reported_via,
        since=since,
        until=until,
        has_triage=has_triage,
        limit=limit,
        offset=offset,
    )
    return [e for e in (_row_to_event(r) for r in rows) if e is not None]


def count_by_severity(
    tenant_id: int,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> dict[str, int]:
    """
    Contagem de eventos por severidade no escopo/janela. Severidades sem
    eventos nao aparecem (consumidor deve default 0).
    """
    return repo.count_by_severity(tenant_id, since=since, until=until)


def record_triage_result(
    event_id: int,
    *,
    tenant_id: int,
    ai_triage_result: dict[str, Any],
    triaged_by: Optional[int] = None,
) -> Optional[AdverseEvent]:
    """
    Gancho para F3.4: grava o JSON bruto da triagem IA em
    `ai_triage_result`. Nao interpreta campos — o shape e contrato
    do `ai/agents/regulatorio.py`.
    """
    if not isinstance(ai_triage_result, dict):
        raise AdverseEventValidationError(
            "ai_triage_result deve ser dict serializavel em JSONB"
        )
    row = repo.update_triage_result(
        event_id,
        tenant_id=tenant_id,
        ai_triage_result=ai_triage_result,
        triaged_by=triaged_by,
    )
    return _row_to_event(row)


def set_clinical_assessment(
    event_id: int,
    *,
    tenant_id: int,
    assessment: str,
) -> Optional[AdverseEvent]:
    """Registra o parecer clinico do medico revisor."""
    if not assessment or not assessment.strip():
        raise AdverseEventValidationError(
            "clinical_assessment nao pode ser vazio"
        )
    row = repo.update_clinical_assessment(
        event_id, tenant_id=tenant_id, clinical_assessment=assessment.strip()
    )
    return _row_to_event(row)


def set_outcome(
    event_id: int,
    *,
    tenant_id: int,
    outcome: str,
) -> Optional[AdverseEvent]:
    """Atualiza o outcome clinico do evento (whitelist validada)."""
    if outcome not in OUTCOME_CHOICES:
        raise AdverseEventValidationError(
            f"outcome invalido: {outcome!r}. "
            f"Esperado um de {OUTCOME_CHOICES}"
        )
    row = repo.update_outcome(event_id, tenant_id=tenant_id, outcome=outcome)
    return _row_to_event(row)
