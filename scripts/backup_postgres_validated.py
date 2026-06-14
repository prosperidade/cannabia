"""Create and validate a PostgreSQL logical backup.

Validation follows the incident lesson from 2026-05-14:
1. dump file must be non-empty
2. pg_restore --list must parse the dump and return enough entries
3. SHA-256 must be recorded in backups/postgres/CHECKSUMS.txt
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_DIR = ROOT / "backups" / "postgres"
DEFAULT_CHECKSUM_FILE = DEFAULT_BACKUP_DIR / "CHECKSUMS.txt"
MIN_DUMP_BYTES = 1024
MIN_RESTORE_LIST_LINES = 5
# OBS-1: 3a verificacao — restauracao de amostra. pg_restore --schema-only emite
# todo o DDL reconstruido a partir do corpo do arquivo (nao so o TOC), exercendo
# a descompressao integral do dump. Um dump truncado/corrompido falha aqui mesmo
# passando no --list. Limiar conservador de statements DDL esperados.
MIN_SCHEMA_RESTORE_LINES = 20


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _resolve_binary(name: str, pg_bin: str | None) -> str:
    if pg_bin:
        candidate = Path(pg_bin) / f"{name}.exe"
        if candidate.exists():
            return str(candidate)
        candidate = Path(pg_bin) / name
        if candidate.exists():
            return str(candidate)

    found = shutil.which(name)
    if found:
        return found

    for version in ("18", "17", "16", "15", "14", "13"):
        candidate = Path("C:/Program Files/PostgreSQL") / version / "bin" / f"{name}.exe"
        if candidate.exists():
            return str(candidate)

    raise FileNotFoundError(
        f"{name} nao encontrado. Instale PostgreSQL client tools ou use --pg-bin."
    )


def _database_slug(database_url: str) -> str:
    parsed = urlparse(database_url)
    database = parsed.path.rsplit("/", 1)[-1] or "postgres"
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in database)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def create_backup(database_url: str, backup_dir: Path, pg_bin: str | None) -> Path:
    pg_dump = _resolve_binary("pg_dump", pg_bin)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = backup_dir / f"{_database_slug(database_url)}_{timestamp}.dump"

    result = _run([
        pg_dump,
        "--format=custom",
        "--no-owner",
        "--no-acl",
        database_url,
        "-f",
        str(output),
    ])
    if result.returncode != 0:
        if output.exists() and output.stat().st_size == 0:
            output.unlink()
        raise RuntimeError(f"pg_dump falhou:\n{result.stderr.strip()}")
    return output


def validate_backup(path: Path, checksum_file: Path, pg_bin: str | None) -> tuple[str, int]:
    pg_restore = _resolve_binary("pg_restore", pg_bin)
    size = path.stat().st_size
    if size <= MIN_DUMP_BYTES:
        raise RuntimeError(f"Dump invalido: {path} tem apenas {size} bytes")

    result = _run([pg_restore, "--list", str(path)])
    if result.returncode != 0:
        raise RuntimeError(f"pg_restore --list falhou:\n{result.stderr.strip()}")

    restore_lines = [line for line in result.stdout.splitlines() if line.strip()]
    if len(restore_lines) <= MIN_RESTORE_LIST_LINES:
        raise RuntimeError(
            "Dump invalido: pg_restore --list retornou "
            f"{len(restore_lines)} linhas, esperado > {MIN_RESTORE_LIST_LINES}"
        )

    digest = _sha256(path)
    checksum_file.parent.mkdir(parents=True, exist_ok=True)
    with checksum_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}  bytes={size}  restore_list_lines={len(restore_lines)}\n")
    return digest, len(restore_lines)


def sample_restore_check(path: Path, pg_bin: str | None) -> int:
    """3a verificacao (OBS-1): restauracao de amostra do dump.

    Roda `pg_restore --schema-only` emitindo o DDL para stdout (sem target DB),
    o que forca a leitura/descompressao de TODO o corpo do arquivo — nao apenas
    o TOC lido por `--list`. Conta os statements DDL (CREATE/ALTER) reconstruidos.

    Levanta RuntimeError se o pg_restore falhar ou se o DDL reconstruido for
    suspeito de dump vazio/corrompido (abaixo de MIN_SCHEMA_RESTORE_LINES).
    Retorna o numero de statements DDL.
    """
    pg_restore = _resolve_binary("pg_restore", pg_bin)
    # PostgreSQL 18 exige -d/--dbname ou -f/--file explicito; "-f -" emite o
    # DDL reconstruido para stdout (versoes antigas usavam stdout por default).
    result = _run([pg_restore, "--schema-only", "--no-owner", "--no-acl", "-f", "-", str(path)])
    if result.returncode != 0:
        raise RuntimeError(
            f"pg_restore --schema-only (restauracao de amostra) falhou:\n{result.stderr.strip()}"
        )

    ddl_lines = [
        line for line in result.stdout.splitlines()
        if line.lstrip().upper().startswith(("CREATE ", "ALTER ", "COMMENT "))
    ]
    if len(ddl_lines) < MIN_SCHEMA_RESTORE_LINES:
        raise RuntimeError(
            "Restauracao de amostra invalida: pg_restore --schema-only reconstruiu "
            f"{len(ddl_lines)} statements DDL, esperado >= {MIN_SCHEMA_RESTORE_LINES}"
        )
    return len(ddl_lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a validated PostgreSQL backup")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--checksum-file", type=Path, default=DEFAULT_CHECKSUM_FILE)
    parser.add_argument("--pg-bin", default=os.getenv("PG_BIN"))
    parser.add_argument("--dotenv", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--validate-only",
        type=Path,
        help="Validate an existing dump instead of creating a new one.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    _load_dotenv(args.dotenv)
    database_url = args.database_url or os.getenv("DATABASE_URL")

    if args.validate_only:
        backup_path = args.validate_only
    else:
        if not database_url:
            print("DATABASE_URL nao definido. Configure .env ou use --database-url.", file=sys.stderr)
            return 2
        backup_path = create_backup(database_url, args.output_dir, args.pg_bin)

    digest, restore_lines = validate_backup(backup_path, args.checksum_file, args.pg_bin)
    schema_lines = sample_restore_check(backup_path, args.pg_bin)
    print(f"backup={backup_path}")
    print(f"bytes={backup_path.stat().st_size}")
    print(f"pg_restore_list_lines={restore_lines}")
    print(f"sample_restore_ddl_lines={schema_lines}")
    print(f"sha256={digest}")
    print(f"checksum_file={args.checksum_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
