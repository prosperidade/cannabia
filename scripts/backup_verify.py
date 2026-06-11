"""
Verificacao tripla AUTOMATICA de backup, com heartbeat e alerta em falha.

OBS-1 (doc 30 OBS-1 / 29.5 R12 / BUG-001). Antidoto direto ao incidente de
14/05: o backup de 11/05 falhou em SILENCIO (0 bytes) e so foi notado quando
o volume ja tinha sido apagado. Aqui cada execucao:

  1. (re)cria ou localiza um dump custom (pg_dump --format=custom -f);
  2. roda os 3 gates de scripts/backup_postgres_validated.py:
       - tamanho > limiar
       - integridade (pg_restore --list)
       - restauracao de amostra (pg_restore --schema-only)
  3. GRAVA o resultado em backup_verification_events (sucesso OU falha) —
     transformando falha silenciosa em falha visivel (heartbeat);
  4. em falha: ALERTA (Sentry se configurado + log ERROR) e sai != 0.

Cron diario no render.yaml (cannabia-backup-verify). Kill switch
BACKUP_VERIFY_ENABLED (default false): cron agendado mas no-op ate liberacao.

Env:
  BACKUP_VERIFY_ENABLED     "true" para rodar (default false = no-op)
  BACKUP_VERIFY_PATH        valida um dump existente em vez de criar um novo
  DATABASE_URL              fonte do dump e destino do heartbeat
  PG_BIN                    diretorio dos binarios pg_dump/pg_restore (opcional)
"""
from __future__ import annotations

import logging
import os
import socket
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("cannabia.obs.backup_verify")


def _alert(message: str) -> None:
    """Alerta best-effort: Sentry (se configurado) + log ERROR.

    A falha de backup NUNCA pode ser silenciosa (licao do BUG-001).
    """
    logger.error("ALERTA BACKUP: %s", message)
    try:
        import sentry_sdk  # type: ignore

        if os.getenv("SENTRY_DSN"):
            sentry_sdk.capture_message(f"[backup-verify] {message}", level="error")
    except Exception:  # noqa: BLE001
        logger.debug("Sentry indisponivel para alerta de backup", exc_info=True)


def record_event(
    *,
    success: bool,
    dump_path: Optional[str],
    dump_bytes: Optional[int],
    restore_list_lines: Optional[int],
    sample_restore_ddl_lines: Optional[int],
    sha256: Optional[str],
    error_message: Optional[str],
) -> Optional[int]:
    """Grava o heartbeat em backup_verification_events (fail-safe)."""
    try:
        from src.infra.database import db_cursor

        try:
            host = socket.gethostname()
        except Exception:  # noqa: BLE001
            host = "cron"

        with db_cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO backup_verification_events
                  (finished_at, dump_path, dump_bytes, restore_list_lines,
                   sample_restore_ddl_lines, sha256, success, executor_host,
                   error_message)
                VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (dump_path, dump_bytes, restore_list_lines,
                 sample_restore_ddl_lines, sha256, success, host or "cron",
                 error_message),
            )
            event_id = cur.fetchone()[0]
            conn.commit()
        return event_id
    except Exception:  # noqa: BLE001
        # Se nem o heartbeat grava, ainda assim alertamos no caller.
        logger.exception("Falha ao gravar backup_verification_event")
        return None


def run() -> dict:
    from scripts.backup_postgres_validated import (
        DEFAULT_BACKUP_DIR,
        DEFAULT_CHECKSUM_FILE,
        create_backup,
        sample_restore_check,
        validate_backup,
    )

    pg_bin = os.getenv("PG_BIN")
    database_url = os.getenv("DATABASE_URL")
    existing = os.getenv("BACKUP_VERIFY_PATH")

    dump_path: Optional[Path] = None
    dump_bytes = restore_lines = schema_lines = None
    digest = None
    error_message: Optional[str] = None
    success = False

    try:
        if existing:
            dump_path = Path(existing)
            if not dump_path.exists():
                raise RuntimeError(f"BACKUP_VERIFY_PATH nao existe: {dump_path}")
        else:
            if not database_url:
                raise RuntimeError("DATABASE_URL nao definido — impossivel criar backup.")
            dump_path = create_backup(database_url, DEFAULT_BACKUP_DIR, pg_bin)

        dump_bytes = dump_path.stat().st_size
        digest, restore_lines = validate_backup(dump_path, DEFAULT_CHECKSUM_FILE, pg_bin)
        schema_lines = sample_restore_check(dump_path, pg_bin)
        success = True
    except Exception as exc:  # noqa: BLE001
        error_message = repr(exc)[:1000]
        logger.exception("Verificacao de backup FALHOU")

    event_id = record_event(
        success=success,
        dump_path=str(dump_path) if dump_path else None,
        dump_bytes=dump_bytes,
        restore_list_lines=restore_lines,
        sample_restore_ddl_lines=schema_lines,
        sha256=digest,
        error_message=error_message,
    )

    if not success:
        _alert(
            f"verificacao de backup falhou (dump={dump_path}, erro={error_message}). "
            f"heartbeat_event={event_id}"
        )

    return {
        "success": success,
        "event_id": event_id,
        "dump_path": str(dump_path) if dump_path else None,
        "dump_bytes": dump_bytes,
        "restore_list_lines": restore_lines,
        "sample_restore_ddl_lines": schema_lines,
        "error_message": error_message,
    }


def main() -> int:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    enabled = os.getenv("BACKUP_VERIFY_ENABLED", "false").strip().lower()
    if enabled not in {"true", "1", "yes"}:
        logger.info(
            "BACKUP_VERIFY_ENABLED=%r — verificacao de backup DESATIVADA (no-op). "
            "Para ativar: set BACKUP_VERIFY_ENABLED=true no Render dashboard.",
            enabled,
        )
        return 0

    stats = run()
    logger.info("Backup verify done: %s", stats)
    return 0 if stats["success"] else 2


if __name__ == "__main__":
    sys.exit(main())
