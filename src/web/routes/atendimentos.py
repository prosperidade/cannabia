# src/web/routes/atendimentos.py
from flask import Blueprint, abort, redirect, render_template, request, g, url_for
from src.infra.security import role_required
from src.repositories.anamnesis_repository import get_report, list_reports, mark_reviewed
from src.repositories.patient_timeline_repository import create_event, list_patient_events
from src.web.routes.auth import generate_csrf_token, validate_csrf_from_form

atendimentos_bp = Blueprint("atendimentos", __name__)


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
    if report.get("patient_id"):
        timeline_events = list_patient_events(g.clinic_id, report["patient_id"], limit=20)
    return render_template(
        "atendimentos_detail.html",
        report=report,
        timeline_events=timeline_events,
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
