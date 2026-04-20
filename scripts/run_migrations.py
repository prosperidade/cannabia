"""
scripts/run_migrations.py
Wrapper CLI para o runner versionado de migrations.

Uso local:
    env\\Scripts\\python scripts/run_migrations.py

Uso em produção:
    python scripts/run_migrations.py
"""
from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

from src.infra.run_migrations import run_all


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("cannabia.migrations")


def main() -> None:
    applied = run_all()
    if applied:
        logger.info("%d migration(s) nova(s) aplicada(s).", len(applied))
        return
    logger.info("Nenhuma migration nova para aplicar.")


if __name__ == "__main__":
    main()
