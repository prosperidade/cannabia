# src/web/routes/returns.py
"""
Returns / Follow-up / Dosage adjustment API endpoints.
Prefix: /api/v1
"""

from __future__ import annotations

import logging
from flask import Blueprint, g, request

from src.infra.database import db_cursor
from src.web.routes.api_v1 import (
    _error,
    _paginate,
    _pagination_args,
    _serialize,
    _success,
    api_role_required,
)

from src.config import FRONTEND_ORIGINS

logger = logging.getLogger("cannabia.returns")

returns_bp = Blueprint("returns", __name__, url_prefix="/api/v1")


@returns_bp.after_request
def apply_cors(response):
    origin = request.headers.get("Origin")
    if origin and origin in FRONTEND_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Vary"] = "Origin"
    return response


# ==================================================================
# GET /api/v1/returns
# ==================================================================

@returns_bp.get("/returns")
@api_role_required("Admin", "Medico")
def list_returns():
    """List patients due for follow-up / dosage adjustment."""
    page, page_size = _pagination_args()
    status_filter = request.args.get("status")  # pending, scheduled, completed
    search = (request.args.get("search") or "").strip()

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            # Try to query from treatment_plans joined with patients
            where_clauses = ["tp.clinic_id = %s"]
            params: list = [g.clinic_id]

            if status_filter:
                where_clauses.append("tp.status = %s")
                params.append(status_filter)

            if search:
                where_clauses.append("p.name ILIKE %s")
                params.append(f"%{search}%")

            where_sql = " AND ".join(where_clauses)

            cursor.execute(
                f"""
                SELECT
                    tp.id AS treatment_plan_id,
                    tp.patient_id,
                    p.name AS patient_name,
                    p.phone AS patient_phone,
                    tp.plan_name,
                    tp.status AS treatment_status,
                    tp.cbd_thc_ratio,
                    tp.dosage,
                    tp.next_return_date,
                    tp.updated_at AS last_update
                FROM treatment_plans tp
                JOIN patients p ON p.id = tp.patient_id AND p.clinic_id = tp.clinic_id
                WHERE {where_sql}
                ORDER BY tp.next_return_date ASC NULLS LAST, tp.updated_at DESC
                """,
                tuple(params),
            )
            rows = cursor.fetchall()

            # Count meta
            total = len(rows)
            pending = sum(1 for r in rows if r.get("treatment_status") in ("ativo", "pendente"))
            scheduled = sum(1 for r in rows if r.get("next_return_date") is not None)

            items, page_meta = _paginate(rows, page, page_size)

            meta = {
                **page_meta,
                "total_returns": total,
                "pending": pending,
                "scheduled": scheduled,
            }
            return _success(items, meta=meta)

    except Exception:
        logger.warning("Error fetching returns from DB", exc_info=True)

    return _success([], meta={"page": page, "page_size": page_size, "total": 0, "total_returns": 0, "pending": 0, "scheduled": 0})
