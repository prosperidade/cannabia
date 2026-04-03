# src/infra/database.py
"""
Camada de acesso ao banco com connection pooling.
Pool inicializado sob demanda (lazy) para evitar conexoes no import time.
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager

from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

from src.config import DATABASE_URL

logger = logging.getLogger("cannabia.database")

_pool: SimpleConnectionPool | None = None
_pool_lock = threading.Lock()

DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "2"))
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))


def _get_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        with _pool_lock:
            if _pool is None or _pool.closed:
                logger.info(
                    "Inicializando pool de conexoes (min=%d, max=%d)",
                    DB_POOL_MIN,
                    DB_POOL_MAX,
                )
                _pool = SimpleConnectionPool(
                    minconn=DB_POOL_MIN,
                    maxconn=DB_POOL_MAX,
                    dsn=DATABASE_URL,
                )
    return _pool


def get_connection():
    """Obtém uma conexão do pool."""
    return _get_pool().getconn()


def release_connection(conn) -> None:
    """Devolve uma conexão ao pool."""
    try:
        pool = _get_pool()
        pool.putconn(conn)
    except Exception:
        logger.warning("Erro ao devolver conexao ao pool", exc_info=True)


@contextmanager
def db_cursor(dictionary=False):
    pool = _get_pool()
    conn = pool.getconn()
    try:
        if dictionary:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:
            cursor = conn.cursor()
        try:
            yield conn, cursor
        finally:
            cursor.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def get_pool_stats() -> dict:
    """Retorna estatisticas do pool para o health check."""
    pool = _get_pool()
    # SimpleConnectionPool nao expoe contadores diretamente,
    # mas podemos inferir do estado interno
    used = len(pool._used) if hasattr(pool, "_used") else 0
    available = len(pool._pool) if hasattr(pool, "_pool") else 0
    return {
        "min": DB_POOL_MIN,
        "max": DB_POOL_MAX,
        "used": used,
        "available": available,
    }
