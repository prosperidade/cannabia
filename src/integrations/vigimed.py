"""Notificacao regulatoria de eventos adversos — F3.5 do SCC.

Wrapper de submissao a orgaos reguladores (VigiMed/ANVISA e NotiVisa) com
dispatcher por provider. Segue o mesmo padrao arquitetural de F5.3
(``opentimestamps.py``) / F5.4 (``polygon_anchor.py``): protocolo abstrato
do client, implementacao mock deterministica para CI/dev, stubs de
producao com lazy import das libs oficiais, e dispatcher por env var.

Providers suportados (``ANVISA_NOTIFICATION_PROVIDER``):

  - ``mock``     — default em dev/CI. Gera ``notification_reference``
                   deterministica a partir do payload, sem tocar rede.
                   Persistencia posterior usa ``notification_target =
                   'internal_only'`` para refletir que a notificacao e
                   apenas registro interno sem envio regulatorio real.
  - ``vigimed``  — integracao oficial ANVISA (stub). Producao exige
                   credenciais e lib/client oficial — hoje levanta
                   :class:`VigiMedUnavailableError`.
  - ``notivisa`` — integracao estadual/municipal (stub). Mesmo tratamento.

Decoupling deliberado do DB:

  - Este modulo NAO persiste. Retorna :class:`NotificationReceipt` com o
    target + reference + payload de resposta. A gravacao na tabela
    ``pharmacovigilance_notifications`` e responsabilidade do blueprint
    ``pharmacovigilance`` (F3.6), que ira construir um service
    orquestrador.

Testabilidade:

  - ``submit_notification(..., client=None)`` aceita client injetavel.
  - ``_resolve_provider`` e publico o suficiente para testes
    verificarem a cascata de prioridade (arg > env > default).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

logger = logging.getLogger("cannabia.vigimed")


# ---------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------

NOTIFICATION_PROVIDER_ENV = "ANVISA_NOTIFICATION_PROVIDER"
VALID_PROVIDERS: frozenset[str] = frozenset({"mock", "vigimed", "notivisa"})
DEFAULT_PROVIDER = "mock"

# Mapeamento provider -> valor persistido em
# pharmacovigilance_notifications.notification_target (whitelist da
# migration 031: 'vigimed', 'notivisa', 'internal_only').
_PROVIDER_TO_TARGET: dict[str, str] = {
    "mock": "internal_only",
    "vigimed": "vigimed",
    "notivisa": "notivisa",
}

MOCK_MODEL_VERSION = "vigimed-mock-v1"


# ---------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------


class PharmacovigilanceError(Exception):
    """Base para erros do wrapper de notificacao regulatoria."""


class UnknownProviderError(PharmacovigilanceError):
    """Provider fora da whitelist ``VALID_PROVIDERS``."""


class VigiMedUnavailableError(PharmacovigilanceError):
    """Integracao real (vigimed/notivisa) nao plugada no ambiente."""


class VigiMedSubmissionError(PharmacovigilanceError):
    """Falha na submissao ao orgao regulador (rede, timeout, schema)."""


# ---------------------------------------------------------------------
# Receipt — shape estavel consumido por F3.6 (blueprint)
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class NotificationReceipt:
    """Resultado de uma submissao a orgao regulador.

    Attributes:
        notification_target: valor para
            ``pharmacovigilance_notifications.notification_target`` —
            'vigimed' | 'notivisa' | 'internal_only'.
        notification_reference: protocolo/identificador retornado pelo
            orgao (ou gerado deterministicamente pelo mock).
        submitted_at: timestamp UTC da submissao.
        response_payload: resposta bruta do orgao em formato JSON-
            serializavel. No mock, contem metadados sinteticos que
            permitem auditar a decisao.
    """

    notification_target: str
    notification_reference: str
    submitted_at: datetime
    response_payload: dict[str, Any]


# ---------------------------------------------------------------------
# Protocolo do client (para injection em testes)
# ---------------------------------------------------------------------


class _NotificationClient(Protocol):
    """Subset minimo que o dispatcher chama.

    Implementacoes reais (VigiMed, NotiVisa) devem traduzir o payload
    generico para o schema da agencia, submeter via HTTPS, e retornar o
    receipt preenchido.
    """

    def submit(self, payload: dict[str, Any]) -> NotificationReceipt: ...   # noqa: E704


# ---------------------------------------------------------------------
# Mock client — deterministico, sem rede
# ---------------------------------------------------------------------


class MockNotificationClient:
    """Client sem efeito colateral externo. Usado em CI e dev.

    A ``notification_reference`` e deterministica: SHA-256 do payload
    canonicalizado em JSON. Mesmo payload => mesma referencia, util
    para idempotencia em testes.
    """

    def __init__(self, *, provider: str = "mock") -> None:
        if provider not in VALID_PROVIDERS:
            raise UnknownProviderError(
                f"Provider '{provider}' invalido "
                f"(permitidos: {sorted(VALID_PROVIDERS)})."
            )
        self._provider = provider

    def submit(self, payload: dict[str, Any]) -> NotificationReceipt:
        canon = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
        digest = hashlib.sha256(canon.encode("utf-8")).hexdigest()
        reference = f"MOCK-{digest[:16].upper()}"
        submitted_at = datetime.now(timezone.utc)
        target = _PROVIDER_TO_TARGET[self._provider]

        response_payload = {
            "provider": self._provider,
            "model_version": MOCK_MODEL_VERSION,
            "accepted": True,
            "reference": reference,
            "received_at": submitted_at.isoformat(),
            "note": (
                "Notificacao simulada — nenhum dado saiu do sistema. "
                "Para envio regulatorio real, configurar "
                f"{NOTIFICATION_PROVIDER_ENV}=vigimed ou =notivisa."
            ),
        }
        logger.info(
            "mock_notification provider=%s target=%s reference=%s",
            self._provider, target, reference,
        )
        return NotificationReceipt(
            notification_target=target,
            notification_reference=reference,
            submitted_at=submitted_at,
            response_payload=response_payload,
        )


# ---------------------------------------------------------------------
# Production stubs — lazy import das libs reais
# ---------------------------------------------------------------------


class _ProductionVigiMedClient:                              # pragma: no cover
    """Stub do client VigiMed. Ativacao exige credenciais da ANVISA
    e a biblioteca/sdk oficial (a ser definida em F3.6/ops).
    Enquanto nao plugado, qualquer submissao falha com erro claro."""

    def submit(self, payload: dict[str, Any]) -> NotificationReceipt:
        raise VigiMedSubmissionError(
            "Client VigiMed real nao plugado (F3.5 deixa o wrapper em "
            "place; integracao oficial com ANVISA depende de "
            "credenciais e lib publicada)."
        )


class _ProductionNotivisaClient:                             # pragma: no cover
    """Stub analogo para NotiVisa (sistema estadual/municipal)."""

    def submit(self, payload: dict[str, Any]) -> NotificationReceipt:
        raise VigiMedSubmissionError(
            "Client NotiVisa real nao plugado (F3.5 deixa o wrapper em "
            "place; integracao oficial depende do estado/municipio "
            "destino)."
        )


def _load_client_for(provider: str) -> _NotificationClient:
    """Fabrica do client concreto para o provider resolvido.

    Raises:
        UnknownProviderError: provider fora da whitelist.
        VigiMedUnavailableError: lib oficial nao instalada (so em
            vigimed/notivisa).
    """
    if provider == "mock":
        return MockNotificationClient(provider="mock")
    if provider == "vigimed":
        try:
            return _ProductionVigiMedClient()               # pragma: no cover
        except ImportError as exc:                          # pragma: no cover
            raise VigiMedUnavailableError(
                "Lib oficial VigiMed nao instalada no ambiente."
            ) from exc
    if provider == "notivisa":
        try:
            return _ProductionNotivisaClient()              # pragma: no cover
        except ImportError as exc:                          # pragma: no cover
            raise VigiMedUnavailableError(
                "Lib oficial NotiVisa nao instalada no ambiente."
            ) from exc
    raise UnknownProviderError(
        f"Provider '{provider}' invalido "
        f"(permitidos: {sorted(VALID_PROVIDERS)})."
    )


# ---------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------


def _resolve_provider(explicit: Optional[str]) -> str:
    """Resolve qual provider usar.

    Prioridade: argumento explicito > env ``ANVISA_NOTIFICATION_PROVIDER``
    > ``DEFAULT_PROVIDER`` ('mock').

    Raises:
        UnknownProviderError: valor resolvido fora da whitelist.
    """
    candidate = (
        explicit
        or os.environ.get(NOTIFICATION_PROVIDER_ENV)
        or DEFAULT_PROVIDER
    ).lower()
    if candidate not in VALID_PROVIDERS:
        raise UnknownProviderError(
            f"Provider '{candidate}' invalido "
            f"(permitidos: {sorted(VALID_PROVIDERS)})."
        )
    return candidate


def build_notification_payload(adverse_event: Any) -> dict[str, Any]:
    """Serializa um evento adverso (dict ou dataclass) para o formato
    generico consumido pelos clients.

    Tenta ler atributos comuns e normalizar datetimes para ISO-8601.
    A escolha do que o orgao regulador precisa ver fica com o client
    concreto (que fara mapping para o schema oficial).
    """
    def _get(name: str) -> Any:
        if adverse_event is None:
            return None
        if isinstance(adverse_event, dict):
            return adverse_event.get(name)
        return getattr(adverse_event, name, None)

    def _iso(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    payload: dict[str, Any] = {
        "event_id": _get("id"),
        "tenant_id": _get("tenant_id"),
        "member_id": _get("member_id"),
        "preparation_id": _get("preparation_id"),
        "severity": _get("severity"),
        "reported_via": _get("reported_via"),
        "description": _get("description"),
        "reported_at": _iso(_get("reported_at")),
        "event_onset_at": _iso(_get("event_onset_at")),
        "clinical_assessment": _get("clinical_assessment"),
        "outcome": _get("outcome"),
        "ai_triage_result": _get("ai_triage_result"),
    }
    return payload


def submit_notification(
    adverse_event: Any,
    *,
    provider: Optional[str] = None,
    client: Optional[_NotificationClient] = None,
) -> NotificationReceipt:
    """Submete a notificacao de um evento adverso ao provider resolvido.

    Args:
        adverse_event: dict ou dataclass (compat com ``AdverseEvent`` do
            ``adverse_event_service``). Serializado via
            :func:`build_notification_payload`.
        provider: override explicito. Se ``None``, usa env var /
            ``DEFAULT_PROVIDER``.
        client: client injetavel (testes). Se ``None``, constroi via
            :func:`_load_client_for`.

    Returns:
        :class:`NotificationReceipt`. O caller (F3.6) grava em
        ``pharmacovigilance_notifications``.

    Raises:
        PharmacovigilanceError: falha na resolucao/submissao.
    """
    if adverse_event is None:
        raise VigiMedSubmissionError("adverse_event obrigatorio.")

    resolved = _resolve_provider(provider)
    active_client = client if client is not None else _load_client_for(resolved)

    payload = build_notification_payload(adverse_event)
    if not payload.get("description"):
        raise VigiMedSubmissionError(
            "adverse_event sem descricao — payload insuficiente para "
            "notificacao regulatoria."
        )

    try:
        receipt = active_client.submit(payload)
    except PharmacovigilanceError:
        raise
    except Exception as exc:
        raise VigiMedSubmissionError(
            f"Falha ao submeter notificacao (provider={resolved}): {exc}"
        ) from exc

    logger.info(
        "submit_notification provider=%s target=%s reference=%s event_id=%s",
        resolved, receipt.notification_target, receipt.notification_reference,
        payload.get("event_id"),
    )
    return receipt
