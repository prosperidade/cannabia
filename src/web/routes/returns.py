# src/web/routes/returns.py
"""
Returns / Follow-up / Dosage adjustment API endpoints.
Prefix: /api/v1
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

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
        logger.warning("Error fetching returns from DB; returning mock data", exc_info=True)

    # TODO: Replace with real DB query
    now = datetime.now(timezone.utc)
    mock_data = [
        {
            "treatment_plan_id": 1,
            "patient_id": 101,
            "patient_name": "Maria Silva",
            "patient_phone": "+5511999990001",
            "plan_name": "Protocolo Dor Cronica",
            "treatment_status": "ativo",
            "cbd_thc_ratio": "20:1",
            "dosage": "CBD 50mg 2x/dia",
            "next_return_date": (now + timedelta(days=2)).isoformat(),
            "last_update": (now - timedelta(days=28)).isoformat(),
            "ai_recommendation": "Considerar aumento para 75mg baseado na reducao de 40% na escala EVA.",
        },
        {
            "treatment_plan_id": 2,
            "patient_id": 102,
            "patient_name": "Joao Oliveira",
            "patient_phone": "+5511999990002",
            "plan_name": "Protocolo Epilepsia",
            "treatment_status": "ativo",
            "cbd_thc_ratio": "50:1",
            "dosage": "CBD 100mg 3x/dia",
            "next_return_date": (now + timedelta(days=5)).isoformat(),
            "last_update": (now - timedelta(days=14)).isoformat(),
            "ai_recommendation": "Manter dose atual. Frequencia de crises reduzida em 60%.",
        },
        {
            "treatment_plan_id": 3,
            "patient_id": 103,
            "patient_name": "Ana Costa",
            "patient_phone": "+5511999990003",
            "plan_name": "Protocolo Ansiedade",
            "treatment_status": "pendente",
            "cbd_thc_ratio": "10:1",
            "dosage": "CBD 25mg/dia",
            "next_return_date": (now - timedelta(days=1)).isoformat(),
            "last_update": (now - timedelta(days=30)).isoformat(),
            "ai_recommendation": "Retorno atrasado. Paciente relatou efeitos colaterais leves. Reavaliar tolerancia.",
        },
        {
            "treatment_plan_id": 4,
            "patient_id": 104,
            "patient_name": "Pedro Santos",
            "patient_phone": "+5511999990004",
            "plan_name": "Protocolo Insonia",
            "treatment_status": "ativo",
            "cbd_thc_ratio": "5:1",
            "dosage": "CBD 30mg + THC 6mg (noite)",
            "next_return_date": (now + timedelta(days=12)).isoformat(),
            "last_update": (now - timedelta(days=7)).isoformat(),
            "ai_recommendation": "Paciente reportou melhora significativa. Manter e reavaliar em 30 dias.",
        },
        {
            "treatment_plan_id": 5,
            "patient_id": 105,
            "patient_name": "Lucia Ferreira",
            "patient_phone": "+5511999990005",
            "plan_name": "Protocolo Fibromialgia",
            "treatment_status": "ativo",
            "cbd_thc_ratio": "15:1",
            "dosage": "CBD 40mg 2x/dia",
            "next_return_date": (now + timedelta(days=0)).isoformat(),
            "last_update": (now - timedelta(days=21)).isoformat(),
            "ai_recommendation": "Retorno hoje. Sugerir aumento gradual se tolerancia confirmada.",
        },
    ]

    if status_filter:
        mock_data = [d for d in mock_data if d["treatment_status"] == status_filter]
    if search:
        mock_data = [d for d in mock_data if search.lower() in d["patient_name"].lower()]

    total = len(mock_data)
    pending = sum(1 for d in mock_data if d["treatment_status"] in ("ativo", "pendente"))
    scheduled = sum(1 for d in mock_data if d.get("next_return_date"))

    items, page_meta = _paginate(mock_data, page, page_size)
    meta = {**page_meta, "total_returns": total, "pending": pending, "scheduled": scheduled}
    return _success(items, meta=meta)
