"""
Tests do agregador compliance (F6.4 do docs/BACKLOG_SCC.md).

Cobre as 7 funcoes `<submodulo>_summary(tenant_id)` que calculam score
por submodulo do SCC. Fixtures inserem dados controlados, validam que
cada check responde conforme esperado e que o overall_score e media
simples dos 7.

Nao cobre o endpoint HTTP (autenticacao) — isso fica para test_routes.
Foco aqui: logica deterministica das funcoes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from src.infra.database import db_cursor
from src.web.routes.compliance import (
    SUBMODULES,
    crypto_summary,
    governance_summary,
    members_summary,
    pharmacovigilance_summary,
    quality_summary,
    regulatory_summary,
    traceability_summary,
)


def _db_reachable() -> bool:
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="DB local nao alcancavel"
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def tenant_with_clinic() -> int:
    """Cria tenant (association) + clinic atrelada com id == tenant_id.

    Retorna o tenant_id que tambem e clinic_id por convencao SCC.
    Cleanup remove tudo com bypass de triggers append-only.
    """
    suffix = uuid.uuid4().hex[:8]
    name = f"compliance_test_{suffix}"
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO tenants (tenant_type_id, tenant_type, legal_name,
                                 display_name, slug, status,
                                 cnpj, incorporation_date)
            VALUES (
              (SELECT id FROM tenant_types WHERE slug='association' LIMIT 1),
              'association', %s, %s, %s, 'active',
              %s, %s
            )
            RETURNING id
            """,
            (name, name, name, f"{uuid.uuid4().int % 10**14:014d}",
             date.today() - timedelta(days=365 * 3)),
        )
        tenant_id = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO clinics (id, name, slug, is_active, tenant_id) "
            "VALUES (%s, %s, %s, TRUE, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (tenant_id, name, name, tenant_id),
        )
        conn.commit()

    yield tenant_id

    with db_cursor() as (conn, cur):
        cur.execute("SET LOCAL session_replication_role = 'replica'")
        cur.execute(
            "DELETE FROM pharmacovigilance_notifications WHERE adverse_event_id IN ("
            " SELECT id FROM adverse_events WHERE tenant_id = %s)", (tenant_id,))
        cur.execute("DELETE FROM adverse_events WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM sanitary_risks WHERE tenant_id = %s", (tenant_id,))
        cur.execute(
            "DELETE FROM capa_actions WHERE deviation_id IN ("
            "  SELECT id FROM sop_deviations WHERE tenant_id = %s)", (tenant_id,))
        cur.execute("DELETE FROM sop_deviations WHERE tenant_id = %s", (tenant_id,))
        cur.execute(
            "DELETE FROM sop_versions WHERE sop_id IN ("
            "  SELECT id FROM sops WHERE tenant_id = %s)", (tenant_id,))
        cur.execute("UPDATE sops SET current_version_id = NULL "
                    "WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM sops WHERE tenant_id = %s", (tenant_id,))
        cur.execute(
            "DELETE FROM anchor_event_mappings WHERE anchor_id IN ("
            "  SELECT id FROM blockchain_anchors WHERE tenant_id = %s)",
            (tenant_id,))
        cur.execute("DELETE FROM blockchain_anchors WHERE tenant_id = %s",
                    (tenant_id,))
        cur.execute(
            "DELETE FROM sandbox_indicator_values WHERE indicator_id IN ("
            "  SELECT si.id FROM sandbox_indicators si JOIN sandbox_projects sp"
            "    ON sp.id = si.project_id WHERE sp.tenant_id = %s)", (tenant_id,))
        cur.execute(
            "DELETE FROM sandbox_indicators WHERE project_id IN ("
            "  SELECT id FROM sandbox_projects WHERE tenant_id = %s)", (tenant_id,))
        cur.execute("DELETE FROM sandbox_projects WHERE tenant_id = %s",
                    (tenant_id,))
        cur.execute("DELETE FROM traceability_events WHERE tenant_id = %s",
                    (tenant_id,))
        cur.execute(
            "DELETE FROM member_consents WHERE member_id IN ("
            "  SELECT id FROM association_members WHERE tenant_id = %s)",
            (tenant_id,))
        cur.execute("DELETE FROM association_members WHERE tenant_id = %s",
                    (tenant_id,))
        cur.execute(
            "DELETE FROM technical_responsibles WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM institutional_documents WHERE tenant_id = %s",
                    (tenant_id,))
        cur.execute("DELETE FROM clinics WHERE id = %s OR tenant_id = %s",
                    (tenant_id, tenant_id))
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        conn.commit()


# ===========================================================================
# Governance
# ===========================================================================


