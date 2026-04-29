"""Tests do envelope JSON de /api/v1/patient/profile e /evolution.

Foco: shape envelope corrigido (bug capturado em project_sprint_progress.md
2026-04-27). Profile vinha top-level mas o frontend espera 3 sub-objetos
{patient, appointment, treatment}; evolution vinha plano mas o frontend
espera {evolution: {<key>: {label, value, prev}}}.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

from flask import Flask, g
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.patient_portal import patient_portal_bp


CLINIC_ID = 1
USER_ID = 11
PATIENT_ID = 99


def _build_app(*, role: str = "Paciente") -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(USER_ID):
            return AppUser(user_id=USER_ID, username="paciente_dev", role=role)
        return None

    @app.before_request
    def inject_tenant():
        g.clinic_id = CLINIC_ID

    app.register_blueprint(patient_portal_bp)
    return app


def _client(app: Flask):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(USER_ID)
    return c


# ---------------------------------------------------------------------------
# Helpers para simular db_cursor(dictionary=True)
# ---------------------------------------------------------------------------


def _make_db_cursor(*, fetchone_results: list, fetchall_results: list | None = None):
    """Cria um context manager fake yielding (conn, cursor) com fetchone/fetchall scriptaveis."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = list(fetchone_results)
    if fetchall_results is not None:
        cursor.fetchall.side_effect = list(fetchall_results)
    conn = MagicMock()

    @contextmanager
    def fake(dictionary=True):
        yield conn, cursor

    return fake, cursor


# ---------------------------------------------------------------------------
# GET /api/v1/patient/profile
# ---------------------------------------------------------------------------


def test_profile_returns_envelope_with_patient_appointment_treatment():
    """Happy path: paciente vinculado, com plano e proxima consulta."""
    fetchone_results = [
        # _get_patient_id_for_user — primeira query
        {"id": PATIENT_ID},
        # SELECT FROM patients
        {
            "id": PATIENT_ID,
            "name": "Maria",
            "phone": "+551199999",
            "email": "maria@example.com",
            "status": "ativo",
            "created_at": datetime(2026, 1, 1),
        },
        # SELECT FROM treatment_plans
        {
            "status": "ativo",
            "dosage": "5mg",
            "cbd_thc_ratio": "20:1",
            "plan_name": "Plano CBD",
            "frequency": "2x/dia",
            "created_at": datetime(2026, 4, 1),
            "treatment_phase": "manutencao",
        },
        # SELECT FROM appointments (proximo)
        {
            "id": 7,
            "appointment_date": datetime(2026, 5, 15, 14, 30),
            "status": "agendado",
        },
    ]
    fake_db_cursor, _ = _make_db_cursor(fetchone_results=fetchone_results)

    app = _build_app()
    with patch("src.web.routes.patient_portal.db_cursor", fake_db_cursor):
        resp = _client(app).get("/api/v1/patient/profile")

    assert resp.status_code == 200
    data = resp.get_json()["data"]

    assert set(data.keys()) == {"patient", "appointment", "treatment"}

    patient = data["patient"]
    assert patient["id"] == PATIENT_ID
    assert patient["name"] == "Maria"
    assert patient["treatment_status"] == "ativo"
    assert patient["treatment_phase"] == "manutencao"
    assert patient["treatment_day"] >= 0
    assert patient["treatment_total_days"] is None  # campo ainda nao existe no schema

    appt = data["appointment"]
    assert appt["date"] == "15 mai"
    assert appt["time"] == "14:30"
    assert appt["doctor"] == "A confirmar"
    assert appt["modality"] == "presencial"

    treatment = data["treatment"]
    assert treatment["product"] == "Plano CBD"
    assert treatment["dose"] == "5mg"
    assert treatment["frequency"] == "2x/dia"
    assert treatment["cbd_mg"] is None
    assert treatment["thc_mg"] is None


