# tests/test_metrics.py
"""Testes do coletor de métricas in-process."""

from src.infra.metrics import record, percentile, get_stats, get_all_stats, reset


def setup_function():
    """Limpa métricas antes de cada teste."""
    reset()


def test_record_and_percentile():
    """Registrar amostras e calcular percentis."""
    for i in range(100):
        record("test.latency", float(i))

    p50 = percentile("test.latency", 50)
    p95 = percentile("test.latency", 95)
    p99 = percentile("test.latency", 99)

    assert p50 is not None
    assert 45 <= p50 <= 55
    assert p95 is not None
    assert 90 <= p95 <= 99
    assert p99 is not None


def test_percentile_empty_metric():
    """Percentil de métrica sem amostras deve retornar None."""
    assert percentile("inexistente", 50) is None


def test_get_stats_structure():
    """get_stats deve retornar dict com count, p50, p95, p99."""
    record("test.api", 10.0)
    record("test.api", 20.0)
    record("test.api", 30.0)

    stats = get_stats("test.api")
    assert stats["count"] == 3
    assert "p50_ms" in stats
    assert "p95_ms" in stats
    assert "p99_ms" in stats


def test_get_all_stats():
    """get_all_stats deve retornar stats de todas as métricas."""
    record("metric.a", 10.0)
    record("metric.b", 20.0)

    all_stats = get_all_stats()
    assert "metric.a" in all_stats
    assert "metric.b" in all_stats


def test_sliding_window_limit():
    """Histograma deve respeitar o limite de amostras (janela deslizante)."""
    from src.infra.metrics import _MAX_SAMPLES

    for i in range(_MAX_SAMPLES + 500):
        record("test.overflow", float(i))

    stats = get_stats("test.overflow")
    assert stats["count"] == _MAX_SAMPLES
