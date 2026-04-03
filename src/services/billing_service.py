# src/services/billing_service.py
"""
Serviço de billing — o xerife que garante hard/soft limits de IA por tenant.

Responsabilidades:
  1. Verificar se o tenant pode executar uma chamada de IA (check_ai_allowance)
  2. Registrar consumo de IA após execução (record_ai_usage)
  3. Emitir eventos de billing (soft_limit_hit, hard_limit_hit)
  4. Consultar uso atual e plano do tenant (get_usage_summary)
  5. Gerenciar ciclo de billing (reset mensal de contadores)

Enforcement:
  - soft_limit: emite evento + log warning (não bloqueia)
  - hard_limit: levanta BillingLimitExceeded (bloqueia chamada de IA)
  - Limite 0 = ilimitado (Enterprise)
  - Feature flag FF_BILLING_ENABLED controla se enforcement está ativo
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger("cannabia.billing")


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEÇÕES
# ═══════════════════════════════════════════════════════════════════════════════

class BillingLimitExceeded(Exception):
    """Levantada quando o tenant atingiu o hard limit de IA."""

    def __init__(self, clinic_id: int, resource: str, current: int, limit: int):
        self.clinic_id = clinic_id
        self.resource = resource
        self.current = current
        self.limit = limit
        super().__init__(
            f"Limite de {resource} atingido para clinic_id={clinic_id}: "
            f"{current}/{limit}. Upgrade de plano necessário."
        )


class NoPlanAssigned(Exception):
    """Levantada quando o tenant não possui plano ativo."""

    def __init__(self, clinic_id: int):
        self.clinic_id = clinic_id
        super().__init__(
            f"Nenhum plano ativo para clinic_id={clinic_id}. "
            f"Assinatura necessária."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

class AllowanceVerdict(Enum):
    ALLOWED = "allowed"
    SOFT_LIMIT = "soft_limit"
    HARD_LIMIT = "hard_limit"
    NO_PLAN = "no_plan"
    BILLING_DISABLED = "billing_disabled"


@dataclass
class AIAllowance:
    """Resultado da verificação de permissão de uso de IA."""
    verdict: AllowanceVerdict
    clinic_id: int
    plan_slug: Optional[str] = None
    requests_used: int = 0
    requests_limit: int = 0
    tokens_used: int = 0
    tokens_limit: int = 0
    soft_limit_pct: int = 80
    message: str = ""

    @property
    def allowed(self) -> bool:
        return self.verdict in (AllowanceVerdict.ALLOWED, AllowanceVerdict.SOFT_LIMIT)


@dataclass
class UsageSummary:
    """Resumo de uso do tenant no ciclo atual."""
    clinic_id: int
    plan_slug: str
    plan_name: str
    billing_cycle: str
    period_start: str
    period_end: str
    ai_requests_used: int
    ai_requests_limit: int
    ai_tokens_used: int
    ai_tokens_limit: int
    ai_requests_pct: float
    ai_tokens_pct: float
    soft_limit_hit: bool
    hard_limit_hit: bool
    estimated_cost_cents: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clinic_id": self.clinic_id,
            "plan": {"slug": self.plan_slug, "name": self.plan_name},
            "billing_cycle": self.billing_cycle,
            "period": {"start": self.period_start, "end": self.period_end},
            "ai_requests": {
                "used": self.ai_requests_used,
                "limit": self.ai_requests_limit,
                "pct": round(self.ai_requests_pct, 1),
            },
            "ai_tokens": {
                "used": self.ai_tokens_used,
                "limit": self.ai_tokens_limit,
                "pct": round(self.ai_tokens_pct, 1),
            },
            "soft_limit_hit": self.soft_limit_hit,
            "hard_limit_hit": self.hard_limit_hit,
            "estimated_cost_cents": self.estimated_cost_cents,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ═══════════════════════════════════════════════════════════════════════════════

def _current_period_start() -> date:
    """Retorna o primeiro dia do mês corrente (UTC)."""
    today = datetime.now(timezone.utc).date()
    return today.replace(day=1)


def _current_period_end() -> date:
    """Retorna o último dia do mês corrente (UTC)."""
    start = _current_period_start()
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1, day=1)
    return start.replace(month=start.month + 1, day=1)


def _pct(used: int, limit: int) -> float:
    """Calcula percentual de uso. Limite 0 = ilimitado = 0%."""
    if limit <= 0:
        return 0.0
    return (used / limit) * 100


def _billing_enabled() -> bool:
    """Verifica se o enforcement de billing está ativo via feature flag."""
    try:
        from src.web.routes.system import flags
        return flags.is_enabled("billing_enabled")
    except Exception:
        return True  # Se não conseguir ler a flag, enforça por segurança


# ═══════════════════════════════════════════════════════════════════════════════
# ACESSO AO BANCO
# ═══════════════════════════════════════════════════════════════════════════════

def _get_active_plan(clinic_id: int) -> Optional[Dict[str, Any]]:
    """Retorna o plano ativo do tenant, ou None."""
    from src.infra.database import db_cursor

    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            SELECT p.slug, p.display_name, p.ai_requests_limit, p.ai_tokens_limit,
                   p.max_patients, p.max_users, p.soft_limit_pct, p.features,
                   s.billing_cycle, s.current_period_start, s.current_period_end, s.status
            FROM billing_subscriptions s
            JOIN billing_plans p ON p.id = s.plan_id
            WHERE s.clinic_id = %s AND s.status IN ('active', 'trial')
            LIMIT 1
            """,
            (clinic_id,),
        )
        return cur.fetchone()


