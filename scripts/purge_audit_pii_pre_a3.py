"""
Purge retroativo de PII em ai_audit_logs gravados ANTES do merge de A.3.

Sprint 2 Track LGPD — fecha Divida 1 do BACKLOG_LGPD.md.

A.3 (commit aae1237) introduziu sanitize_clinical_payload em
src/repositories/ai_audit_repository.py:67-68. Toda gravacao A PARTIR do
merge fica protegida. Logs gravados antes (cutoff default
2026-05-10T17:00:00Z, 1h margin pos-merge) passaram em claro e precisam
de re-sanitizacao in-place.

Estrategia (Q-LGPD-2/3/5/7):
  1. Snapshot backup table ai_audit_logs_pre_redact_backup_<YYYYMMDD>
     com TTL 30d (alerta manual no runbook). CREATE IF NOT EXISTS = idempotente.
  2. Loop batched: SELECT id, input_payload, output_payload de rows
     anteriores ao cutoff que nao estao em ai_audit_purge_processed_ids
     -> aplica sanitize_clinical_payload -> UPDATE in-place + insert em
     ai_audit_purge_processed_ids dentro da mesma tx.
  3. Evento gravado em ai_audit_purge_events (started/finished/contagens).

Mutually exclusive: --dry-run (default) e --commit.
Cutoff fixo 2026-05-10T17:00:00+00:00 (override por --cutoff).

CRITICO: idempotencia depende de sanitize ser f(f(x))==f(x)
(garantido pelos testes em tests/test_audit_redaction.py:test_sanitize_idempotent_*).
"""
from __future__ import annotations

import argparse
import getpass
import json
import logging
import socket
import sys
from datetime import datetime, timezone
from typing import Optional

from src.ai.audit_redaction import sanitize_clinical_payload
from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.lgpd.purge_audit_pii")


DEFAULT_CUTOFF = "2026-05-10T17:00:00+00:00"
DEFAULT_BATCH_SIZE = 1000
SNAPSHOT_TABLE_PREFIX = "ai_audit_logs_pre_redact_backup_"


# =====================================================
# CLI
# =====================================================

