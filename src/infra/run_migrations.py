# src/infra/run_migrations.py
"""
Runner de migrations com versionamento.
Registra cada migration aplicada em schema_migrations com checksum SHA-256.
Re-runs pulam migrations ja aplicadas. Checksum mismatch gera WARNING.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.migrations")

MIGRATIONS_DIR = Path("migrations")


def _ensure_tracking_table() -> None:
    """Garante que a tabela schema_migrations existe."""
    tracking_sql = (MIGRATIONS_DIR / "000_migration_tracking.sql").read_text(encoding="utf-8")
    with db_cursor() as (connection, cursor):
        cursor.execute(tracking_sql)
        connection.commit()


def _get_applied() -> dict[str, str]:
    """Retorna dict {version: checksum} das migrations ja aplicadas."""
    with db_cursor(dictionary=True) as (connection, cursor):
        cursor.execute("SELECT version, checksum FROM schema_migrations ORDER BY version")
        rows = cursor.fetchall()
    return {row["version"]: row["checksum"] for row in rows}


def _extract_version(filename: str) -> str:
    """Extrai o prefixo de versao do nome do arquivo (ex: '001' de '001_initial_schema.sql')."""
    return filename.split("_")[0]


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def run_sql_file(path: Path) -> None:
    sql_content = path.read_text(encoding="utf-8")
    if not sql_content.strip():
        return
    with db_cursor() as (connection, cursor):
        cursor.execute(sql_content)
        connection.commit()


def _record_migration(version: str, filename: str, checksum: str) -> None:
    with db_cursor() as (connection, cursor):
        cursor.execute(
            "INSERT INTO schema_migrations (version, filename, checksum) VALUES (%s, %s, %s) "
            "ON CONFLICT (version) DO NOTHING",
            (version, filename, checksum),
        )
        connection.commit()


def list_migration_files() -> list[Path]:
    """Lista arquivos .sql em ordem, excluindo 000_migration_tracking.sql."""
    return sorted(
        f for f in MIGRATIONS_DIR.glob("*.sql")
        if not f.name.startswith("000_")
    )


def run_all() -> list[str]:
    _ensure_tracking_table()
    applied = _get_applied()
    results: list[str] = []

    for migration_file in list_migration_files():
        version = _extract_version(migration_file.name)
        content = migration_file.read_text(encoding="utf-8")
        checksum = _sha256(content)

        if version in applied:
            if applied[version] != checksum:
                logger.warning(
                    "Migration %s (%s) checksum mismatch! Expected %s, got %s. "
                    "O arquivo pode ter sido alterado apos aplicacao.",
                    version,
                    migration_file.name,
                    applied[version],
                    checksum,
                )
            else:
                logger.info("Migration %s ja aplicada, pulando.", version)
            continue

        logger.info("Aplicando migration %s (%s)...", version, migration_file.name)
        run_sql_file(migration_file)
        _record_migration(version, migration_file.name, checksum)
        results.append(str(migration_file))
        logger.info("Migration %s aplicada com sucesso.", version)

    return results


if __name__ == "__main__":
    applied = run_all()
    if applied:
        print(f"{len(applied)} migrations aplicadas com sucesso.")
    else:
        print("Nenhuma migration nova para aplicar.")
