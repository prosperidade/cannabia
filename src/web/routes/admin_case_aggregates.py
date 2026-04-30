# src/web/routes/admin_case_aggregates.py
"""
Admin endpoint para disparar manualmente o pipeline de agregacao de
casos clinicos (C7).

Roles: somente Admin (global). AdminClinica nao roda — o pipeline
opera sobre dados cross-tenant (k-anonymity precisa olhar todos os
tenants para somar pacientes).
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, request

from src.infra.database import db_cursor
from src.knowledge.case_aggregator import (
    DEFAULT_LOOKBACK_DAYS,
    MIN_K,
    aggregate_clinical_cases,
    aggregate_summary_dict,
    persist_aggregates_to_catalog,
)
from src.web.routes.api_v1 import _require_json_csrf, _success, api_role_required

logger = logging.getLogger("cannabia.admin_case_aggregates")

admin_case_aggregates_bp = Blueprint(
    "admin_case_aggregates",
    __name__,
    url_prefix="/api/v1/admin/case-aggregates",
)


def _coerce_int(raw: Any, *, default: int, low: int, high: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(low, min(value, high))


@admin_case_aggregates_bp.post("/run")
@api_role_required("Admin")
def run_pipeline():
    """Roda agregacao end-to-end e persiste em knowledge_catalog.

    Body opcional (JSON):
      {
        "lookback_days": 180,    # janela retroativa (1..730)
        "min_group_size": 5,     # k-anonymity (3..50)
        "dry_run": false         # se true, retorna preview sem inserir
      }
    """
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = (request.get_json(silent=True) or {}) if request.data else {}
    lookback_days = _coerce_int(
        payload.get("lookback_days"), default=DEFAULT_LOOKBACK_DAYS, low=1, high=730,
    )
    min_group_size = _coerce_int(
        payload.get("min_group_size"), default=MIN_K, low=3, high=50,
    )
    dry_run = bool(payload.get("dry_run"))

    aggregates = aggregate_clinical_cases(
        min_group_size=min_group_size,
        lookback_days=lookback_days,
    )
    summary = aggregate_summary_dict(aggregates)
    summary["lookback_days"] = lookback_days
    summary["dry_run"] = dry_run
    summary["min_group_size"] = min_group_size

    if dry_run or not aggregates:
        summary["persisted"] = {"inserted": 0, "refreshed_stale": 0}
        logger.info(
            "Case aggregator dry-run: %d groups, %d patients covered",
            summary["groups_total"], summary["patients_covered"],
        )
        return _success(summary)

    from flask_login import current_user
    user_id = None
    try:
        user_id = int(current_user.id) if current_user and current_user.is_authenticated else None
    except (AttributeError, TypeError, ValueError):
        user_id = None

    persisted = persist_aggregates_to_catalog(aggregates, user_id=user_id)
    summary["persisted"] = persisted
    logger.info(
        "Case aggregator run: %d groups inserted (refreshed %d stale)",
        persisted["inserted"], persisted["refreshed_stale"],
    )
    return _success(summary)


@admin_case_aggregates_bp.get("/last")
@api_role_required("Admin")
def list_recent_aggregates():
    """Lista os ultimos N casos agregados ja persistidos.

    Query string ``limit`` (default 20, max 100).
    """
    limit = _coerce_int(request.args.get("limit"), default=20, low=1, high=100)

    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(
            """
            SELECT id, title, abstract, ingested_at, case_aggregate_metadata
            FROM knowledge_catalog
            WHERE doc_type = 'case_aggregate'
            ORDER BY ingested_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall() or []

    return _success({
        "items": [
            {
                "id": r["id"],
                "title": r["title"],
                "abstract": r["abstract"],
                "ingested_at": r["ingested_at"].isoformat() if r["ingested_at"] else None,
                "metadata": r["case_aggregate_metadata"],
            }
            for r in rows
        ],
        "count": len(rows),
    })
