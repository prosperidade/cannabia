# src/web/routes/compliance.py
"""
ANVISA Compliance API.
Prefix: /api/v1/org
"""
from __future__ import annotations
import logging
from flask import Blueprint, g
from src.infra.database import db_cursor
from src.web.routes.api_v1 import _success, api_role_required

logger = logging.getLogger("cannabia.compliance")
compliance_bp = Blueprint("compliance", __name__, url_prefix="/api/v1/org")


@compliance_bp.get("/compliance")
@api_role_required("Admin", "Medico")
def get_compliance():
    """ANVISA compliance checklist derived from real system state."""
    clinic_id = g.clinic_id
    checks = []

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            # 1. Prescriptions with required fields
            cursor.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN doctor_crm IS NOT NULL AND doctor_crm != '' THEN 1 ELSE 0 END) AS with_crm
                   FROM prescriptions WHERE clinic_id = %s""",
                (clinic_id,),
            )
            rx = cursor.fetchone()
            total_rx = rx["total"] or 0
            crm_rx = rx["with_crm"] or 0
            checks.append({
                "category": "prescricoes",
                "name": "Prescricoes com CRM do medico",
                "status": "ok" if total_rx == 0 or crm_rx == total_rx else "warning",
                "detail": f"{crm_rx}/{total_rx} prescricoes com CRM preenchido",
            })

            # 2. Patient consent (all patients have status)
            cursor.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN status IS NOT NULL AND status != '' THEN 1 ELSE 0 END) AS with_status
                   FROM patients WHERE clinic_id = %s""",
                (clinic_id,),
            )
            pt = cursor.fetchone()
            checks.append({
                "category": "dados",
                "name": "Pacientes com status cadastral",
                "status": "ok" if (pt["total"] or 0) == 0 or pt["with_status"] == pt["total"] else "warning",
                "detail": f"{pt['with_status']}/{pt['total']} pacientes com status",
            })

            # 3. Audit trail active
            cursor.execute(
                "SELECT COUNT(*) AS total FROM audit_trail WHERE clinic_id = %s",
                (clinic_id,),
            )
            audit_count = cursor.fetchone()["total"]
            checks.append({
                "category": "rastreabilidade",
                "name": "Trilha de auditoria ativa",
                "status": "ok" if audit_count > 0 else "warning",
                "detail": f"{audit_count} eventos registrados",
            })

            # 4. Stock with expiry tracking
            cursor.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN expiry_date IS NOT NULL THEN 1 ELSE 0 END) AS with_expiry
                   FROM stock_inventory WHERE clinic_id = %s""",
                (clinic_id,),
            )
            stock = cursor.fetchone()
            checks.append({
                "category": "rastreabilidade",
                "name": "Estoque com validade registrada",
                "status": "ok" if (stock["total"] or 0) == 0 or stock["with_expiry"] == stock["total"] else "warning",
                "detail": f"{stock['with_expiry']}/{stock['total']} itens com validade",
            })

            # 5. Medical records completeness
            cursor.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN clinical_assessment IS NOT NULL AND clinical_assessment != '' THEN 1 ELSE 0 END) AS complete
                   FROM medical_record_entries WHERE clinic_id = %s""",
                (clinic_id,),
            )
            mre = cursor.fetchone()
            checks.append({
                "category": "documentacao",
                "name": "Prontuarios com avaliacao clinica",
                "status": "ok" if (mre["total"] or 0) == 0 or mre["complete"] == mre["total"] else "warning",
                "detail": f"{mre['complete']}/{mre['total']} entradas com avaliacao",
            })

            # Overall score
            ok_count = sum(1 for c in checks if c["status"] == "ok")
            score = round(ok_count / len(checks) * 100) if checks else 0

            return _success({
                "score": score,
                "checks": checks,
                "total_checks": len(checks),
                "passed": ok_count,
            })
    except Exception:
        logger.error("Error generating compliance report", exc_info=True)
        return _success({"score": 0, "checks": [], "total_checks": 0, "passed": 0})
