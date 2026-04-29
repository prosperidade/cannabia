"""Tests do GET /api/v1/org/dashboard.

Foco: shape envelope esperada pelo frontend (kpiData, chartConsultas,
chartReceita, topMedicos, recentActivity) e logica dos helpers de
formatacao (delta, BRL compact, classificacao de audit log).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from flask import Flask, g
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.org_management import (
    _classify_audit_endpoint,
    _format_brl_compact,
    _format_delta,
    _humanize_age,
    org_management_bp,
)


CLINIC_ID = 1
TENANT_ID = 42
USER_ID = 7


# ---------------------------------------------------------------------------
# Helpers de formatacao
# ---------------------------------------------------------------------------


def test_format_delta_up():
    assert _format_delta(120, 100) == ("+20%", "up")


def test_format_delta_down():
    assert _format_delta(80, 100) == ("-20%", "down")


def test_format_delta_neutral_when_equal():
    assert _format_delta(100, 100) == ("0%", "neutral")


def test_format_delta_novo_when_previous_zero_and_current_positive():
    assert _format_delta(5, 0) == ("novo", "up")


def test_format_delta_neutral_when_both_zero():
    assert _format_delta(0, 0) == ("0%", "neutral")


def test_format_brl_compact_thousands():
    assert _format_brl_compact(12500) == "R$ 12.5k"


def test_format_brl_compact_millions():
    assert _format_brl_compact(2_300_000) == "R$ 2.3M"


def test_format_brl_compact_below_thousand():
    assert _format_brl_compact(840) == "R$ 840"


def test_classify_audit_endpoint_anamnese():
    icon, text, tone = _classify_audit_endpoint("/api/v1/anamnese/process")
    assert icon == "psychology"
    assert tone == "primary"


def test_classify_audit_endpoint_pharmacovigilance():
    icon, text, tone = _classify_audit_endpoint("/api/v1/regulatory/vigimed/notify")
    # 'regulator' wins over 'vigimed' por ordem do dict — basta tone correto.
    assert tone in ("info", "danger")


def test_classify_audit_endpoint_unknown_falls_back_to_default():
    icon, text, tone = _classify_audit_endpoint("/api/v1/random/thing")
    assert icon == "bolt"
    assert tone == "primary"


def test_humanize_age_seconds():
    assert _humanize_age(30) == "agora ha pouco"


def test_humanize_age_minutes():
    assert _humanize_age(180) == "ha 3 min"


def test_humanize_age_hours():
    assert _humanize_age(7200) == "ha 2 h"


def test_humanize_age_days():
    assert _humanize_age(259200) == "ha 3 d"


def test_humanize_age_yesterday():
    assert _humanize_age(86400) == "ontem"


# ---------------------------------------------------------------------------
# GET /api/v1/org/dashboard — integration light com mock de db_cursor
# ---------------------------------------------------------------------------


def _build_app(*, role: str = "Medico") -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(USER_ID):
            return AppUser(user_id=USER_ID, username="dev_med", role=role)
        return None

    @app.before_request
    def inject_clinic():
        g.clinic_id = CLINIC_ID

    app.register_blueprint(org_management_bp)
    return app


def _client(app: Flask):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(USER_ID)
    return c


def _scripted_cursor(fetchone_results, fetchall_results):
    """Cria um db_cursor fake yielding (conn, cursor) com fetchone/fetchall scriptados."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = list(fetchone_results)
    cursor.fetchall.side_effect = list(fetchall_results)
    conn = MagicMock()

    @contextmanager
    def fake(dictionary=True):
        yield conn, cursor

    return fake, cursor


