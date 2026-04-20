"""
Static validation of migration 032 (Regulatory Schema — F3.2 do SCC).

Valida por inspecao estatica do SQL que a migration:

1. Cria as 6 tabelas previstas no doc 25 §§9.1-9.3.
2. Respeita ordem de criacao das FKs internas
   (sandbox_projects → protocols/indicators/submissions/reports,
    sandbox_indicators → indicator_values).
3. Aplica CHECKs whitelist dos campos enum do doc + CHECKs defensivos
   extras de ordem temporal.
4. Respeita FKs externas para tenants (024) e users (foundation).
5. NAO invade outras fases.
6. Tem down-script reverso paralelo.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_032 = MIGRATIONS_DIR / "032_regulatory_schema.sql"
MIGRATION_032_DOWN = MIGRATIONS_DIR / "down" / "032_regulatory_schema_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_032() -> str:
    assert MIGRATION_032.exists()
    content = _read(MIGRATION_032)
    assert content.strip()
    return content


@pytest.fixture(scope="module")
def sql_032_down() -> str:
    assert MIGRATION_032_DOWN.exists()
    return _read(MIGRATION_032_DOWN)


@pytest.fixture(scope="module")
def sql_032_code(sql_032: str) -> str:
    return "\n".join(
        line for line in sql_032.splitlines()
        if not line.lstrip().startswith("--")
    )


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestMigration032Structure:
    def test_has_header(self, sql_032: str) -> None:
        assert "Migration 032" in sql_032
        assert "Regulatory Schema" in sql_032

    def test_references_backlog_and_doc25(self, sql_032: str) -> None:
        assert "F3.2" in sql_032
        assert "BACKLOG_SCC" in sql_032 or "doc 25" in sql_032 or "25_SCC_DATA_MODEL" in sql_032

    def test_references_doc25_sections(self, sql_032: str) -> None:
        for s in ("§9.1", "§9.2", "§9.3"):
            assert s in sql_032, f"falta {s}"

    def test_no_manual_schema_migrations_insert(self, sql_032: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_032


# ---------------------------------------------------------------------------
# Tabelas criadas
# ---------------------------------------------------------------------------

class TestMigration032Tables:
    @pytest.mark.parametrize(
        "table",
        [
            "sandbox_projects",
            "sandbox_protocols",
            "sandbox_indicators",
            "sandbox_indicator_values",
            "regulatory_submissions",
            "regulatory_reports",
        ],
    )
    def test_creates_table(self, sql_032: str, table: str) -> None:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql_032

    def test_creates_exactly_six_tables(self, sql_032_code: str) -> None:
        assert sql_032_code.count("CREATE TABLE IF NOT EXISTS") == 6
        assert sql_032_code.count("CREATE TABLE ") == sql_032_code.count(
            "CREATE TABLE IF NOT EXISTS"
        )


# ---------------------------------------------------------------------------
# sandbox_projects (doc 25 §9.1)
# ---------------------------------------------------------------------------

class TestSandboxProjects:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "tenant_id        INT NOT NULL REFERENCES tenants(id)",
            "project_code     VARCHAR(64) NOT NULL",
            "title            VARCHAR(255) NOT NULL",
            "status           VARCHAR(32) NOT NULL",
            "submitted_at     TIMESTAMPTZ",
            "approved_at      TIMESTAMPTZ",
            "started_at       TIMESTAMPTZ",
            "concluded_at     TIMESTAMPTZ",
            "anvisa_reference VARCHAR(128)",
        ],
    )
    def test_has_column(self, sql_032: str, column_decl: str) -> None:
        assert column_decl in sql_032

    def test_unique_tenant_project_code(self, sql_032: str) -> None:
        assert (
            "CONSTRAINT uq_sandbox_projects_tenant_code UNIQUE (tenant_id, project_code)"
            in sql_032
        )

    def test_status_whitelist(self, sql_032: str) -> None:
        assert "CONSTRAINT chk_sandbox_projects_status CHECK" in sql_032
        for st in (
            "'draft'", "'submitted'", "'under_review'", "'approved'",
            "'active'", "'suspended'", "'concluded'", "'discontinued'",
        ):
            assert st in sql_032

    def test_temporal_order_checks(self, sql_032: str) -> None:
        # Defensivos: approved >= submitted, started >= approved, concluded >= started.
        assert "CONSTRAINT chk_sandbox_projects_approved_order CHECK" in sql_032
        assert "approved_at >= submitted_at" in sql_032
        assert "CONSTRAINT chk_sandbox_projects_started_order CHECK" in sql_032
        assert "started_at >= approved_at" in sql_032
        assert "CONSTRAINT chk_sandbox_projects_concluded_order CHECK" in sql_032
        assert "concluded_at >= started_at" in sql_032

    def test_indexes(self, sql_032: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_sandbox_projects_tenant" in sql_032
        assert "CREATE INDEX IF NOT EXISTS idx_sandbox_projects_status" in sql_032


# ---------------------------------------------------------------------------
# sandbox_protocols (doc 25 §9.1)
# ---------------------------------------------------------------------------

class TestSandboxProtocols:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "project_id               INT NOT NULL REFERENCES sandbox_projects(id)",
            "protocol_version         VARCHAR(32) NOT NULL",
            "scope                    JSONB NOT NULL",
            "applicable_norms         JSONB NOT NULL",
            "modulated_norms          JSONB NOT NULL DEFAULT '{}'::jsonb",
            "monitoring_parameters    JSONB NOT NULL",
            "discontinuity_plan       JSONB NOT NULL",
            "quality_requirements     JSONB NOT NULL",
            "data_sharing_obligations JSONB NOT NULL",
            "effective_from           TIMESTAMPTZ",
            "effective_until          TIMESTAMPTZ",
        ],
    )
    def test_has_column(self, sql_032: str, column_decl: str) -> None:
        assert column_decl in sql_032

    def test_unique_version(self, sql_032: str) -> None:
        assert (
            "CONSTRAINT uq_sandbox_protocols_version UNIQUE (project_id, protocol_version)"
            in sql_032
        )

    def test_effective_order_check(self, sql_032: str) -> None:
        assert "CONSTRAINT chk_sandbox_protocols_effective_order CHECK" in sql_032
        assert "effective_until >= effective_from" in sql_032

    def test_index(self, sql_032: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_sandbox_protocols_project" in sql_032


# ---------------------------------------------------------------------------
# sandbox_indicators (doc 25 §9.2)
# ---------------------------------------------------------------------------

class TestSandboxIndicators:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "project_id          INT NOT NULL REFERENCES sandbox_projects(id)",
            "indicator_code      VARCHAR(64) NOT NULL",
            "indicator_name      VARCHAR(255) NOT NULL",
            "calculation_formula TEXT NOT NULL",
            "unit                VARCHAR(32)",
            "target_value        NUMERIC(18,4)",
            "reporting_frequency VARCHAR(32) NOT NULL",
            "is_mandatory        BOOLEAN NOT NULL DEFAULT TRUE",
        ],
    )
    def test_has_column(self, sql_032: str, column_decl: str) -> None:
        assert column_decl in sql_032

    def test_unique_indicator_code(self, sql_032: str) -> None:
        assert (
            "CONSTRAINT uq_sandbox_indicators_code UNIQUE (project_id, indicator_code)"
            in sql_032
        )

    def test_frequency_whitelist(self, sql_032: str) -> None:
        assert "CONSTRAINT chk_sandbox_indicators_frequency CHECK" in sql_032
        for freq in ("'daily'", "'weekly'", "'monthly'", "'quarterly'", "'annual'"):
            assert freq in sql_032

    def test_index(self, sql_032: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_sandbox_indicators_project" in sql_032


# ---------------------------------------------------------------------------
# sandbox_indicator_values (doc 25 §9.2)
# ---------------------------------------------------------------------------

class TestSandboxIndicatorValues:
    def test_uses_bigserial(self, sql_032: str) -> None:
        # Alta frequencia — projetos de longa duracao com indicadores diarios.
        assert "id                  BIGSERIAL PRIMARY KEY" in sql_032

    @pytest.mark.parametrize(
        "column_decl",
        [
            "indicator_id        INT NOT NULL REFERENCES sandbox_indicators(id)",
            "period_start        TIMESTAMPTZ NOT NULL",
            "period_end          TIMESTAMPTZ NOT NULL",
            "calculated_value    NUMERIC(18,4) NOT NULL",
            "calculation_details JSONB",
        ],
    )
    def test_has_column(self, sql_032: str, column_decl: str) -> None:
        assert column_decl in sql_032

    def test_period_order_check(self, sql_032: str) -> None:
        assert "CONSTRAINT chk_siv_period_order CHECK" in sql_032
        assert "period_end >= period_start" in sql_032

    def test_indexes(self, sql_032: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_siv_indicator" in sql_032
        assert "CREATE INDEX IF NOT EXISTS idx_siv_period" in sql_032


# ---------------------------------------------------------------------------
# regulatory_submissions (doc 25 §9.3)
# ---------------------------------------------------------------------------

class TestRegulatorySubmissions:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "tenant_id           INT NOT NULL REFERENCES tenants(id)",
            "project_id          INT REFERENCES sandbox_projects(id)",
            "submission_type     VARCHAR(64) NOT NULL",
            "submitted_at        TIMESTAMPTZ NOT NULL",
            "submitted_by        INT REFERENCES users(id)",
            "payload_uri         TEXT NOT NULL",
            "payload_hash        CHAR(64) NOT NULL",
            "anvisa_response_uri TEXT",
            "anvisa_response_at  TIMESTAMPTZ",
        ],
    )
    def test_has_column(self, sql_032: str, column_decl: str) -> None:
        assert column_decl in sql_032

    def test_response_order_check(self, sql_032: str) -> None:
        assert "CONSTRAINT chk_reg_submissions_response_order CHECK" in sql_032
        assert "anvisa_response_at >= submitted_at" in sql_032

    def test_indexes(self, sql_032: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_reg_submissions_tenant" in sql_032
        assert "CREATE INDEX IF NOT EXISTS idx_reg_submissions_project" in sql_032


# ---------------------------------------------------------------------------
# regulatory_reports (doc 25 §9.3)
# ---------------------------------------------------------------------------

class TestRegulatoryReports:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "tenant_id    INT NOT NULL REFERENCES tenants(id)",
            "project_id   INT REFERENCES sandbox_projects(id)",
            "report_type  VARCHAR(64) NOT NULL",
            "version      VARCHAR(32) NOT NULL",
            "content_uri  TEXT NOT NULL",
            "content_hash CHAR(64) NOT NULL",
            "approved_by  INT REFERENCES users(id)",
            "approved_at  TIMESTAMPTZ",
        ],
    )
    def test_has_column(self, sql_032: str, column_decl: str) -> None:
        assert column_decl in sql_032

    def test_report_type_whitelist(self, sql_032: str) -> None:
        assert "CONSTRAINT chk_reg_reports_type CHECK" in sql_032
        for rt in (
            "'work_plan'",
            "'communication_plan'",
            "'discontinuity_plan'",
            "'monitoring_plan'",
            "'risk_management_plan'",
            "'final_monitoring_opinion'",
            "'eligibility_dossier'",
        ):
            assert rt in sql_032

    def test_approval_order_check(self, sql_032: str) -> None:
        assert "CONSTRAINT chk_reg_reports_approval_order CHECK" in sql_032
        assert "approved_at >= generated_at" in sql_032

    def test_indexes(self, sql_032: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_reg_reports_tenant" in sql_032
        assert "CREATE INDEX IF NOT EXISTS idx_reg_reports_type" in sql_032


# ---------------------------------------------------------------------------
# Ordem de criacao (FKs)
# ---------------------------------------------------------------------------

class TestMigration032CreationOrder:
    def test_projects_before_protocols(self, sql_032: str) -> None:
        pos_p = sql_032.find("CREATE TABLE IF NOT EXISTS sandbox_projects")
        pos_pr = sql_032.find("CREATE TABLE IF NOT EXISTS sandbox_protocols")
        assert 0 < pos_p < pos_pr

    def test_projects_before_indicators(self, sql_032: str) -> None:
        pos_p = sql_032.find("CREATE TABLE IF NOT EXISTS sandbox_projects")
        pos_i = sql_032.find("CREATE TABLE IF NOT EXISTS sandbox_indicators")
        assert 0 < pos_p < pos_i

    def test_indicators_before_values(self, sql_032: str) -> None:
        pos_i = sql_032.find("CREATE TABLE IF NOT EXISTS sandbox_indicators")
        pos_iv = sql_032.find("CREATE TABLE IF NOT EXISTS sandbox_indicator_values")
        assert 0 < pos_i < pos_iv

    def test_projects_before_submissions(self, sql_032: str) -> None:
        pos_p = sql_032.find("CREATE TABLE IF NOT EXISTS sandbox_projects")
        pos_s = sql_032.find("CREATE TABLE IF NOT EXISTS regulatory_submissions")
        assert 0 < pos_p < pos_s

    def test_projects_before_reports(self, sql_032: str) -> None:
        pos_p = sql_032.find("CREATE TABLE IF NOT EXISTS sandbox_projects")
        pos_r = sql_032.find("CREATE TABLE IF NOT EXISTS regulatory_reports")
        assert 0 < pos_p < pos_r


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

class TestMigration032Idempotency:
    def test_create_table_if_not_exists(self, sql_032_code: str) -> None:
        assert sql_032_code.count("CREATE TABLE") == sql_032_code.count(
            "CREATE TABLE IF NOT EXISTS"
        )

    def test_create_index_if_not_exists(self, sql_032_code: str) -> None:
        assert sql_032_code.count("CREATE INDEX") == sql_032_code.count(
            "CREATE INDEX IF NOT EXISTS"
        )


# ---------------------------------------------------------------------------
# Escopo
# ---------------------------------------------------------------------------

class TestMigration032Scope:
    @pytest.mark.parametrize(
        "out_of_scope_table",
        [
            # ja existem em migrations anteriores
            "tenants", "users", "association_members", "preparations",
            "sops", "traceability_events",
            "adverse_events", "pharmacovigilance_notifications",
            "sanitary_risks", "risk_controls",
            # futuras (fase 4+)
            "blockchain_anchors",
        ],
    )
    def test_does_not_recreate_out_of_scope(self, sql_032: str, out_of_scope_table: str) -> None:
        assert f"CREATE TABLE {out_of_scope_table}" not in sql_032
        assert f"CREATE TABLE IF NOT EXISTS {out_of_scope_table}" not in sql_032

    def test_does_not_create_triggers(self, sql_032_code: str) -> None:
        # Regulatory e dominio mutavel — status/effective transitam.
        assert "CREATE TRIGGER" not in sql_032_code


# ---------------------------------------------------------------------------
# Down script
# ---------------------------------------------------------------------------

class TestMigration032Down:
    def test_has_header(self, sql_032_down: str) -> None:
        assert "Down migration 032" in sql_032_down

    @pytest.mark.parametrize(
        "table",
        [
            "regulatory_reports",
            "regulatory_submissions",
            "sandbox_indicator_values",
            "sandbox_indicators",
            "sandbox_protocols",
            "sandbox_projects",
        ],
    )
    def test_drops_every_table(self, sql_032_down: str, table: str) -> None:
        assert f"DROP TABLE IF EXISTS {table}" in sql_032_down

    def test_reverse_order_reports_before_projects(self, sql_032_down: str) -> None:
        pos_r = sql_032_down.find("DROP TABLE IF EXISTS regulatory_reports")
        pos_p = sql_032_down.find("DROP TABLE IF EXISTS sandbox_projects")
        assert 0 < pos_r < pos_p

    def test_reverse_order_values_before_indicators(self, sql_032_down: str) -> None:
        pos_v = sql_032_down.find("DROP TABLE IF EXISTS sandbox_indicator_values")
        pos_i = sql_032_down.find("DROP TABLE IF EXISTS sandbox_indicators")
        assert 0 < pos_v < pos_i

    def test_reverse_order_submissions_before_projects(self, sql_032_down: str) -> None:
        pos_s = sql_032_down.find("DROP TABLE IF EXISTS regulatory_submissions")
        pos_p = sql_032_down.find("DROP TABLE IF EXISTS sandbox_projects")
        assert 0 < pos_s < pos_p

    def test_reverse_order_protocols_before_projects(self, sql_032_down: str) -> None:
        pos_pr = sql_032_down.find("DROP TABLE IF EXISTS sandbox_protocols")
        pos_p = sql_032_down.find("DROP TABLE IF EXISTS sandbox_projects")
        assert 0 < pos_pr < pos_p

    def test_all_drops_use_if_exists(self, sql_032_down: str) -> None:
        code = "\n".join(
            line for line in sql_032_down.splitlines()
            if not line.lstrip().startswith("--")
        )
        assert code.count("DROP TABLE") == code.count("DROP TABLE IF EXISTS")

    def test_does_not_touch_preexisting(self, sql_032_down: str) -> None:
        for preexisting in (
            "tenants", "users", "association_members", "preparations",
            "sops", "traceability_events",
            "adverse_events", "pharmacovigilance_notifications",
            "sanitary_risks", "risk_controls",
        ):
            assert f"DROP TABLE IF EXISTS {preexisting}" not in sql_032_down
            assert f"DROP TABLE {preexisting}" not in sql_032_down
