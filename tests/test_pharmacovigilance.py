"""Tests integrados ponta-a-ponta de pharmacovigilance — F3.8 do SCC.

Diferente dos arquivos por camada (`test_adverse_event_service`,
`test_agente_regulatorio`, `test_vigimed_integration`,
`test_pharmacovigilance_service`, `test_pharmacovigilance_routes`),
este modulo exercita o pipeline completo F3.3 → F3.4 → F3.5 → F3.6
em cenarios end-to-end:

  - Pipeline HTTP completo: POST capture → POST triage → POST notify
    → GET notifications → GET dashboard, contra Postgres real e o
    blueprint registrado num Flask de teste (sem mocks de service).

  - Pipeline cross-camada: captura via service direto (simula webhook
    WhatsApp), triagem via skill IA, notificacao via dispatcher F3.5,
    leitura via blueprint HTTP. Garante que as 3 camadas conversam
    coerentemente quando combinadas.

  - Isolamento por tenant end-to-end via test_client.

  - Agregacao do dashboard com multiplos eventos.

NAO duplica testes unitarios das camadas — foco e contratos
inter-camadas e o pipeline real exercitado por usuario do blueprint.
"""

from __future__ import annotations

import uuid

import pytest
from flask import Flask, g
from flask_login import LoginManager

from src.infra.database import db_cursor
from src.services import adverse_event_service
from src.web.auth_identity import AppUser
from src.web.routes.pharmacovigilance import pharmacovigilance_bp


# =====================================================================
# Skip global se DB nao alcancavel
# =====================================================================


def _db_reachable() -> bool:
    try:
        with db_cursor() as (_, cur):
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="DB local nao alcancavel"
)


# =====================================================================
# Constantes de fixture
# =====================================================================


CSRF_TOKEN = "test-csrf-token"


# =====================================================================
# Setup
# =====================================================================


@pytest.fixture(autouse=True)
def _force_mock_provider(monkeypatch):
    """Garante que a F3.5 fica em mock — testes nao tocam rede."""
    monkeypatch.delenv("ANVISA_NOTIFICATION_PROVIDER", raising=False)
    yield


@pytest.fixture
def fixture_setup():
    """
    Tenant + user Admin reais por teste, com cleanup completo no
    teardown. User real necessario para FK
    `adverse_events.triaged_by → users.id` quando o blueprint
    persiste a triagem.

    Retorna dict com `tenant_id` e `admin_id`.
    """
    suffix = uuid.uuid4().hex[:8]
    name = f"e2e_pv_{suffix}"
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO tenants (tenant_type_id, tenant_type, legal_name,
                                 display_name, slug, status)
            VALUES (
              (SELECT id FROM tenant_types WHERE slug='association' LIMIT 1),
              'association', %s, %s, %s, 'active'
            )
            RETURNING id
            """,
            (name, name, name),
        )
        tenant_id = cur.fetchone()["id"]

        cur.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (%s, 'x', 'Admin')
            RETURNING id
            """,
            (f"admin_{suffix}",),
        )
        admin_id = cur.fetchone()["id"]
        conn.commit()

    yield {"tenant_id": tenant_id, "admin_id": admin_id}

    with db_cursor() as (conn, cur):
        cur.execute(
            "DELETE FROM pharmacovigilance_notifications "
            "WHERE adverse_event_id IN "
            "(SELECT id FROM adverse_events WHERE tenant_id = %s)",
            (tenant_id,),
        )
        cur.execute(
            "DELETE FROM adverse_events WHERE tenant_id = %s", (tenant_id,)
        )
        cur.execute(
            "DELETE FROM association_members WHERE tenant_id = %s",
            (tenant_id,),
        )
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (admin_id,))
        conn.commit()


def _build_client(tenant_id: int, admin_id: int, monkeypatch):
    """
    Constroi um Flask test_client com:
      - blueprint pharmacovigilance registrado
      - login session de Admin com `admin_id` (precisa ser id REAL
        em users porque adverse_events.triaged_by tem FK)
      - g.tenant_id injetado a cada request
    """

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(admin_id):
            return AppUser(user_id=admin_id, username="admin", role="Admin")
        return None

    @app.before_request
    def inject_tenant():
        g.tenant_id = tenant_id

    app.register_blueprint(pharmacovigilance_bp)
    test_client = app.test_client()
    with test_client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["csrf_token"] = CSRF_TOKEN
    return test_client


def _headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "X-CSRF-Token": CSRF_TOKEN}


