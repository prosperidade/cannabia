"""Sprint C MVP: regressao do /api/v1/med/onboarding.

Garante:
- GET retorna defaults quando perfil ainda nao existe
- GET serializa perfil existente
- POST /complete rejeita sem CSRF
- POST /complete valida campos obrigatorios (full_name, crm, specialty)
- POST /complete happy path: chama upsert + mark_completed e retorna serializacao
- Roles nao-medicas (Paciente, Recepcao, Financeiro, AdminClinica sozinho) sao bloqueadas
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from flask import Flask, g
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.med_onboarding import med_onboarding_bp
from src.web.routes.api_v1 import api_v1_bp


USER_ID = 42
CSRF_TOKEN = "test-csrf"


def _build_app(*, role: str = "Medico") -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(USER_ID):
            return AppUser(user_id=USER_ID, username="dr_test", role=role)
        return None

    @app.before_request
    def inject_tenant():
        g.clinic_id = 1

    app.register_blueprint(api_v1_bp)
    app.register_blueprint(med_onboarding_bp)
    return app


def _client(app: Flask):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(USER_ID)
        sess["csrf_token"] = CSRF_TOKEN
    return c


def _headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "X-CSRF-Token": CSRF_TOKEN}


# ---------------------------------------------------------------------------
# GET /api/v1/med/onboarding
# ---------------------------------------------------------------------------


def test_get_returns_defaults_when_profile_missing():
    app = _build_app()
    with patch(
        "src.web.routes.med_onboarding.profile_repo.get_by_user_id",
        return_value=None,
    ):
        resp = _client(app).get("/api/v1/med/onboarding")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data == {
        "full_name": "",
        "crm": "",
        "specialty": "",
        "photo_url": None,
        "crm_doc_url": None,
        "diploma_url": None,
        "prefs_notifications": True,
        "prefs_ai_level": "avancado",
        "onboarding_completed_at": None,
    }


def test_get_serializes_existing_profile():
    completed = datetime(2026, 5, 25, 14, 30, tzinfo=timezone.utc)
    app = _build_app()
    fake_row = {
        "user_id": USER_ID,
        "full_name": "Dr. Test",
        "crm": "123456/SP",
        "specialty": "Neurologia",
        "photo_url": None,
        "crm_doc_url": None,
        "diploma_url": None,
        "prefs_notifications": False,
        "prefs_ai_level": "completo",
        "onboarding_completed_at": completed,
    }
    with patch(
        "src.web.routes.med_onboarding.profile_repo.get_by_user_id",
        return_value=fake_row,
    ):
        resp = _client(app).get("/api/v1/med/onboarding")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["full_name"] == "Dr. Test"
    assert data["crm"] == "123456/SP"
    assert data["specialty"] == "Neurologia"
    assert data["prefs_notifications"] is False
    assert data["prefs_ai_level"] == "completo"
    assert data["onboarding_completed_at"] == "2026-05-25T14:30:00+00:00"


# ---------------------------------------------------------------------------
# POST /api/v1/med/onboarding/complete
# ---------------------------------------------------------------------------


def test_complete_rejects_without_csrf():
    app = _build_app()
    resp = _client(app).post(
        "/api/v1/med/onboarding/complete",
        json={"full_name": "X", "crm": "1/SP", "specialty": "Y"},
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "csrf_invalid"


def test_complete_requires_full_name():
    app = _build_app()
    resp = _client(app).post(
        "/api/v1/med/onboarding/complete",
        json={"crm": "1/SP", "specialty": "Y"},
        headers=_headers(),
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "validation_error"


def test_complete_requires_crm():
    app = _build_app()
    resp = _client(app).post(
        "/api/v1/med/onboarding/complete",
        json={"full_name": "Dr.", "specialty": "Y"},
        headers=_headers(),
    )
    assert resp.status_code == 422


def test_complete_requires_specialty():
    app = _build_app()
    resp = _client(app).post(
        "/api/v1/med/onboarding/complete",
        json={"full_name": "Dr.", "crm": "1/SP"},
        headers=_headers(),
    )
    assert resp.status_code == 422


def test_complete_happy_path_calls_upsert_and_mark_completed():
    completed = datetime(2026, 5, 25, 18, 0, tzinfo=timezone.utc)
    final_row = {
        "user_id": USER_ID,
        "full_name": "Dr. Test",
        "crm": "123456/SP",
        "specialty": "Neurologia",
        "photo_url": None,
        "crm_doc_url": None,
        "diploma_url": None,
        "prefs_notifications": True,
        "prefs_ai_level": "avancado",
        "onboarding_completed_at": completed,
    }
    app = _build_app()
    with patch(
        "src.web.routes.med_onboarding.profile_repo.upsert",
        return_value=final_row,
    ) as upsert_mock, patch(
        "src.web.routes.med_onboarding.profile_repo.mark_completed",
        return_value=final_row,
    ) as mark_mock:
        resp = _client(app).post(
            "/api/v1/med/onboarding/complete",
            json={
                "full_name": "Dr. Test",
                "crm": "123456/SP",
                "specialty": "Neurologia",
                "prefs_notifications": True,
                "prefs_ai_level": "avancado",
            },
            headers=_headers(),
        )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["full_name"] == "Dr. Test"
    assert data["onboarding_completed_at"] == "2026-05-25T18:00:00+00:00"
    upsert_mock.assert_called_once()
    mark_mock.assert_called_once_with(USER_ID)


def test_complete_blocks_paciente_role():
    app = _build_app(role="Paciente")
    resp = _client(app).post(
        "/api/v1/med/onboarding/complete",
        json={"full_name": "Dr.", "crm": "1/SP", "specialty": "Y"},
        headers=_headers(),
    )
    assert resp.status_code == 403


def test_complete_blocks_recepcao_role():
    app = _build_app(role="Recepcao")
    resp = _client(app).post(
        "/api/v1/med/onboarding/complete",
        json={"full_name": "Dr.", "crm": "1/SP", "specialty": "Y"},
        headers=_headers(),
    )
    assert resp.status_code == 403


def test_get_blocks_financeiro_role():
    app = _build_app(role="Financeiro")
    resp = _client(app).get("/api/v1/med/onboarding")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/v1/med/onboarding/upload/<field>  (Sprint D M1)
# ---------------------------------------------------------------------------

import io


def _upload(client, field: str, *, csrf: str | None = CSRF_TOKEN, data: bytes = b"PDFDATA",
            mime: str = "application/pdf", filename: str = "doc.pdf"):
    headers = {}
    if csrf is not None:
        headers["X-CSRF-Token"] = csrf
    return client.post(
        f"/api/v1/med/onboarding/upload/{field}",
        data={"file": (io.BytesIO(data), filename, mime)},
        content_type="multipart/form-data",
        headers=headers,
    )


def test_upload_rejects_invalid_field():
    app = _build_app()
    resp = _upload(_client(app), "invalido")
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "validation_error"


def test_upload_rejects_without_csrf():
    app = _build_app()
    resp = _upload(_client(app), "crm_doc", csrf=None)
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "csrf_invalid"


def test_upload_rejects_when_file_field_missing():
    app = _build_app()
    resp = _client(app).post(
        "/api/v1/med/onboarding/upload/crm_doc",
        data={},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert resp.status_code == 422


def test_upload_rejects_empty_file():
    app = _build_app()
    resp = _upload(_client(app), "crm_doc", data=b"")
    assert resp.status_code == 422


def test_upload_rejects_oversized_file():
    app = _build_app()
    # 6MB > MAX_FILE_SIZE (5MB)
    big = b"x" * (6 * 1024 * 1024)
    resp = _upload(_client(app), "crm_doc", data=big)
    assert resp.status_code == 413
    assert resp.get_json()["error"]["code"] == "file_too_large"


def test_upload_rejects_disallowed_mime():
    app = _build_app()
    resp = _upload(_client(app), "crm_doc", data=b"text", mime="text/plain", filename="doc.txt")
    assert resp.status_code == 422


def test_upload_returns_503_when_storage_not_configured(monkeypatch):
    """Default sem STORAGE_PROVIDER: NoopStorage retorna 503 com mensagem."""
    monkeypatch.delenv("STORAGE_PROVIDER", raising=False)
    app = _build_app()
    with patch(
        "src.web.routes.med_onboarding.profile_repo.upsert",
        return_value={},
    ):
        resp = _upload(_client(app), "crm_doc")
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "storage_not_configured"


def test_upload_happy_path_persists_url(monkeypatch):
    """Stub do storage backend: verifica que upload e chamado com a key
    esperada e que profile_repo.upsert recebe a URL."""
    fake_backend = MagicMock()
    fake_backend.upload.return_value = "https://cdn.local/onboarding/42/crm_doc.pdf"

    app = _build_app()
    with patch("src.web.routes.med_onboarding.storage.get_backend", return_value=fake_backend), \
         patch("src.web.routes.med_onboarding.profile_repo.upsert") as upsert_mock:
        resp = _upload(_client(app), "crm_doc", data=b"PDF1.4")

    assert resp.status_code == 200
    body = resp.get_json()["data"]
    assert body == {
        "field": "crm_doc",
        "url": "https://cdn.local/onboarding/42/crm_doc.pdf",
    }

    fake_backend.upload.assert_called_once()
    call_kwargs = fake_backend.upload.call_args.kwargs
    assert call_kwargs["key"] == f"onboarding/{USER_ID}/crm_doc.pdf"
    assert call_kwargs["content"] == b"PDF1.4"
    assert call_kwargs["content_type"] == "application/pdf"

    upsert_mock.assert_called_once_with(USER_ID, {"crm_doc_url": "https://cdn.local/onboarding/42/crm_doc.pdf"})


def test_upload_picks_extension_from_mime():
    """PNG mime -> .png extension na key."""
    fake_backend = MagicMock()
    fake_backend.upload.return_value = "/uploads/onboarding/42/photo.png"
    app = _build_app()
    with patch("src.web.routes.med_onboarding.storage.get_backend", return_value=fake_backend), \
         patch("src.web.routes.med_onboarding.profile_repo.upsert"):
        resp = _upload(_client(app), "photo", data=b"PNG", mime="image/png", filename="me.png")

    assert resp.status_code == 200
    key = fake_backend.upload.call_args.kwargs["key"]
    assert key == f"onboarding/{USER_ID}/photo.png"


def test_upload_blocks_paciente_role():
    app = _build_app(role="Paciente")
    resp = _upload(_client(app), "crm_doc")
    assert resp.status_code == 403
