"""Tests do regulatory_reporting_repository (F3.7 do SCC).

Roda contra Postgres real (skip automatico se DB nao alcancavel).
Cobre as queries read-only sobre as 6 tabelas de migration 032 e a
view `v_sandbox_indicator_dashboard` (F6.2). Usa fixture com fluxo
completo: tenant → project → protocol → indicator → values →
submission → report.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest

from src.infra.database import db_cursor
from src.repositories import regulatory_reporting_repository as repo


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


def _hash() -> str:
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()


@pytest.fixture
def fixture_full_setup():
    """
    Cria tenant + projeto + protocolo vigente + 2 indicadores
    (1 mandatorio com valor on_target, 1 mandatorio sem valor) +
    1 submission pendente + 1 submission respondida +
    1 report aprovado + 1 report nao aprovado.

    Retorna dict com os ids relevantes para os testes inspecionarem.
    """
    suffix = uuid.uuid4().hex[:8]
    name = f"reg_test_{suffix}"

    ids: dict[str, int] = {}

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
        ids["tenant_id"] = cur.fetchone()["id"]

        # Projeto active
        cur.execute(
            """
            INSERT INTO sandbox_projects (
              tenant_id, project_code, title, status,
              submitted_at, approved_at, started_at
            )
            VALUES (%s, %s, %s, 'active', NOW() - INTERVAL '30 days',
                    NOW() - INTERVAL '20 days', NOW() - INTERVAL '15 days')
            RETURNING id
            """,
            (ids["tenant_id"], f"PROJ-{suffix}", "Projeto Sandbox Teste"),
        )
        ids["project_id"] = cur.fetchone()["id"]

        # Projeto draft (sera filtrado em alguns testes)
        cur.execute(
            """
            INSERT INTO sandbox_projects (tenant_id, project_code, title, status)
            VALUES (%s, %s, %s, 'draft')
            RETURNING id
            """,
            (ids["tenant_id"], f"PROJ-DRAFT-{suffix}", "Draft"),
        )
        ids["project_draft_id"] = cur.fetchone()["id"]

        # Protocolo vigente (effective_until NULL)
        protocol_jsons = (
            json.dumps({"area": "test"}),  # scope
            json.dumps([]),                 # applicable_norms
            json.dumps({}),                 # modulated_norms
            json.dumps({}),                 # monitoring_parameters
            json.dumps({}),                 # discontinuity_plan
            json.dumps({}),                 # quality_requirements
            json.dumps({}),                 # data_sharing_obligations
        )
        cur.execute(
            """
            INSERT INTO sandbox_protocols (
              project_id, protocol_version,
              scope, applicable_norms, modulated_norms,
              monitoring_parameters, discontinuity_plan,
              quality_requirements, data_sharing_obligations,
              effective_from
            )
            VALUES (%s, 'v1.0', %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb, %s::jsonb,
                    NOW() - INTERVAL '15 days')
            RETURNING id
            """,
            (ids["project_id"], *protocol_jsons),
        )
        ids["protocol_id"] = cur.fetchone()["id"]

        # Protocolo antigo (effective_until preenchido)
        cur.execute(
            """
            INSERT INTO sandbox_protocols (
              project_id, protocol_version,
              scope, applicable_norms, modulated_norms,
              monitoring_parameters, discontinuity_plan,
              quality_requirements, data_sharing_obligations,
              effective_from, effective_until
            )
            VALUES (%s, 'v0.9', %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb, %s::jsonb,
                    NOW() - INTERVAL '40 days', NOW() - INTERVAL '15 days')
            RETURNING id
            """,
            (ids["project_id"], *protocol_jsons),
        )

        # Indicador mandatorio com valor on_target
        cur.execute(
            """
            INSERT INTO sandbox_indicators (
              project_id, indicator_code, indicator_name,
              calculation_formula, unit, target_value,
              reporting_frequency, is_mandatory
            )
            VALUES (%s, %s, %s, 'foo', 'pct', 80.0, 'monthly', TRUE)
            RETURNING id
            """,
            (ids["project_id"], f"IND-{suffix}-1", "Indicador A"),
        )
        ids["ind_with_value"] = cur.fetchone()["id"]

        # Latest = 82 → on_target=True (2.5% off vs target 80, dentro dos 5%
        # de tolerancia da view v_sandbox_indicator_dashboard).
        cur.execute(
            """
            INSERT INTO sandbox_indicator_values (
              indicator_id, period_start, period_end, calculated_value
            )
            VALUES (%s, NOW() - INTERVAL '7 days', NOW(), 82.0),
                   (%s, NOW() - INTERVAL '14 days', NOW() - INTERVAL '7 days', 79.0)
            """,
            (ids["ind_with_value"], ids["ind_with_value"]),
        )

        # Indicador mandatorio sem valor
        cur.execute(
            """
            INSERT INTO sandbox_indicators (
              project_id, indicator_code, indicator_name,
              calculation_formula, unit, target_value,
              reporting_frequency, is_mandatory
            )
            VALUES (%s, %s, %s, 'bar', 'pct', 50.0, 'monthly', TRUE)
            RETURNING id
            """,
            (ids["project_id"], f"IND-{suffix}-2", "Indicador B"),
        )
        ids["ind_without_value"] = cur.fetchone()["id"]

        # Submission pendente
        cur.execute(
            """
            INSERT INTO regulatory_submissions (
              tenant_id, project_id, submission_type,
              submitted_at, payload_uri, payload_hash
            )
            VALUES (%s, %s, 'monthly_report',
                    NOW() - INTERVAL '5 days',
                    %s, %s)
            RETURNING id
            """,
            (ids["tenant_id"], ids["project_id"],
             "/storage/sub.json", _hash()),
        )
        ids["sub_pending"] = cur.fetchone()["id"]

        # Submission respondida
        cur.execute(
            """
            INSERT INTO regulatory_submissions (
              tenant_id, project_id, submission_type,
              submitted_at, payload_uri, payload_hash,
              anvisa_response_uri, anvisa_response_at
            )
            VALUES (%s, %s, 'quarterly_report',
                    NOW() - INTERVAL '20 days',
                    %s, %s,
                    '/storage/resp.json',
                    NOW() - INTERVAL '15 days')
            RETURNING id
            """,
            (ids["tenant_id"], ids["project_id"],
             "/storage/sub2.json", _hash()),
        )
        ids["sub_responded"] = cur.fetchone()["id"]

        # Report aprovado
        cur.execute(
            """
            INSERT INTO regulatory_reports (
              tenant_id, project_id, report_type, version,
              content_uri, content_hash, generated_at, approved_at
            )
            VALUES (%s, %s, 'monitoring_plan', 'v1.0',
                    '/storage/plan.md', %s,
                    NOW() - INTERVAL '10 days',
                    NOW() - INTERVAL '5 days')
            RETURNING id
            """,
            (ids["tenant_id"], ids["project_id"], _hash()),
        )
        ids["report_approved"] = cur.fetchone()["id"]

        # Report nao aprovado
        cur.execute(
            """
            INSERT INTO regulatory_reports (
              tenant_id, project_id, report_type, version,
              content_uri, content_hash, generated_at
            )
            VALUES (%s, %s, 'risk_management_plan', 'v0.1',
                    '/storage/risk.md', %s,
                    NOW() - INTERVAL '2 days')
            RETURNING id
            """,
            (ids["tenant_id"], ids["project_id"], _hash()),
        )
        ids["report_pending"] = cur.fetchone()["id"]

        conn.commit()

    yield ids

    with db_cursor() as (conn, cur):
        tid = ids["tenant_id"]
        cur.execute(
            "DELETE FROM regulatory_reports WHERE tenant_id = %s", (tid,)
        )
        cur.execute(
            "DELETE FROM regulatory_submissions WHERE tenant_id = %s", (tid,)
        )
        cur.execute(
            "DELETE FROM sandbox_indicator_values "
            "WHERE indicator_id IN (SELECT id FROM sandbox_indicators "
            "WHERE project_id IN (SELECT id FROM sandbox_projects "
            "WHERE tenant_id = %s))",
            (tid,),
        )
        cur.execute(
            "DELETE FROM sandbox_indicators "
            "WHERE project_id IN "
            "(SELECT id FROM sandbox_projects WHERE tenant_id = %s)",
            (tid,),
        )
        cur.execute(
            "DELETE FROM sandbox_protocols "
            "WHERE project_id IN "
            "(SELECT id FROM sandbox_projects WHERE tenant_id = %s)",
            (tid,),
        )
        cur.execute(
            "DELETE FROM sandbox_projects WHERE tenant_id = %s", (tid,)
        )
        cur.execute("DELETE FROM tenants WHERE id = %s", (tid,))
        conn.commit()


# =====================================================================
# Projects
# =====================================================================


class TestProjects:
    def test_list_projects_returns_both(self, fixture_full_setup):
        rows = repo.list_projects(fixture_full_setup["tenant_id"])
        assert len(rows) == 2

    def test_list_projects_filtered_by_status(self, fixture_full_setup):
        rows = repo.list_projects(
            fixture_full_setup["tenant_id"], status="active"
        )
        assert len(rows) == 1
        assert rows[0]["id"] == fixture_full_setup["project_id"]

    def test_list_projects_pagination_clamps(self, fixture_full_setup):
        rows = repo.list_projects(
            fixture_full_setup["tenant_id"], limit=1, offset=0
        )
        assert len(rows) == 1

    def test_get_project_roundtrip(self, fixture_full_setup):
        project = repo.get_project(
            fixture_full_setup["project_id"],
            tenant_id=fixture_full_setup["tenant_id"],
        )
        assert project is not None
        assert project["status"] == "active"

    def test_get_project_isolated_by_tenant(self, fixture_full_setup):
        # Tenant 999 nunca veria esse projeto
        assert repo.get_project(
            fixture_full_setup["project_id"], tenant_id=999_999_999
        ) is None

    def test_count_projects_by_status(self, fixture_full_setup):
        counts = repo.count_projects_by_status(
            fixture_full_setup["tenant_id"]
        )
        assert counts.get("active") == 1
        assert counts.get("draft") == 1


# =====================================================================
# Protocols
# =====================================================================


class TestProtocols:
    def test_active_protocol_returns_open_window(self, fixture_full_setup):
        protocol = repo.get_active_protocol(
            fixture_full_setup["project_id"],
            tenant_id=fixture_full_setup["tenant_id"],
        )
        assert protocol is not None
        assert protocol["protocol_version"] == "v1.0"
        assert protocol["effective_until"] is None

    def test_active_protocol_returns_none_for_other_tenant(
        self, fixture_full_setup
    ):
        protocol = repo.get_active_protocol(
            fixture_full_setup["project_id"], tenant_id=999_999_999
        )
        assert protocol is None


# =====================================================================
# Indicators (view)
# =====================================================================


class TestIndicatorDashboard:
    def test_list_returns_both_indicators(self, fixture_full_setup):
        rows = repo.list_indicator_dashboard(
            fixture_full_setup["tenant_id"]
        )
        ids = {r["indicator_id"] for r in rows}
        assert fixture_full_setup["ind_with_value"] in ids
        assert fixture_full_setup["ind_without_value"] in ids

    def test_filter_by_project(self, fixture_full_setup):
        rows = repo.list_indicator_dashboard(
            fixture_full_setup["tenant_id"],
            project_id=fixture_full_setup["project_id"],
        )
        assert len(rows) == 2

    def test_filter_only_off_target(self, fixture_full_setup):
        rows = repo.list_indicator_dashboard(
            fixture_full_setup["tenant_id"], only_off_target=True
        )
        # ind_without_value tem on_target IS NULL ou false dependendo
        # da view; ind_with_value (90 vs target 80) eh on_target=True.
        ids = {r["indicator_id"] for r in rows}
        assert fixture_full_setup["ind_with_value"] not in ids

    def test_get_dashboard_row(self, fixture_full_setup):
        row = repo.get_indicator_dashboard_row(
            fixture_full_setup["ind_with_value"],
            tenant_id=fixture_full_setup["tenant_id"],
        )
        assert row is not None
        assert row["latest_value"] == 82.0
        assert row["n_periods"] == 2
        assert row["on_target"] is True

    def test_history_returns_values_desc(self, fixture_full_setup):
        rows = repo.list_indicator_history(
            fixture_full_setup["ind_with_value"],
            tenant_id=fixture_full_setup["tenant_id"],
        )
        assert len(rows) == 2
        assert rows[0]["period_start"] >= rows[1]["period_start"]

    def test_history_isolated_by_tenant(self, fixture_full_setup):
        rows = repo.list_indicator_history(
            fixture_full_setup["ind_with_value"], tenant_id=999_999_999
        )
        assert rows == []

    def test_count_indicators_status(self, fixture_full_setup):
        counts = repo.count_indicators_status(
            fixture_full_setup["tenant_id"]
        )
        assert counts["mandatory_total"] == 2
        assert counts["mandatory_with_value"] == 1
        # ind_with_value entra como on_target
        assert counts["mandatory_on_target"] >= 1


# =====================================================================
# Submissions
# =====================================================================


class TestSubmissions:
    def test_list_returns_both(self, fixture_full_setup):
        rows = repo.list_submissions(fixture_full_setup["tenant_id"])
        assert len(rows) == 2

    def test_filter_awaiting_response(self, fixture_full_setup):
        rows = repo.list_submissions(
            fixture_full_setup["tenant_id"], awaiting_response=True
        )
        assert len(rows) == 1
        assert rows[0]["id"] == fixture_full_setup["sub_pending"]

    def test_filter_by_submission_type(self, fixture_full_setup):
        rows = repo.list_submissions(
            fixture_full_setup["tenant_id"],
            submission_type="quarterly_report",
        )
        assert len(rows) == 1
        assert rows[0]["id"] == fixture_full_setup["sub_responded"]

    def test_count_submissions_pending(self, fixture_full_setup):
        n = repo.count_submissions_pending(
            fixture_full_setup["tenant_id"]
        )
        assert n == 1


# =====================================================================
# Reports
# =====================================================================


class TestReports:
    def test_list_returns_both(self, fixture_full_setup):
        rows = repo.list_reports(fixture_full_setup["tenant_id"])
        assert len(rows) == 2

    def test_filter_only_approved_true(self, fixture_full_setup):
        rows = repo.list_reports(
            fixture_full_setup["tenant_id"], only_approved=True
        )
        assert len(rows) == 1
        assert rows[0]["id"] == fixture_full_setup["report_approved"]

    def test_filter_only_approved_false(self, fixture_full_setup):
        rows = repo.list_reports(
            fixture_full_setup["tenant_id"], only_approved=False
        )
        assert len(rows) == 1
        assert rows[0]["id"] == fixture_full_setup["report_pending"]

    def test_filter_by_report_type(self, fixture_full_setup):
        rows = repo.list_reports(
            fixture_full_setup["tenant_id"],
            report_type="monitoring_plan",
        )
        assert len(rows) == 1

    def test_count_by_type(self, fixture_full_setup):
        counts = repo.count_reports_by_type(
            fixture_full_setup["tenant_id"]
        )
        assert counts.get("monitoring_plan") == 1
        assert counts.get("risk_management_plan") == 1


# =====================================================================
# Cross-tenant isolation smoke
# =====================================================================


class TestCrossTenantIsolation:
    def test_other_tenant_sees_nothing(self, fixture_full_setup):  # noqa: ARG002 — fixture executa para garantir dados em OUTRO tenant
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
                (f"reg_other_{suffix}",) * 3,
            )
            other = cur.fetchone()["id"]
            conn.commit()
        try:
            assert repo.list_projects(other) == []
            assert repo.list_submissions(other) == []
            assert repo.list_reports(other) == []
            assert repo.count_submissions_pending(other) == 0
            assert repo.count_indicators_status(other)["mandatory_total"] == 0
        finally:
            with db_cursor() as (conn, cur):
                cur.execute("DELETE FROM tenants WHERE id = %s", (other,))
                conn.commit()
