# src/web/routes/org_management.py
"""
Organization management API endpoints.
Prefix: /api/v1/org
"""

from __future__ import annotations

import logging
from flask import Blueprint, g, request
from flask_login import current_user
from psycopg2 import DatabaseError, OperationalError

from src.infra.database import db_cursor
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _paginate,
    _pagination_args,
    _require_json_csrf,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.org_management")

org_management_bp = Blueprint("org_management", __name__, url_prefix="/api/v1/org")
FINANCIAL_ROLES = ("Admin", "AdminClinica", "Financeiro")
OPERATION_ROLES = ("Admin", "AdminClinica", "Medico", "Recepcao")


# ==================================================================
# GET /api/v1/org/dashboard
# ==================================================================
#
# Shape esperada pelo frontend (frontend/app/org/dashboard/page.tsx):
#   {
#     kpiData:        [{icon, label, value, delta, deltaType}],
#     chartConsultas: [{month, novo, retorno}],
#     chartReceita:   [{month, value}],   # value em R$ mil
#     topMedicos:     [{name, specialty, count, rating}],
#     recentActivity: [{icon, text, time, tone}]
#   }
#
# Fontes ja disponiveis: patients, anamnesis_reports, billing, adverse_events,
# users, ai_audit_logs. Top medicos fica vazio ate anamnesis_reports.doctor_id
# existir (TODO).

PT_MONTH_ABBR = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _format_delta(current: float, previous: float) -> tuple[str, str]:
    """Calcula delta percentual e retorna (texto, deltaType)."""
    if previous in (0, 0.0, None):
        if current > 0:
            return ("novo", "up")
        return ("0%", "neutral")
    pct = round(((current - previous) / previous) * 100)
    if pct > 0:
        return (f"+{pct}%", "up")
    if pct < 0:
        return (f"{pct}%", "down")
    return ("0%", "neutral")


def _format_brl_compact(value: float) -> str:
    if value >= 1_000_000:
        return f"R$ {value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"R$ {value / 1_000:.1f}k"
    return f"R$ {value:.0f}"


# Mapa de endpoint do ai_audit_logs -> mensagem amigavel + icone + tone.
AUDIT_ACTIVITY_MAP = {
    "/api/v1/triage": ("vaccines", "Triagem concluida", "primary"),
    "anamnese": ("psychology", "Anamnese processada", "primary"),
    "tratamento": ("medication", "Plano de tratamento gerado", "success"),
    "cientifico": ("science", "Relatorio cientifico gerado", "info"),
    "regulator": ("policy", "Validacao regulatoria executada", "info"),
    "follow": ("schedule", "Follow-up enviado", "primary"),
    "knowledge": ("library_books", "Base cientifica atualizada", "info"),
    "vigimed": ("warning", "Notificacao de farmacovigilancia", "danger"),
    "anvisa": ("warning", "Notificacao ANVISA", "danger"),
}


def _classify_audit_endpoint(endpoint: str) -> tuple[str, str, str]:
    e = (endpoint or "").lower()
    for needle, payload in AUDIT_ACTIVITY_MAP.items():
        if needle in e:
            return payload
    return ("bolt", "Acao do agente IA", "primary")


def _humanize_age(seconds: int) -> str:
    if seconds < 60:
        return "agora ha pouco"
    if seconds < 3600:
        return f"ha {seconds // 60} min"
    if seconds < 86400:
        return f"ha {seconds // 3600} h"
    days = seconds // 86400
    return f"ha {days} d" if days > 1 else "ontem"