class TestGovernanceSummary:
    def test_empty_tenant_has_partial_score(self, tenant_with_clinic: int) -> None:
        # Tenant com cnpj+incorporation_date preenchidos mas sem RT e estatuto
        result = governance_summary(tenant_with_clinic)
        # Score deve ser entre 0 e 100
        assert 0 <= result["score"] <= 100
        # 4 checks esperados
        assert len(result["checks"]) == 4

    def test_tenant_with_rt_and_statute_has_high_score(
        self, tenant_with_clinic: int
    ) -> None:
        import uuid as _uuid
        rt_council_number = _uuid.uuid4().hex[:8].upper()
        # Adiciona RT ativo + estatuto. council_number aleatorio para
        # nao colidir com seed_scc.py (que reserva CRM 12345/SP).
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO technical_responsibles
                  (tenant_id, full_name, professional_council, council_number,
                   council_state, habilitation_valid_until, is_active)
                VALUES (%s, 'Dr RT Teste', 'CRM', %s, 'SP',
                        CURRENT_DATE + INTERVAL '1 year', TRUE)
                """,
                (tenant_with_clinic, rt_council_number),
            )
            cur.execute(
                """
                INSERT INTO institutional_documents
                  (tenant_id, document_type, title, version, file_uri,
                   file_hash, valid_from, is_active)
                VALUES (%s, 'statute', 'Estatuto Social', 'v1', 'file://x',
                        %s, CURRENT_DATE - INTERVAL '100 days', TRUE)
                """,
                (tenant_with_clinic, "a" * 64),
            )
            conn.commit()

        result = governance_summary(tenant_with_clinic)
        # Todos os 4 checks passam
        assert result["score"] == 100


# ===========================================================================
# Members
# ===========================================================================


class TestMembersSummary:
    def test_no_members_returns_warning_but_valid_score(
        self, tenant_with_clinic: int
    ) -> None:
        result = members_summary(tenant_with_clinic)
        assert len(result["checks"]) == 3
        # Sem membros: check #1 (associados ativos) = warning;
        # checks #2 e #3 pulam via "active_members == 0 or ..." -> ok.
        # Score = 2/3 = ~67%.
        assert result["checks"][0]["status"] == "warning"
        assert result["checks"][1]["status"] == "ok"
        assert result["checks"][2]["status"] == "ok"
        assert result["score"] == 67

    def test_with_active_members_no_rx_reports_correctly(
        self, tenant_with_clinic: int
    ) -> None:
        # Cria 1 membro ativo sem prescription_on_file
        with db_cursor() as (conn, cur):
            cur.execute(
                "INSERT INTO patients (clinic_id, name, phone, status) "
                "VALUES (%s, 'P1', '5511', 'em_tratamento') RETURNING id",
                (tenant_with_clinic,),
            )
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                "INSERT INTO patients (clinic_id, name, phone, status) "
                "VALUES (%s, 'P2', '5511', 'em_tratamento') RETURNING id",
                (tenant_with_clinic,),
            )
            patient_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO association_members
                  (tenant_id, patient_id, membership_number, membership_status,
                   joined_at)
                VALUES (%s, %s, %s, 'active', CURRENT_DATE)
                """,
                (tenant_with_clinic, patient_id, f"M-{uuid.uuid4().hex[:6]}"),
            )
            conn.commit()

        result = members_summary(tenant_with_clinic)
        # 1 ativo mas sem rx valido nem consent — primeiro check ok,
        # segundo e terceiro warning
        checks_by_status = [c["status"] for c in result["checks"]]
        assert "ok" in checks_by_status  # pelo menos 1 ativo
        assert "warning" in checks_by_status


# ===========================================================================
# Quality (SOPs)
# ===========================================================================


class TestQualitySummary:
    def test_no_sops_returns_fail(self, tenant_with_clinic: int) -> None:
        result = quality_summary(tenant_with_clinic)
        assert len(result["checks"]) == 3
        # Sem SOPs: primeiro check fail, segundo ok (zero-of-zero), terceiro ok
        first_check = result["checks"][0]
        assert first_check["status"] == "fail"

    def test_with_5_sops_reaches_ok_threshold(
        self, tenant_with_clinic: int
    ) -> None:
        # Seed 10 SOPs via funcao da migration 037
        with db_cursor() as (conn, cur):
            cur.execute("SELECT * FROM seed_sandbox_defaults(%s)",
                        (tenant_with_clinic,))
            cur.fetchall()
            conn.commit()

        result = quality_summary(tenant_with_clinic)
        first_check = result["checks"][0]
        assert first_check["status"] == "ok"  # >= 5 SOPs
        assert "10" in first_check["detail"]


# ===========================================================================
# Traceability
# ===========================================================================


