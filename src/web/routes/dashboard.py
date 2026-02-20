# src/web/routes/dashboard.py
from flask import Blueprint, render_template, request
from flask_login import login_required

from src.infra.security import role_required
from src.repositories import message_repository
from src.repositories.ai_audit_repository import (
    get_ai_audit_summary,
    get_recent_ai_logs,
)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET"])
@login_required
@role_required("Admin", "Medico")
def dashboard():
    sender_filter = request.args.get("sender")

    try:
        message_repository.ensure_message_tables()
        messages = message_repository.list_messages(sender_filter)
        agg_data = message_repository.aggregate_messages_by_contact()
        agg_time_data = message_repository.aggregate_messages_by_day()

        labels = [row["contact_name"] for row in agg_data]
        counts = [row["message_count"] for row in agg_data]
        line_labels = [str(row["message_date"]) for row in agg_time_data]
        line_data = [row["total_messages"] for row in agg_time_data]

        return render_template(
            "dashboard.html",
            messages=messages,
            sender_filter=sender_filter,
            labels=labels,
            counts=counts,
            line_labels=line_labels,
            line_data=line_data,
        )

    except Exception as e:
        return f"Erro ao acessar o dashboard: {e}", 500


@dashboard_bp.route("/ai-audit", methods=["GET"])
@login_required
@role_required("Admin", "Medico")
def ai_audit_dashboard():
    summary = get_ai_audit_summary()
    logs = get_recent_ai_logs()

    return render_template(
        "ai_audit_dashboard.html",
        summary=summary,
        logs=logs,
    )
