# src/repositories/regulatory_reporting_repository.py
"""
Repositorio do Regulatory Reporting (F3.7 do docs/BACKLOG_SCC.md).

SQL puro, read-only, para alimentar dashboards ANVISA-ready do
blueprint `regulatory_reporting.py`. Cobre as 6 tabelas regulatorias da
migration 032 + a view `v_sandbox_indicator_dashboard` (F6.2 / migration
036).

Tabelas/views:
  - sandbox_projects             (timeline draft→submitted→...)
  - sandbox_protocols            (protocolo versionado por projeto)
  - sandbox_indicators           (definicao do indicador)
  - sandbox_indicator_values     (telemetria periodica do indicador)
  - regulatory_submissions       (submissoes a ANVISA)
  - regulatory_reports           (relatorios aprovados — 7 tipos)
  - v_sandbox_indicator_dashboard (snapshot por indicador com on_target)

Por convencao SCC, escopagem por tenant via `tenant_id` direto na
tabela quando existe; em sandbox_indicators / sandbox_indicator_values
e via JOIN com sandbox_projects.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.repo.regulatory_reporting")


# ---------------------------------------------------------------------------
# Projects (sandbox_projects)
# ---------------------------------------------------------------------------

_PROJECT_COLS = """
    id, tenant_id, project_code, title, status,
    submitted_at, approved_at, started_at, concluded_at,
    anvisa_reference, created_at, updated_at
"""


def list_projects(
    tenant_id: int,
    *,
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    sql_where = ["tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if status is not None:
        sql_where.append("status = %s")
        params.append(status)
    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT {_PROJECT_COLS}
        FROM sandbox_projects
        WHERE {where_clause}
        ORDER BY COALESCE(started_at, submitted_at, created_at) DESC, id DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        return list(cur.fetchall())


def get_project(project_id: int, *, tenant_id: int) -> Optional[dict[str, Any]]:
    sql = f"""
        SELECT {_PROJECT_COLS}
        FROM sandbox_projects
        WHERE id = %s AND tenant_id = %s
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (project_id, tenant_id))
        return cur.fetchone()


def count_projects_by_status(tenant_id: int) -> dict[str, int]:
    """Counts por status para overview. Status ausentes nao aparecem."""
    sql = """
        SELECT status, COUNT(*) AS n
        FROM sandbox_projects
        WHERE tenant_id = %s
        GROUP BY status
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (tenant_id,))
        return {r["status"]: int(r["n"]) for r in cur.fetchall()}


# ---------------------------------------------------------------------------
# Protocols (sandbox_protocols) — protocolo vigente por projeto
# ---------------------------------------------------------------------------

def get_active_protocol(
    project_id: int, *, tenant_id: int
) -> Optional[dict[str, Any]]:
    """
    Protocolo vigente do projeto: o que tem `effective_until IS NULL`
    (ou o mais recente, caso varios estejam em vigor).
    """
    sql = """
        SELECT sp.id, sp.project_id, sp.protocol_version,
               sp.scope, sp.applicable_norms, sp.modulated_norms,
               sp.monitoring_parameters, sp.discontinuity_plan,
               sp.quality_requirements, sp.data_sharing_obligations,
               sp.effective_from, sp.effective_until, sp.created_at
        FROM sandbox_protocols sp
        JOIN sandbox_projects pr ON pr.id = sp.project_id
        WHERE sp.project_id = %s AND pr.tenant_id = %s
        ORDER BY (sp.effective_until IS NULL) DESC,
                 sp.effective_from DESC NULLS LAST,
                 sp.created_at DESC
        LIMIT 1
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (project_id, tenant_id))
        return cur.fetchone()


# ---------------------------------------------------------------------------
# Indicators dashboard (v_sandbox_indicator_dashboard)
# ---------------------------------------------------------------------------

_DASH_COLS = """
    indicator_id, project_id, tenant_id,
    indicator_code, indicator_name, unit,
    target_value, reporting_frequency, is_mandatory,
    latest_value, latest_period_start, latest_period_end,
    latest_calculated_at, n_periods, on_target
"""


