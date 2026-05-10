"""
Retention policy automatizada para ai_audit_logs.

Sprint 2 Track LGPD — fecha Divida 2 do BACKLOG_LGPD.md.

Roda diariamente via Render Cron Job (render.yaml: cannabia-audit-retention,
schedule "0 4 * * *"). pg_cron NAO esta disponivel em basic-256mb.

Estrategia archive-then-delete (decisao do coordenador):
  1. Move rows aposentados pra ai_audit_logs_archive (com archived_at).
  2. DELETE em ai_audit_logs.
  3. Cleanup do archive: DELETE em ai_audit_logs_archive cujo archived_at
     ultrapassa LGPD_AUDIT_ARCHIVE_RETENTION_DAYS.

Prazos defensaveis (Q-LGPD-2) MAS production run espera OK juridico:
  LGPD_AUDIT_RETENTION_DAYS_DETAIL    = 90    (rows comuns)
  LGPD_AUDIT_RETENTION_DAYS_CRITICAL  = 365   (status IN ('security_blocked','error'))
  LGPD_AUDIT_ARCHIVE_RETENTION_DAYS   = 1825  (5y — cleanup do archive)

Critical = mais relevante pra forensics + investigacao de incidente.
Detail = ja serviu seu proposito de operacao/dashboard.

Idempotente + transactional. Race com inserts em ai_audit_logs durante
a execucao NAO afeta rows novos (filtro por created_at < threshold).

Registra evento em ai_audit_purge_events (executor_host='cron').
"""
from __future__ import annotations

import logging
import os
import socket
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.lgpd.retention")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("ENV %s invalido (%r) — usando default %d", name, raw, default)
        return default


CRITICAL_STATUSES = ("security_blocked", "error")


def open_event(
    cutoff_iso: str,
    detail_days: int,
    critical_days: int,
    archive_days: int,
) -> Optional[int]:
    try:
        host = socket.gethostname()
    except Exception:  # noqa: BLE001
        host = "cron"

    summary = (
        f"retention detail={detail_days}d critical={critical_days}d "
        f"archive_cleanup={archive_days}d"
    )

    try:
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO ai_audit_purge_events
                  (cutoff_timestamp, dry_run, batch_size, executor_user,
                   executor_host, error_summary)
                VALUES (%s, FALSE, 0, %s, %s, %s)
                RETURNING id
                """,
                (cutoff_iso, "cron", host or "cron", summary),
            )
            event_id = cur.fetchone()[0]
            conn.commit()
        return event_id
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao abrir purge_event — continuando sem tracking")
        return None


def finish_event(
    event_id: Optional[int],
    rows_scanned: int,
    rows_updated: int,
    rows_failed: int,
    error_summary: Optional[str] = None,
) -> None:
    if event_id is None:
        return
    try:
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                UPDATE ai_audit_purge_events
                SET finished_at = NOW(),
                    rows_scanned = %s,
                    rows_updated = %s,
                    rows_failed = %s,
                    error_summary = COALESCE(%s, error_summary)
                WHERE id = %s
                """,
                (rows_scanned, rows_updated, rows_failed, error_summary, event_id),
            )
            conn.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao fechar purge_event id=%s", event_id)


# =====================================================
# Core: archive + delete (single transaction)
# =====================================================

