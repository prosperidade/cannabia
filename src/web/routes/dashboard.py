from flask import Blueprint, render_template, request, g
from flask_login import login_required

from src.infra.security import role_required
from src.repositories import message_repository
from src.repositories.ai_audit_repository import (
    get_recent_ai_logs,
)
from src.repositories.dashboard_repository import get_dashboard_metrics

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET"])
@login_required
@role_required("Admin", "Medico")
def dashboard():

    clinic_id = g.clinic_id
    sender_filter = request.args.get("sender")

    metrics = get_dashboard_metrics()

    messages = message_repository.list_messages(clinic_id, sender_filter)
    agg_data = message_repository.aggregate_messages_by_contact(clinic_id)
    agg_time_data = message_repository.aggregate_messages_by_day(clinic_id)

    logs = get_recent_ai_logs()

    labels = [row["contact_name"] for row in agg_data]
    counts = [row["message_count"] for row in agg_data]
    line_labels = [str(row["message_date"]) for row in agg_time_data]
    line_data = [row["total_messages"] for row in agg_time_data]

    return render_template(
        "dashboard.html",
        metrics=metrics,
        messages=messages,
        logs=logs,
        sender_filter=sender_filter,
        labels=labels,
        counts=counts,
        line_labels=line_labels,
        line_data=line_data,
    )