# =====================================================================
# Pipeline 1 — Fluxo HTTP completo end-to-end (capture → triage →
# notify → notifications → dashboard) sem mocks de service
# =====================================================================


class TestE2EPipelineHttp:
    def test_full_lifecycle_via_http(self, fixture_setup, monkeypatch):
        client = _build_client(
            fixture_setup["tenant_id"], fixture_setup["admin_id"], monkeypatch
        )

        # 1. Captura: paciente publico (sem member_id) com sintomas
        #    moderados que a triage devera escalar.
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events",
            headers=_headers(),
            json={
                "description": "Paciente foi internado apos crise convulsiva.",
                "severity": "moderate",
                "reported_via": "whatsapp",
            },
        )
        assert resp.status_code == 201, resp.get_json()
        event_id = resp.get_json()["data"]["adverse_event"]["id"]

        # 2. Triagem heuristica (F3.4): keywords "internado" e
        #    "convuls" devem escalar moderate → life_threatening.
        resp = client.post(
            f"/api/v1/pharmacovigilance/adverse-events/{event_id}/triage",
            headers=_headers(),
        )
        assert resp.status_code == 200
        triage = resp.get_json()["data"]
        assert triage["ok"] is True
        assert triage["severity_reported"] == "moderate"
        assert triage["severity_suggested"] == "life_threatening"
        assert triage["escalated"] is True
        assert triage["notify_required"] is True
        assert "convuls" in " ".join(triage["red_flags"])
        # ai_triage_result foi persistido no evento
        assert (
            triage["adverse_event"]["ai_triage_result"]["severity_suggested"]
            == "life_threatening"
        )

        # 3. Notificacao regulatoria (F3.5 dispatcher → mock):
        resp = client.post(
            f"/api/v1/pharmacovigilance/adverse-events/{event_id}/notify",
            headers=_headers(),
            json={},
        )
        assert resp.status_code == 201
        notif = resp.get_json()["data"]["notification"]
        assert notif["notification_target"] == "internal_only"
        assert notif["notification_reference"].startswith("MOCK-")
        assert notif["adverse_event_id"] == event_id

        # 4. Lista notifications do evento
        resp = client.get(
            f"/api/v1/pharmacovigilance/adverse-events/{event_id}/notifications"
        )
        assert resp.status_code == 200
        notifs = resp.get_json()["data"]["notifications"]
        assert len(notifs) == 1
        assert notifs[0]["id"] == notif["id"]

        # 5. Dashboard agrega: 1 evento moderate, 0 notificavel
        #    pelo CONTAGEM de severidade reportada (severity reportado
        #    permanece 'moderate' mesmo apos triagem — F3.4 nao altera
        #    a coluna severity, so registra ai_triage_result), 1
        #    notificacao em internal_only.
        resp = client.get(
            "/api/v1/pharmacovigilance/dashboard?period_days=7"
        )
        assert resp.status_code == 200
        dash = resp.get_json()["data"]
        assert dash["total_events"] == 1
        assert dash["events_by_severity"].get("moderate") == 1
        assert dash["events_requiring_notification"] == 0  # moderate nao e notificavel
        assert dash["notifications_by_target"].get("internal_only") == 1

    def test_capture_endpoint_round_trips_to_get(
        self, fixture_setup, monkeypatch
    ):
        """Garante que POST cria a linha que GET recupera com mesmos campos."""
        client = _build_client(
            fixture_setup["tenant_id"], fixture_setup["admin_id"], monkeypatch
        )

        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events",
            headers=_headers(),
            json={
                "description": "evento basico",
                "severity": "mild",
                "reported_via": "web",
            },
        )
        event_id = resp.get_json()["data"]["adverse_event"]["id"]

        get_resp = client.get(
            f"/api/v1/pharmacovigilance/adverse-events/{event_id}"
        )
        assert get_resp.status_code == 200
        ev = get_resp.get_json()["data"]["adverse_event"]
        assert ev["id"] == event_id
        assert ev["description"] == "evento basico"
        assert ev["severity"] == "mild"
        assert ev["reported_via"] == "web"
        assert ev["requires_regulatory_notification"] is False


# =====================================================================
# Pipeline 2 — captura via SERVICE (simula webhook WhatsApp) +
# triagem + notificacao + leitura via HTTP
# =====================================================================


