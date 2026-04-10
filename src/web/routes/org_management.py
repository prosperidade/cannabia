# src/web/routes/org_management.py
"""
Organization management API endpoints.
Prefix: /api/v1/org
"""

from __future__ import annotations

import logging
from flask import Blueprint, g, request
from flask_login import current_user

from src.infra.database import db_cursor
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _paginate,
    _pagination_args,
    _require_json_csrf,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.org_management")

org_management_bp = Blueprint("org_management", __name__, url_prefix="/api/v1/org")


# ==================================================================
# GET /api/v1/org/dashboard
# ==================================================================

@org_management_bp.get("/dashboard")
@api_role_required("Admin", "Medico", "Atendente")
def org_dashboard():
    """Organization-level KPIs and chart data."""
    clinic_id = g.clinic_id

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            # Active patients
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM patients WHERE clinic_id = %s",
                (clinic_id,),
            )
            patients_active = cursor.fetchone()["cnt"]

            # Consultations this month
            cursor.execute(
                """
                SELECT COUNT(*) AS cnt FROM anamnesis_reports
                WHERE clinic_id = %s
                  AND created_at >= date_trunc('month', CURRENT_DATE)
                """,
                (clinic_id,),
            )
            consultations_month = cursor.fetchone()["cnt"]

            # Consultations by month (last 6 months)
            cursor.execute(
                """
                SELECT to_char(created_at, 'YYYY-MM') AS month, COUNT(*) AS total
                FROM anamnesis_reports
                WHERE clinic_id = %s
                  AND created_at >= CURRENT_DATE - INTERVAL '6 months'
                GROUP BY 1 ORDER BY 1
                """,
                (clinic_id,),
            )
            consultations_by_month = cursor.fetchall()

            cursor.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM billing
                WHERE clinic_id = %s AND status = 'pago'
                  AND created_at >= date_trunc('month', CURRENT_DATE)
                """,
                (clinic_id,),
            )
            revenue_month = float(cursor.fetchone()["total"])

            # Revenue by month chart (last 6 months)
            cursor.execute(
                """
                SELECT to_char(created_at, 'YYYY-MM') AS month,
                       COALESCE(SUM(amount), 0) AS total
                FROM billing
                WHERE clinic_id = %s AND status = 'pago'
                  AND created_at >= CURRENT_DATE - INTERVAL '6 months'
                GROUP BY 1 ORDER BY 1
                """,
                (clinic_id,),
            )
            revenue_by_month = cursor.fetchall()

            return _success({
                "metrics": {
                    "patients_active": patients_active,
                    "consultations_month": consultations_month,
                    "revenue_month": revenue_month,
                    "conversion_rate": 0,
                },
                "charts": {
                    "consultations_by_month": consultations_by_month,
                    "revenue_by_month": revenue_by_month,
                },
            })
    except Exception:
        logger.warning("Error fetching org dashboard from DB", exc_info=True)
        return _success({
            "metrics": {"patients_active": 0, "consultations_month": 0, "revenue_month": 0, "conversion_rate": 0},
            "charts": {"consultations_by_month": [], "revenue_by_month": []},
        })


# ==================================================================
# GET /api/v1/org/patients
# ==================================================================

@org_management_bp.get("/patients")
@api_role_required("Admin", "Medico", "Atendente")
def org_patients():
    """List all patients for the organization with search and pagination."""
    page, page_size = _pagination_args()
    search = (request.args.get("search") or "").strip()
    status_filter = (request.args.get("status") or "").strip()

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            where_clauses = ["clinic_id = %s"]
            params: list = [g.clinic_id]

            if search:
                where_clauses.append("(name ILIKE %s OR phone ILIKE %s OR email ILIKE %s)")
                like = f"%{search}%"
                params.extend([like, like, like])

            if status_filter:
                where_clauses.append("status = %s")
                params.append(status_filter)

            where_sql = " AND ".join(where_clauses)

            cursor.execute(
                f"""
                SELECT id, name, phone, email, status, created_at
                FROM patients
                WHERE {where_sql}
                ORDER BY name ASC
                """,
                tuple(params),
            )
            rows = cursor.fetchall()
            items, meta = _paginate(rows, page, page_size)
            return _success(items, meta=meta)
    except Exception:
        logger.warning("Error fetching org patients from DB", exc_info=True)
        return _success([], meta={"page": page, "page_size": page_size, "total": 0})


# ==================================================================
# GET /api/v1/org/doctors
# ==================================================================

@org_management_bp.get("/doctors")
@api_role_required("Admin", "Medico", "Atendente")
def org_doctors():
    """List doctors for the organization."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT u.id, u.username AS name, u.role,
                       cm.clinic_role, cm.created_at AS joined_at
                FROM users u
                JOIN clinic_members cm ON cm.user_id = u.id
                WHERE cm.clinic_id = %s
                  AND (cm.clinic_role = 'Medico' OR u.role = 'Medico')
                ORDER BY u.username
                """,
                (g.clinic_id,),
            )
            doctors = cursor.fetchall()
            return _success(doctors)
    except Exception:
        logger.warning("Error fetching doctors from DB", exc_info=True)
        return _success([])


# ==================================================================
# GET /api/v1/org/stock
# ==================================================================

@org_management_bp.get("/stock")
@api_role_required("Admin", "Atendente")
def org_stock():
    """Stock inventory listing."""
    page, page_size = _pagination_args()
    search = (request.args.get("search") or "").strip()

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT id, product_name, batch_number, quantity, unit,
                       expiry_date, status, supplier, created_at
                FROM stock_inventory
                WHERE clinic_id = %s
                ORDER BY product_name, expiry_date
                """,
                (g.clinic_id,),
            )
            rows = cursor.fetchall()
            if search:
                rows = [r for r in rows if search.lower() in (r.get("product_name") or "").lower()]
            items, meta = _paginate(rows, page, page_size)
            return _success(items, meta=meta)
    except Exception:
        logger.warning("Error fetching stock from DB", exc_info=True)
        return _success([], meta={"page": page, "page_size": page_size, "total": 0})