def _get_or_create_usage(clinic_id: int) -> Dict[str, Any]:
    """
    Retorna o registro de uso do mês corrente, criando se não existir.
    Usa INSERT ON CONFLICT para idempotência.
    """
    from src.infra.database import db_cursor

    period_start = _current_period_start()
    period_end = _current_period_end()

    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO billing_usage (clinic_id, period_start, period_end)
            VALUES (%s, %s, %s)
            ON CONFLICT (clinic_id, period_start) DO NOTHING
            RETURNING *
            """,
            (clinic_id, period_start, period_end),
        )
        row = cur.fetchone()

        if row is None:
            # Já existia — busca o registro
            cur.execute(
                "SELECT * FROM billing_usage WHERE clinic_id = %s AND period_start = %s",
                (clinic_id, period_start),
            )
            row = cur.fetchone()

        conn.commit()
        return row


def _increment_usage(clinic_id: int, requests_delta: int = 1, tokens_delta: int = 0, cost_cents_delta: int = 0) -> Dict[str, Any]:
    """Incrementa contadores de uso do mês corrente. Retorna registro atualizado."""
    from src.infra.database import db_cursor

    period_start = _current_period_start()

    # Garante que o registro existe
    _get_or_create_usage(clinic_id)

    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            UPDATE billing_usage
            SET ai_requests_count = ai_requests_count + %s,
                ai_tokens_used = ai_tokens_used + %s,
                estimated_cost_cents = estimated_cost_cents + %s,
                updated_at = NOW()
            WHERE clinic_id = %s AND period_start = %s
            RETURNING *
            """,
            (requests_delta, tokens_delta, cost_cents_delta, clinic_id, period_start),
        )
        row = cur.fetchone()
        conn.commit()
        return row


def _set_limit_flag(clinic_id: int, flag: str) -> None:
    """Marca soft_limit_hit ou hard_limit_hit no registro de uso."""
    from src.infra.database import db_cursor

    period_start = _current_period_start()

    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            f"""
            UPDATE billing_usage
            SET {flag} = TRUE, {flag}_at = NOW(), updated_at = NOW()
            WHERE clinic_id = %s AND period_start = %s AND {flag} = FALSE
            """,
            (clinic_id, period_start),
        )
        conn.commit()


