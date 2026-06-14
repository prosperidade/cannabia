"""
scripts/setup_worktree_db.py
Provisiona um banco de teste ISOLADO por worktree.

Motivacao (2026-06-14): o DB de dev e o DB de teste eram o mesmo
(`cannabia` em 127.0.0.1:5434) e todas as worktrees copiam o mesmo `.env`,
entao duas execucoes de pytest concorrentes (ex.: agentes em paralelo)
escreviam no MESMO banco -> contaminacao cross-process intermitente
(flake do test_smoke_full_pipeline). Cada worktree passa a ter o seu
proprio banco de teste, derivado do caminho absoluto da worktree.

Espelha exatamente o que a CI faz (.github/workflows/ci.yml job "Backend"):
banco proprio -> CREATE EXTENSION postgis -> run_all() de migrations.

Uso:
    env/Scripts/python scripts/setup_worktree_db.py            # cria se nao existe + migra
    env/Scripts/python scripts/setup_worktree_db.py --recreate # DROP + recria do zero
    env/Scripts/python scripts/setup_worktree_db.py --name foo # nome explicito

Ao final, imprime a linha `TEST_DATABASE_URL=...` para colar no `.env`
DESTA worktree. O conftest.py da precedencia a TEST_DATABASE_URL sobre o
DATABASE_URL de dev.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg2
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent


def _base_database_url() -> str:
    """DATABASE_URL de dev (do shell ou do .env da worktree)."""
    load_dotenv(REPO_ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL nao definido (shell nem .env). Configure o DB de dev primeiro.")
    return url


def _derive_db_name() -> str:
    """Nome estavel e unico por worktree: cannabia_test_<hash8(abspath)>."""
    digest = hashlib.sha1(str(REPO_ROOT).encode("utf-8")).hexdigest()[:8]
    return f"cannabia_test_{digest}"


def _with_dbname(url: str, dbname: str) -> str:
    parts = urlparse(url)
    return urlunparse(parts._replace(path=f"/{dbname}"))


def _connect_maintenance(url: str):
    """Conexao autocommit ao DB de manutencao 'postgres' (CREATE DATABASE
    nao roda dentro de transacao)."""
    conn = psycopg2.connect(_with_dbname(url, "postgres"))
    conn.autocommit = True
    return conn


def _db_exists(cur, name: str) -> bool:
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
    return cur.fetchone() is not None


def main() -> None:
    ap = argparse.ArgumentParser(description="Provisiona DB de teste isolado por worktree.")
    ap.add_argument("--name", help="Nome do DB (default: cannabia_test_<hash da worktree>)")
    ap.add_argument("--recreate", action="store_true", help="DROP DATABASE antes de criar")
    args = ap.parse_args()

    base_url = _base_database_url()
    db_name = args.name or _derive_db_name()
    target_url = _with_dbname(base_url, db_name)

    print(f"[setup] worktree : {REPO_ROOT}")
    print(f"[setup] DB alvo   : {db_name}")

    # 1) CREATE/RECREATE DATABASE via conexao de manutencao
    conn = _connect_maintenance(base_url)
    try:
        with conn.cursor() as cur:
            if args.recreate and _db_exists(cur, db_name):
                # encerra conexoes residuais antes do DROP
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (db_name,),
                )
                cur.execute(f'DROP DATABASE "{db_name}"')
                print(f"[setup] DROP DATABASE {db_name} (recreate)")
            if not _db_exists(cur, db_name):
                cur.execute(f'CREATE DATABASE "{db_name}"')
                print(f"[setup] CREATE DATABASE {db_name}")
            else:
                print(f"[setup] DB ja existe — migrando incrementalmente (idempotente)")
    finally:
        conn.close()

    # 2) postgis defensivo (espelha a CI) + 3) migrations no DB alvo
    with psycopg2.connect(target_url) as ext_conn:
        ext_conn.autocommit = True
        with ext_conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    ext_conn.close()

    # run_all() usa src.config.DATABASE_URL (snapshot no import) -> setar ANTES
    os.environ["DATABASE_URL"] = target_url
    os.chdir(REPO_ROOT)  # MIGRATIONS_DIR = Path("migrations") e relativo ao cwd
    sys.path.insert(0, str(REPO_ROOT))
    from src.infra.run_migrations import run_all

    applied = run_all()
    print(f"[setup] migrations aplicadas: {len(applied)}")

    print()
    print("=" * 70)
    print("Cole esta linha no .env DESTA worktree (ou exporte no shell):")
    print(f"TEST_DATABASE_URL={target_url}")
    print("=" * 70)


if __name__ == "__main__":
    main()
