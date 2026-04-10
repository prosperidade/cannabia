# src/web/routes/reports.py
"""
BI Reports API.
Prefix: /api/v1/org
"""
from __future__ import annotations
import logging
from flask import Blueprint, g, request
from src.infra.database import db_cursor
from src.web.routes.api_v1 import _success, api_role_required

logger = logging.getLogger("cannabia.reports")
reports_bp = Blueprint("reports", __name__, url_prefix="/api/v1/org")


@reports_bp.get("/reports")
@api_role_required("Admin", "Medico")
def get_reports():
    """Aggregated BI reports for the organization."""
    period = request.args.get("period", "6m")  # 1m, 3m, 6m, 12m
    interval_map = {"1m": "1 month", "3m": "3 months", "6m": "6 months", "12m": "12 months"}
    interval = interval_map.get(period, "6 months")

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            clinic_id = g.clinic_id

            # Attendance stats by month
            cursor.execute(
                f"""
                SELECT to_char(created_at, 'YYYY-MM') AS month,
                       COUNT(*) AS total,
                       SUM(CASE WHEN status = 'revisado' THEN 1 ELSE 0 END) AS reviewed
                FROM anamnesis_reports
                WHERE clinic_id = %s AND created_at >= CURRENT_DATE - INTERVAL '{interval}'
                GROUP BY 1 ORDER BY 1
                """,
                (clinic_id,),
            )
            attendance_by_month = cursor.fetchall()

            # Financial stats by month
            cursor.execute(
                f"""
                SELECT to_char(created_at, 'YYYY-MM') AS month,
                       COALESCE(SUM(CASE WHEN status = 'pago' THEN amount ELSE 0 END), 0) AS revenue,
                       COALESCE(SUM(CASE WHEN status = 'pendente' THEN amount ELSE 0 END), 0) AS pending,
                       COALESCE(SUM(CASE WHEN status = 'vencido' THEN amount ELSE 0 END), 0) AS overdue
                FROM billing
                WHERE clinic_id = %s AND created_at >= CURRENT_DATE - INTERVAL '{interval}'
                GROUP BY 1 ORDER BY 1
                """,
                (clinic_id,),
            )
            financial_by_month = cursor.fetchall()

            # Patient stats
            cursor.execute(
                f"""
                SELECT to_char(created_at, 'YYYY-MM') AS month, COUNT(*) AS new_patients
                FROM patients
                WHERE clinic_id = %s AND created_at >= CURRENT_DATE - INTERVAL '{interval}'
                GROUP BY 1 ORDER BY 1
                """,
                (clinic_id,),
            )
            patients_by_month = cursor.fetchall()

            # AI stats
            cursor.execute(
                f"""
                SELECT to_char(created_at, 'YYYY-MM') AS month,
                       COUNT(*) AS total_requests,
                       COALESCE(SUM(total_tokens), 0) AS total_tokens,
                       COALESCE(SUM(estimated_cost_usd), 0) AS total_cost
                FROM ai_audit_logs
                WHERE clinic_id = %s AND created_at >= CURRENT_DATE - INTERVAL '{interval}'
                GROUP BY 1 ORDER BY 1
                """,
                (clinic_id,),
            )
            ai_by_month = cursor.fetchall()

            # Summary totals
            cursor.execute(
                "SELECT COUNT(*) AS total FROM patients WHERE clinic_id = %s",
                (clinic_id,),
            )
            total_patients = cursor.fetchone()["total"]

            cursor.execute(
                "SELECT COUNT(*) AS total FROM anamnesis_reports WHERE clinic_id = %s",
                (clinic_id,),
            )
            total_attendances = cursor.fetchone()["total"]

            cursor.execute(
                """SELECT COALESCE(SUM(CASE WHEN status='pago' THEN amount ELSE 0 END), 0) AS revenue
                   FROM billing WHERE clinic_id = %s""",
                (clinic_id,),
            )
            total_revenue = float(cursor.fetchone()["revenue"])

            return _success({
                "summary": {
                    "total_patients": total_patients,
                    "total_attendances": total_attendances,
                    "total_revenue": total_revenue,
                },
                "attendance_by_month": attendance_by_month,
                "financial_by_month": financial_by_month,
                "patients_by_month": patients_by_month,
                "ai_by_month": ai_by_month,
            })
    except Exception:
        logger.error("Error generating reports", exc_info=True)
        return _success({
            "summary": {"total_patients": 0, "total_attendances": 0, "total_revenue": 0},
            "attendance_by_month": [], "financial_by_month": [],
            "patients_by_month": [], "ai_by_month": [],
        })
