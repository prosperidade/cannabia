"""
Testes do connection pool — Track A.2 Sprint 1.

Verifica que ThreadedConnectionPool aguenta checkout/return concorrente
sem deadlock, race em _used/_pool, ou perda de conexoes — propriedade
que SimpleConnectionPool NAO oferecia (motivo do swap).

Pre-requisito: DATABASE_URL aponta pra um Postgres real (Docker local
em 5434 via .env, conforme conftest._load_project_dotenv).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from psycopg2.pool import ThreadedConnectionPool


def test_pool_is_threaded_pool():
    """O pool em uso eh ThreadedConnectionPool, nao SimpleConnectionPool."""
    from src.infra.database import _get_pool

    pool = _get_pool()
    assert isinstance(pool, ThreadedConnectionPool), (
        f"Pool deve ser ThreadedConnectionPool para suportar gunicorn "
        f"multi-worker; recebeu {type(pool).__name__}"
    )


def test_concurrent_getconn_putconn_no_deadlock():
    """8 threads concorrentes pegam, executam SELECT 1 e devolvem conexao.

    Maxconn=10 (default) entao nao deve esgotar. Confirma que o pool
    nao deadlocka nem perde conexoes sob concorrencia real.
    """
    from src.infra.database import get_connection, release_connection

    n_threads = 8
    iterations_per_thread = 5
    errors: list[tuple[int, BaseException]] = []

    def worker(thread_id: int) -> int:
        success = 0
        for _ in range(iterations_per_thread):
            try:
                conn = get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    assert result == (1,), (
                        f"thread {thread_id}: SELECT 1 retornou {result}"
                    )
                    cur.close()
                    success += 1
                finally:
                    release_connection(conn)
            except BaseException as exc:
                errors.append((thread_id, exc))
        return success

    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(n_threads)]
        results = [f.result(timeout=15) for f in as_completed(futures)]

    assert errors == [], f"Erros nas threads: {errors}"
    assert sum(results) == n_threads * iterations_per_thread, (
        f"Esperado {n_threads * iterations_per_thread} SELECTs, "
        f"recebido {sum(results)}"
    )


def test_pool_stats_balanced_after_release():
    """Apos checkout + release de uma conexao, used volta ao baseline.

    Garante que putconn devolve a conexao corretamente ao pool — a
    comparacao eh relativa (+1 / volta a 0) pra ser robusto a estado
    residual de outros testes.
    """
    from src.infra.database import (
        get_connection,
        get_pool_stats,
        release_connection,
    )

    baseline = get_pool_stats()

    conn = get_connection()
    try:
        after_checkout = get_pool_stats()
        assert after_checkout["used"] == baseline["used"] + 1, (
            f"used deveria subir 1 apos checkout: "
            f"{baseline} -> {after_checkout}"
        )
    finally:
        release_connection(conn)

    after_release = get_pool_stats()
    assert after_release["used"] == baseline["used"], (
        f"used deveria voltar ao baseline apos release: "
        f"{baseline} -> {after_release}"
    )