# ==================================================================
# POST /api/v1/org/stock/entry
# ==================================================================

@org_management_bp.post("/stock/entry")
@api_role_required("Admin", "Medico", "Atendente")
def org_stock_entry():
    """Register a stock entry."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()

    product_name = (payload.get("product_name") or "").strip()
    batch_number = (payload.get("batch_number") or "").strip()
    quantity = payload.get("quantity")
    unit = (payload.get("unit") or "frascos").strip()
    expiry_date = (payload.get("expiry_date") or "").strip()
    supplier = (payload.get("supplier") or "").strip()

    if not product_name or quantity is None:
        return _error("validation_error", "product_name e quantity sao obrigatorios.", 422)

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return _error("validation_error", "quantity deve ser um numero inteiro.", 422)

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute(
                """
                INSERT INTO stock_inventory
                    (clinic_id, product_name, batch_number, quantity, unit,
                     expiry_date, status, supplier, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'disponivel', %s, NOW())
                RETURNING id, created_at
                """,
                (
                    g.clinic_id,
                    product_name,
                    batch_number,
                    quantity,
                    unit,
                    expiry_date or None,
                    supplier,
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return _success({"id": row["id"], "created_at": row["created_at"]}, status=201)
    except Exception:
        logger.error("Failed to insert stock entry", exc_info=True)
        return _error("internal_error", "Falha ao registrar entrada de estoque.", 500)


# ==================================================================
# POST /api/v1/org/stock/dispensation
# ==================================================================

@org_management_bp.post("/stock/dispensation")
@api_role_required("Admin", "Medico", "Atendente")
def org_stock_dispensation():
    """Register a stock dispensation to a patient."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()

    stock_item_id = payload.get("stock_item_id")
    patient_id = payload.get("patient_id")
    quantity = payload.get("quantity")
    notes = (payload.get("notes") or "").strip()

    if not stock_item_id or not patient_id or quantity is None:
        return _error("validation_error", "stock_item_id, patient_id e quantity sao obrigatorios.", 422)

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return _error("validation_error", "quantity deve ser um numero inteiro.", 422)

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            # Decrement stock
            cursor.execute(
                """
                UPDATE stock_inventory
                SET quantity = quantity - %s
                WHERE id = %s AND clinic_id = %s AND quantity >= %s
                RETURNING id, quantity
                """,
                (quantity, stock_item_id, g.clinic_id, quantity),
            )
            updated = cursor.fetchone()
            if not updated:
                conn.rollback()
                return _error("conflict", "Estoque insuficiente ou item nao encontrado.", 409)

            # Log dispensation
            cursor.execute(
                """
                INSERT INTO stock_dispensations
                    (clinic_id, stock_item_id, patient_id, quantity, dispensed_by,
                     notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING id, created_at
                """,
                (
                    g.clinic_id,
                    stock_item_id,
                    patient_id,
                    quantity,
                    int(current_user.id),
                    notes,
                ),
            )
            disp = cursor.fetchone()
            conn.commit()
            return _success({
                "dispensation_id": disp["id"],
                "remaining_quantity": updated["quantity"],
                "created_at": disp["created_at"],
            }, status=201)
    except Exception:
        logger.error("Failed to register dispensation", exc_info=True)
        return _error("internal_error", "Falha ao registrar dispensacao.", 500)


