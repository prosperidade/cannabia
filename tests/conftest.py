# tests/conftest.py
"""
Fixtures compartilhadas para testes do CannabIA.

Arquitetura de testes:
    - Usa banco PostgreSQL real (configurável via TEST_DATABASE_URL).
    - Flask test client com sessão autenticada para testes de API.
    - Mocks de provedores de IA para testes isolados do pipeline.
    - Cada teste roda em transação com rollback automático (sem poluir o banco).
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

# Garante que variáveis de teste são carregadas antes do import da app
os.environ.setdefault("DATABASE_URL", os.getenv("TEST_DATABASE_URL", "postgresql://localhost/cannabia_test"))
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-32chars-ok!!")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3001")


@pytest.fixture(scope="session")
def app():
    """Cria a aplicação Flask em modo de teste (uma vez por sessão)."""
    from src.app import create_app

    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SERVER_NAME": "localhost",
    })
    yield app


@pytest.fixture(scope="function")
def client(app):
    """Flask test client com contexto de aplicação ativo."""
    with app.test_client() as client:
        with app.app_context():
            yield client


@pytest.fixture(scope="function")
def db_connection():
    """
    Conexão de banco com transação isolada.
    Faz rollback ao final de cada teste para manter o banco limpo.
    """
    from src.infra.database import get_connection, release_connection

    conn = get_connection()
    conn.autocommit = False
    yield conn
    conn.rollback()
    release_connection(conn)


@pytest.fixture(scope="function")
def db_cursor(db_connection):
    """Cursor de banco vinculado à transação isolada do teste."""
    from psycopg2.extras import RealDictCursor

    cursor = db_connection.cursor(cursor_factory=RealDictCursor)
    yield cursor
    cursor.close()


@pytest.fixture(scope="function")
def authenticated_client(client, app):
    """
    Client Flask com sessão autenticada como admin.
    Simula login sem depender do banco para criar o usuário.
    """
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"
        sess["active_clinic_id"] = 1
        sess["csrf_token"] = "test-csrf-token"
    yield client


@pytest.fixture
def csrf_headers():
    """Headers padrão para requests que exigem CSRF."""
    return {
        "Content-Type": "application/json",
        "X-CSRF-Token": "test-csrf-token",
    }


@pytest.fixture
def mock_openai():
    """Mock do cliente OpenAI para testes sem chamadas reais à API."""
    with patch("src.ai.chains.openai") as mock:
        # Simula resposta do ChatCompletion
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps({
                "risk_level": "moderado",
                "probable_conditions": ["dor cronica"],
                "recommended_exams": [],
                "clinical_summary": "Paciente com dor cronica.",
            })))
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        mock.OpenAI.return_value.chat.completions.create.return_value = mock_response
        yield mock


@pytest.fixture
def mock_gemini():
    """Mock do cliente Google GenAI para testes sem chamadas reais."""
    with patch("src.ai.chains.genai") as mock:
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "scientific_basis": "Estudos indicam beneficios.",
            "references": [],
            "evidence_level": "moderado",
            "clinical_considerations": "Monitorar efeitos.",
        })
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=80,
            candidates_token_count=40,
            total_token_count=120,
        )
        mock.Client.return_value.models.generate_content.return_value = mock_response
        yield mock


@pytest.fixture
def sample_anamnesis_data():
    """Dados de anamnese válidos para testes do pipeline de IA."""
    return {
        "patient_name": "Paciente Teste",
        "age": 45,
        "main_complaint": "Dor cronica lombar",
        "symptoms": "Dor lombar persistente, dificuldade para dormir",
        "current_medications": "Paracetamol 500mg",
        "allergies": "Nenhuma conhecida",
        "medical_history": "Historico de artrite",
    }
