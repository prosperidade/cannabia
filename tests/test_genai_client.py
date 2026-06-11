"""Factory do client GenAI — seleção AI Studio vs Vertex AI (billing GCP)."""

from __future__ import annotations

import pytest

import src.infra.genai_client as gc


@pytest.fixture
def capture_client(monkeypatch):
    captured = {}
    monkeypatch.setattr(gc.genai, "Client", lambda **kw: captured.update(kw) or "fake-client")
    return captured


def test_default_uses_ai_studio_api_key(monkeypatch, capture_client):
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "AIza-test")
    gc.make_genai_client()
    assert capture_client.get("api_key") == "AIza-test"
    assert "vertexai" not in capture_client  # nao toca Vertex por default


def test_vertex_mode_uses_project_and_location(monkeypatch, capture_client):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "meu-projeto-gcp")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "southamerica-east1")
    gc.make_genai_client()
    assert capture_client.get("vertexai") is True
    assert capture_client.get("project") == "meu-projeto-gcp"
    assert capture_client.get("location") == "southamerica-east1"
    assert "api_key" not in capture_client  # Vertex usa ADC, nao api_key


def test_vertex_default_location(monkeypatch, capture_client):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "1")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    gc.make_genai_client()
    assert capture_client.get("location") == "us-central1"


def test_vertex_requires_project(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        gc.make_genai_client()


def test_ai_studio_requires_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        gc.make_genai_client()


def test_use_vertex_truthy_values(monkeypatch):
    for v in ("true", "1", "yes", "on", "TRUE"):
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", v)
        assert gc.use_vertex() is True
    for v in ("false", "0", "no", ""):
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", v)
        assert gc.use_vertex() is False
