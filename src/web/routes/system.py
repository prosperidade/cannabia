# src/web/routes/system.py
"""
Endpoint de status do sistema e Feature Flags para Degradação Graceful.

Arquitetura:
  - Feature Flags lidas de env vars + DB (env prevalece para kill-switches de emergência).
  - Estado consolidado exposto em GET /api/v1/system/status (público, sem auth).
  - Estado detalhado em GET /api/v1/system/flags (admin-only).
  - Quando IA está indisponível (circuit aberto ou flag desligada), requests de IA
    são enfileirados para processamento posterior ao invés de descartados.

Flags:
  FF_AI_ENABLED        — habilita/desabilita pipeline de IA (padrão: true)
  FF_AI_ASYNC_ENABLED  — habilita/desabilita fila assíncrona (padrão: true)
  FF_RAG_ENABLED       — habilita/desabilita consulta RAG (padrão: true)
  FF_WHATSAPP_ENABLED  — habilita/desabilita integração WhatsApp (padrão: true)
  FF_BILLING_ENABLED   — habilita/desabilita enforcement de billing (padrão: true)
  FF_MAINTENANCE_MODE  — ativa modo manutenção geral (padrão: false)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, g, request

from src.web.routes.api_v1 import api_role_required

logger = logging.getLogger("cannabia.system")

system_bp = Blueprint("system", __name__, url_prefix="/api/v1/system")


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE FLAGS — Registry Central
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FeatureFlag:
    """Definição de uma feature flag."""
    key: str
    description: str
    default: bool
    category: str  # "ai", "integration", "billing", "system"


# Registro de todas as flags do sistema
_FLAG_DEFINITIONS: Dict[str, FeatureFlag] = {
    "ai_enabled": FeatureFlag(
        key="FF_AI_ENABLED",
        description="Pipeline de IA (análise clínica, plano terapêutico, relatório)",
        default=True,
        category="ai",
    ),
    "ai_async_enabled": FeatureFlag(
        key="FF_AI_ASYNC_ENABLED",
        description="Processamento assíncrono de IA via Redis/RQ",
        default=True,
        category="ai",
    ),
    "rag_enabled": FeatureFlag(
        key="FF_RAG_ENABLED",
        description="Consulta RAG ao ChromaDB para relatório científico",
        default=True,
        category="ai",
    ),
    "whatsapp_enabled": FeatureFlag(
        key="FF_WHATSAPP_ENABLED",
        description="Integração com WhatsApp Business API",
        default=True,
        category="integration",
    ),
    "billing_enabled": FeatureFlag(
        key="FF_BILLING_ENABLED",
        description="Enforcement de limites de billing por tenant",
        default=True,
        category="billing",
    ),
    "maintenance_mode": FeatureFlag(
        key="FF_MAINTENANCE_MODE",
        description="Modo manutenção — rejeita requests não-essenciais",
        default=False,
        category="system",
    ),
}


def _env_bool(key: str, default: bool) -> bool:
    """Lê flag booleana do ambiente."""
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


class FeatureFlagRegistry:
    """
    Registry thread-safe de feature flags.

    Prioridade de leitura:
      1. Override em memória (via API admin — temporário, não sobrevive restart)
      2. Variável de ambiente (kill-switch persistente)
      3. Banco de dados (configuração gerenciada)
      4. Valor default da definição
    """

    def __init__(self) -> None:
        self._overrides: Dict[str, bool] = {}
        self._db_cache: Dict[str, bool] = {}
        self._db_cache_ts: float = 0.0
        self._db_cache_ttl: float = 60.0  # Recarrega do DB a cada 60s
        self._lock = threading.Lock()

    def is_enabled(self, flag_name: str) -> bool:
        """Verifica se uma flag está habilitada."""
        defn = _FLAG_DEFINITIONS.get(flag_name)
        if defn is None:
            logger.warning("Flag desconhecida consultada: '%s'", flag_name)
            return False

        # 1. Override em memória
        with self._lock:
            if flag_name in self._overrides:
                return self._overrides[flag_name]

        # 2. Variável de ambiente
        env_val = os.getenv(defn.key)
        if env_val is not None:
            return env_val.lower() in ("1", "true", "yes", "on")

        # 3. Banco de dados (com cache)
        db_val = self._load_from_db(flag_name)
        if db_val is not None:
            return db_val

        # 4. Default
        return defn.default

    def set_override(self, flag_name: str, value: bool) -> None:
        """Define override temporário em memória (não sobrevive restart)."""
        with self._lock:
            self._overrides[flag_name] = value
        logger.info("Feature flag override: %s = %s", flag_name, value)

    def clear_override(self, flag_name: str) -> None:
        """Remove override em memória."""
        with self._lock:
            self._overrides.pop(flag_name, None)
        logger.info("Feature flag override removido: %s", flag_name)

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Retorna estado completo de todas as flags."""
        result = {}
        for name, defn in _FLAG_DEFINITIONS.items():
            enabled = self.is_enabled(name)
            source = self._resolve_source(name)
            result[name] = {
                "enabled": enabled,
                "source": source,
                "category": defn.category,
                "description": defn.description,
                "env_key": defn.key,
            }
        return result

    def _resolve_source(self, flag_name: str) -> str:
        """Identifica de onde vem o valor atual da flag."""
        defn = _FLAG_DEFINITIONS.get(flag_name)
        if defn is None:
            return "unknown"

        with self._lock:
            if flag_name in self._overrides:
                return "override"

        if os.getenv(defn.key) is not None:
            return "env"

        db_val = self._load_from_db(flag_name)
        if db_val is not None:
            return "database"

        return "default"

    def _load_from_db(self, flag_name: str) -> Optional[bool]:
        """Carrega flag do banco de dados com cache TTL."""
        now = time.time()

        with self._lock:
            if now - self._db_cache_ts < self._db_cache_ttl:
                return self._db_cache.get(flag_name)

        # Recarrega cache do DB
        try:
            from src.infra.database import db_cursor

            with db_cursor(dictionary=True) as (conn, cur):
                cur.execute(
                    "SELECT flag_name, is_enabled FROM feature_flags WHERE flag_name = %s",
                    (flag_name,),
                )
                row = cur.fetchone()

            with self._lock:
                self._db_cache_ts = now
                if row:
                    self._db_cache[flag_name] = row["is_enabled"]
                    return row["is_enabled"]
                return None

        except Exception:
            # DB indisponível ou tabela não existe — silencioso
            return None