def test_profile_returns_empty_envelope_when_no_patient_linked():
    """User sem patient vinculado recebe envelope vazio com nome do user."""
    fetchone_results = [None]  # _get_patient_id_for_user — primeira query
    fake_db_cursor, _ = _make_db_cursor(fetchone_results=fetchone_results)

    app = _build_app()
    with patch("src.web.routes.patient_portal.db_cursor", fake_db_cursor):
        resp = _client(app).get("/api/v1/patient/profile")

    assert resp.status_code == 200
    data = resp.get_json()["data"]

    assert data["appointment"] is None
    assert data["treatment"] is None
    assert data["patient"]["id"] == 0
    assert data["patient"]["name"] == "paciente_dev"
    assert data["patient"]["treatment_total_days"] is None


def test_profile_appointment_is_null_when_no_future_appointment():
    """Sem appointment futuro, sub-objeto appointment vem como None."""
    fetchone_results = [
        {"id": PATIENT_ID},
        {
            "id": PATIENT_ID,
            "name": "Joao",
            "phone": None,
            "email": None,
            "status": "ativo",
            "created_at": datetime(2026, 1, 1),
        },
        None,  # sem treatment_plan
        None,  # sem appointment futuro
    ]
    fake_db_cursor, _ = _make_db_cursor(fetchone_results=fetchone_results)

    app = _build_app()
    with patch("src.web.routes.patient_portal.db_cursor", fake_db_cursor):
        resp = _client(app).get("/api/v1/patient/profile")

    data = resp.get_json()["data"]
    assert data["appointment"] is None
    assert data["treatment"] is None
    assert data["patient"]["treatment_phase"] is None


def test_profile_requires_authentication():
    app = _build_app()
    resp = app.test_client().get("/api/v1/patient/profile")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/patient/evolution
# ---------------------------------------------------------------------------


def test_evolution_returns_envelope_with_label_value_prev():
    """Shape esperado: envelope.evolution.{key}.{label, value, prev} em escala 0-100."""
    fetchone_results = [
        {"id": PATIENT_ID},
        # period atual: dor 3, sono 7, humor 8 (escala 0-10)
        {"avg_pain": 3, "avg_sleep": 7, "avg_mood": 8},
        # period anterior: dor 5, sono 5, humor 6
        {"avg_pain": 5, "avg_sleep": 5, "avg_mood": 6},
    ]
    fake_db_cursor, _ = _make_db_cursor(fetchone_results=fetchone_results)

    app = _build_app()
    with patch("src.web.routes.patient_portal.db_cursor", fake_db_cursor):
        resp = _client(app).get("/api/v1/patient/evolution")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert set(data.keys()) == {"evolution"}
    evo = data["evolution"]

    assert set(evo.keys()) == {"pain", "sleep", "mood"}

    # Labels em PT-BR
    assert evo["pain"]["label"] == "Dor"
    assert evo["sleep"]["label"] == "Sono"
    assert evo["mood"]["label"] == "Humor"

    # Sono e humor: escala direta (× 10)
    assert evo["sleep"]["value"] == 70
    assert evo["sleep"]["prev"] == 50
    assert evo["mood"]["value"] == 80
    assert evo["mood"]["prev"] == 60

    # Dor e invertida: avg=3 → value = 100 - 30 = 70 (melhorou em relacao a 50)
    assert evo["pain"]["value"] == 70
    assert evo["pain"]["prev"] == 50


def test_evolution_handles_null_averages():
    """AVG retorna None quando nao ha registros — vira 0."""
    fetchone_results = [
        {"id": PATIENT_ID},
        {"avg_pain": None, "avg_sleep": None, "avg_mood": None},
        {"avg_pain": None, "avg_sleep": None, "avg_mood": None},
    ]
    fake_db_cursor, _ = _make_db_cursor(fetchone_results=fetchone_results)

    app = _build_app()
    with patch("src.web.routes.patient_portal.db_cursor", fake_db_cursor):
        resp = _client(app).get("/api/v1/patient/evolution")

    evo = resp.get_json()["data"]["evolution"]
    for key in ("pain", "sleep", "mood"):
        assert evo[key]["value"] == 0
        assert evo[key]["prev"] == 0


