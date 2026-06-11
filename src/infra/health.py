# src/infra/health.py
"""
Health check com probes para cada componente do sistema.
Retorna status por componente + latencia em ms.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("cannabia.health")


@dataclass
class ProbeResult:
    status: str  # "ok" | "error"
    latency_ms: int = 0
    detail: str = ""


@dataclass
class HealthReport:
    status: str = "healthy"  # "healthy" | "degraded" | "unhealthy"
    components: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "components": self.components,
        }

    @property
    def http_status(self) -> int:
        if self.status == "unhealthy":
            return 503
        return 200


def _probe_db() -> ProbeResult:
    from src.infra.database import db_cursor, get_pool_stats

    start = time.perf_counter()
    try:
        with db_cursor() as (conn, cur):
            cur.execute("SELECT 1")
            cur.fetchone()
        elapsed = int((time.perf_counter() - start) * 1000)
        pool = get_pool_stats()
        return ProbeResult(
            status="ok",
            latency_ms=elapsed,
            detail=f"pool: {pool['used']} used / {pool['available']} available",
        )
    except Exception as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        logger.warning("Health probe DB falhou: %s", exc)
        return ProbeResult(status="error", latency_ms=elapsed, detail=str(exc))


def _probe_openai() -> ProbeResult:
    import openai

    start = time.perf_counter()
    try:
        client = openai.OpenAI()
        client.models.list()
        elapsed = int((time.perf_counter() - start) * 1000)
        return ProbeResult(status="ok", latency_ms=elapsed)
    except Exception as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        logger.warning("Health probe OpenAI falhou: %s", exc)
        return ProbeResult(status="error", latency_ms=elapsed, detail=str(exc))


def _probe_gemini() -> ProbeResult:
    from src.config import GOOGLE_API_KEY

    start = time.perf_counter()
    if not GOOGLE_API_KEY:
        return ProbeResult(status="error", latency_ms=0, detail="GOOGLE_API_KEY not configured")
    try:
        import google.genai as genai

        client = genai.Client(api_key=GOOGLE_API_KEY)
        client.models.list(config={"page_size": 1})
        elapsed = int((time.perf_counter() - start) * 1000)
        return ProbeResult(status="ok", latency_ms=elapsed)
    except Exception as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        logger.warning("Health probe Gemini falhou: %s", exc)
        return ProbeResult(status="error", latency_ms=elapsed, detail=str(exc))


def _probe_chromadb() -> ProbeResult:
    start = time.perf_counter()
    try:
        from src.knowledge.vector_store import KnowledgeStore

        store = KnowledgeStore()
        count = store.count()
        elapsed = int((time.perf_counter() - start) * 1000)
        return ProbeResult(status="ok", latency_ms=elapsed, detail=f"{count} chunks")
    except Exception as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        logger.warning("Health probe ChromaDB falhou: %s", exc)
        return ProbeResult(status="error", latency_ms=elapsed, detail=str(exc))


def _probe_circuit_breakers() -> ProbeResult:
    """Probe que reporta estado dos circuit breakers de IA."""
    start = time.perf_counter()
    try:
        from src.ai.chains import get_circuit_breaker_status
        cb = get_circuit_breaker_status()
        elapsed = int((time.perf_counter() - start) * 1000)

        openai_state = cb["openai"]["state"]
        gemini_state = cb["gemini"]["state"]

        if openai_state == "open" and gemini_state == "open":
            return ProbeResult(
                status="error", latency_ms=elapsed,
                detail=f"openai={openai_state}, gemini={gemini_state}",
            )
        elif openai_state == "open" or gemini_state == "open":
            return ProbeResult(
                status="ok", latency_ms=elapsed,
                detail=f"openai={openai_state}, gemini={gemini_state} (failover ativo)",
            )
        return ProbeResult(
            status="ok", latency_ms=elapsed,
            detail=f"openai={openai_state}, gemini={gemini_state}",
        )
    except Exception as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        return ProbeResult(status="ok", latency_ms=elapsed, detail=f"não disponível: {exc}")


def _probe_redis() -> ProbeResult:
    """Probe da fila assincrona (Redis/RQ) — INFRA-1 / 29.1 R8.

    Nao-critico: enquanto o pipeline ainda roda sincrono (cutover e Onda 2),
    Redis indisponivel degrada (nao derruba) o sistema.
    """
    start = time.perf_counter()
    try:
        from src.infra.tasks import redis_available, REDIS_URL

        ok = redis_available()
        elapsed = int((time.perf_counter() - start) * 1000)
        if ok:
            return ProbeResult(status="ok", latency_ms=elapsed, detail=f"fila: {QUEUE_HINT}")
        return ProbeResult(
            status="error", latency_ms=elapsed,
            detail=f"Redis indisponivel ({REDIS_URL}) — fila assincrona offline",
        )
    except Exception as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        logger.warning("Health probe Redis falhou: %s", exc)
        return ProbeResult(status="error", latency_ms=elapsed, detail=str(exc))


QUEUE_HINT = "cannabia-ai"


def run_health_check() -> HealthReport:
    """
    Executa todos os probes e retorna um HealthReport.

    - DB down -> unhealthy (503)
    - AI providers / Redis down -> degraded (200)
    - Tudo ok -> healthy (200)
    """
    report = HealthReport()

    probes = {
        "db": _probe_db,
        "redis": _probe_redis,
        "openai": _probe_openai,
        "gemini": _probe_gemini,
        "chromadb": _probe_chromadb,
        "circuit_breakers": _probe_circuit_breakers,
    }

    critical_failed = False
    non_critical_failed = False

    for name, probe_fn in probes.items():
        result = probe_fn()
        report.components[name] = {
            "status": result.status,
            "latency_ms": result.latency_ms,
        }
        if result.detail:
            report.components[name]["detail"] = result.detail

        if result.status == "error":
            if name == "db":
                critical_failed = True
            else:
                non_critical_failed = True

    if critical_failed:
        report.status = "unhealthy"
    elif non_critical_failed:
        report.status = "degraded"
    else:
        report.status = "healthy"

    return report