# Instância global singleton
flags = FeatureFlagRegistry()


# ═══════════════════════════════════════════════════════════════════════════════
# DEGRADAÇÃO GRACEFUL — Estratégias por componente
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DegradationStatus:
    """Estado de degradação de um componente."""
    component: str
    operational: bool
    strategy: str  # "normal", "queued", "cached", "disabled"
    message: str


def evaluate_degradation() -> Dict[str, DegradationStatus]:
    """
    Avalia o estado de degradação de cada componente.
    Integra feature flags + circuit breakers + health probes.
    """
    statuses: Dict[str, DegradationStatus] = {}

    # ── IA Pipeline ──
    if not flags.is_enabled("ai_enabled"):
        statuses["ai_pipeline"] = DegradationStatus(
            component="ai_pipeline",
            operational=False,
            strategy="disabled",
            message="Pipeline de IA desabilitado via feature flag.",
        )
    else:
        try:
            from src.ai.chains import get_circuit_breaker_status
            cb_status = get_circuit_breaker_status()
            openai_open = cb_status["openai"]["state"] == "open"
            gemini_open = cb_status["gemini"]["state"] == "open"

            if openai_open and gemini_open:
                statuses["ai_pipeline"] = DegradationStatus(
                    component="ai_pipeline",
                    operational=False,
                    strategy="queued",
                    message="Ambos provedores LLM com circuit aberto. Requests enfileirados.",
                )
            elif openai_open or gemini_open:
                failed = "OpenAI" if openai_open else "Gemini"
                statuses["ai_pipeline"] = DegradationStatus(
                    component="ai_pipeline",
                    operational=True,
                    strategy="normal",
                    message=f"{failed} indisponível — failover ativo para provedor alternativo.",
                )
            else:
                statuses["ai_pipeline"] = DegradationStatus(
                    component="ai_pipeline",
                    operational=True,
                    strategy="normal",
                    message="Operacional.",
                )
        except Exception:
            statuses["ai_pipeline"] = DegradationStatus(
                component="ai_pipeline",
                operational=True,
                strategy="normal",
                message="Não foi possível consultar circuit breakers.",
            )

    # ── Fila Assíncrona ──
    if not flags.is_enabled("ai_async_enabled"):
        statuses["async_queue"] = DegradationStatus(
            component="async_queue",
            operational=False,
            strategy="disabled",
            message="Fila assíncrona desabilitada. Pipeline roda síncrono.",
        )
    else:
        try:
            from src.infra.tasks import redis_available
            if redis_available():
                statuses["async_queue"] = DegradationStatus(
                    component="async_queue",
                    operational=True,
                    strategy="normal",
                    message="Redis conectado.",
                )
            else:
                statuses["async_queue"] = DegradationStatus(
                    component="async_queue",
                    operational=False,
                    strategy="disabled",
                    message="Redis indisponível. Fallback para processamento síncrono.",
                )
        except Exception:
            statuses["async_queue"] = DegradationStatus(
                component="async_queue",
                operational=False,
                strategy="disabled",
                message="Redis não configurado.",
            )

    # ── RAG / ChromaDB ──
    if not flags.is_enabled("rag_enabled"):
        statuses["rag"] = DegradationStatus(
            component="rag",
            operational=False,
            strategy="disabled",
            message="RAG desabilitado. Relatório científico usa LLM direto.",
        )
    else:
        statuses["rag"] = DegradationStatus(
            component="rag",
            operational=True,
            strategy="normal",
            message="Operacional.",
        )

    # ── WhatsApp ──
    if not flags.is_enabled("whatsapp_enabled"):
        statuses["whatsapp"] = DegradationStatus(
            component="whatsapp",
            operational=False,
            strategy="queued",
            message="WhatsApp desabilitado. Mensagens enfileiradas para envio posterior.",
        )
    else:
        statuses["whatsapp"] = DegradationStatus(
            component="whatsapp",
            operational=True,
            strategy="normal",
            message="Operacional.",
        )

    # ── Billing ──
    if not flags.is_enabled("billing_enabled"):
        statuses["billing"] = DegradationStatus(
            component="billing",
            operational=False,
            strategy="disabled",
            message="Billing desabilitado. Limites não enforced.",
        )
    else:
        statuses["billing"] = DegradationStatus(
            component="billing",
            operational=True,
            strategy="normal",
            message="Operacional.",
        )

    # ── Manutenção ──
    if flags.is_enabled("maintenance_mode"):
        statuses["maintenance"] = DegradationStatus(
            component="maintenance",
            operational=False,
            strategy="disabled",
            message="Sistema em modo manutenção.",
        )

    return statuses


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@system_bp.route("/status", methods=["GET"])
def system_status():
    """
    GET /api/v1/system/status — Estado público do sistema.
    Sem autenticação — consumido pelo frontend para exibir banners de degradação.
    """
    degradation = evaluate_degradation()

    # Determina status geral
    all_operational = all(d.operational for d in degradation.values())
    any_down = any(not d.operational for d in degradation.values())
    maintenance = flags.is_enabled("maintenance_mode")

    if maintenance:
        overall = "maintenance"
    elif all_operational:
        overall = "operational"
    elif any_down:
        overall = "degraded"
    else:
        overall = "operational"

    components = {}
    for name, status in degradation.items():
        components[name] = {
            "operational": status.operational,
            "strategy": status.strategy,
            "message": status.message,
        }

    return jsonify({
        "status": overall,
        "maintenance_mode": maintenance,
        "components": components,
    }), 200


