"""
scripts/run_migrations.py
Executa todas as migrations SQL na ordem correta.
Deve ser chamado no primeiro deploy ou sempre que houver novas migrations.

Uso local:
    env\\Scripts\\python scripts/run_migrations.py

Uso em produção (Render Build Command):
    pip install -r requirements.txt && python scripts/run_migrations.py
"""
import glob
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from src.infra.database import db_cursor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("cannabia.migrations")


def split_statements(sql: str) -> list[str]:
    """
    Remove comentários de linha (--) e divide o SQL em statements individuais.
    """
    # Remove comentários linha-a-linha ANTES de dividir por ;
    clean_lines = [
        line for line in sql.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    clean_sql = "\n".join(clean_lines)

    stmts = []
    for raw in clean_sql.split(";"):
        stmt = raw.strip()
        if stmt:
            stmts.append(stmt)
    return stmts


def run_all() -> None:
    migration_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
    files = sorted(glob.glob(os.path.join(migration_dir, "*.sql")))

    if not files:
        logger.warning("Nenhum arquivo .sql encontrado em migrations/")
        return

    logger.info("Iniciando %d migration(s)...", len(files))

    with db_cursor() as (conn, cursor):
        for path in files:
            name = os.path.basename(path)
            logger.info("Executando: %s", name)
            try:
                sql   = open(path, encoding="utf-8").read()
                stmts = split_statements(sql)
                for stmt in stmts:
                    cursor.execute(stmt)
                conn.commit()
                logger.info("  ✅ %s — OK", name)
            except Exception as exc:
                # Erros de "tabela já existe" (42P07 em Postgres) são esperados em re-deploys
                if hasattr(exc, "pgcode") and exc.pgcode == "42P07":
                    logger.info("  ⏭️  %s — tabela já existe, ignorando.", name)
                    conn.rollback()
                else:
                    logger.error("  ❌ %s — ERRO: %s", name, exc)
                    raise

    logger.info("✅ Todas as migrations concluídas com sucesso.")


if __name__ == "__main__":
    run_all()