def test_evolution_returns_empty_envelope_when_no_patient_linked():
    fetchone_results = [None]
    fake_db_cursor, _ = _make_db_cursor(fetchone_results=fetchone_results)

    app = _build_app()
    with patch("src.web.routes.patient_portal.db_cursor", fake_db_cursor):
        resp = _client(app).get("/api/v1/patient/evolution")

    assert resp.status_code == 200
    evo = resp.get_json()["data"]["evolution"]
    assert evo["pain"] == {"label": "Dor", "value": 0, "prev": 0}
    assert evo["sleep"] == {"label": "Sono", "value": 0, "prev": 0}
    assert evo["mood"] == {"label": "Humor", "value": 0, "prev": 0}


# ---------------------------------------------------------------------------
# GET /api/v1/patient/appointments
# ---------------------------------------------------------------------------


def test_appointments_returns_upcoming_and_past_split():
    """Endpoint separa appointments em upcoming e past, com formatacao PT-BR."""
    upcoming_rows = [
        {"id": 1, "appointment_date": datetime(2026, 5, 15, 14, 30), "status": "agendado", "notes": None},
        {"id": 2, "appointment_date": datetime(2026, 6, 1, 10, 0), "status": "confirmado", "notes": "Trazer exames"},
    ]
    past_rows = [
        {"id": 99, "appointment_date": datetime(2026, 3, 1, 9, 0), "status": "concluido", "notes": "Ajustar dose"},
    ]

    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"id": PATIENT_ID}]
    cursor.fetchall.side_effect = [upcoming_rows, past_rows]
    conn = MagicMock()

    @contextmanager
    def fake(dictionary=True):
        yield conn, cursor

    app = _build_app()
    with patch("src.web.routes.patient_portal.db_cursor", fake):
        resp = _client(app).get("/api/v1/patient/appointments")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert set(data.keys()) == {"upcoming", "past"}
    assert len(data["upcoming"]) == 2
    assert len(data["past"]) == 1

    first = data["upcoming"][0]
    assert first["id"] == 1
    assert first["date"] == "15 mai 2026"
    assert first["time"] == "14:30"
    assert first["status"] == "agendado"
    assert first["doctor"] == "A confirmar"
    assert first["modality"] == "presencial"
    assert first["notes"] is None

    past_first = data["past"][0]
    assert past_first["id"] == 99
    assert past_first["status"] == "concluido"
    assert past_first["notes"] == "Ajustar dose"


def test_appointments_returns_empty_when_no_patient_linked():
    fetchone_results = [None]
    fake_db_cursor, _ = _make_db_cursor(fetchone_results=fetchone_results)

    app = _build_app()
    with patch("src.web.routes.patient_portal.db_cursor", fake_db_cursor):
        resp = _client(app).get("/api/v1/patient/appointments")

    assert resp.status_code == 200
    assert resp.get_json()["data"] == {"upcoming": [], "past": []}


def test_appointments_requires_authentication():
    app = _build_app()
    resp = app.test_client().get("/api/v1/patient/appointments")
    assert resp.status_code == 401


def test_evolution_clamps_extremes():
    """Valores fora de 0-10 sao clampados em 0-100."""
    fetchone_results = [
        {"id": PATIENT_ID},
        {"avg_pain": 0, "avg_sleep": 10, "avg_mood": 10},
        {"avg_pain": 10, "avg_sleep": 0, "avg_mood": 0},
    ]
    fake_db_cursor, _ = _make_db_cursor(fetchone_results=fetchone_results)

    app = _build_app()
    with patch("src.web.routes.patient_portal.db_cursor", fake_db_cursor):
        resp = _client(app).get("/api/v1/patient/evolution")

    evo = resp.get_json()["data"]["evolution"]
    # pain: avg 0 → 100 - 0 = 100; prev avg 10 → 100 - 100 = 0
    assert evo["pain"]["value"] == 100
    assert evo["pain"]["prev"] == 0
    # sleep: avg 10 → 100; prev 0 → 0
    assert evo["sleep"]["value"] == 100
    assert evo["sleep"]["prev"] == 0
    # mood: avg 10 → 100; prev 0 → 0
    assert evo["mood"]["value"] == 100
    assert evo["mood"]["prev"] == 0