class TestServiceToBlueprintHandoff:
    def test_whatsapp_capture_then_blueprint_consumes(
        self, fixture_setup, monkeypatch
    ):
        # Fase 1: webhook do WhatsApp chama o SERVICE direto, com auth
        # HMAC propria — nao passa pelo blueprint.
        captured = adverse_event_service.capture_adverse_event(
            tenant_id=fixture_setup["tenant_id"],
            description="Paciente reportou anafilaxia apos primeira dose.",
            severity="mild",
            reported_via="whatsapp",
        )
        assert captured.id > 0

        # Fase 2: agora o painel medico lista o evento via HTTP
        client = _build_client(
            fixture_setup["tenant_id"], fixture_setup["admin_id"], monkeypatch
        )
        list_resp = client.get(
            "/api/v1/pharmacovigilance/adverse-events"
            "?reported_via=whatsapp"
        )
        assert list_resp.status_code == 200
        events = list_resp.get_json()["data"]["adverse_events"]
        assert len(events) == 1
        assert events[0]["id"] == captured.id

        # Fase 3: medico aciona triage via HTTP → escala para
        # life_threatening (anafilaxia) e marca notify_required.
        triage_resp = client.post(
            f"/api/v1/pharmacovigilance/adverse-events/{captured.id}/triage",
            headers=_headers(),
        )
        assert triage_resp.status_code == 200
        triage = triage_resp.get_json()["data"]
        assert triage["severity_suggested"] == "life_threatening"
        assert triage["notify_required"] is True

        # Fase 4: notify regulatoria via HTTP, depois tenta segunda
        # notificacao — historico fica com 2 entradas (idempotencia
        # via reference deterministica do mock).
        client.post(
            f"/api/v1/pharmacovigilance/adverse-events/{captured.id}/notify",
            headers=_headers(),
            json={},
        )
        client.post(
            f"/api/v1/pharmacovigilance/adverse-events/{captured.id}/notify",
            headers=_headers(),
            json={},
        )
        notif_resp = client.get(
            f"/api/v1/pharmacovigilance/adverse-events/{captured.id}/notifications"
        )
        notifs = notif_resp.get_json()["data"]["notifications"]
        assert len(notifs) == 2
        # Mock e deterministico → mesma reference para mesmo payload
        assert (
            notifs[0]["notification_reference"]
            == notifs[1]["notification_reference"]
        )


# =====================================================================
# Pipeline 3 — Cross-tenant isolation end-to-end via HTTP
# =====================================================================


class TestCrossTenantIsolationHttp:
    def test_tenant_b_cannot_see_tenant_a_events_via_http(
        self, fixture_setup, monkeypatch
    ):
        # Cria evento no tenant A via service
        ev_a = adverse_event_service.capture_adverse_event(
            tenant_id=fixture_setup["tenant_id"],
            description="evento confidencial do tenant A",
            severity="severe",
            reported_via="consultation",
        )

        # Cria tenant B + user B em paralelo
        suffix = uuid.uuid4().hex[:8]
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                """
                INSERT INTO tenants (tenant_type_id, tenant_type, legal_name,
                                     display_name, slug, status)
                VALUES (
                  (SELECT id FROM tenant_types WHERE slug='association' LIMIT 1),
                  'association', %s, %s, %s, 'active'
                )
                RETURNING id
                """,
                (f"e2e_other_{suffix}",) * 3,
            )
            tenant_b = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO users (username, password_hash, role) "
                "VALUES (%s, 'x', 'Admin') RETURNING id",
                (f"admin_b_{suffix}",),
            )
            admin_b = cur.fetchone()["id"]
            conn.commit()
        try:
            client_b = _build_client(tenant_b, admin_b, monkeypatch)

            # GET no detalhe → 404 (cross-tenant)
            r = client_b.get(
                f"/api/v1/pharmacovigilance/adverse-events/{ev_a.id}"
            )
            assert r.status_code == 404

            # LIST → vazio
            r = client_b.get(
                "/api/v1/pharmacovigilance/adverse-events"
            )
            assert r.get_json()["data"]["adverse_events"] == []

            # NOTIFY no evento alheio → 404
            r = client_b.post(
                f"/api/v1/pharmacovigilance/adverse-events/{ev_a.id}/notify",
                headers=_headers(),
                json={},
            )
            assert r.status_code == 404

            # TRIAGE no evento alheio → 404
            r = client_b.post(
                f"/api/v1/pharmacovigilance/adverse-events/{ev_a.id}/triage",
                headers=_headers(),
            )
            assert r.status_code == 404

            # DASHBOARD → zerado
            r = client_b.get(
                "/api/v1/pharmacovigilance/dashboard?period_days=7"
            )
            dash = r.get_json()["data"]
            assert dash["total_events"] == 0
        finally:
            with db_cursor() as (conn, cur):
                cur.execute(
                    "DELETE FROM tenants WHERE id = %s", (tenant_b,)
                )
                cur.execute(
                    "DELETE FROM users WHERE id = %s", (admin_b,)
                )
                conn.commit()