def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="purge_audit_pii_pre_a3",
        description=(
            "Purge LGPD: re-sanitiza in-place rows de ai_audit_logs "
            "gravados antes do merge de A.3 (cutoff default %s)." % DEFAULT_CUTOFF
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Default. Estima volume + lista impacto sem mutar DB.",
    )
    mode.add_argument(
        "--commit",
        action="store_true",
        default=False,
        help="Aplica UPDATE in-place. Requer snapshot ja criado.",
    )
    parser.add_argument(
        "--cutoff",
        default=DEFAULT_CUTOFF,
        help="ISO8601 timestamp tz-aware. Rows com created_at < cutoff sao alvo.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Rows por batch (default %d)." % DEFAULT_BATCH_SIZE,
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Safety stop em N batches (default: ilimitado, mas warn).",
    )
    parser.add_argument(
        "--clinic-id",
        type=int,
        default=None,
        help="Restringe purge a 1 clinic_id (default: todos).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )

    args = parser.parse_args(argv)

    # Quando o usuario passa --commit explicito, dry_run vira False.
    # argparse mantem dry_run=True por causa do default e do
    # mutually_exclusive_group, entao reconciliamos manualmente:
    if args.commit:
        args.dry_run = False
    else:
        args.dry_run = True

    return args


# =====================================================
# Snapshot table (TTL 30d)
# =====================================================

def _snapshot_table_name(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"{SNAPSHOT_TABLE_PREFIX}{now.strftime('%Y%m%d')}"


def ensure_snapshot(cutoff_iso: str, dry_run: bool) -> str:
    """Cria snapshot ai_audit_logs_pre_redact_backup_YYYYMMDD se nao existir.

    Idempotente: CREATE TABLE IF NOT EXISTS ... AS SELECT ... WHERE created_at < cutoff.
    Em dry-run apenas reporta o nome que seria usado.
    """
    snapshot_name = _snapshot_table_name()
    if dry_run:
        logger.info("[dry-run] snapshot que seria criado: %s", snapshot_name)
        return snapshot_name

    with db_cursor() as (conn, cur):
        # Verifica se ja existe
        cur.execute(
            "SELECT to_regclass(%s) IS NOT NULL", (f"public.{snapshot_name}",)
        )
        exists = cur.fetchone()[0]
        if exists:
            logger.info("Snapshot ja existe: %s (sem recriar)", snapshot_name)
            return snapshot_name

        logger.info(
            "Criando snapshot %s com rows anteriores a %s...",
            snapshot_name,
            cutoff_iso,
        )
        cur.execute(
            f"CREATE TABLE {snapshot_name} AS "
            "SELECT * FROM ai_audit_logs WHERE created_at < %s",
            (cutoff_iso,),
        )
        conn.commit()
        cur.execute(f"SELECT COUNT(*) FROM {snapshot_name}")
        count = cur.fetchone()[0]
        logger.info(
            "Snapshot %s criado com %d rows. TTL 30d — agendar DROP no runbook.",
            snapshot_name,
            count,
        )
    return snapshot_name


# =====================================================
# Event row
# =====================================================

def open_purge_event(
    cutoff_iso: str, dry_run: bool, batch_size: int, dry_run_persist: bool = True
) -> Optional[int]:
    """Insere row em ai_audit_purge_events e devolve o id.

    Em dry-run NAO cria event row por padrao (evita poluir tabela). Caso
    user queira tracking de dry-runs, dry_run_persist=False muda comportamento.
    """
    if dry_run and not dry_run_persist:
        return None

    try:
        host = socket.gethostname()
    except Exception:  # noqa: BLE001
        host = None
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = None

    with db_cursor() as (conn, cur):
        cur.execute(
            """
            INSERT INTO ai_audit_purge_events
              (cutoff_timestamp, dry_run, batch_size, executor_user, executor_host)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (cutoff_iso, dry_run, batch_size, user, host),
        )
        event_id = cur.fetchone()[0]
        conn.commit()
    return event_id


def update_purge_event(
    event_id: Optional[int],
    *,
    rows_scanned: Optional[int] = None,
    rows_updated: Optional[int] = None,
    rows_failed: Optional[int] = None,
    finished: bool = False,
    error_summary: Optional[str] = None,
) -> None:
    if event_id is None:
        return
    sets = []
    params: list = []
    if rows_scanned is not None:
        sets.append("rows_scanned = %s")
        params.append(rows_scanned)
    if rows_updated is not None:
        sets.append("rows_updated = %s")
        params.append(rows_updated)
    if rows_failed is not None:
        sets.append("rows_failed = %s")
        params.append(rows_failed)
    if finished:
        sets.append("finished_at = NOW()")
    if error_summary is not None:
        sets.append("error_summary = %s")
        params.append(error_summary)
    if not sets:
        return
    params.append(event_id)
    with db_cursor() as (conn, cur):
        cur.execute(
            f"UPDATE ai_audit_purge_events SET {', '.join(sets)} WHERE id = %s",
            params,
        )
        conn.commit()


# =====================================================
# Core loop
# =====================================================

def _estimate_total(cutoff_iso: str, clinic_id: Optional[int]) -> int:
    where = ["created_at < %s"]
    params: list = [cutoff_iso]
    if clinic_id is not None:
        where.append("clinic_id = %s")
        params.append(clinic_id)
    where.append(
        "id NOT IN (SELECT audit_log_id FROM ai_audit_purge_processed_ids)"
    )
    sql = (
        "SELECT COUNT(*) FROM ai_audit_logs WHERE " + " AND ".join(where)
    )
    with db_cursor() as (_, cur):
        cur.execute(sql, params)
        return int(cur.fetchone()[0])


def _fetch_batch(
    cutoff_iso: str, clinic_id: Optional[int], batch_size: int
) -> list[tuple]:
    where = ["created_at < %s"]
    params: list = [cutoff_iso]
    if clinic_id is not None:
        where.append("clinic_id = %s")
        params.append(clinic_id)
    where.append(
        "id NOT IN (SELECT audit_log_id FROM ai_audit_purge_processed_ids)"
    )
    sql = (
        "SELECT id, input_payload, output_payload FROM ai_audit_logs "
        "WHERE " + " AND ".join(where) + " ORDER BY id LIMIT %s"
    )
    params.append(batch_size)
    with db_cursor() as (_, cur):
        cur.execute(sql, params)
        return list(cur.fetchall())


def _apply_batch(
    rows: list[tuple],
    event_id: Optional[int],
    dry_run: bool,
) -> tuple[int, int]:
    """Sanitiza + UPDATE in-place rows do batch + marca processed.

    Returns (updated_count, failed_count).
    """
    updated = 0
    failed = 0
    if dry_run:
        # Apenas conta — nao toca DB.
        for _ in rows:
            updated += 1
        return updated, failed

    with db_cursor() as (conn, cur):
        for row_id, input_payload, output_payload in rows:
            try:
                new_input = sanitize_clinical_payload(input_payload)
                new_output = (
                    sanitize_clinical_payload(output_payload)
                    if output_payload is not None
                    else None
                )
                cur.execute(
                    "UPDATE ai_audit_logs SET input_payload = %s, output_payload = %s "
                    "WHERE id = %s",
                    (
                        json.dumps(new_input, ensure_ascii=False),
                        json.dumps(new_output, ensure_ascii=False)
                        if new_output is not None
                        else None,
                        row_id,
                    ),
                )
                cur.execute(
                    "INSERT INTO ai_audit_purge_processed_ids "
                    "(audit_log_id, purge_event_id) VALUES (%s, %s) "
                    "ON CONFLICT (audit_log_id) DO NOTHING",
                    (row_id, event_id),
                )
                updated += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("Falha sanitize row id=%s: %r", row_id, exc)
                failed += 1
                # NAO bloqueia o batch — apenas registra.
        conn.commit()
    return updated, failed


def run_purge(args: argparse.Namespace) -> dict:
    """Driver principal. Devolve dict de stats."""
    cutoff_iso = args.cutoff
    dry_run = args.dry_run
    batch_size = args.batch_size
    max_batches = args.max_batches
    clinic_id = args.clinic_id

    logger.info(
        "Iniciando purge LGPD — mode=%s cutoff=%s batch=%d clinic=%s max_batches=%s",
        "DRY-RUN" if dry_run else "COMMIT",
        cutoff_iso,
        batch_size,
        clinic_id if clinic_id is not None else "ALL",
        max_batches if max_batches is not None else "unlimited",
    )

    if max_batches is None:
        logger.warning(
            "max_batches=unlimited: script roda ate esgotar rows. "
            "Pra safety stop, use --max-batches N."
        )

    snapshot_name = ensure_snapshot(cutoff_iso, dry_run)
    event_id = open_purge_event(cutoff_iso, dry_run, batch_size)

    estimated_total = _estimate_total(cutoff_iso, clinic_id)
    logger.info("Total estimado de rows pendentes: %d", estimated_total)

    if estimated_total == 0:
        logger.info("Nada a fazer.")
        update_purge_event(
            event_id,
            rows_scanned=0,
            rows_updated=0,
            rows_failed=0,
            finished=True,
        )
        return {
            "snapshot": snapshot_name,
            "event_id": event_id,
            "estimated_total": 0,
            "rows_scanned": 0,
            "rows_updated": 0,
            "rows_failed": 0,
            "batches": 0,
        }

    total_scanned = 0
    total_updated = 0
    total_failed = 0
    batch_num = 0
    error_summary: Optional[str] = None

    try:
        while True:
            if max_batches is not None and batch_num >= max_batches:
                logger.info("Safety stop: atingido max_batches=%d", max_batches)
                break

            rows = _fetch_batch(cutoff_iso, clinic_id, batch_size)
            if not rows:
                break

            batch_num += 1
            updated, failed = _apply_batch(rows, event_id, dry_run)
            total_scanned += len(rows)
            total_updated += updated
            total_failed += failed

            # Update event com progresso (so nao-dry-run pra evitar lock)
            if not dry_run:
                update_purge_event(
                    event_id,
                    rows_scanned=total_scanned,
                    rows_updated=total_updated,
                    rows_failed=total_failed,
                )

            pct = (total_scanned / estimated_total * 100) if estimated_total else 0
            logger.info(
                "[batch %d] scanned=%d updated=%d failed=%d (%.1f%%)",
                batch_num,
                total_scanned,
                total_updated,
                total_failed,
                pct,
            )

            # Em dry-run, sai apos primeiro batch — apenas amostragem.
            if dry_run:
                logger.info(
                    "[dry-run] saindo apos primeiro batch. "
                    "Total pendente real: %d rows.",
                    estimated_total,
                )
                break
    except Exception as exc:  # noqa: BLE001
        error_summary = repr(exc)[:500]
        logger.exception("Erro fatal durante purge: %r", exc)
    finally:
        update_purge_event(
            event_id,
            rows_scanned=total_scanned,
            rows_updated=total_updated,
            rows_failed=total_failed,
            finished=True,
            error_summary=error_summary,
        )

    stats = {
        "snapshot": snapshot_name,
        "event_id": event_id,
        "estimated_total": estimated_total,
        "rows_scanned": total_scanned,
        "rows_updated": total_updated,
        "rows_failed": total_failed,
        "batches": batch_num,
        "dry_run": dry_run,
    }
    logger.info("Stats finais: %s", stats)
    return stats


# =====================================================
# Entrypoint
# =====================================================

def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        stats = run_purge(args)
    except Exception:  # noqa: BLE001
        logger.exception("Falha fatal no run_purge")
        return 1

    if stats["rows_failed"] > 0 and not args.dry_run:
        logger.warning(
            "Purge concluido com %d rows falhadas — investigar logs.",
            stats["rows_failed"],
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
