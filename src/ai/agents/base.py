# src/ai/agents/base.py
"""
BaseAgent — foundation for all Cannabia AI agents.

Cada agente:
- Auto-loga timing de execucao via `run()`.
- Tem skills registradas (callable functions).
- Reporta metricas (duration, tokens, confidence) via AgentResult.

Nota historica: ate Track C.2 da Sprint 1, BaseAgent integrava MemPalace
para recall/diary/knowledge graph. MemPalace foi classificado como fraude
em 2026-04-24 e o path inteiro foi extirpado. Os metodos memory-related
(recall_memory, remember, remember_fact, get_diary) e o atributo
palace_room nao existem mais — agentes que precisarem de memoria
persistente devem usar storage explicito (DB, knowledge_catalog).
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("cannabia.agents")


@dataclass
class Skill:
    """A registered skill that an agent can invoke."""
    name: str
    description: str
    handler: Callable
    input_schema: Optional[Dict] = None
    output_schema: Optional[Dict] = None


@dataclass
class AgentResult:
    """Standard result from agent execution."""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    tokens: Dict[str, int] = field(default_factory=dict)
    duration_ms: int = 0
    confidence: float = 0.0
    agent_name: str = ""
    skills_used: List[str] = field(default_factory=list)


class BaseAgent(ABC):
    """
    Abstract base class for all Cannabia AI agents.

    Subclasses must implement:
        - execute(**kwargs) -> AgentResult

    Subclasses should set:
        - agent_name: str (display name)
        - description: str (what this agent does)
    """

    agent_name: str = "base"
    description: str = "Base agent"

    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {}
        self._register_skills()

    # ── Skill Registration ──

    def register_skill(self, name: str, handler: Callable, description: str = "",
                       input_schema: Optional[Dict] = None, output_schema: Optional[Dict] = None) -> None:
        """Register a skill for this agent."""
        self._skills[name] = Skill(
            name=name,
            description=description,
            handler=handler,
            input_schema=input_schema,
            output_schema=output_schema,
        )

    def _register_skills(self) -> None:
        """Override to register agent-specific skills. Called in __init__."""
        pass

    def get_skills(self) -> Dict[str, Skill]:
        """Get all registered skills."""
        return self._skills

    def invoke_skill(self, name: str, **kwargs) -> Any:
        """Invoke a registered skill by name."""
        skill = self._skills.get(name)
        if not skill:
            raise ValueError(f"Skill '{name}' not registered for agent '{self.agent_name}'")
        return skill.handler(**kwargs)

    # ── Knowledge base ingestion (fire-and-forget) ──

    def register_to_knowledge_base(
        self,
        doc_data: Dict[str, Any],
        created_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Registra um documento (artigo PubMed, legislacao, etc.) na knowledge_catalog
        durante a execucao do agente. Fire-and-forget: nunca levanta excecao.

        Usa-se quando o agente, ao consultar fonte externa durante atendimento,
        encontra material relevante que ainda nao esta no catalogo. A insercao
        usa dedup por DOI/source_url, entao chamadas repetidas para o mesmo
        artigo sao seguras.

        Marca ingested_by com o nome do agente + sufixo "_auto" para distinguir
        do fluxo manual.
        """
        try:
            from src.knowledge.auto_ingest import register_article_in_catalog

            payload = dict(doc_data)
            payload.setdefault("ingested_by", f"agent_{self.agent_name}_auto")
            if created_by is not None:
                payload["created_by"] = created_by

            return register_article_in_catalog(payload)
        except Exception as e:
            logger.warning(
                "Agent '%s' failed to register article in knowledge base: %s",
                self.agent_name,
                e,
            )
            return {"registered": False, "reason": "exception", "error": str(e), "catalog_id": None}

    # ── Execution ──

    @abstractmethod
    def execute(self, **kwargs) -> AgentResult:
        """
        Execute the agent's main task.
        Must be implemented by each agent.

        Returns AgentResult with success/failure, data, tokens, etc.
        """
        ...

    def run(self, **kwargs) -> AgentResult:
        """
        Run the agent with timing and error handling.
        Wraps execute() — sem memory ops (MemPalace extirpado em Track C.2).
        """
        start = time.time()
        result = AgentResult(success=False, agent_name=self.agent_name)

        # Compat com call sites pre-C.2 (clinical_flow ainda passa _memory_query
        # e agentes individuais checam _memory_context). Pop e descarta — nada
        # alimenta esses kwargs apos a extirpacao do MemPalace.
        kwargs.pop("_memory_query", None)

        try:
            result = self.execute(**kwargs)
            result.agent_name = self.agent_name
            result.duration_ms = int((time.time() - start) * 1000)
        except Exception as e:
            result.duration_ms = int((time.time() - start) * 1000)
            result.error = str(e)
            logger.error("Agent '%s' failed: %s", self.agent_name, e, exc_info=True)

        return result

    def __repr__(self) -> str:
        skills = ", ".join(self._skills.keys())
        return f"<{self.__class__.__name__} skills=[{skills}]>"
