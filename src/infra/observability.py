"""
Observabilidade Sentry — Sprint 2 Track Obs (init) + Sprint 3 Track Obs-Harden.

Plug Sentry SDK em producao com sanitizacao rigorosa de PII (LGPD-critical
em contexto clinico) e tags uteis pra forensics:
    - request_id, user_id, clinic_id, tenant_id (via tag_request).

Decisoes do coordenador Sprint 2 (Q-Obs-1..5):
    - SOFT em prod: SENTRY_DSN ausente nao bloqueia deploy.  ⚠ SUPERSEDED.
    - DEFENSE IN DEPTH: send_default_pii=False (Sentry nativo) +
      before_send hook reusando sanitize_clinical_payload (Track A.3).
    - traces_sample_rate=0.0 — performance traces OFF Sprint 2 (caro).
                                                           ⚠ SUPERSEDED.
    - include_local_variables=False — locals em traceback podem vazar PII.
                                                           ⚠ SUPERSEDED.
    - LoggingIntegration: ERROR vira event Sentry, WARNING vira breadcrumb.

Decisoes Sprint 3 Track Obs-Harden (Q-OH-1..5), supersede Sprint 2:
    - Q-OH-1: SENTRY_DSN obrigatorio em prod — raise direto (config.py).
    - Q-OH-2: traces_sample_rate=0.1 (10% piloto pra calibrar Sprint 4),
              override via SENTRY_TRACES_SAMPLE_RATE com clamp 0..1.
    - Q-OH-3: include_local_variables=True SEMPRE — sanitizacao em
              _sentry_before_send via walk recursivo em frames[].vars
              (sanitize_clinical_payload) e' a defesa, nao FLASK_ENV.

FAIL-SAFE: _sentry_before_send NUNCA raise. Se sanitization quebrar,
DROPA o event (return None) — preferir perder telemetria do que vazar PII.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("cannabia.observability")

# Imports defensivos: sentry_sdk pode nao estar instalado em algum
# ambiente exotico (teste de conftest sem deps, por exemplo). Toda
# call site checa estas flags.
try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    _SENTRY_AVAILABLE = True
except ImportError:  # pragma: no cover — defensivo
    sentry_sdk = None  # type: ignore[assignment]
    FlaskIntegration = None  # type: ignore[assignment,misc]
    LoggingIntegration = None  # type: ignore[assignment,misc]
    _SENTRY_AVAILABLE = False


def _sentry_before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Hook before_send — sanitiza PII antes do event sair pra Sentry.

    Walk em campos conhecidos do event:
        - event["request"]["data"]
        - event["extra"]
        - event["breadcrumbs"][i]["data"]
        - event["exception"]["values"][i]["stacktrace"]["frames"][j]["vars"]

    Reusa sanitize_clinical_payload (Track A.3 / src/ai/audit_redaction.py)
    pra consistencia com o redactor de ai_audit_logs.

    FAIL-SAFE OBRIGATORIO: se sanitizer quebrar, DROPA o event retornando
    None. Em LGPD-critical, perder um event Sentry e' aceitavel; vazar
    PII em DSN externo NAO e'.
    """
    # Import local pra evitar custo de import se Sentry desligado.
    try:
        from src.ai.audit_redaction import sanitize_clinical_payload
    except Exception as exc:  # pragma: no cover — defensivo
        logger.error("Falha ao importar sanitize_clinical_payload: %r", exc)
        return None

    try:
        # 1. request.data
        request = event.get("request")
        if isinstance(request, dict):
            data = request.get("data")
            if data is not None:
                request["data"] = sanitize_clinical_payload(data)

        # 2. extra (free-form context anexado via sentry_sdk.set_extra)
        extra = event.get("extra")
        if extra is not None:
            event["extra"] = sanitize_clinical_payload(extra)

        # 3. breadcrumbs (lista de eventos historicos)
        breadcrumbs = event.get("breadcrumbs")
        if isinstance(breadcrumbs, dict):
            # Sentry SDK >= 1.x usa {"values": [...]}
            values = breadcrumbs.get("values")
            if isinstance(values, list):
                for crumb in values:
                    if isinstance(crumb, dict) and crumb.get("data") is not None:
                        crumb["data"] = sanitize_clinical_payload(crumb["data"])
        elif isinstance(breadcrumbs, list):
            # Compat com formato antigo (lista direta)
            for crumb in breadcrumbs:
                if isinstance(crumb, dict) and crumb.get("data") is not None:
                    crumb["data"] = sanitize_clinical_payload(crumb["data"])

        # 4. exception.values[i].stacktrace.frames[j].vars
        exception = event.get("exception")
        if isinstance(exception, dict):
            values = exception.get("values")
            if isinstance(values, list):
                for exc_value in values:
                    if not isinstance(exc_value, dict):
                        continue
                    stacktrace = exc_value.get("stacktrace")
                    if not isinstance(stacktrace, dict):
                        continue
                    frames = stacktrace.get("frames")
                    if not isinstance(frames, list):
                        continue
                    for frame in frames:
                        if not isinstance(frame, dict):
                            continue
                        vars_ = frame.get("vars")
                        if vars_ is not None:
                            frame["vars"] = sanitize_clinical_payload(vars_)

        return event
    except BaseException as exc:  # noqa: BLE001 — fail-safe abrangente
        logger.error(
            "Falha em _sentry_before_send — DROPANDO event pra evitar vazamento PII. "
            "Erro: %r",
            exc,
        )
        return None


