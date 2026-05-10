# src/web/routes/clinical_intelligence.py
"""
Clinical Intelligence API (advanced medical pages).
Prefix: /api/v1/clinical
"""
from __future__ import annotations
import logging
from flask import Blueprint, g, request
from src.infra.database import db_cursor
from src.web.routes.api_v1 import _success, api_role_required

logger = logging.getLogger("cannabia.clinical_intelligence")
clinical_intel_bp = Blueprint("clinical_intelligence", __name__, url_prefix="/api/v1/clinical")


@clinical_intel_bp.get("/intelligence")
@api_role_required("Admin", "Medico")
def intelligence_dashboard():
    """AI intelligence dashboard — aggregated AI usage and outcomes."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            clinic_id = g.clinic_id

            # AI usage stats
            cursor.execute(
                """SELECT COUNT(*) AS total_analyses,
                          COALESCE(AVG(total_time_ms), 0) AS avg_latency_ms,
                          COALESCE(SUM(total_tokens), 0) AS total_tokens,
                          COALESCE(SUM(estimated_cost_usd), 0) AS total_cost_usd,
                          COUNT(DISTINCT patient_id) AS patients_analyzed
                   FROM ai_audit_logs WHERE clinic_id = %s""",
                (clinic_id,),
            )
            stats = cursor.fetchone()

            # By model
            cursor.execute(
                """SELECT model, COUNT(*) AS count, COALESCE(AVG(total_time_ms), 0) AS avg_ms
                   FROM ai_audit_logs WHERE clinic_id = %s AND model IS NOT NULL
                   GROUP BY model ORDER BY count DESC""",
                (clinic_id,),
            )
            by_model = cursor.fetchall()

            # Recent executions
            cursor.execute(
                """SELECT id, patient_id, model, status, total_time_ms, total_tokens,
                          estimated_cost_usd, created_at
                   FROM ai_audit_logs WHERE clinic_id = %s
                   ORDER BY created_at DESC LIMIT 20""",
                (clinic_id,),
            )
            recent = cursor.fetchall()

            # Conditions from anamnesis
            cursor.execute(
                """SELECT anamnesis_data->>'chief_complaint' AS condition, COUNT(*) AS count
                   FROM anamnesis_reports WHERE clinic_id = %s
                     AND anamnesis_data->>'chief_complaint' IS NOT NULL
                   GROUP BY 1 ORDER BY count DESC LIMIT 10""",
                (clinic_id,),
            )
            top_conditions = cursor.fetchall()

            return _success({
                "stats": stats,
                "by_model": by_model,
                "recent_executions": recent,
                "top_conditions": top_conditions,
            })
    except Exception:
        logger.error("Error fetching intelligence data", exc_info=True)
        # FIXME(sprint-2): decidir entre 500 explicito vs empty data conforme
        # contrato com frontend (ver Track D do Sprint 1).
        return _success({"stats": {}, "by_model": [], "recent_executions": [], "top_conditions": []})


@clinical_intel_bp.get("/botanical")
@api_role_required("Admin", "Medico")
def botanical_analysis():
    """Botanical/cultivar analysis — prescription patterns."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            clinic_id = g.clinic_id

            # Prescription patterns
            cursor.execute(
                """SELECT cannabinoid_ratio, spectrum, administration_route,
                          COUNT(*) AS count,
                          AVG(concentration_mg_ml) AS avg_concentration,
                          AVG(max_daily_mg) AS avg_daily_mg
                   FROM prescriptions WHERE clinic_id = %s
                   GROUP BY cannabinoid_ratio, spectrum, administration_route
                   ORDER BY count DESC LIMIT 10""",
                (clinic_id,),
            )
            patterns = cursor.fetchall()

            # Top ratios
            cursor.execute(
                """SELECT cannabinoid_ratio, COUNT(*) AS count
                   FROM prescriptions WHERE clinic_id = %s AND cannabinoid_ratio IS NOT NULL
                   GROUP BY 1 ORDER BY count DESC LIMIT 5""",
                (clinic_id,),
            )
            top_ratios = cursor.fetchall()

            # Prescriptions with evidence
            cursor.execute(
                """SELECT id, cannabinoid_ratio, spectrum, administration_route,
                          confidence_score, evidence_sources, clinical_rationale, created_at
                   FROM prescriptions WHERE clinic_id = %s
                   ORDER BY created_at DESC LIMIT 10""",
                (clinic_id,),
            )
            recent_prescriptions = cursor.fetchall()

            return _success({
                "patterns": patterns,
                "top_ratios": top_ratios,
                "recent_prescriptions": recent_prescriptions,
            })
    except Exception:
        logger.error("Error fetching botanical data", exc_info=True)
        # FIXME(sprint-2): decidir entre 500 explicito vs empty data conforme
        # contrato com frontend (ver Track D do Sprint 1).
        return _success({"patterns": [], "top_ratios": [], "recent_prescriptions": []})