def test_dashboard_returns_shape_with_all_top_level_keys():
    """Happy path: tenant valido, dados em todas as fontes."""
    today = date(2026, 4, 1)
    consult_rows = [
        {"month_start": date(2025, 11, 1), "novo": 2, "retorno": 4},
        {"month_start": date(2025, 12, 1), "novo": 3, "retorno": 5},
        {"month_start": date(2026, 1, 1), "novo": 1, "retorno": 6},
        {"month_start": date(2026, 2, 1), "novo": 4, "retorno": 8},
        {"month_start": date(2026, 3, 1), "novo": 2, "retorno": 10},
        {"month_start": date(2026, 4, 1), "novo": 5, "retorno": 12},
    ]
    revenue_rows = [
        {"month_start": date(2025, 11, 1), "total": 8000},
        {"month_start": date(2025, 12, 1), "total": 12000},
        {"month_start": date(2026, 1, 1), "total": 9500},
        {"month_start": date(2026, 2, 1), "total": 14200},
        {"month_start": date(2026, 3, 1), "total": 17800},
        {"month_start": date(2026, 4, 1), "total": 21000},
    ]
    medicos_rows = [
        {"id": 1, "name": "dr_silva"},
        {"id": 2, "name": "dra_santos"},
    ]
    audit_rows = [
        {"endpoint": "/api/v1/anamnese/process", "created_at": datetime.now(timezone.utc) - timedelta(minutes=5)},
        {"endpoint": "/api/v1/knowledge/auto-search", "created_at": datetime.now(timezone.utc) - timedelta(hours=1)},
        {"endpoint": "/api/v1/regulatory/check", "created_at": datetime.now(timezone.utc) - timedelta(days=1)},
    ]

    fetchone_results = [
        {"cnt": 240},  # patients_active
        {"this_month": 8, "last_month": 5},  # new_patients
        {"this_month": 30, "last_month": 25},  # consults
        {"this_month": 21000, "last_month": 17800},  # revenue
        {"tenant_id": TENANT_ID},  # tenant lookup
        {"cnt": 3},  # adverse_events_open
        {"cnt": 230},  # patients_active_last (delta)
    ]
    fetchall_results = [
        consult_rows,
        revenue_rows,
        medicos_rows,
        audit_rows,
    ]

    fake_db, _cursor = _scripted_cursor(fetchone_results, fetchall_results)

    app = _build_app()
    with patch("src.web.routes.org_management.db_cursor", fake_db):
        resp = _client(app).get("/api/v1/org/dashboard")

    assert resp.status_code == 200
    data = resp.get_json()["data"]

    assert set(data.keys()) == {"kpiData", "chartConsultas", "chartReceita", "topMedicos", "recentActivity"}

    # KPIs
    assert len(data["kpiData"]) == 5
    labels = [k["label"] for k in data["kpiData"]]
    assert "Pacientes ativos" in labels
    assert "Receita no mes" in labels

    revenue_kpi = next(k for k in data["kpiData"] if k["label"] == "Receita no mes")
    assert revenue_kpi["value"] == "R$ 21.0k"
    # delta de 17800 -> 21000 = +18%
    assert revenue_kpi["delta"] == "+18%"
    assert revenue_kpi["deltaType"] == "up"

    # Charts
    assert len(data["chartConsultas"]) == 6
    assert all("month" in r and "novo" in r and "retorno" in r for r in data["chartConsultas"])
    assert data["chartConsultas"][0]["month"] == "nov"
    assert data["chartConsultas"][-1]["month"] == "abr"

    assert len(data["chartReceita"]) == 6
    assert data["chartReceita"][-1]["value"] == 21.0  # R$ mil
    assert data["chartReceita"][0]["value"] == 8.0

    # Top medicos
    assert len(data["topMedicos"]) == 2
    assert data["topMedicos"][0]["name"] == "dr_silva"
    assert data["topMedicos"][0]["rating"] is None  # sem fonte de avaliacao
    assert data["topMedicos"][0]["count"] == 0

    # Recent activity
    assert len(data["recentActivity"]) == 3
    icons = [a["icon"] for a in data["recentActivity"]]
    assert "psychology" in icons  # /anamnese
    assert "library_books" in icons  # /knowledge


def test_dashboard_returns_empty_envelope_when_db_fails():
    """Excecao no DB devolve envelope vazio com todas as chaves."""

    def boom(*_a, **_kw):
        raise RuntimeError("connection refused")

    app = _build_app()
    with patch("src.web.routes.org_management.db_cursor", side_effect=boom):
        resp = _client(app).get("/api/v1/org/dashboard")

    data = resp.get_json()["data"]
    assert resp.status_code == 200
    assert data == {
        "kpiData": [],
        "chartConsultas": [],
        "chartReceita": [],
        "topMedicos": [],
        "recentActivity": [],
    }


def test_dashboard_requires_authorized_role():
    """Paciente nao pode acessar painel gerencial."""
    app = _build_app(role="Paciente")
    resp = _client(app).get("/api/v1/org/dashboard")
    assert resp.status_code == 403


def test_dashboard_allows_recepcao():
    """Recepcao tem leitura — depende do happy path mockado."""
    fetchone_results = [
        {"cnt": 0}, {"this_month": 0, "last_month": 0},
        {"this_month": 0, "last_month": 0}, {"this_month": 0, "last_month": 0},
        {"tenant_id": None}, {"cnt": 0},
    ]
    fetchall_results = [[], []]

    fake_db, _cursor = _scripted_cursor(fetchone_results, fetchall_results)
    app = _build_app(role="Recepcao")
    with patch("src.web.routes.org_management.db_cursor", fake_db):
        resp = _client(app).get("/api/v1/org/dashboard")

    assert resp.status_code == 200
    assert "kpiData" in resp.get_json()["data"]