class TestTraceabilitySummary:
    def test_no_events_returns_warnings(self, tenant_with_clinic: int) -> None:
        result = traceability_summary(tenant_with_clinic)
        assert len(result["checks"]) == 3
        # Nenhum evento: todos warning/fail
        assert result["score"] < 100

    def test_recent_event_produces_fresh_ok(
        self, tenant_with_clinic: int
    ) -> None:
        # Insere 1 evento recente bypassando trigger pra simplificar
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO traceability_events
                  (tenant_id, event_type, subject_type, subject_id, payload,
                   chain_id, chain_sequence, event_hash, occurred_at)
                VALUES (%s, 'planting', 'plant', 1, '{}'::jsonb,
                        'chain-A', 1, %s, NOW())
                """,
                (tenant_with_clinic, "a" * 64),
            )
            conn.commit()

        result = traceability_summary(tenant_with_clinic)
        # total_events=1, chains=1, freshness ok
        assert result["score"] == 100


# ===========================================================================
# Pharmacovigilance
# ===========================================================================


class TestPharmacovigilanceSummary:
    def test_no_events_no_risks_is_not_100(self, tenant_with_clinic: int) -> None:
        result = pharmacovigilance_summary(tenant_with_clinic)
        assert len(result["checks"]) == 3
        # Sem riscos cadastrados -> 3o check fail
        assert result["score"] < 100

    def test_severe_event_without_notification_is_fail(
        self, tenant_with_clinic: int
    ) -> None:
        # Cria paciente + membro + AE severe sem notification
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                "INSERT INTO patients (clinic_id, name, phone) "
                "VALUES (%s, 'Pac AE', '5511') RETURNING id",
                (tenant_with_clinic,),
            )
            patient_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO association_members
                  (tenant_id, patient_id, membership_number,
                   membership_status, joined_at)
                VALUES (%s, %s, %s, 'active', CURRENT_DATE) RETURNING id
                """,
                (tenant_with_clinic, patient_id, f"M-{uuid.uuid4().hex[:6]}"),
            )
            member_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO adverse_events
                  (tenant_id, member_id, reported_at, severity,
                   description, reported_via)
                VALUES (%s, %s, NOW(), 'severe',
                        'Teste de evento grave sem notificacao',
                        'whatsapp')
                """,
                (tenant_with_clinic, member_id),
            )
            conn.commit()

        result = pharmacovigilance_summary(tenant_with_clinic)
        # Check de notificacao obrigatoria deve ser fail (1 grave, 0 notificado)
        notif_check = next(
            c for c in result["checks"]
            if "Notificacao obrigatoria" in c["name"]
        )
        assert notif_check["status"] == "fail"


# ===========================================================================
# Regulatory
# ===========================================================================


class TestRegulatorySummary:
    def test_no_projects_returns_warnings(self, tenant_with_clinic: int) -> None:
        result = regulatory_summary(tenant_with_clinic)
        assert len(result["checks"]) == 3
        assert result["score"] < 100


# ===========================================================================
# Crypto
# ===========================================================================


class TestCryptoSummary:
    def test_no_anchors_returns_warnings(self, tenant_with_clinic: int) -> None:
        result = crypto_summary(tenant_with_clinic)
        assert len(result["checks"]) == 3
        # Sem anchors: 1st warning, 2nd ok (0 stuck), 3rd fail
        assert result["score"] < 100

    def test_fresh_confirmed_anchor_is_100(
        self, tenant_with_clinic: int
    ) -> None:
        with db_cursor() as (conn, cur):
            now = datetime.now(timezone.utc)
            cur.execute(
                """
                INSERT INTO blockchain_anchors
                  (tenant_id, anchor_scope, covered_from, covered_until,
                   events_count, merkle_root, blockchain_network,
                   transaction_id, anchored_at, verification_status)
                VALUES (%s, 'tenant', %s, %s,
                        1, %s, 'polygon', 'tx-test', %s, 'confirmed')
                """,
                (tenant_with_clinic, now - timedelta(days=1), now,
                 "c" * 64, now - timedelta(hours=1)),
            )
            conn.commit()

        result = crypto_summary(tenant_with_clinic)
        assert result["score"] == 100


# ===========================================================================
# Registry + overall score
# ===========================================================================


class TestSubmoduleRegistry:
    def test_has_all_7_submodules(self) -> None:
        expected = {
            "governance", "members", "quality", "traceability",
            "pharmacovigilance", "regulatory", "crypto",
        }
        assert set(SUBMODULES.keys()) == expected

    def test_every_summary_returns_score_and_checks(
        self, tenant_with_clinic: int
    ) -> None:
        for name, fn in SUBMODULES.items():
            result = fn(tenant_with_clinic)
            assert isinstance(result.get("score"), int), (
                f"{name} sem score int"
            )
            assert 0 <= result["score"] <= 100
            assert isinstance(result.get("checks"), list)
            assert len(result["checks"]) > 0