def _log_billing_event(clinic_id: int, event_type: str, details: Dict[str, Any]) -> None:
    """Registra evento imutável no log de billing."""
    from src.infra.database import db_cursor

    try:
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                """
                INSERT INTO billing_events (clinic_id, event_type, details)
                VALUES (%s, %s, %s::JSONB)
                """,
                (clinic_id, event_type, __import__("json").dumps(details)),
            )
            conn.commit()
    except Exception as exc:
        # Nunca derruba operação principal por falha de logging
        logger.warning("Falha ao registrar billing event: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════════
# API PÚBLICA
# ═══════════════════════════════════════════════════════════════════════════════

def check_ai_allowance(clinic_id: int) -> AIAllowance:
    """
    Verifica se o tenant pode executar uma chamada de IA.

    Retorna AIAllowance com o veredito:
      - ALLOWED: pode executar normalmente
      - SOFT_LIMIT: pode executar, mas está próximo do limite (emite aviso)
      - HARD_LIMIT: bloqueado — atingiu o limite máximo
      - NO_PLAN: tenant sem plano ativo
      - BILLING_DISABLED: billing desligado via feature flag

    Chamado ANTES de executar o pipeline de IA.
    """
    # Bypass se billing está desabilitado
    if not _billing_enabled():
        return AIAllowance(
            verdict=AllowanceVerdict.BILLING_DISABLED,
            clinic_id=clinic_id,
            message="Billing desabilitado — sem enforcement de limites.",
        )

    # Busca plano ativo
    plan = _get_active_plan(clinic_id)
    if plan is None:
        return AIAllowance(
            verdict=AllowanceVerdict.NO_PLAN,
            clinic_id=clinic_id,
            message="Nenhum plano ativo. Assinatura necessária.",
        )

    # Busca uso do ciclo atual
    usage = _get_or_create_usage(clinic_id)

    requests_used = usage["ai_requests_count"]
    tokens_used = usage["ai_tokens_used"]
    requests_limit = plan["ai_requests_limit"]
    tokens_limit = plan["ai_tokens_limit"]
    soft_pct = plan["soft_limit_pct"]

    base = AIAllowance(
        verdict=AllowanceVerdict.ALLOWED,
        clinic_id=clinic_id,
        plan_slug=plan["slug"],
        requests_used=requests_used,
        requests_limit=requests_limit,
        tokens_used=tokens_used,
        tokens_limit=tokens_limit,
        soft_limit_pct=soft_pct,
    )

    # Limite 0 = ilimitado (Enterprise)
    if requests_limit <= 0 and tokens_limit <= 0:
        base.message = "Plano sem limites."
        return base

    # Hard limit — requests
    if requests_limit > 0 and requests_used >= requests_limit:
        base.verdict = AllowanceVerdict.HARD_LIMIT
        base.message = f"Limite de {requests_limit} requests atingido ({requests_used} usados)."

        if not usage["hard_limit_hit"]:
            _set_limit_flag(clinic_id, "hard_limit_hit")
            _log_billing_event(clinic_id, "hard_limit_hit", {
                "resource": "ai_requests",
                "used": requests_used,
                "limit": requests_limit,
                "plan": plan["slug"],
            })
            logger.warning(
                "HARD LIMIT atingido: clinic_id=%s, requests=%d/%d, plan=%s",
                clinic_id, requests_used, requests_limit, plan["slug"],
            )
        return base

    # Hard limit — tokens
    if tokens_limit > 0 and tokens_used >= tokens_limit:
        base.verdict = AllowanceVerdict.HARD_LIMIT
        base.message = f"Limite de {tokens_limit} tokens atingido ({tokens_used} usados)."

        if not usage["hard_limit_hit"]:
            _set_limit_flag(clinic_id, "hard_limit_hit")
            _log_billing_event(clinic_id, "hard_limit_hit", {
                "resource": "ai_tokens",
                "used": tokens_used,
                "limit": tokens_limit,
                "plan": plan["slug"],
            })
            logger.warning(
                "HARD LIMIT atingido: clinic_id=%s, tokens=%d/%d, plan=%s",
                clinic_id, tokens_used, tokens_limit, plan["slug"],
            )
        return base

    # Soft limit — verifica se ultrapassou o percentual de aviso
    requests_pct = _pct(requests_used, requests_limit)
    tokens_pct = _pct(tokens_used, tokens_limit)

    if requests_pct >= soft_pct or tokens_pct >= soft_pct:
        base.verdict = AllowanceVerdict.SOFT_LIMIT
        resource = "requests" if requests_pct >= soft_pct else "tokens"
        pct = requests_pct if requests_pct >= soft_pct else tokens_pct
        base.message = f"Atenção: {pct:.0f}% do limite de {resource} consumido."

        if not usage["soft_limit_hit"]:
            _set_limit_flag(clinic_id, "soft_limit_hit")
            _log_billing_event(clinic_id, "soft_limit_hit", {
                "resource": resource,
                "pct": round(pct, 1),
                "plan": plan["slug"],
            })
            logger.info(
                "Soft limit atingido: clinic_id=%s, %s=%.0f%%, plan=%s",
                clinic_id, resource, pct, plan["slug"],
            )
        return base

    # Dentro dos limites
    base.message = "Dentro dos limites do plano."
    return base


def record_ai_usage(
    clinic_id: int,
    tokens_used: int = 0,
    estimated_cost_usd: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Registra consumo de IA após execução bem-sucedida do pipeline.

    Chamado DEPOIS de executar o pipeline de IA.
    Incrementa: requests +1, tokens, custo estimado.
    """
    cost_cents = int((estimated_cost_usd or 0) * 100)

    usage = _increment_usage(
        clinic_id=clinic_id,
        requests_delta=1,
        tokens_delta=tokens_used,
        cost_cents_delta=cost_cents,
    )

    logger.debug(
        "Uso registrado: clinic_id=%s, requests=%d, tokens=%d",
        clinic_id, usage["ai_requests_count"], usage["ai_tokens_used"],
    )

    return {
        "ai_requests_count": usage["ai_requests_count"],
        "ai_tokens_used": usage["ai_tokens_used"],
        "estimated_cost_cents": usage["estimated_cost_cents"],
    }


def get_usage_summary(clinic_id: int) -> Optional[UsageSummary]:
    """
    Retorna resumo consolidado do uso do tenant no ciclo atual.
    Inclui plano, limites, percentuais e flags de limit.
    """
    plan = _get_active_plan(clinic_id)
    if plan is None:
        return None

    usage = _get_or_create_usage(clinic_id)

    requests_limit = plan["ai_requests_limit"]
    tokens_limit = plan["ai_tokens_limit"]

    return UsageSummary(
        clinic_id=clinic_id,
        plan_slug=plan["slug"],
        plan_name=plan["display_name"],
        billing_cycle=plan["billing_cycle"],
        period_start=str(usage["period_start"]),
        period_end=str(usage["period_end"]),
        ai_requests_used=usage["ai_requests_count"],
        ai_requests_limit=requests_limit,
        ai_tokens_used=usage["ai_tokens_used"],
        ai_tokens_limit=tokens_limit,
        ai_requests_pct=_pct(usage["ai_requests_count"], requests_limit),
        ai_tokens_pct=_pct(usage["ai_tokens_used"], tokens_limit),
        soft_limit_hit=usage["soft_limit_hit"],
        hard_limit_hit=usage["hard_limit_hit"],
        estimated_cost_cents=usage["estimated_cost_cents"],
    )


def assign_plan(clinic_id: int, plan_slug: str, billing_cycle: str = "monthly") -> int:
    """
    Atribui um plano a um tenant. Cria billing_subscription.
    Se já existir assinatura ativa, levanta ValueError.
    Retorna o ID da subscription criada.
    """
    from src.infra.database import db_cursor

    with db_cursor(dictionary=True) as (conn, cur):
        # Busca plan_id
        cur.execute("SELECT id FROM billing_plans WHERE slug = %s AND is_active = TRUE", (plan_slug,))
        plan_row = cur.fetchone()
        if plan_row is None:
            raise ValueError(f"Plano '{plan_slug}' não encontrado ou inativo.")

        # Verifica se já tem assinatura ativa
        existing = _get_active_plan(clinic_id)
        if existing:
            raise ValueError(
                f"Tenant clinic_id={clinic_id} já possui plano ativo: '{existing['slug']}'. "
                f"Cancele o atual antes de atribuir novo."
            )

        period_start = _current_period_start()
        period_end = _current_period_end()

        cur.execute(
            """
            INSERT INTO billing_subscriptions
                (clinic_id, plan_id, status, billing_cycle, current_period_start, current_period_end)
            VALUES (%s, %s, 'active', %s, %s, %s)
            RETURNING id
            """,
            (clinic_id, plan_row["id"], billing_cycle, period_start, period_end),
        )
        sub_id = cur.fetchone()["id"]
        conn.commit()

    _log_billing_event(clinic_id, "subscription_created", {
        "plan": plan_slug,
        "billing_cycle": billing_cycle,
        "subscription_id": sub_id,
    })

    logger.info("Plano '%s' atribuído a clinic_id=%s (sub_id=%d)", plan_slug, clinic_id, sub_id)
    return sub_id


def get_available_plans() -> list:
    """Retorna lista de planos ativos ordenados por sort_order."""
    from src.infra.database import db_cursor

    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            SELECT slug, display_name, description, ai_requests_limit, ai_tokens_limit,
                   max_patients, max_users, price_cents_monthly, price_cents_yearly,
                   features, sort_order
            FROM billing_plans
            WHERE is_active = TRUE
            ORDER BY sort_order
            """
        )
        return cur.fetchall()
