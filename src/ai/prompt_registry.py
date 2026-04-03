# src/ai/prompt_registry.py
"""
Registro de versões de prompts com fallback para hardcoded (Fase 3.5).

Arquitetura:
  1. Carrega prompts da tabela `ai_prompt_versions` do banco de dados.
  2. Se o DB não tiver versão ativa, usa o prompt hardcoded de `src/ai/prompts.py`.
  3. Cada uso registra a versão e o hash SHA-256 do prompt (para auditoria).
  4. Cache em memória com TTL configurável para evitar queries excessivas.

Tabela utilizada: `ai_prompt_versions` (já existente no schema).
Campos esperados:
  - prompt_key   : identificador único (ex: "anamnesis", "treatment_plan")
  - prompt_text  : texto completo do prompt template
  - version      : rótulo de versão (ex: "v1.0", "v2.1")
  - is_active    : boolean — apenas 1 ativa por prompt_key
  - created_at   : timestamp de criação
  - created_by   : user_id de quem criou
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger("cannabia.ai.prompts")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

CACHE_TTL = int(os.getenv("PROMPT_CACHE_TTL", "300"))  # 5 minutos


@dataclass
class PromptVersion:
    """Representação de uma versão de prompt carregada."""
    key: str
    text: str
    version: str
    hash: str
    source: str  # "database" ou "hardcoded"
    loaded_at: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPTS HARDCODED (fallback)
# Importados de src/ai/prompts.py — fonte canônica dos prompts padrão
# ═══════════════════════════════════════════════════════════════════════════════

from src.ai.prompts import (
    ANAMNESIS_PROMPT,
    TREATMENT_PLAN_PROMPT,
    SCIENTIFIC_REPORT_PROMPT,
    SCIENTIFIC_REPORT_RAG_PROMPT,
    TRIAGE_AGENT_SYSTEM_PROMPT,
)

_HARDCODED_PROMPTS: Dict[str, str] = {
    "anamnesis": ANAMNESIS_PROMPT,
    "treatment_plan": TREATMENT_PLAN_PROMPT,
    "scientific_report": SCIENTIFIC_REPORT_PROMPT,
    "scientific_report_rag": SCIENTIFIC_REPORT_RAG_PROMPT,
    "triage_agent": TRIAGE_AGENT_SYSTEM_PROMPT,
}


def _compute_hash(text: str) -> str:
    """Gera SHA-256 do texto do prompt (para auditoria)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE EM MEMÓRIA (thread-safe, TTL configurável)
# ═══════════════════════════════════════════════════════════════════════════════

class _PromptCache:
    """Cache simples em memória com TTL por entrada."""

    def __init__(self, ttl: int = CACHE_TTL) -> None:
        self._store: Dict[str, PromptVersion] = {}
        self._lock = threading.Lock()
        self._ttl = ttl

    def get(self, key: str) -> Optional[PromptVersion]:
        with self._lock:
            entry = self._store.get(key)
            if entry and (time.time() - entry.loaded_at) < self._ttl:
                return entry
            # Expirado ou inexistente
            if entry:
                del self._store[key]
            return None

    def put(self, prompt: PromptVersion) -> None:
        with self._lock:
            self._store[prompt.key] = prompt

    def invalidate(self, key: Optional[str] = None) -> None:
        """Invalida uma chave específica ou todo o cache."""
        with self._lock:
            if key:
                self._store.pop(key, None)
            else:
                self._store.clear()


_cache = _PromptCache()


# ═══════════════════════════════════════════════════════════════════════════════
# ACESSO AO BANCO DE DADOS
# ═══════════════════════════════════════════════════════════════════════════════