@system_bp.route("/flags", methods=["GET"])
@api_role_required("Admin")
def system_flags():
    """
    GET /api/v1/system/flags — Estado detalhado das feature flags.
    Admin-only.
    """
    return jsonify({
        "flags": flags.get_all(),
    }), 200


@system_bp.route("/flags/<flag_name>", methods=["PUT"])
@api_role_required("Admin")
def set_flag(flag_name: str):
    """
    PUT /api/v1/system/flags/<flag_name> — Override temporário de uma flag.
    Admin-only. Body: {"enabled": true/false}
    """
    if flag_name not in _FLAG_DEFINITIONS:
        return jsonify({"error": f"Flag desconhecida: '{flag_name}'"}), 404

    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")

    if enabled is None:
        return jsonify({"error": "Campo 'enabled' obrigatório."}), 400

    flags.set_override(flag_name, bool(enabled))

    return jsonify({
        "flag": flag_name,
        "enabled": bool(enabled),
        "source": "override",
        "note": "Override temporário — não sobrevive restart do processo.",
    }), 200


@system_bp.route("/flags/<flag_name>", methods=["DELETE"])
@api_role_required("Admin")
def clear_flag(flag_name: str):
    """
    DELETE /api/v1/system/flags/<flag_name> — Remove override de uma flag.
    Admin-only.
    """
    if flag_name not in _FLAG_DEFINITIONS:
        return jsonify({"error": f"Flag desconhecida: '{flag_name}'"}), 404

    flags.clear_override(flag_name)

    current = flags.is_enabled(flag_name)
    source = flags._resolve_source(flag_name)

    return jsonify({
        "flag": flag_name,
        "enabled": current,
        "source": source,
    }), 200