# =====================================================================
# Pipeline 4 — Dashboard agregando multiplos eventos com mix de
# severidades e notificacoes parciais
# =====================================================================


class TestDashboardAggregation:
    def test_dashboard_reflects_mixed_severities_and_partial_notifications(
        self, fixture_setup, monkeypatch
    ):
        client = _build_client(
            fixture_setup["tenant_id"], fixture_setup["admin_id"], monkeypatch
        )

        # 5 eventos: 2 mild, 1 moderate, 2 severe.
        for desc, sev in [
            ("evento 1 mild", "mild"),
            ("evento 2 mild", "mild"),
            ("evento 3 moderate", "moderate"),
            ("evento 4 severe", "severe"),
            ("evento 5 severe", "severe"),
        ]:
            r = client.post(
                "/api/v1/pharmacovigilance/adverse-events",
                headers=_headers(),
                json={
                    "description": desc, "severity": sev,
                    "reported_via": "web",
                },
            )
            assert r.status_code == 201

        # Notifica apenas os 2 severe (notify_required) e 1 mild
        # (decisao manual do medico — pode notificar internal_only
        # mesmo de eventos nao-criticos).
        events_resp = client.get(
            "/api/v1/pharmacovigilance/adverse-events?severity=severe"
        )
        for ev in events_resp.get_json()["data"]["adverse_events"]:
            client.post(
                f"/api/v1/pharmacovigilance/adverse-events/{ev['id']}/notify",
                headers=_headers(),
                json={},
            )

        mild_resp = client.get(
            "/api/v1/pharmacovigilance/adverse-events?severity=mild"
        )
        first_mild = mild_resp.get_json()["data"]["adverse_events"][0]
        client.post(
            f"/api/v1/pharmacovigilance/adverse-events/{first_mild['id']}/notify",
            headers=_headers(),
            json={},
        )

        # Dashboard
        dash = client.get(
            "/api/v1/pharmacovigilance/dashboard?period_days=7"
        ).get_json()["data"]

        assert dash["total_events"] == 5
        assert dash["events_by_severity"] == {
            "mild": 2, "moderate": 1, "severe": 2
        }
        assert dash["events_requiring_notification"] == 2  # so os severe
        assert dash["notifications_by_target"]["internal_only"] == 3
        assert dash["period_days"] == 7


# =====================================================================
# Pipeline 5 — Validacoes HTTP que cruzam camadas
# =====================================================================


class TestCrossLayerValidations:
    def test_capture_with_invalid_severity_returns_422_via_http(
        self, fixture_setup, monkeypatch
    ):
        client = _build_client(
            fixture_setup["tenant_id"], fixture_setup["admin_id"], monkeypatch
        )
        r = client.post(
            "/api/v1/pharmacovigilance/adverse-events",
            headers=_headers(),
            json={
                "description": "x", "severity": "catastrophic",
                "reported_via": "web",
            },
        )
        assert r.status_code == 422
        assert "severity" in r.get_json()["error"]["message"]

    def test_notify_with_invalid_provider_returns_422(
        self, fixture_setup, monkeypatch
    ):
        client = _build_client(
            fixture_setup["tenant_id"], fixture_setup["admin_id"], monkeypatch
        )
        captured = adverse_event_service.capture_adverse_event(
            tenant_id=fixture_setup["tenant_id"],
            description="evento qualquer", severity="severe",
            reported_via="web",
        )
        r = client.post(
            f"/api/v1/pharmacovigilance/adverse-events/{captured.id}/notify",
            headers=_headers(),
            json={"provider": "anvisa-direto"},
        )
        assert r.status_code == 422
        assert "invalido" in r.get_json()["error"]["message"]

    def test_triage_returns_404_for_nonexistent_event(
        self, fixture_setup, monkeypatch
    ):
        client = _build_client(
            fixture_setup["tenant_id"], fixture_setup["admin_id"], monkeypatch
        )
        r = client.post(
            "/api/v1/pharmacovigilance/adverse-events/999999999/triage",
            headers=_headers(),
        )
        assert r.status_code == 404