def init_sentry(config: dict[str, Any] | None) -> None:
    """Inicializa Sentry SDK com config sanitizada.

    Se config for None (DSN ausente), nao chama sentry_sdk.init — app
    sobe sem observabilidade externa (decisao Q-Obs-1: soft em prod).

    Se sentry_sdk nao estiver instalado, loga warning e segue.
    """
    if config is None:
        logger.debug("init_sentry: config None, Sentry off.")
        return

    if not _SENTRY_AVAILABLE:
        logger.warning(
            "init_sentry: sentry-sdk nao instalado, mas SENTRY_DSN configurado. "
            "Adicione 'sentry-sdk[flask]>=2.0.0' a requirements.txt."
        )
        return

    try:
        sentry_sdk.init(
            dsn=config["dsn"],
            environment=config.get("environment", "development"),
            sample_rate=config.get("sample_rate", 1.0),
            # Q-OH-2 (Sprint 3 Obs-Harden): traces 10% piloto. Valor vem do
            # config dict (env override SENTRY_TRACES_SAMPLE_RATE, default 0.1).
            traces_sample_rate=config.get("traces_sample_rate", 0.1),
            send_default_pii=False,  # Q-Obs-2: denylist nativa
            # Q-OH-3 (Sprint 3 Obs-Harden): TRUE sempre. Locals em traceback
            # sao valiosos pra debug, e o walk recursivo em
            # exception.values[].stacktrace.frames[].vars dentro de
            # _sentry_before_send ja sanitiza PII via sanitize_clinical_payload
            # (Track A.3). Defesa em sanitizacao, nao em FLASK_ENV.
            # (Era with_locals em sentry-sdk 1.x; renomeado em 2.x.)
            include_local_variables=True,
            before_send=_sentry_before_send,
            integrations=[
                FlaskIntegration(),
                LoggingIntegration(
                    level=logging.WARNING,        # WARNING vira breadcrumb
                    event_level=logging.ERROR,    # ERROR/CRITICAL vira event
                ),
            ],
        )
        logger.info(
            "Sentry inicializado — environment=%s sample_rate=%s traces_sample_rate=%s",
            config.get("environment"),
            config.get("sample_rate"),
            config.get("traces_sample_rate"),
        )
    except Exception as exc:  # noqa: BLE001 — Sentry init nao deve quebrar app
        logger.error("Falha ao inicializar Sentry: %r", exc)


def tag_request(g: Any) -> None:
    """Anexa tags request-scope ao escopo Sentry corrente.

    Chamado num before_request APOS request_id estar setado em g.
    Usa getattr defensivo — se algum atributo nao estiver setado
    (request publico sem auth, por exemplo), apenas omite a tag.

    Tags:
        - request_id (correlacao cross-log)
        - user_id (via set_user — separado, conforme convencao Sentry)
        - clinic_id (forensics multi-tenant)
        - tenant_id (forensics multi-tenant)
    """
    if not _SENTRY_AVAILABLE:
        return

    try:
        request_id = getattr(g, "request_id", None)
        if request_id is not None:
            sentry_sdk.set_tag("request_id", str(request_id))

        user_id = getattr(g, "user_id", None)
        if user_id is not None:
            sentry_sdk.set_user({"id": str(user_id)})

        clinic_id = getattr(g, "clinic_id", None)
        if clinic_id is not None:
            sentry_sdk.set_tag("clinic_id", str(clinic_id))

        tenant_id = getattr(g, "tenant_id", None)
        if tenant_id is not None:
            sentry_sdk.set_tag("tenant_id", str(tenant_id))
    except Exception as exc:  # noqa: BLE001 — tag failure nao deve quebrar request
        logger.warning("Falha em tag_request: %r", exc)
