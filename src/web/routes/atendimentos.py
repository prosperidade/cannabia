# src/web/routes/atendimentos.py
from flask import Blueprint, abort, flash, redirect, render_template, request, g, url_for
from flask_login import current_user
from src.infra.security import role_required
from src.repositories.anamnesis_repository import get_report, list_reports, mark_reviewed
from src.repositories.medical_record_repository import (
    get_consultation_entry_by_report,
    list_patient_record_entries,
    upsert_consultation_entry,
)
from src.repositories.patient_timeline_repository import create_event, list_patient_events
from src.web.routes.auth import generate_csrf_token, validate_csrf_from_form

atendimentos_bp = Blueprint("atendimentos", __name__)


def _parse_requested_exams(raw_text: str) -> list[str]:
    return [item.strip() for item in (raw_text or "").replace("\r", "").replace("\n", ",").split(",") if item.strip()]


@atendimentos_bp.route("/atendimentos")
@role_required("Admin", "Medico")
def lista():
    status = request.args.get("status") or None
    reports = list_reports(g.clinic_id, status=status)
    total   = list_reports(g.clinic_id)
    pending = [r for r in total if r["status"] == "pendente"]
    return render_template(
        "atendimentos_list.html",
        reports=reports,
        status_filter=status,
        total_count=len(total),
        pending_count=len(pending),
    )


@atendimentos_bp.route("/atendimentos/<int:report_id>")
@role_required("Admin", "Medico")
def detalhe(report_id):
    report = get_report(g.clinic_id, report_id)
    if not report:
        abort(404)
    timeline_events = []
    medical_record_entries = []
    clinical_entry = None
    if report.get("patient_id"):
        timeline_events = list_patient_events(g.clinic_id, report["patient_id"], limit=20)
        medical_record_entries = list_patient_record_entries(g.clinic_id, report["patient_id"], limit=10)
        clinical_entry = get_consultation_entry_by_report(g.clinic_id, report_id)
    return render_template(
        "atendimentos_detail.html",
        report=report,
        timeline_events=timeline_events,
        medical_record_entries=medical_record_entries,
        clinical_entry=clinical_entry,
        csrf_token=generate_csrf_token(),
    )


@atendimentos_bp.route("/atendimentos/<int:report_id>/revisar", methods=["POST"])
@role_required("Admin", "Medico")
def revisar(report_id):
    if not validate_csrf_from_form():
        return "CSRF inválido.", 400

    report = get_report(g.clinic_id, report_id)
    if not report:
        abort(404)

    if report.get("status") != "revisado":
        mark_reviewed(g.clinic_id, report_id)
        if report.get("patient_id"):
            create_event(
                clinic_id=g.clinic_id,
                tenant_id=getattr(g, "tenant_id", None),
                patient_id=report["patient_id"],
                event_type="anamnesis_reviewed",
                journey_stage="caso_revisado",
                title="Atendimento revisado pelo médico",
                description="O relatório da anamnese foi validado e arquivado no painel clínico.",
                source_type="anamnesis_report",
                source_id=report_id,
                metadata={"status": "revisado"},
            )
    return redirect(url_for("atendimentos.detalhe", report_id=report_id))


@atendimentos_bp.route("/atendimentos/<int:report_id>/prontuario", methods=["POST"])
@role_required("Admin", "Medico")
def salvar_prontuario(report_id):
    if not validate_csrf_from_form():
        return "CSRF inválido.", 400

    report = get_report(g.clinic_id, report_id)
    if not report:
        abort(404)

    patient_id = report.get("patient_id")
    if not patient_id:
        flash("Este atendimento ainda não possui paciente vinculado para prontuário.", "error")
        return redirect(url_for("atendimentos.detalhe", report_id=report_id))

    consultation_status = (request.form.get("consultation_status") or "em_revisao").strip()
    medical_observations = (request.form.get("medical_observations") or "").strip()
    clinical_assessment = (request.form.get("clinical_assessment") or "").strip()
    conduct = (request.form.get("conduct") or "").strip()
    follow_up_plan = (request.form.get("follow_up_plan") or "").strip()
    requested_exams = _parse_requested_exams(request.form.get("requested_exams") or "")

    if not any([medical_observations, clinical_assessment, conduct, follow_up_plan, requested_exams]):
        flash("Preencha pelo menos um campo clínico antes de salvar o prontuário.", "error")
        return redirect(url_for("atendimentos.detalhe", report_id=report_id))

    result = upsert_consultation_entry(
        clinic_id=g.clinic_id,
        tenant_id=getattr(g, "tenant_id", None),
        patient_id=patient_id,
        author_user_id=int(current_user.id),
        author_name=getattr(current_user, "username", "medico"),
        source_report_id=report_id,
        consultation_status=consultation_status,
        medical_observations=medical_observations,
        clinical_assessment=clinical_assessment,
        conduct=conduct,
        requested_exams=requested_exams,
        follow_up_plan=follow_up_plan,
    )

    if not result["enabled"]:
        flash("O schema de prontuário ainda não foi aplicado no banco local.", "error")
        return redirect(url_for("atendimentos.detalhe", report_id=report_id))

    if consultation_status == "consulta_nao_realizada":
        event_type = "consultation_not_completed"
        journey_stage = "ausencia_em_consulta"
        title = "Consulta não realizada"
        description = "A consulta não foi concluída e o caso permanece em acompanhamento operacional."
    elif result["created"]:
        event_type = "conduct_registered"
        journey_stage = "conduta_registrada"
        title = "Conduta clínica registrada"
        description = "O médico registrou a decisão clínica inicial no prontuário."
    else:
        event_type = "medical_record_updated"
        journey_stage = "prontuario_atualizado"
        title = "Prontuário atualizado"
        description = "A entrada clínica vinculada ao caso foi atualizada."

    create_event(
        clinic_id=g.clinic_id,
        tenant_id=getattr(g, "tenant_id", None),
        patient_id=patient_id,
        event_type=event_type,
        journey_stage=journey_stage,
        title=title,
        description=description,
        source_type="medical_record_entry",
        source_id=result["entry_id"],
        metadata={
            "consultation_status": consultation_status,
            "requested_exams_count": len(requested_exams),
        },
    )
    flash("Registro clínico salvo no prontuário longitudinal.", "success")
    return redirect(url_for("atendimentos.detalhe", report_id=report_id))
