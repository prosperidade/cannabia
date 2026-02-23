from flask import g
from src.infra.database import db_cursor


def _get_clinic_id():
    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        raise RuntimeError("clinic_id não encontrado no contexto da request")
    return clinic_id


def get_dashboard_metrics():

    clinic_id = _get_clinic_id()

    with db_cursor(dictionary=True) as (_, cursor):

        # Total mensagens
        cursor.execute(
            "SELECT COUNT(*) AS total_messages FROM incoming_messages WHERE clinic_id = %s",
            (clinic_id,),
        )
        total_messages = cursor.fetchone()["total_messages"]

        # Total pacientes
        cursor.execute(
            "SELECT COUNT(*) AS total_patients FROM patients WHERE clinic_id = %s",
            (clinic_id,),
        )
        total_patients = cursor.fetchone()["total_patients"]

        # Total appointments
        cursor.execute(
            "SELECT COUNT(*) AS total_appointments FROM appointments WHERE clinic_id = %s",
            (clinic_id,),
        )
        total_appointments = cursor.fetchone()["total_appointments"]

        # Total execuções IA
        cursor.execute(
            "SELECT COUNT(*) AS total_ai FROM ai_audit_logs WHERE clinic_id = %s",
            (clinic_id,),
        )
        total_ai = cursor.fetchone()["total_ai"]

        return {
            "total_messages": total_messages,
            "total_patients": total_patients,
            "total_appointments": total_appointments,
            "total_ai": total_ai,
        }