@org_management_bp.get("/dashboard")
@api_role_required("Admin", "AdminClinica", "Medico", "Recepcao", "Financeiro")
def org_dashboard():
    """KPIs, charts, top medicos e atividade recente — todos com dados reais.

    Campos sem fonte real ainda (rating de medico, count de consultas por
    medico) sao retornados como None e o frontend ja tem fallback de
    'Dados de desempenho serao exibidos quando houver atendimentos
    suficientes' para a tabela.
    """
    clinic_id = g.clinic_id

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            # ── KPIs do mes corrente vs mes anterior ──
            cursor.execute(
                """
                SELECT COUNT(*) AS cnt FROM patients
                WHERE clinic_id = %s
                """,
                (clinic_id,),
            )
            patients_active = cursor.fetchone()["cnt"]

            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE created_at >= date_trunc('month', CURRENT_DATE))           AS this_month,
                    COUNT(*) FILTER (WHERE created_at >= date_trunc('month', CURRENT_DATE) - INTERVAL '1 month'
                                       AND created_at <  date_trunc('month', CURRENT_DATE))           AS last_month
                FROM patients WHERE clinic_id = %s
                """,
                (clinic_id,),
            )
            new_patients = cursor.fetchone()
            new_patients_this = new_patients["this_month"]
            new_patients_last = new_patients["last_month"]

            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE created_at >= date_trunc('month', CURRENT_DATE))           AS this_month,
                    COUNT(*) FILTER (WHERE created_at >= date_trunc('month', CURRENT_DATE) - INTERVAL '1 month'
                                       AND created_at <  date_trunc('month', CURRENT_DATE))           AS last_month
                FROM anamnesis_reports WHERE clinic_id = %s
                """,
                (clinic_id,),
            )
            consults = cursor.fetchone()
            consults_this = consults["this_month"]
            consults_last = consults["last_month"]

            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(amount) FILTER (WHERE created_at >= date_trunc('month', CURRENT_DATE)
                                              AND status = 'pago'), 0)        AS this_month,
                    COALESCE(SUM(amount) FILTER (WHERE created_at >= date_trunc('month', CURRENT_DATE) - INTERVAL '1 month'
                                              AND created_at <  date_trunc('month', CURRENT_DATE)
                                              AND status = 'pago'), 0)        AS last_month
                FROM billing WHERE clinic_id = %s
                """,
                (clinic_id,),
            )
            revenue = cursor.fetchone()
            revenue_this = float(revenue["this_month"])
            revenue_last = float(revenue["last_month"])

            cursor.execute(
                """
                SELECT
                    (SELECT clinics.tenant_id FROM clinics WHERE clinics.id = %s) AS tenant_id
                """,
                (clinic_id,),
            )
            tenant_row = cursor.fetchone()
            tenant_id = tenant_row["tenant_id"] if tenant_row else None

            adverse_events_open = 0
            if tenant_id is not None:
                cursor.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM adverse_events
                    WHERE tenant_id = %s AND outcome IS NULL
                    """,
                    (tenant_id,),
                )
                adverse_events_open = cursor.fetchone()["cnt"]

            # Delta de pacientes ativos: comparar contagem atual com NOW() - 1 month
            cursor.execute(
                """
                SELECT COUNT(*) AS cnt FROM patients
                WHERE clinic_id = %s AND created_at < date_trunc('month', CURRENT_DATE)
                """,
                (clinic_id,),
            )
            patients_active_last = cursor.fetchone()["cnt"]

            kpi_data = [
                {
                    "icon": "groups",
                    "label": "Pacientes ativos",
                    "value": str(patients_active),
                    **dict(zip(("delta", "deltaType"), _format_delta(patients_active, patients_active_last))),
                },
                {
                    "icon": "person_add",
                    "label": "Novos pacientes",
                    "value": str(new_patients_this),
                    **dict(zip(("delta", "deltaType"), _format_delta(new_patients_this, new_patients_last))),
                },
                {
                    "icon": "event",
                    "label": "Consultas no mes",
                    "value": str(consults_this),
                    **dict(zip(("delta", "deltaType"), _format_delta(consults_this, consults_last))),
                },
                {
                    "icon": "payments",
                    "label": "Receita no mes",
                    "value": _format_brl_compact(revenue_this),
                    **dict(zip(("delta", "deltaType"), _format_delta(revenue_this, revenue_last))),
                },
                {
                    "icon": "warning",
                    "label": "Eventos adversos abertos",
                    "value": str(adverse_events_open),
                    "delta": "monitor",
                    "deltaType": "neutral",
                },
            ]

            # ── chartConsultas: 6 meses, novo vs retorno ──
            cursor.execute(
                """
                WITH first_anamnesis AS (
                    SELECT patient_id, MIN(date_trunc('month', created_at)) AS first_month
                    FROM anamnesis_reports
                    WHERE clinic_id = %(clinic)s AND patient_id IS NOT NULL
                    GROUP BY patient_id
                ),
                months AS (
                    SELECT generate_series(
                        date_trunc('month', CURRENT_DATE) - INTERVAL '5 months',
                        date_trunc('month', CURRENT_DATE),
                        INTERVAL '1 month'
                    )::date AS month_start
                )
                SELECT
                    m.month_start,
                    COUNT(*) FILTER (WHERE fa.first_month = m.month_start) AS novo,
                    COUNT(*) FILTER (WHERE fa.first_month <> m.month_start OR fa.first_month IS NULL) AS retorno
                FROM months m
                LEFT JOIN anamnesis_reports a
                    ON date_trunc('month', a.created_at) = m.month_start
                    AND a.clinic_id = %(clinic)s
                LEFT JOIN first_anamnesis fa ON a.patient_id = fa.patient_id
                GROUP BY m.month_start
                ORDER BY m.month_start
                """,
                {"clinic": clinic_id},
            )
            consult_rows = cursor.fetchall()
            max_count = max((r["novo"] + r["retorno"] for r in consult_rows), default=0) or 1
            chart_consultas = [
                {
                    "month": PT_MONTH_ABBR[r["month_start"].month - 1],
                    # Frontend escala height: %, entao mandamos 0-100.
                    "novo": int(round((r["novo"] / max_count) * 90)),
                    "retorno": int(round((r["retorno"] / max_count) * 90)),
                }
                for r in consult_rows
            ]

            # ── chartReceita: 6 meses em R$ mil ──
            cursor.execute(
                """
                WITH months AS (
                    SELECT generate_series(
                        date_trunc('month', CURRENT_DATE) - INTERVAL '5 months',
                        date_trunc('month', CURRENT_DATE),
                        INTERVAL '1 month'
                    )::date AS month_start
                )
                SELECT m.month_start,
                       COALESCE(SUM(b.amount) FILTER (WHERE b.status = 'pago'), 0) AS total
                FROM months m
                LEFT JOIN billing b
                    ON date_trunc('month', b.created_at) = m.month_start
                    AND b.clinic_id = %s
                GROUP BY m.month_start
                ORDER BY m.month_start
                """,
                (clinic_id,),
            )
            revenue_rows = cursor.fetchall()
            chart_receita = [
                {
                    "month": PT_MONTH_ABBR[r["month_start"].month - 1],
                    "value": round(float(r["total"]) / 1000, 1),
                }
                for r in revenue_rows
            ]

            # ── topMedicos: lista de medicos do tenant.
            # TODO: schema atual nao tem doctor_id em anamnesis_reports —
            # count e rating viram None ate sprint dedicada de attendances.
            top_medicos: list[dict] = []
            if tenant_id is not None:
                cursor.execute(
                    """
                    SELECT u.id, u.username AS name
                    FROM users u
                    JOIN user_clinics uc ON uc.user_id = u.id
                    JOIN clinics c ON c.id = uc.clinic_id
                    WHERE c.tenant_id = %s
                      AND u.role = 'Medico'
                      AND u.is_active = TRUE
                    GROUP BY u.id, u.username
                    ORDER BY u.username
                    LIMIT 5
                    """,
                    (tenant_id,),
                )
                top_medicos = [
                    {
                        "name": row["name"],
                        "specialty": "Cannabis Medicinal",
                        "count": 0,
                        "rating": None,
                    }
                    for row in cursor.fetchall()
                ]

            # ── recentActivity: ultimas 8 entradas em ai_audit_logs do tenant ──
            cursor.execute(
                """
                SELECT a.endpoint, a.created_at
                FROM ai_audit_logs a
                JOIN clinics c ON c.id = a.clinic_id
                WHERE c.tenant_id = %s
                ORDER BY a.created_at DESC
                LIMIT 8
                """,
                (tenant_id,) if tenant_id is not None else (-1,),
            )
            activity_rows = cursor.fetchall() if tenant_id is not None else []
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            recent_activity = []
            for row in activity_rows:
                icon, text, tone = _classify_audit_endpoint(row["endpoint"] or "")
                created = row["created_at"]
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age_seconds = int((now - created).total_seconds())
                recent_activity.append({
                    "icon": icon,
                    "text": text,
                    "time": _humanize_age(age_seconds),
                    "tone": tone,
                })

            return _success({
                "kpiData": kpi_data,
                "chartConsultas": chart_consultas,
                "chartReceita": chart_receita,
                "topMedicos": top_medicos,
                "recentActivity": recent_activity,
            })
    except OperationalError:
        logger.error("DB unavailable on org_management.org_dashboard", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, RuntimeError, TypeError, ValueError, KeyError, AttributeError):
        logger.error("Unexpected error on org_management.org_dashboard", exc_info=True)
        return _error("internal_error", "Erro interno ao processar requisicao.", 500)