def archive_and_delete(
    detail_days: int, critical_days: int
) -> tuple[int, int]:
    """Move logs aposentados pra archive e DELETE em ai_audit_logs.

    Predicate:
      created_at < (NOW() - detail_days)
      AND (status NOT IN critical OR created_at < (NOW() - critical_days))

    Significa: rows comuns saem com 90d. Rows criticos so com 365d.

    Returns: (archived_count, archive_failed_count)
    """
    archived = 0
    failed = 0

    # CTE: copia + delete na mesma tx pra evitar race com inserts
    # concorrentes (rows novos tem created_at recente, fora do filtro).
    sql = """
    WITH to_archive AS (
        SELECT *
        FROM ai_audit_logs
        WHERE created_at < (NOW() - (%(detail)s || ' days')::INTERVAL)
          AND (
            status NOT IN %(critical_statuses)s
            OR created_at < (NOW() - (%(critical)s || ' days')::INTERVAL)
          )
    ),
    inserted AS (
        INSERT INTO ai_audit_logs_archive
        SELECT *, NOW() AS archived_at FROM to_archive
        RETURNING id
    ),
    deleted AS (
        DELETE FROM ai_audit_logs
        WHERE id IN (SELECT id FROM inserted)
        RETURNING id
    )
    SELECT (SELECT COUNT(*) FROM inserted) AS archived,
           (SELECT COUNT(*) FROM deleted)  AS deleted;
    """
    try:
        with db_cursor() as (conn, cur):
            cur.execute(
                sql,
                {
                    "detail": detail_days,
                    "critical": critical_days,
                    "critical_statuses": CRITICAL_STATUSES,
                },
            )
            row = cur.fetchone()
            archived_count = int(row[0])
            deleted_count = int(row[1])
            conn.commit()

        if archived_count != deleted_count:
            logger.error(
                "INCONSISTENCIA: archived=%d != deleted=%d",
                archived_count,
                deleted_count,
            )
            failed = abs(archived_count - deleted_count)

        archived = archived_count
        logger.info(
            "Retention archive+delete: archived=%d deleted=%d",
            archived_count,
            deleted_count,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha em archive_and_delete: %r", exc)
        failed += 1

    return archived, failed


def cleanup_archive(archive_days: int) -> int:
    """DELETE em ai_audit_logs_archive cujo archived_at expirou."""
    try:
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                DELETE FROM ai_audit_logs_archive
                WHERE archived_at < (NOW() - (%s || ' days')::INTERVAL)
                """,
                (archive_days,),
            )
            deleted = cur.rowcount
            conn.commit()
        logger.info("Cleanup archive: deleted=%d (TTL %dd)", deleted, archive_days)
        return int(deleted or 0)
    except Exception:  # noqa: BLE001
        logger.exception("Falha em cleanup_archive")
        return 0


# =====================================================
# Entrypoint
# =====================================================

def run() -> dict:
    detail_days = _env_int("LGPD_AUDIT_RETENTION_DAYS_DETAIL", 90)
    critical_days = _env_int("LGPD_AUDIT_RETENTION_DAYS_CRITICAL", 365)
    archive_days = _env_int("LGPD_AUDIT_ARCHIVE_RETENTION_DAYS", 1825)

    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(days=detail_days)
    ).isoformat()

    logger.info(
        "Retention start — detail=%dd critical=%dd archive_cleanup=%dd",
        detail_days,
        critical_days,
        archive_days,
    )

    event_id = open_event(cutoff_iso, detail_days, critical_days, archive_days)
    error_summary: Optional[str] = None

    try:
        archived, archive_failed = archive_and_delete(detail_days, critical_days)
        cleaned = cleanup_archive(archive_days)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erro fatal em retention: %r", exc)
        error_summary = repr(exc)[:500]
        archived = 0
        archive_failed = 1
        cleaned = 0

    stats = {
        "event_id": event_id,
        "archived": archived,
        "archive_failed": archive_failed,
        "archive_cleanup_deleted": cleaned,
        "detail_days": detail_days,
        "critical_days": critical_days,
        "archive_days": archive_days,
    }

    finish_event(
        event_id,
        rows_scanned=archived + cleaned,
        rows_updated=archived + cleaned,
        rows_failed=archive_failed,
        error_summary=error_summary,
    )

    logger.info("Retention done: %s", stats)
    return stats


def main() -> int:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        stats = run()
    except Exception:  # noqa: BLE001
        logger.exception("Falha fatal em retention")
        return 1

    if stats.get("archive_failed", 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
