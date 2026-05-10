from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask
from flask_login import LoginManager

import src.ai.agents as agents_module
from src.web.auth_identity import AppUser
from src.web.routes.admin_agents import admin_agents_bp


class _FakeAgent:
    agent_name = "tratamento"
    description = "Agente fake de tratamento"

    def __init__(self):
        self._skills = {
            "build_plan": SimpleNamespace(
                description="Gera plano terapêutico inicial.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
        }

    def get_skills(self):
        return self._skills

    def get_diary(self, last_n=100):
        return [{"event": "ok"}]

    def run(self, **payload):
        return SimpleNamespace(
            success=True,
            data={"echo": payload},
            error=None,
            duration_ms=12,
            confidence=0.91,
            skills_used=["build_plan"],
            tokens={"total_tokens": 42},
        )


def _patch_agents(monkeypatch):
    for attr in (
        "AgenteTriagem",
        "AgenteAnamnese",
        "AgenteTratamento",
        "AgentePrescritor",
        "AgenteCientifico",
        "AgenteRegulatorio",
        "AgenteFollowUp",
        "AgenteExtrator",
        ):
        monkeypatch.setattr(agents_module, attr, _FakeAgent)


@pytest.fixture
def admin_agents_client():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
    )

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == "1":
            return AppUser(user_id=1, username="admin", role="Admin")
        return None

    app.register_blueprint(admin_agents_bp)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["csrf_token"] = "test-csrf-token"
        yield client


def test_list_agents_returns_specialist_inventory(admin_agents_client, monkeypatch):
    _patch_agents(monkeypatch)

    response = admin_agents_client.get("/api/v1/admin/agents/")

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["data"]) == 8
    assert any(agent["name"] == "tratamento" for agent in payload["data"])
    assert all(agent["skills_count"] == 1 for agent in payload["data"])


def test_get_agent_skills_returns_skill_metadata(admin_agents_client, monkeypatch):
    _patch_agents(monkeypatch)

    response = admin_agents_client.get("/api/v1/admin/agents/tratamento/skills")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["agent"] == "tratamento"
    assert payload["skills"][0]["name"] == "build_plan"


def test_execute_agent_returns_run_result(admin_agents_client, monkeypatch):
    _patch_agents(monkeypatch)

    response = admin_agents_client.post(
        "/api/v1/admin/agents/tratamento/execute",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={"patient_name": "Maria"},
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["success"] is True
    assert payload["data"]["echo"]["patient_name"] == "Maria"
    assert payload["skills_used"] == ["build_plan"]
