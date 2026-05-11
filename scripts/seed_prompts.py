"""
Seed inicial de ai_prompt_versions a partir do snapshot hardcoded.

Sprint 2 Track Reg.

Para cada uma das 7 chaves de _HARDCODED_PROMPTS, computa SHA-256 do
conteudo e faz INSERT ON CONFLICT DO NOTHING como version="v1.0.0",
active=TRUE. Idempotente: rodar varias vezes nao duplica.

Uso:
    python -m scripts.seed_prompts                # dry-run (default)
    python -m scripts.seed_prompts --commit       # grava no DB

Pre-requisito: migration 046_prompt_registry_alignment.sql aplicada.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from typing import Tuple

from src.ai.prompt_registry import _HARDCODED_PROMPTS

logger = logging.getLogger("cannabia.scripts.seed_prompts")
logging.basicConfig(level=logging.INFO, format="%(message)s")

SEED_VERSION = "v1.0.0"
SEED_CREATED_BY = "system_seed"


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seed_one(prompt_key: str, prompt_text: str, commit: bool) -> Tuple[str, str]:
    """
    Retorna (hash, status) onde status in {'inserted', 'skipped', 'dry-run'}.
    """
    text_hash = _compute_hash(prompt_text)

    if not commit:
        return text_hash, "dry-run"

    from src.infra.database import db_cursor

    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO ai_prompt_versions
                (name, prompt_key, version, prompt_text, hash, active, created_by)
            VALUES
                (%s, %s, %s, %s, %s, TRUE, %s)
            ON CONFLICT (prompt_key, version) DO NOTHING
            RETURNING id
            """,
            (prompt_key, prompt_key, SEED_VERSION, prompt_text, text_hash, SEED_CREATED_BY),
        )
        row = cur.fetchone()
        conn.commit()

    return text_hash, ("inserted" if row else "skipped")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Seed ai_prompt_versions")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Grava no DB. Sem essa flag, roda em dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit dry-run (default sem --commit).",
    )
    args = parser.parse_args(argv)

    commit = bool(args.commit) and not args.dry_run

    mode = "COMMIT" if commit else "DRY-RUN"
    logger.info("=" * 60)
    logger.info("Seed de ai_prompt_versions — modo: %s", mode)
    logger.info("Versao: %s | created_by: %s", SEED_VERSION, SEED_CREATED_BY)
    logger.info("=" * 60)

    rows = []
    for key, text in _HARDCODED_PROMPTS.items():
        text_hash, status = _seed_one(key, text, commit)
        rows.append((key, text_hash, status))
        logger.info(
            "  %-25s hash=%s  -> %s",
            key, text_hash[:12], status,
        )

    logger.info("=" * 60)
    if not commit:
        logger.info("DRY-RUN concluido. Re-execute com --commit para gravar.")
    else:
        inserted = sum(1 for _, _, s in rows if s == "inserted")
        skipped = sum(1 for _, _, s in rows if s == "skipped")
        logger.info(
            "Concluido: %d inserted, %d skipped (total %d).",
            inserted, skipped, len(rows),
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
