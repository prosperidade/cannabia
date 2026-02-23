# src/web/routes/atendimentos.py
from flask import Blueprint, abort, redirect, render_template, request, g, url_for
from src.infra.security import role_required
from src.repositories.anamnesis_repository import get_report, list_reports, mark_reviewed

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
    return render_template("atendimentos_detail.html", report=report)


@atendimentos_bp.route("/atendimentos/<int:report_id>/revisar", methods=["POST"])
@role_required("Admin", "Medico")
def revisar(report_id):
    mark_reviewed(g.clinic_id, report_id)
    return redirect(url_for("atendimentos.detalhe", report_id=report_id))
