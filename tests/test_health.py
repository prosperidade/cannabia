# tests/test_health.py
"""Testes do endpoint /api/v1/health e dos probes do health check."""

from unittest.mock import patch, MagicMock


def test_health_returns_json(client):
    """Health check deve retornar JSON com campo 'data'."""
    with patch("src.infra.health._probe_db") as mock_db, \
         patch("src.infra.health._probe_openai") as mock_openai, \
         patch("src.infra.health._probe_gemini") as mock_gemini, \
         patch("src.infra.health._probe_chromadb") as mock_chroma:

        from src.infra.health import ProbeResult
        mock_db.return_value = ProbeResult(status="ok", latency_ms=5)
        mock_openai.return_value = ProbeResult(status="ok", latency_ms=100)
        mock_gemini.return_value = ProbeResult(status="ok", latency_ms=120)
        mock_chroma.return_value = ProbeResult(status="ok", latency_ms=10)

        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.get_json()
        assert "data" in data
        assert data["data"]["status"] == "healthy"


def test_health_degraded_when_ai_down(client):
    """Se provedores de IA estão indisponíveis, status deve ser 'degraded' com HTTP 200."""
    with patch("src.infra.health._probe_db") as mock_db, \
         patch("src.infra.health._probe_openai") as mock_openai, \
         patch("src.infra.health._probe_gemini") as mock_gemini, \
         patch("src.infra.health._probe_chromadb") as mock_chroma:

        from src.infra.health import ProbeResult
        mock_db.return_value = ProbeResult(status="ok", latency_ms=5)
        mock_openai.return_value = ProbeResult(status="error", latency_ms=0, detail="timeout")
        mock_gemini.return_value = ProbeResult(status="error", latency_ms=0, detail="timeout")
        mock_chroma.return_value = ProbeResult(status="ok", latency_ms=10)

        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["status"] == "degraded"


def test_health_unhealthy_when_db_down(client):
    """Se o banco está indisponível, status deve ser 'unhealthy' com HTTP 503."""
    with patch("src.infra.health._probe_db") as mock_db, \
         patch("src.infra.health._probe_openai") as mock_openai, \
         patch("src.infra.health._probe_gemini") as mock_gemini, \
         patch("src.infra.health._probe_chromadb") as mock_chroma:

        from src.infra.health import ProbeResult
        mock_db.return_value = ProbeResult(status="error", latency_ms=0, detail="connection refused")
        mock_openai.return_value = ProbeResult(status="ok", latency_ms=100)
        mock_gemini.return_value = ProbeResult(status="ok", latency_ms=120)
        mock_chroma.return_value = ProbeResult(status="ok", latency_ms=10)

        response = client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.get_json()
        assert data["data"]["status"] == "unhealthy"


def test_health_components_have_latency(client):
    """Cada componente deve incluir latency_ms na resposta."""
    with patch("src.infra.health._probe_db") as mock_db, \
         patch("src.infra.health._probe_openai") as mock_openai, \
         patch("src.infra.health._probe_gemini") as mock_gemini, \
         patch("src.infra.health._probe_chromadb") as mock_chroma:

        from src.infra.health import ProbeResult
        mock_db.return_value = ProbeResult(status="ok", latency_ms=5)
        mock_openai.return_value = ProbeResult(status="ok", latency_ms=150)
        mock_gemini.return_value = ProbeResult(status="ok", latency_ms=200)
        mock_chroma.return_value = ProbeResult(status="ok", latency_ms=8)

        response = client.get("/api/v1/health")
        data = response.get_json()["data"]
        for component in ("db", "openai", "gemini", "chromadb"):
            assert component in data["components"]
            assert "latency_ms" in data["components"][component]
            assert "status" in data["components"][component]