# ==================================================================
# GET /api/v1/org/patients
# ==================================================================

@org_management_bp.get("/patients")
@api_role_required(*OPERATION_ROLES)
def org_patients():
    """List all patients for the organization with search and pagination."""
    page, page_size = _pagination_args()
    search = (request.args.get("search") or "").strip()
    status_filter = (request.args.get("status") or "").strip()

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            where_clauses = ["clinic_id = %s"]
            params: list = [g.clinic_id]

            if search:
                where_clauses.append("(name ILIKE %s OR phone ILIKE %s OR email ILIKE %s)")
                like = f"%{search}%"
                params.extend([like, like, like])

            if status_filter:
                where_clauses.append("status = %s")
                params.append(status_filter)

            where_sql = " AND ".join(where_clauses)

            cursor.execute(
                f"""
                SELECT id, name, phone, email, status, created_at
                FROM patients
                WHERE {where_sql}
                ORDER BY name ASC
                """,
                tuple(params),
            )
            rows = cursor.fetchall()
            items, meta = _paginate(rows, page, page_size)
            return _success(items, meta=meta)
    except OperationalError:
        logger.error("DB unavailable on org_management.org_patients", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, RuntimeError, TypeError, ValueError, KeyError):
        logger.error("Unexpected error on org_management.org_patients", exc_info=True)
        return _error("internal_error", "Erro interno ao processar requisicao.", 500)