# ==================================================================
# GET /api/v1/org/billing
# ==================================================================

@org_management_bp.get("/billing")
@api_role_required("Admin", "Medico", "Atendente")
def org_billing():
    """Billing records for the organization."""
    page, page_size = _pagination_args()
    status_filter = (request.args.get("status") or "").strip()

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            where_clauses = ["b.clinic_id = %s"]
            params: list = [g.clinic_id]

            if status_filter:
                where_clauses.append("b.status = %s")
                params.append(status_filter)

            where_sql = " AND ".join(where_clauses)
            cursor.execute(
                f"""
                SELECT b.id, b.patient_id, p.name AS patient_name,
                       b.description, b.amount, b.status, b.due_date,
                       b.paid_at, b.created_at
                FROM billing b
                LEFT JOIN patients p ON p.id = b.patient_id AND p.clinic_id = b.clinic_id
                WHERE {where_sql}
                ORDER BY b.created_at DESC
                """,
                tuple(params),
            )
            rows = cursor.fetchall()

            total_revenue = sum(float(r.get("amount", 0)) for r in rows if r.get("status") == "pago")
            pending = sum(float(r.get("amount", 0)) for r in rows if r.get("status") == "pendente")
            overdue = sum(float(r.get("amount", 0)) for r in rows if r.get("status") == "vencido")

            items, page_meta = _paginate(rows, page, page_size)
            meta = {**page_meta, "total_revenue": total_revenue, "pending": pending, "overdue": overdue}
            return _success(items, meta=meta)
    except Exception:
        logger.warning("Error fetching billing from DB", exc_info=True)
        return _success([], meta={"page": page, "page_size": page_size, "total": 0, "total_revenue": 0, "pending": 0, "overdue": 0})


# ==================================================================
# GET /api/v1/org/financial
# ==================================================================

@org_management_bp.get("/financial")
@api_role_required("Admin", "Medico", "Atendente")
def org_financial():
    """Financial summary for the organization."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            # Try to pull from billing table for revenue
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'pago' THEN amount ELSE 0 END), 0) AS revenue,
                    COALESCE(SUM(CASE WHEN status = 'pendente' THEN amount ELSE 0 END), 0) AS pending,
                    COALESCE(SUM(CASE WHEN status = 'vencido' THEN amount ELSE 0 END), 0) AS overdue
                FROM billing
                WHERE clinic_id = %s
                  AND created_at >= date_trunc('month', CURRENT_DATE)
                """,
                (g.clinic_id,),
            )
            row = cursor.fetchone()
            revenue = float(row["revenue"])
            costs = revenue * 0.35  # placeholder ratio
            profit = revenue - costs

            return _success({
                "revenue": revenue,
                "costs": round(costs, 2),
                "profit": round(profit, 2),
                "margin": round((profit / revenue * 100) if revenue else 0, 1),
                "pending": float(row["pending"]),
                "overdue": float(row["overdue"]),
                "transfers": [],
            })
    except Exception:
        logger.warning("Error fetching financial data from DB", exc_info=True)
        return _success({
            "revenue": 0, "costs": 0, "profit": 0, "margin": 0,
            "pending": 0, "overdue": 0, "transfers": [],
        })