def _load_from_db(prompt_key: str) -> Optional[PromptVersion]:
    """
    Carrega a versão ativa do prompt do banco de dados.
    Retorna None se não existir tabela, registro, ou se o DB estiver inacessível.
    """
    try:
        from src.infra.database import db_cursor

        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                """
                SELECT prompt_text, version
                FROM ai_prompt_versions
                WHERE prompt_key = %s AND is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (prompt_key,),
            )
            row = cur.fetchone()

        if row:
            text = row["prompt_text"]
            return PromptVersion(
                key=prompt_key,
                text=text,
                version=row["version"],
                hash=_compute_hash(text),
                source="database",
            )

    except Exception as exc:
        # Falha silenciosa: DB indisponível ou tabela inexistente → usa hardcoded
        logger.debug(
            "Não foi possível carregar prompt '%s' do DB (fallback para hardcoded): %s",
            prompt_key, str(exc),
        )

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# API PÚBLICA
# ═══════════════════════════════════════════════════════════════════════════════

def get_prompt(prompt_key: str) -> PromptVersion:
    """
    Retorna a versão ativa do prompt para a chave dada.

    Ordem de prioridade:
      1. Cache em memória (se válido)
      2. Banco de dados (tabela ai_prompt_versions)
      3. Hardcoded (src/ai/prompts.py)

    Sempre retorna um PromptVersion — nunca falha.
    """
    # 1. Cache
    cached = _cache.get(prompt_key)
    if cached:
        return cached

    # 2. Banco de dados
    db_prompt = _load_from_db(prompt_key)
    if db_prompt:
        _cache.put(db_prompt)
        logger.info(
            "Prompt '%s' carregado do DB: version=%s, hash=%s",
            prompt_key, db_prompt.version, db_prompt.hash[:12],
        )
        return db_prompt

    # 3. Hardcoded (fallback garantido)
    hardcoded_text = _HARDCODED_PROMPTS.get(prompt_key)
    if hardcoded_text is None:
        raise KeyError(
            f"Prompt '{prompt_key}' não encontrado (nem no DB nem no hardcoded). "
            f"Chaves válidas: {list(_HARDCODED_PROMPTS.keys())}"
        )

    fallback = PromptVersion(
        key=prompt_key,
        text=hardcoded_text,
        version="hardcoded",
        hash=_compute_hash(hardcoded_text),
        source="hardcoded",
    )
    _cache.put(fallback)
    return fallback


def invalidate_cache(prompt_key: Optional[str] = None) -> None:
    """
    Invalida o cache de prompts.
    Chamado após CRUD de prompts via API admin.
    """
    _cache.invalidate(prompt_key)
    logger.info("Cache de prompts invalidado: %s", prompt_key or "ALL")


def list_available_prompts() -> Dict[str, Dict]:
    """
    Lista todos os prompts disponíveis com sua fonte atual.
    Útil para API admin de gestão de prompts.
    """
    result = {}
    for key in _HARDCODED_PROMPTS:
        prompt = get_prompt(key)
        result[key] = {
            "version": prompt.version,
            "source": prompt.source,
            "hash": prompt.hash[:12],
        }
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD DE PROMPTS (para API admin)
# ═══════════════════════════════════════════════════════════════════════════════

def save_prompt_version(
    prompt_key: str,
    prompt_text: str,
    version: str,
    created_by: str,
    activate: bool = False,
) -> int:
    """
    Salva uma nova versão de prompt no banco de dados.
    Se activate=True, desativa todas as outras versões da mesma chave e ativa esta.
    Retorna o ID do registro criado.
    """
    from src.infra.database import db_cursor

    with db_cursor(dictionary=True) as (conn, cur):
        if activate:
            # Desativa versões anteriores
            cur.execute(
                "UPDATE ai_prompt_versions SET is_active = FALSE WHERE prompt_key = %s",
                (prompt_key,),
            )

        cur.execute(
            """
            INSERT INTO ai_prompt_versions (prompt_key, prompt_text, version, is_active, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (prompt_key, prompt_text, version, activate, created_by),
        )
        row = cur.fetchone()
        conn.commit()

    # Invalida cache para forçar reload
    invalidate_cache(prompt_key)

    prompt_id = row["id"]
    logger.info(
        "Prompt salvo: key=%s, version=%s, active=%s, id=%d, by=%s",
        prompt_key, version, activate, prompt_id, created_by,
    )
    return prompt_id


def activate_prompt_version(prompt_key: str, version: str) -> bool:
    """
    Ativa uma versão específica do prompt (e desativa as demais).
    Retorna True se encontrou e ativou, False se versão não existe.
    """
    from src.infra.database import db_cursor

    with db_cursor(dictionary=True) as (conn, cur):
        # Desativa todas
        cur.execute(
            "UPDATE ai_prompt_versions SET is_active = FALSE WHERE prompt_key = %s",
            (prompt_key,),
        )

        # Ativa a versão desejada
        cur.execute(
            """
            UPDATE ai_prompt_versions
            SET is_active = TRUE
            WHERE prompt_key = %s AND version = %s
            RETURNING id
            """,
            (prompt_key, version),
        )
        row = cur.fetchone()
        conn.commit()

    invalidate_cache(prompt_key)

    if row:
        logger.info("Prompt ativado: key=%s, version=%s", prompt_key, version)
        return True

    logger.warning("Versão não encontrada: key=%s, version=%s", prompt_key, version)
    return False
