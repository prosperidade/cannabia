# src/ai/agents/base.py
"""
BaseAgent — foundation for all Cannabia AI agents.

Each agent:
- Has a palace_room for MemPalace memory
- Auto-logs execution diary entries
- Can recall past memory and remember new facts
- Has registered skills (callable functions)
- Reports execution metrics (duration, tokens, cost)

Design: Fire-and-forget for memory ops. Agent execution NEVER blocked by memory failures.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.ai.memory import (
    diary_write,
    diary_read,
    kg_add,
    kg_query,
    recall_agent_context,
    _sanitize_pii,
)

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
        - palace_room: str (MemPalace room name)
        - agent_name: str (display name)
        - description: str (what this agent does)
    """

    palace_room: str = "general"
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

    # ── Memory Operations (fire-and-forget) ──

    def recall_memory(self, query: str, diary_n: int = 5, search_n: int = 3) -> Dict:
        """Recall relevant past memory for this agent."""
        return recall_agent_context(self.palace_room, query, diary_n=diary_n, search_n=search_n)

    def remember(self, content: str) -> bool:
        """Save a note to this agent's diary."""
        sanitized = _sanitize_pii(content)
        return diary_write(self.palace_room, sanitized)

    def remember_fact(self, subject: str, predicate: str, obj: str, confidence: str = "high") -> bool:
        """Add a structured fact to the knowledge graph."""
        return kg_add(subject, predicate, obj, confidence)

    def get_diary(self, last_n: int = 10) -> List[Dict]:
        """Get recent diary entries for this agent."""
        return diary_read(self.palace_room, last_n=last_n)

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
        Run the agent with automatic diary logging and metrics.
        Wraps execute() with timing, memory ops, and error handling.
        """
        start = time.time()
        result = AgentResult(success=False, agent_name=self.agent_name)

        try:
            # Optional: recall context if query provided
            context_query = kwargs.pop("_memory_query", None)
            if context_query:
                memory = self.recall_memory(context_query)
                if memory.get("has_memory"):
                    kwargs["_memory_context"] = memory

            # Execute agent logic
            result = self.execute(**kwargs)
            result.agent_name = self.agent_name
            result.duration_ms = int((time.time() - start) * 1000)

            # Auto-log success diary
            diary_write(
                self.palace_room,
                f"[OK] {self.agent_name} | duration={result.duration_ms}ms | "
                f"confidence={result.confidence:.2f} | skills={result.skills_used}",
            )

            # Auto-log knowledge graph fact
            if result.success and result.data.get("_kg_subject"):
                kg_add(
                    result.data["_kg_subject"],
                    f"analyzed_by_{self.agent_name}",
                    f"confidence={result.confidence}",
                )

        except Exception as e:
            result.duration_ms = int((time.time() - start) * 1000)
            result.error = str(e)
            logger.error("Agent '%s' failed: %s", self.agent_name, e, exc_info=True)

            # Auto-log failure diary
            diary_write(
                self.palace_room,
                f"[FAIL] {self.agent_name} | duration={result.duration_ms}ms | error={str(e)[:200]}",
            )

        return result

    def __repr__(self) -> str:
        skills = ", ".join(self._skills.keys())
        return f"<{self.__class__.__name__} room='{self.palace_room}' skills=[{skills}]>"
