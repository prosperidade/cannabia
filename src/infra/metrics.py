# src/infra/metrics.py
"""
Coletor de metricas in-process com histograma para calculo de percentis.
Thread-safe via lock. Armazena ultimas N amostras por metrica (janela deslizante).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any


_MAX_SAMPLES = 1000
_lock = threading.Lock()
_histograms: dict[str, list[float]] = defaultdict(list)


def record(metric_name: str, value_ms: float) -> None:
    """Registra uma amostra em ms para a metrica dada."""
    with _lock:
        samples = _histograms[metric_name]
        if len(samples) >= _MAX_SAMPLES:
            samples.pop(0)
        samples.append(value_ms)


@contextmanager
def measure(metric_name: str):
    """Context manager que mede o tempo e registra automaticamente."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        record(metric_name, elapsed_ms)


def percentile(metric_name: str, p: float) -> float | None:
    """Calcula o percentil p (0-100) para a metrica dada."""
    with _lock:
        samples = sorted(_histograms.get(metric_name, []))
    if not samples:
        return None
    k = (p / 100.0) * (len(samples) - 1)
    f = int(k)
    c = min(f + 1, len(samples) - 1)
    if f == c:
        return round(samples[f], 2)
    return round(samples[f] + (k - f) * (samples[c] - samples[f]), 2)


def get_stats(metric_name: str) -> dict[str, Any]:
    """Retorna p50, p95, p99 e count para a metrica."""
    with _lock:
        count = len(_histograms.get(metric_name, []))
    return {
        "count": count,
        "p50_ms": percentile(metric_name, 50),
        "p95_ms": percentile(metric_name, 95),
        "p99_ms": percentile(metric_name, 99),
    }


def get_all_stats() -> dict[str, dict[str, Any]]:
    """Retorna stats de todas as metricas registradas."""
    with _lock:
        names = list(_histograms.keys())
    return {name: get_stats(name) for name in names}


def reset() -> None:
    """Limpa todas as metricas (para testes)."""
    with _lock:
        _histograms.clear()