# ==================================================================
# GET /api/v1/org/doctors
# ==================================================================

@org_management_bp.get("/doctors")
@api_role_required(*OPERATION_ROLES)
def org_doctors():
    """List doctors for the organization."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT u.id, u.username AS name, u.role,
                       cm.clinic_role, cm.created_at AS joined_at
                FROM users u
                JOIN clinic_members cm ON cm.user_id = u.id
                WHERE cm.clinic_id = %s
                  AND (cm.clinic_role = 'Medico' OR u.role = 'Medico')
                ORDER BY u.username
                """,
                (g.clinic_id,),
            )
            doctors = cursor.fetchall()
            return _success(doctors)
    except OperationalError:
        logger.error("DB unavailable on org_management.org_doctors", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, RuntimeError, TypeError, ValueError, KeyError):
        logger.error("Unexpected error on org_management.org_doctors", exc_info=True)
        return _error("internal_error", "Erro interno ao processar requisicao.", 500)


# ==================================================================
# GET /api/v1/org/stock
# ==================================================================

@org_management_bp.get("/stock")
@api_role_required(*FINANCIAL_ROLES)
def org_stock():
    """Stock inventory listing."""
    page, page_size = _pagination_args()
    search = (request.args.get("search") or "").strip()

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT id, product_name, batch_number, quantity, unit,
                       expiry_date, status, supplier, created_at
                FROM stock_inventory
                WHERE clinic_id = %s
                ORDER BY product_name, expiry_date
                """,
                (g.clinic_id,),
            )
            rows = cursor.fetchall()
            if search:
                rows = [r for r in rows if search.lower() in (r.get("product_name") or "").lower()]
            items, meta = _paginate(rows, page, page_size)
            return _success(items, meta=meta)
    except OperationalError:
        logger.error("DB unavailable on org_management.org_stock", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, RuntimeError, TypeError, ValueError, KeyError):
        logger.error("Unexpected error on org_management.org_stock", exc_info=True)
        return _error("internal_error", "Erro interno ao processar requisicao.", 500)


# ==================================================================
# POST /api/v1/org/stock/entry
# ==================================================================

@org_management_bp.post("/stock/entry")
@api_role_required(*FINANCIAL_ROLES)
def org_stock_entry():
    """Register a stock entry."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()

    product_name = (payload.get("product_name") or "").strip()
    batch_number = (payload.get("batch_number") or "").strip()
    quantity = payload.get("quantity")
    unit = (payload.get("unit") or "frascos").strip()
    expiry_date = (payload.get("expiry_date") or "").strip()
    supplier = (payload.get("supplier") or "").strip()

    if not product_name or quantity is None:
        return _error("validation_error", "product_name e quantity sao obrigatorios.", 422)

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return _error("validation_error", "quantity deve ser um numero inteiro.", 422)

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute(
                """
                INSERT INTO stock_inventory
                    (clinic_id, product_name, batch_number, quantity, unit,
                     expiry_date, status, supplier, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'disponivel', %s, NOW())
                RETURNING id, created_at
                """,
                (
                    g.clinic_id,
                    product_name,
                    batch_number,
                    quantity,
                    unit,
                    expiry_date or None,
                    supplier,
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return _success({"id": row["id"], "created_at": row["created_at"]}, status=201)
    except OperationalError:
        logger.error("DB unavailable on org_management.org_stock_entry", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, RuntimeError, TypeError, ValueError, KeyError):
        logger.error("Failed to insert stock entry", exc_info=True)
        return _error("internal_error", "Falha ao registrar entrada de estoque.", 500)


# ==================================================================
# POST /api/v1/org/stock/dispensation
# ==================================================================

@org_management_bp.post("/stock/dispensation")
@api_role_required(*FINANCIAL_ROLES)
def org_stock_dispensation():
    """Register a stock dispensation to a patient."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()

    stock_item_id = payload.get("stock_item_id")
    patient_id = payload.get("patient_id")
    quantity = payload.get("quantity")
    notes = (payload.get("notes") or "").strip()

    if not stock_item_id or not patient_id or quantity is None:
        return _error("validation_error", "stock_item_id, patient_id e quantity sao obrigatorios.", 422)

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return _error("validation_error", "quantity deve ser um numero inteiro.", 422)

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            # Decrement stock
            cursor.execute(
                """
                UPDATE stock_inventory
                SET quantity = quantity - %s
                WHERE id = %s AND clinic_id = %s AND quantity >= %s
                RETURNING id, quantity
                """,
                (quantity, stock_item_id, g.clinic_id, quantity),
            )
            updated = cursor.fetchone()
            if not updated:
                conn.rollback()
                return _error("conflict", "Estoque insuficiente ou item nao encontrado.", 409)

            # Log dispensation
            cursor.execute(
                """
                INSERT INTO stock_dispensations
                    (clinic_id, stock_item_id, patient_id, quantity, dispensed_by,
                     notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING id, created_at
                """,
                (
                    g.clinic_id,
                    stock_item_id,
                    patient_id,
                    quantity,
                    int(current_user.id),
                    notes,
                ),
            )
            disp = cursor.fetchone()
            conn.commit()
            return _success({
                "dispensation_id": disp["id"],
                "remaining_quantity": updated["quantity"],
                "created_at": disp["created_at"],
            }, status=201)
    except OperationalError:
        logger.error("DB unavailable on org_management.org_stock_dispensation", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, RuntimeError, TypeError, ValueError, KeyError):
        logger.error("Failed to register dispensation", exc_info=True)
        return _error("internal_error", "Falha ao registrar dispensacao.", 500)


# ==================================================================
# GET /api/v1/org/billing
# ==================================================================

@org_management_bp.get("/billing")
@api_role_required(*FINANCIAL_ROLES)
def org_billing():
    """Billing records for the organization."""
    page, page_size = _pagination_args()
    status_filter = (request.args.get("status") or "").strip()

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            where_clauses = ["b.clinic_id = %s"]
            params: list = [g.clinic_id]

            if status_filter:
                where_clauses.append("b.status = %s")
                params.append(status_filter)

            where_sql = " AND ".join(where_clauses)
            cursor.execute(
                f"""
                SELECT b.id, b.patient_id, p.name AS patient_name,
                       b.description, b.amount, b.status, b.due_date,
                       b.paid_at, b.created_at
                FROM billing b
                LEFT JOIN patients p ON p.id = b.patient_id AND p.clinic_id = b.clinic_id
                WHERE {where_sql}
                ORDER BY b.created_at DESC
                """,
                tuple(params),
            )
            rows = cursor.fetchall()

            total_revenue = sum(float(r.get("amount", 0)) for r in rows if r.get("status") == "pago")
            pending = sum(float(r.get("amount", 0)) for r in rows if r.get("status") == "pendente")
            overdue = sum(float(r.get("amount", 0)) for r in rows if r.get("status") == "vencido")

            items, page_meta = _paginate(rows, page, page_size)
            meta = {**page_meta, "total_revenue": total_revenue, "pending": pending, "overdue": overdue}
            return _success(items, meta=meta)
    except OperationalError:
        logger.error("DB unavailable on org_management.org_billing", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, RuntimeError, TypeError, ValueError, KeyError):
        logger.error("Unexpected error on org_management.org_billing", exc_info=True)
        return _error("internal_error", "Erro interno ao processar requisicao.", 500)


# ==================================================================
# GET /api/v1/org/financial
# ==================================================================

@org_management_bp.get("/financial")
@api_role_required(*FINANCIAL_ROLES)
def org_financial():
    """Financial summary for the organization."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            # Try to pull from billing table for revenue
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'pago' THEN amount ELSE 0 END), 0) AS revenue,
                    COALESCE(SUM(CASE WHEN status = 'pendente' THEN amount ELSE 0 END), 0) AS pending,
                    COALESCE(SUM(CASE WHEN status = 'vencido' THEN amount ELSE 0 END), 0) AS overdue
                FROM billing
                WHERE clinic_id = %s
                  AND created_at >= date_trunc('month', CURRENT_DATE)
                """,
                (g.clinic_id,),
            )
            row = cursor.fetchone()
            revenue = float(row["revenue"])
            costs = revenue * 0.35  # placeholder ratio
            profit = revenue - costs

            return _success({
                "revenue": revenue,
                "costs": round(costs, 2),
                "profit": round(profit, 2),
                "margin": round((profit / revenue * 100) if revenue else 0, 1),
                "pending": float(row["pending"]),
                "overdue": float(row["overdue"]),
                "transfers": [],
            })
    except OperationalError:
        logger.error("DB unavailable on org_management.org_financial", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, RuntimeError, TypeError, ValueError, KeyError):
        logger.error("Unexpected error on org_management.org_financial", exc_info=True)
        return _error("internal_error", "Erro interno ao processar requisicao.", 500)
