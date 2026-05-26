"""Regression tests for financial surface role gates.

Financial features belong to Admin, clinic owners/AdminClinica and Financeiro.
Recepcao/Atendente and non-owner Medico must not pass these gates.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from flask import Flask, g
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.campaigns import campaigns_bp
from src.web.routes.org_management import org_management_bp
from src.web.routes.payments import payments_bp


USER_ID = 11
TENANT_ID = 42
CLINIC_ID = 77


def _build_app(*, role: str, is_clinic_admin: bool = False) -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(USER_ID):
            return AppUser(
                user_id=USER_ID,
                username="role-test",
                role=role,
                is_clinic_admin=is_clinic_admin,
            )
        return None

    @app.before_request
    def inject_context():
        g.tenant_id = TENANT_ID
        g.clinic_id = CLINIC_ID

    app.register_blueprint(payments_bp)
    app.register_blueprint(org_management_bp)
    app.register_blueprint(campaigns_bp)
    return app


def _client(app: Flask):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(USER_ID)
    return client


@pytest.mark.parametrize(
    ("role", "is_owner"),
    [
        ("Admin", False),
        ("AdminClinica", False),
        ("Financeiro", False),
        ("Medico", True),
    ],
)
def test_payments_allow_only_financial_roles(
    role: str,
    is_owner: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import payment_service

    monkeypatch.setattr(payment_service, "list_payments", lambda **kwargs: [])

    response = _client(_build_app(role=role, is_clinic_admin=is_owner)).get("/api/v1/payments")

    assert response.status_code == 200


@pytest.mark.parametrize("role", ["Medico", "Recepcao", "Atendente"])
def test_payments_block_non_financial_roles(role: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.services import payment_service

    monkeypatch.setattr(payment_service, "list_payments", lambda **kwargs: pytest.fail("service should not run"))

    response = _client(_build_app(role=role)).get("/api/v1/payments")

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("role", "is_owner"),
    [
        ("Financeiro", False),
        ("AdminClinica", False),
        ("Medico", True),
    ],
)
def test_campaigns_allow_financial_roles(
    role: str,
    is_owner: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import campaign_service

    monkeypatch.setattr(campaign_service, "list_templates", lambda *args, **kwargs: [])

    response = _client(_build_app(role=role, is_clinic_admin=is_owner)).get("/api/v1/campaigns/templates")

    assert response.status_code == 200


@pytest.mark.parametrize("role", ["Medico", "Recepcao", "Atendente"])
def test_campaigns_block_non_financial_roles(role: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.services import campaign_service

    monkeypatch.setattr(campaign_service, "list_templates", lambda *args, **kwargs: pytest.fail("service should not run"))

    response = _client(_build_app(role=role)).get("/api/v1/campaigns/templates")

    assert response.status_code == 403


class _FakeCursor:
    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return {"revenue": 0, "pending": 0, "overdue": 0}


@contextmanager
def _fake_db_cursor(*_args, **_kwargs):
    yield None, _FakeCursor()


def test_org_financial_allows_financeiro(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.web.routes.org_management as org_management

    monkeypatch.setattr(org_management, "db_cursor", _fake_db_cursor)

    response = _client(_build_app(role="Financeiro")).get("/api/v1/org/financial")

    assert response.status_code == 200


@pytest.mark.parametrize("role", ["Medico", "Recepcao", "Atendente"])
def test_org_financial_blocks_non_financial_roles(role: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import src.web.routes.org_management as org_management

    monkeypatch.setattr(org_management, "db_cursor", lambda *args, **kwargs: pytest.fail("db should not run"))

    response = _client(_build_app(role=role)).get("/api/v1/org/financial")

    assert response.status_code == 403
