from flask import Blueprint, render_template
from flask_login import login_required

from src.repositories.ai_audit_repository import (
    get_ai_audit_summary,
    get_recent_ai_logs,
)

ai_admin_bp = Blueprint("ai_admin_bp", __name__)


@ai_admin_bp.route("/admin/ai-metrics")
@login_required
def ai_metrics():

    summary = get_ai_audit_summary()
    recent_logs = get_recent_ai_logs(10)

    total_requests = summary.get("total_requests") or 0
    total_tokens = summary.get("total_tokens") or 0
    total_cost = summary.get("total_cost_usd") or 0

    avg_cost = 0
    if total_requests > 0:
        avg_cost = total_cost / total_requests

    return render_template(
        "ai_metrics.html",
        total_requests=total_requests,
        total_tokens=total_tokens,
        total_cost=round(total_cost, 6),
        avg_cost=round(avg_cost, 6),
        recent_logs=recent_logs,
    )
