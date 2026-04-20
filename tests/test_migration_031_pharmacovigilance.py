"""
Static validation of migration 031 (Pharmacovigilance Schema — F3.1 do SCC).

Valida por inspecao estatica do SQL que a migration:

1. Cria as 4 tabelas previstas no doc 25 §§8.1-8.3.
2. Respeita ordem de criacao das FKs internas
   (adverse_events → notifications, sanitary_risks → risk_controls).
3. Aplica CHECKs whitelist dos campos enum do doc + CHECKs defensivos extras.
4. Respeita FKs externas para tenants, users, association_members,
   preparations, sops.
5. NAO invade outras fases.
6. Tem down-script reverso paralelo.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_031 = MIGRATIONS_DIR / "031_pharmacovigilance_schema.sql"
MIGRATION_031_DOWN = MIGRATIONS_DIR / "down" / "031_pharmacovigilance_schema_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_031() -> str:
    assert MIGRATION_031.exists()
    content = _read(MIGRATION_031)
    assert content.strip()
    return content


@pytest.fixture(scope="module")
def sql_031_down() -> str:
    assert MIGRATION_031_DOWN.exists()
    return _read(MIGRATION_031_DOWN)


@pytest.fixture(scope="module")
def sql_031_code(sql_031: str) -> str:
    return "\n".join(
        line for line in sql_031.splitlines()
        if not line.lstrip().startswith("--")
    )


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestMigration031Structure:
    def test_has_header(self, sql_031: str) -> None:
        assert "Migration 031" in sql_031
        assert "Pharmacovigilance Schema" in sql_031

    def test_references_backlog_and_doc25(self, sql_031: str) -> None:
        assert "F3.1" in sql_031
        assert "BACKLOG_SCC" in sql_031 or "doc 25" in sql_031 or "25_SCC_DATA_MODEL" in sql_031

    def test_references_doc25_sections(self, sql_031: str) -> None:
        for s in ("§8.1", "§8.2", "§8.3"):
            assert s in sql_031, f"falta {s}"

    def test_no_manual_schema_migrations_insert(self, sql_031: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_031


# ---------------------------------------------------------------------------
# Tabelas criadas
# ---------------------------------------------------------------------------

class TestMigration031Tables:
    @pytest.mark.parametrize(
        "table",
        [
            "adverse_events",
            "pharmacovigilance_notifications",
            "sanitary_risks",
            "risk_controls",
        ],
    )
    def test_creates_table(self, sql_031: str, table: str) -> None:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql_031

    def test_creates_exactly_four_tables(self, sql_031_code: str) -> None:
        assert sql_031_code.count("CREATE TABLE IF NOT EXISTS") == 4
        assert sql_031_code.count("CREATE TABLE ") == sql_031_code.count(
            "CREATE TABLE IF NOT EXISTS"
        )


# ---------------------------------------------------------------------------
# adverse_events (doc 25 §8.1)
# ---------------------------------------------------------------------------

class TestAdverseEvents:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "tenant_id           INT NOT NULL REFERENCES tenants(id)",
            "member_id           INT REFERENCES association_members(id)",
            "preparation_id      INT REFERENCES preparations(id)",
            "reported_at         TIMESTAMPTZ NOT NULL",
            "event_onset_at      TIMESTAMPTZ",
            "severity            VARCHAR(16) NOT NULL",
            "description         TEXT NOT NULL",
            "reported_via        VARCHAR(32) NOT NULL",
            "ai_triage_result    JSONB",
            "triaged_by          INT REFERENCES users(id)",
            "clinical_assessment TEXT",
            "outcome             VARCHAR(32)",
        ],
    )
    def test_has_column(self, sql_031: str, column_decl: str) -> None:
        assert column_decl in sql_031

    def test_severity_whitelist(self, sql_031: str) -> None:
        assert "CONSTRAINT chk_ae_severity CHECK" in sql_031
        for sev in ("'mild'", "'moderate'", "'severe'", "'life_threatening'", "'fatal'"):
            assert sev in sql_031

    def test_reported_via_whitelist(self, sql_031: str) -> None:
        assert "CONSTRAINT chk_ae_reported_via CHECK" in sql_031
        for via in ("'whatsapp'", "'web'", "'consultation'", "'phone'", "'other'"):
            assert via in sql_031

    def test_outcome_whitelist_allows_null(self, sql_031: str) -> None:
        assert "CONSTRAINT chk_ae_outcome CHECK" in sql_031
        assert "outcome IS NULL" in sql_031
        for out in ("'resolved'", "'resolving'", "'ongoing'", "'worsened'", "'unknown'"):
            assert out in sql_031

    def test_onset_before_reported_check(self, sql_031: str) -> None:
        # Defensivo alem do doc: onset <= reported.
        assert "CONSTRAINT chk_ae_onset_order CHECK" in sql_031
        assert "event_onset_at IS NULL OR event_onset_at <= reported_at" in sql_031

    def test_indexes(self, sql_031: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_ae_tenant" in sql_031
        assert "CREATE INDEX IF NOT EXISTS idx_ae_member" in sql_031
        assert "CREATE INDEX IF NOT EXISTS idx_ae_severity" in sql_031


# ---------------------------------------------------------------------------
# pharmacovigilance_notifications (doc 25 §8.2)
# ---------------------------------------------------------------------------

class TestPharmacovigilanceNotifications:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "adverse_event_id       INT NOT NULL REFERENCES adverse_events(id)",
            "notification_target    VARCHAR(32) NOT NULL",
            "notified_at            TIMESTAMPTZ NOT NULL",
            "notification_reference VARCHAR(255)",
            "response_received_at   TIMESTAMPTZ",
            "response_payload       JSONB",
        ],
    )
    def test_has_column(self, sql_031: str, column_decl: str) -> None:
        assert column_decl in sql_031

    def test_target_whitelist(self, sql_031: str) -> None:
        assert "CONSTRAINT chk_pv_notif_target CHECK" in sql_031
        for t in ("'vigimed'", "'notivisa'", "'internal_only'"):
            assert t in sql_031

    def test_response_order_check(self, sql_031: str) -> None:
        assert "CONSTRAINT chk_pv_notif_response_order CHECK" in sql_031
        assert "response_received_at IS NULL OR response_received_at >= notified_at" in sql_031

    def test_index(self, sql_031: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_pv_notif_ae" in sql_031


# ---------------------------------------------------------------------------
# sanitary_risks (doc 25 §8.3)
# ---------------------------------------------------------------------------

class TestSanitaryRisks:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "tenant_id   INT NOT NULL REFERENCES tenants(id)",
            "risk_code   VARCHAR(64) NOT NULL",
            "category    VARCHAR(64) NOT NULL",
            "description TEXT NOT NULL",
            "probability VARCHAR(16) NOT NULL",
            "impact      VARCHAR(16) NOT NULL",
            "risk_level  VARCHAR(16) NOT NULL",
            "is_active   BOOLEAN NOT NULL DEFAULT TRUE",
        ],
    )
    def test_has_column(self, sql_031: str, column_decl: str) -> None:
        assert column_decl in sql_031

    def test_unique_tenant_code(self, sql_031: str) -> None:
        assert (
            "CONSTRAINT uq_sanitary_risks_tenant_code UNIQUE (tenant_id, risk_code)"
            in sql_031
        )

    def test_probability_whitelist(self, sql_031: str) -> None:
        assert "CONSTRAINT chk_sanitary_risks_probability CHECK" in sql_031

    def test_impact_whitelist(self, sql_031: str) -> None:
        assert "CONSTRAINT chk_sanitary_risks_impact CHECK" in sql_031

    def test_risk_level_whitelist(self, sql_031: str) -> None:
        assert "CONSTRAINT chk_sanitary_risks_level CHECK" in sql_031
        for lvl in ("'low'", "'medium'", "'high'", "'critical'"):
            assert lvl in sql_031

    def test_probability_impact_share_5_levels(self, sql_031: str) -> None:
        # probability e impact usam mesma escala de 5 niveis.
        for lvl in ("'very_low'", "'high'", "'very_high'"):
            assert lvl in sql_031


# ---------------------------------------------------------------------------
# risk_controls (doc 25 §8.3)
# ---------------------------------------------------------------------------

class TestRiskControls:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "risk_id             INT NOT NULL REFERENCES sanitary_risks(id)",
            "control_description TEXT NOT NULL",
            "control_type        VARCHAR(32) NOT NULL",
            "responsible         INT REFERENCES users(id)",
            "related_sop_id      INT REFERENCES sops(id)",
            "last_verified_at    TIMESTAMPTZ",
            "verification_status VARCHAR(32)",
        ],
    )
    def test_has_column(self, sql_031: str, column_decl: str) -> None:
        assert column_decl in sql_031

    def test_control_type_whitelist(self, sql_031: str) -> None:
        assert "CONSTRAINT chk_risk_controls_type CHECK" in sql_031
        for ct in ("'preventive'", "'detective'", "'corrective'", "'compensating'"):
            assert ct in sql_031

    def test_verification_status_whitelist_allows_null(self, sql_031: str) -> None:
        assert "CONSTRAINT chk_risk_controls_verification CHECK" in sql_031
        assert "verification_status IS NULL" in sql_031
        for vs in ("'effective'", "'partial'", "'ineffective'", "'pending'"):
            assert vs in sql_031

    def test_indexes(self, sql_031: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_risk_controls_risk" in sql_031
        assert "CREATE INDEX IF NOT EXISTS idx_risk_controls_sop" in sql_031


# ---------------------------------------------------------------------------
# Ordem de criacao
# ---------------------------------------------------------------------------

class TestMigration031CreationOrder:
    def test_adverse_events_before_notifications(self, sql_031: str) -> None:
        pos_ae = sql_031.find("CREATE TABLE IF NOT EXISTS adverse_events")
        pos_pv = sql_031.find("CREATE TABLE IF NOT EXISTS pharmacovigilance_notifications")
        assert 0 < pos_ae < pos_pv

    def test_sanitary_risks_before_controls(self, sql_031: str) -> None:
        pos_sr = sql_031.find("CREATE TABLE IF NOT EXISTS sanitary_risks")
        pos_rc = sql_031.find("CREATE TABLE IF NOT EXISTS risk_controls")
        assert 0 < pos_sr < pos_rc


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

class TestMigration031Idempotency:
    def test_create_table_if_not_exists(self, sql_031_code: str) -> None:
        assert sql_031_code.count("CREATE TABLE") == sql_031_code.count(
            "CREATE TABLE IF NOT EXISTS"
        )

    def test_create_index_if_not_exists(self, sql_031_code: str) -> None:
        assert sql_031_code.count("CREATE INDEX") == sql_031_code.count(
            "CREATE INDEX IF NOT EXISTS"
        )


# ---------------------------------------------------------------------------
# Escopo
# ---------------------------------------------------------------------------

class TestMigration031Scope:
    @pytest.mark.parametrize(
        "out_of_scope_table",
        [
            # ja existem em migrations anteriores
            "tenants", "users", "association_members", "preparations",
            "sops", "traceability_events",
            # futuras (fase 3+)
            "sandbox_projects", "regulatory_submissions",
            "blockchain_anchors",
        ],
    )
    def test_does_not_recreate_out_of_scope(self, sql_031: str, out_of_scope_table: str) -> None:
        assert f"CREATE TABLE {out_of_scope_table}" not in sql_031
        assert f"CREATE TABLE IF NOT EXISTS {out_of_scope_table}" not in sql_031

    def test_does_not_create_triggers(self, sql_031_code: str) -> None:
        # Pharmacovigilance nao usa append-only/chain nesta migration.
        assert "CREATE TRIGGER" not in sql_031_code


# ---------------------------------------------------------------------------
# Down script
# ---------------------------------------------------------------------------

class TestMigration031Down:
    def test_has_header(self, sql_031_down: str) -> None:
        assert "Down migration 031" in sql_031_down

    @pytest.mark.parametrize(
        "table",
        [
            "risk_controls",
            "pharmacovigilance_notifications",
            "sanitary_risks",
            "adverse_events",
        ],
    )
    def test_drops_every_table(self, sql_031_down: str, table: str) -> None:
        assert f"DROP TABLE IF EXISTS {table}" in sql_031_down

    def test_reverse_order_controls_before_risks(self, sql_031_down: str) -> None:
        pos_rc = sql_031_down.find("DROP TABLE IF EXISTS risk_controls")
        pos_sr = sql_031_down.find("DROP TABLE IF EXISTS sanitary_risks")
        assert 0 < pos_rc < pos_sr

    def test_reverse_order_notifications_before_ae(self, sql_031_down: str) -> None:
        pos_pv = sql_031_down.find("DROP TABLE IF EXISTS pharmacovigilance_notifications")
        pos_ae = sql_031_down.find("DROP TABLE IF EXISTS adverse_events")
        assert 0 < pos_pv < pos_ae

    def test_all_drops_use_if_exists(self, sql_031_down: str) -> None:
        code = "\n".join(
            line for line in sql_031_down.splitlines()
            if not line.lstrip().startswith("--")
        )
        assert code.count("DROP TABLE") == code.count("DROP TABLE IF EXISTS")

    def test_does_not_touch_preexisting(self, sql_031_down: str) -> None:
        for preexisting in (
            "tenants", "users", "association_members", "preparations",
            "sops", "traceability_events",
        ):
            assert f"DROP TABLE IF EXISTS {preexisting}" not in sql_031_down
            assert f"DROP TABLE {preexisting}" not in sql_031_down