def list_indicator_dashboard(
    tenant_id: int,
    *,
    project_id: Optional[int] = None,
    only_mandatory: bool = False,
    only_off_target: bool = False,
) -> list[dict[str, Any]]:
    """
    Linhas da view `v_sandbox_indicator_dashboard` para o tenant
    (filtros opcionais).
    """
    sql_where = ["tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if project_id is not None:
        sql_where.append("project_id = %s")
        params.append(project_id)
    if only_mandatory:
        sql_where.append("is_mandatory = TRUE")
    if only_off_target:
        sql_where.append("on_target = FALSE")
    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT {_DASH_COLS}
        FROM v_sandbox_indicator_dashboard
        WHERE {where_clause}
        ORDER BY project_id, indicator_code
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        return list(cur.fetchall())


def get_indicator_dashboard_row(
    indicator_id: int, *, tenant_id: int
) -> Optional[dict[str, Any]]:
    sql = f"""
        SELECT {_DASH_COLS}
        FROM v_sandbox_indicator_dashboard
        WHERE indicator_id = %s AND tenant_id = %s
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (indicator_id, tenant_id))
        return cur.fetchone()


def list_indicator_history(
    indicator_id: int,
    *,
    tenant_id: int,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 365,
) -> list[dict[str, Any]]:
    """
    Series temporais do indicador (sandbox_indicator_values) com
    escopagem por tenant via JOIN com sandbox_projects.
    """
    sql_where = [
        "siv.indicator_id = %s",
        "pr.tenant_id = %s",
    ]
    params: list[Any] = [indicator_id, tenant_id]
    if since is not None:
        sql_where.append("siv.period_start >= %s")
        params.append(since)
    if until is not None:
        sql_where.append("siv.period_end <= %s")
        params.append(until)
    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT siv.id, siv.indicator_id,
               siv.period_start, siv.period_end,
               siv.calculated_value, siv.calculation_details,
               siv.calculated_at
        FROM sandbox_indicator_values siv
        JOIN sandbox_indicators si ON si.id = siv.indicator_id
        JOIN sandbox_projects pr ON pr.id = si.project_id
        WHERE {where_clause}
        ORDER BY siv.period_start DESC, siv.id DESC
        LIMIT %s
    """
    params.append(limit)
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        return list(cur.fetchall())


def count_indicators_status(tenant_id: int) -> dict[str, int]:
    """
    Para o overview: total de indicadores mandatorios e quantos com
    `on_target = TRUE`. Indicadores sem valor ainda contam como
    `with_value = False`.
    """
    sql = """
        SELECT
          COUNT(*) FILTER (WHERE is_mandatory)                          AS mandatory_total,
          COUNT(*) FILTER (WHERE is_mandatory AND latest_value IS NOT NULL) AS mandatory_with_value,
          COUNT(*) FILTER (WHERE is_mandatory AND on_target IS TRUE)    AS mandatory_on_target,
          COUNT(*) FILTER (WHERE is_mandatory AND on_target IS FALSE)   AS mandatory_off_target
        FROM v_sandbox_indicator_dashboard
        WHERE tenant_id = %s
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (tenant_id,))
        row = cur.fetchone() or {}
        return {
            "mandatory_total": int(row.get("mandatory_total") or 0),
            "mandatory_with_value": int(row.get("mandatory_with_value") or 0),
            "mandatory_on_target": int(row.get("mandatory_on_target") or 0),
            "mandatory_off_target": int(row.get("mandatory_off_target") or 0),
        }


# ---------------------------------------------------------------------------
# Submissions (regulatory_submissions)
# ---------------------------------------------------------------------------

_SUB_COLS = """
    id, tenant_id, project_id, submission_type,
    submitted_at, submitted_by,
    payload_uri, payload_hash,
    anvisa_response_uri, anvisa_response_at,
    created_at
"""


def list_submissions(
    tenant_id: int,
    *,
    project_id: Optional[int] = None,
    submission_type: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    awaiting_response: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    sql_where = ["tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if project_id is not None:
        sql_where.append("project_id = %s")
        params.append(project_id)
    if submission_type is not None:
        sql_where.append("submission_type = %s")
        params.append(submission_type)
    if since is not None:
        sql_where.append("submitted_at >= %s")
        params.append(since)
    if until is not None:
        sql_where.append("submitted_at < %s")
        params.append(until)
    if awaiting_response is True:
        sql_where.append("anvisa_response_at IS NULL")
    elif awaiting_response is False:
        sql_where.append("anvisa_response_at IS NOT NULL")
    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT {_SUB_COLS}
        FROM regulatory_submissions
        WHERE {where_clause}
        ORDER BY submitted_at DESC, id DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        return list(cur.fetchall())


def count_submissions_pending(tenant_id: int) -> int:
    """Submissoes sem resposta da ANVISA — KPI do overview."""
    sql = """
        SELECT COUNT(*) AS n
        FROM regulatory_submissions
        WHERE tenant_id = %s AND anvisa_response_at IS NULL
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (tenant_id,))
        row = cur.fetchone()
        return int(row["n"] or 0) if row else 0


# ---------------------------------------------------------------------------
# Reports (regulatory_reports — 7 tipos)
# ---------------------------------------------------------------------------

_REP_COLS = """
    id, tenant_id, project_id, report_type, version,
    content_uri, content_hash,
    generated_at, approved_by, approved_at
"""


def list_reports(
    tenant_id: int,
    *,
    project_id: Optional[int] = None,
    report_type: Optional[str] = None,
    only_approved: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    sql_where = ["tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if project_id is not None:
        sql_where.append("project_id = %s")
        params.append(project_id)
    if report_type is not None:
        sql_where.append("report_type = %s")
        params.append(report_type)
    if only_approved is True:
        sql_where.append("approved_at IS NOT NULL")
    elif only_approved is False:
        sql_where.append("approved_at IS NULL")
    where_clause = " AND ".join(sql_where)
    sql = f"""
        SELECT {_REP_COLS}
        FROM regulatory_reports
        WHERE {where_clause}
        ORDER BY generated_at DESC, id DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, tuple(params))
        return list(cur.fetchall())


def count_reports_by_type(tenant_id: int) -> dict[str, int]:
    """Counts por report_type para overview. Tipos sem reports nao aparecem."""
    sql = """
        SELECT report_type, COUNT(*) AS n
        FROM regulatory_reports
        WHERE tenant_id = %s
        GROUP BY report_type
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (tenant_id,))
        return {r["report_type"]: int(r["n"]) for r in cur.fetchall()}
