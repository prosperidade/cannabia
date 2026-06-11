# tests/test_health.py
"""Testes do endpoint /api/v1/health e dos probes do health check."""

from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def _mock_probes(*, db="ok", redis="ok", openai="ok", gemini="ok", chromadb="ok"):
    """Mocka os probes do health check. Cada arg e 'ok' ou 'error'."""
    from src.infra.health import ProbeResult

    def _pr(state, lat):
        return ProbeResult(status=state, latency_ms=lat, detail="" if state == "ok" else "mock")

    with patch("src.infra.health._probe_db", return_value=_pr(db, 5)), \
         patch("src.infra.health._probe_redis", return_value=_pr(redis, 2)), \
         patch("src.infra.health._probe_openai", return_value=_pr(openai, 100)), \
         patch("src.infra.health._probe_gemini", return_value=_pr(gemini, 120)), \
         patch("src.infra.health._probe_chromadb", return_value=_pr(chromadb, 10)):
        yield


def test_health_returns_json(client):
    """Health check deve retornar JSON com campo 'data' e status healthy."""
    with _mock_probes():
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.get_json()
        assert "data" in data
        assert data["data"]["status"] == "healthy"


def test_health_degraded_when_ai_down(client):
    """Provedores de IA indisponiveis -> 'degraded' com HTTP 200."""
    with _mock_probes(openai="error", gemini="error"):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.get_json()["data"]["status"] == "degraded"


def test_health_degraded_when_redis_down(client):
    """INFRA-1: Redis (fila assincrona) indisponivel -> 'degraded' (nao-critico)."""
    with _mock_probes(redis="error"):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert data["status"] == "degraded"
        assert data["components"]["redis"]["status"] == "error"


def test_health_unhealthy_when_db_down(client):
    """Banco indisponivel -> 'unhealthy' com HTTP 503 (unico probe critico)."""
    with _mock_probes(db="error"):
        response = client.get("/api/v1/health")
        assert response.status_code == 503
        assert response.get_json()["data"]["status"] == "unhealthy"


def test_health_components_have_latency(client):
    """Cada componente (incluindo redis) deve incluir latency_ms e status."""
    with _mock_probes():
        response = client.get("/api/v1/health")
        data = response.get_json()["data"]
        for component in ("db", "redis", "openai", "gemini", "chromadb"):
            assert component in data["components"]
            assert "latency_ms" in data["components"][component]
            assert "status" in data["components"][component]
