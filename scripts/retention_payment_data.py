"""
Retencao/expurgo LGPD do trilho de pagamento.

FIN-2 (doc 30 R2 / 29.6 R2 / 29.6 C2) — minimizacao de dados pessoais
financeiros em repouso. Espelha scripts/retention_audit_logs.py (Sprint 2
Track LGPD) e as migrations 044/045.

Roda diariamente via Render Cron Job (render.yaml: cannabia-payment-retention,
schedule "30 4 * * *"). pg_cron NAO esta disponivel em basic-256mb.

O que expurga (apos PAYMENT_DATA_RETENTION_DAYS, default 90d):
  1. payment_transactions.raw_payload -> '{}'::JSONB
     (payload bruto do PSP, contem CPF/end-to-end; payer_document ja entra
      mascarado na gravacao — aqui some o payload integral)
  2. payment_webhook_log.body/headers -> '{}'::JSONB, error_message -> NULL
     (trilha de debug de webhook; preserva provider/received_at/signature_ok/
      status_code como metadado de auditoria, descarta o conteudo sensivel)

Os REGISTROS sao preservados (ledger financeiro + metadados); apenas os campos
de PII bruta sao zerados. Filtro por received_at < cutoff — inserts novos
durante a execucao nunca sao afetados.

Idempotente: re-rodar so re-zera campos ja vazios (no-op efetivo).
Registra evento em payment_data_purge_events (executor_host='cron').

Retencao de 90d APROVADA (decisao do Andre, 2026-06-11) — sem gate juridico/
comercial na Onda 1. PAYMENT_PURGE_ENABLED e apenas o desligamento operacional
de emergencia; no Render fica "true". Default "false" quando a env nao existe,
para que execucoes manuais avulsas nao expurguem sem intencao.
"""
from __future__ import annotations

import logging
import os
import socket
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.lgpd.payment_retention")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("ENV %s invalido (%r) — usando default %d", name, raw, default)
        return default


def open_event(cutoff_iso: str, retention_days: int) -> Optional[int]:
    try:
        host = socket.gethostname()
    except Exception:  # noqa: BLE001
        host = "cron"

    summary = f"payment retention={retention_days}d"
    try:
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO payment_data_purge_events
                  (cutoff_timestamp, dry_run, retention_days, executor_user,
                   executor_host, error_summary)
                VALUES (%s, FALSE, %s, %s, %s, %s)
                RETURNING id
                """,
                (cutoff_iso, retention_days, "cron", host or "cron", summary),
            )
            event_id = cur.fetchone()[0]
            conn.commit()
        return event_id
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao abrir payment purge_event — continuando sem tracking")
        return None


def finish_event(
    event_id: Optional[int],
    tx_payloads_redacted: int,
    webhook_logs_redacted: int,
    rows_failed: int,
    error_summary: Optional[str] = None,
) -> None:
    if event_id is None:
        return
    try:
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                UPDATE payment_data_purge_events
                SET finished_at = NOW(),
                    tx_payloads_redacted = %s,
                    webhook_logs_redacted = %s,
                    rows_failed = %s,
                    error_summary = COALESCE(%s, error_summary)
                WHERE id = %s
                """,
                (tx_payloads_redacted, webhook_logs_redacted, rows_failed,
                 error_summary, event_id),
            )
            conn.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao fechar payment purge_event id=%s", event_id)


# =====================================================
# Core: redact in place (apos cutoff)
# =====================================================

def redact_transaction_payloads(retention_days: int) -> int:
    """Zera raw_payload em payment_transactions com received_at < cutoff.

    Idempotente: WHERE raw_payload <> '{}' evita reescrever rows ja limpas.
    Returns: numero de rows efetivamente redigidas.
    """
    sql = """
        UPDATE payment_transactions
        SET raw_payload = '{}'::JSONB
        WHERE received_at < (NOW() - (%s || ' days')::INTERVAL)
          AND raw_payload IS NOT NULL
          AND raw_payload <> '{}'::JSONB
    """
    with db_cursor() as (conn, cur):
        cur.execute(sql, (retention_days,))
        n = cur.rowcount
        conn.commit()
    logger.info("payment_transactions.raw_payload redigidos: %d", n or 0)
    return int(n or 0)


def redact_webhook_logs(retention_days: int) -> int:
    """Zera body/headers/error_message em payment_webhook_log apos cutoff.

    Preserva provider/received_at/signature_ok/status_code (metadados de
    auditoria, sem PII). Idempotente.
    Returns: numero de rows efetivamente redigidas.
    """
    sql = """
        UPDATE payment_webhook_log
        SET body = '{}'::JSONB,
            headers = '{}'::JSONB,
            error_message = NULL
        WHERE received_at < (NOW() - (%s || ' days')::INTERVAL)
          AND (
            body <> '{}'::JSONB
            OR headers <> '{}'::JSONB
            OR error_message IS NOT NULL
          )
    """
    with db_cursor() as (conn, cur):
        cur.execute(sql, (retention_days,))
        n = cur.rowcount
        conn.commit()
    logger.info("payment_webhook_log body/headers redigidos: %d", n or 0)
    return int(n or 0)


# =====================================================
# Entrypoint
# =====================================================

def run() -> dict:
    retention_days = _env_int("PAYMENT_DATA_RETENTION_DAYS", 90)
    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(days=retention_days)
    ).isoformat()

    logger.info("Payment retention start — retention=%dd", retention_days)

    event_id = open_event(cutoff_iso, retention_days)
    error_summary: Optional[str] = None
    tx_redacted = 0
    log_redacted = 0
    rows_failed = 0

    try:
        tx_redacted = redact_transaction_payloads(retention_days)
        log_redacted = redact_webhook_logs(retention_days)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erro fatal em payment retention: %r", exc)
        error_summary = repr(exc)[:500]
        rows_failed = 1

    stats = {
        "event_id": event_id,
        "tx_payloads_redacted": tx_redacted,
        "webhook_logs_redacted": log_redacted,
        "rows_failed": rows_failed,
        "retention_days": retention_days,
    }

    finish_event(event_id, tx_redacted, log_redacted, rows_failed, error_summary)
    logger.info("Payment retention done: %s", stats)
    return stats


def main() -> int:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Toggle operacional (emergency off). No Render fica "true" (retencao de 90d
    # aprovada, Andre 2026-06-11). Default "false" quando a env nao existe.
    enabled = os.getenv("PAYMENT_PURGE_ENABLED", "false").strip().lower()
    if enabled not in {"true", "1", "yes"}:
        logger.info(
            "PAYMENT_PURGE_ENABLED=%r — payment retention DESATIVADO (no-op). "
            "Para ativar: set PAYMENT_PURGE_ENABLED=true no Render dashboard.",
            enabled,
        )
        return 0

    try:
        stats = run()
    except Exception:  # noqa: BLE001
        logger.exception("Falha fatal em payment retention")
        return 1

    if stats.get("rows_failed", 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