@clinical_intel_bp.get("/lab")
@api_role_required("Admin", "Medico")
def lab_analysis():
    """Lab AI analysis — patient clinical data aggregation."""
    patient_id = request.args.get("patient_id", type=int)

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            clinic_id = g.clinic_id

            if patient_id:
                # Specific patient analysis
                cursor.execute(
                    "SELECT id, name, phone, email, status, created_at FROM patients WHERE id = %s AND clinic_id = %s",
                    (patient_id, clinic_id),
                )
                patient = cursor.fetchone()

                cursor.execute(
                    """SELECT cannabinoid_ratio, concentration_mg_ml, max_daily_mg,
                              administration_route, confidence_score, drug_interactions,
                              contraindications, evidence_sources
                       FROM prescriptions WHERE patient_id = %s AND clinic_id = %s
                       ORDER BY created_at DESC LIMIT 1""",
                    (patient_id, clinic_id),
                )
                prescription = cursor.fetchone()

                cursor.execute(
                    """SELECT AVG(pain_level) AS avg_pain, AVG(sleep_quality) AS avg_sleep,
                              AVG(overall_score) AS avg_overall
                       FROM symptom_diary WHERE patient_id = %s AND clinic_id = %s""",
                    (patient_id, clinic_id),
                )
                diary_stats = cursor.fetchone()

                return _success({
                    "patient": patient,
                    "prescription": prescription,
                    "diary_stats": diary_stats,
                })

            # General lab stats
            cursor.execute(
                """SELECT COUNT(DISTINCT patient_id) AS patients_with_prescriptions
                   FROM prescriptions WHERE clinic_id = %s""",
                (clinic_id,),
            )
            stats = cursor.fetchone()

            return _success({"stats": stats})
    except Exception:
        logger.error("Error fetching lab data", exc_info=True)
        # FIXME(sprint-2): decidir entre 500 explicito vs empty data conforme
        # contrato com frontend (ver Track D do Sprint 1).
        return _success({"patient": None, "prescription": None, "diary_stats": None})


@clinical_intel_bp.get("/trials")
@api_role_required("Admin", "Medico")
def clinical_trials():
    """Clinical trials / research data — treatment outcomes aggregation."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            clinic_id = g.clinic_id

            # Treatment outcomes by plan
            cursor.execute(
                """SELECT tp.plan_name, tp.cbd_thc_ratio, tp.dosage,
                          COUNT(DISTINCT tp.patient_id) AS patient_count,
                          AVG(sd.overall_score) AS avg_outcome,
                          AVG(sd.pain_level) AS avg_pain_reduction
                   FROM treatment_plans tp
                   LEFT JOIN symptom_diary sd ON sd.patient_id = tp.patient_id AND sd.clinic_id = tp.clinic_id
                   WHERE tp.clinic_id = %s
                   GROUP BY tp.plan_name, tp.cbd_thc_ratio, tp.dosage
                   ORDER BY patient_count DESC""",
                (clinic_id,),
            )
            outcomes = cursor.fetchall()

            # Overall stats
            cursor.execute(
                """SELECT COUNT(DISTINCT patient_id) AS total_patients,
                          COUNT(*) AS total_plans
                   FROM treatment_plans WHERE clinic_id = %s""",
                (clinic_id,),
            )
            stats = cursor.fetchone()

            return _success({
                "outcomes": outcomes,
                "stats": stats,
            })
    except Exception:
        logger.error("Error fetching trials data", exc_info=True)
        # FIXME(sprint-2): decidir entre 500 explicito vs empty data conforme
        # contrato com frontend (ver Track D do Sprint 1).
        return _success({"outcomes": [], "stats": {"total_patients": 0, "total_plans": 0}})
