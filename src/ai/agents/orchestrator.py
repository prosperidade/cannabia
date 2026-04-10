# src/ai/agents/orchestrator.py
"""
Orchestrator — chains multiple agents together.

Manages:
- Sequential chains (A → B → C)
- Parallel execution (future)
- Result passing between agents
- Chain-level diary logging
- Error handling and partial results
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from src.ai.agents.base import AgentResult, BaseAgent
from src.ai.memory import diary_write, kg_add

logger = logging.getLogger("cannabia.orchestrator")


@dataclass
class ChainStep:
    """A step in an orchestration chain."""
    agent_class: Type[BaseAgent]
    input_map: Optional[Dict[str, str]] = None  # Maps previous output keys to this step's input
    required: bool = True  # If False, chain continues on failure
    memory_query: Optional[str] = None  # Query for agent recall


@dataclass
class ChainResult:
    """Result from a chain execution."""
    success: bool
    steps: List[AgentResult] = field(default_factory=list)
    final_data: Dict[str, Any] = field(default_factory=dict)
    total_duration_ms: int = 0
    total_tokens: Dict[str, int] = field(default_factory=dict)
    chain_name: str = ""
    failed_at: Optional[str] = None


class Orchestrator:
    """
    Chains agents together with data passing and logging.

    Usage:
        orch = Orchestrator()
        result = orch.run_chain(
            name="diagnostico_completo",
            steps=[
                ChainStep(AgenteAnamnese),
                ChainStep(AgentePrescritor, input_map={"clinical_analysis": "data.clinical_analysis"}),
                ChainStep(AgenteCientifico, input_map={"treatment_plan": "data.treatment_plan"}),
            ],
            initial_data={"patient_data": {...}},
        )
    """

    def __init__(self) -> None:
        self._agent_cache: Dict[str, BaseAgent] = {}

    def _get_agent(self, agent_class: Type[BaseAgent]) -> BaseAgent:
        """Get or create an agent instance (cached)."""
        key = agent_class.__name__
        if key not in self._agent_cache:
            self._agent_cache[key] = agent_class()
        return self._agent_cache[key]

    def _resolve_input(self, input_map: Optional[Dict[str, str]],
                       accumulated: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve input mapping from accumulated chain data."""
        if not input_map:
            return accumulated.copy()

        resolved = {}
        for target_key, source_path in input_map.items():
            # Navigate dotted path: "data.clinical_analysis" → accumulated["data"]["clinical_analysis"]
            value = accumulated
            for part in source_path.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = None
                    break
            if value is not None:
                resolved[target_key] = value

        return resolved

    def run_chain(
        self,
        name: str,
        steps: List[ChainStep],
        initial_data: Optional[Dict[str, Any]] = None,
        clinic_id: Optional[int] = None,
    ) -> ChainResult:
        """
        Execute a chain of agents sequentially.

        Args:
            name: Chain name (for logging)
            steps: Ordered list of ChainSteps
            initial_data: Starting data for the chain
            clinic_id: Clinic context

        Returns:
            ChainResult with all step results and accumulated data
        """
        chain_start = time.time()
        accumulated = initial_data.copy() if initial_data else {}
        step_results: List[AgentResult] = []
        total_tokens: Dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        agent_names: List[str] = []

        logger.info("Starting chain '%s' with %d steps", name, len(steps))

        for i, step in enumerate(steps):
            agent = self._get_agent(step.agent_class)
            agent_names.append(agent.agent_name)

            # Resolve input from accumulated data
            step_input = self._resolve_input(step.input_map, accumulated)

            # Add memory query if specified
            if step.memory_query:
                step_input["_memory_query"] = step.memory_query

            logger.info(
                "Chain '%s' step %d/%d: %s",
                name, i + 1, len(steps), agent.agent_name,
            )

            # Execute step
            result = agent.run(**step_input)
            step_results.append(result)

            # Accumulate tokens
            for k in total_tokens:
                total_tokens[k] += result.tokens.get(k, 0)

            if result.success:
                # Merge result data into accumulated
                accumulated.update(result.data)
                logger.info(
                    "Chain '%s' step %d OK: %s (%dms)",
                    name, i + 1, agent.agent_name, result.duration_ms,
                )
            else:
                logger.warning(
                    "Chain '%s' step %d FAILED: %s — %s",
                    name, i + 1, agent.agent_name, result.error,
                )
                if step.required:
                    # Required step failed — abort chain
                    chain_result = ChainResult(
                        success=False,
                        steps=step_results,
                        final_data=accumulated,
                        total_duration_ms=int((time.time() - chain_start) * 1000),
                        total_tokens=total_tokens,
                        chain_name=name,
                        failed_at=agent.agent_name,
                    )
                    # Log chain failure
                    diary_write(
                        "pipeline_anamnese",
                        f"[CHAIN FAIL] {name} failed_at={agent.agent_name} "
                        f"step={i+1}/{len(steps)} agents={agent_names}",
                    )
                    return chain_result

        total_ms = int((time.time() - chain_start) * 1000)

        chain_result = ChainResult(
            success=True,
            steps=step_results,
            final_data=accumulated,
            total_duration_ms=total_ms,
            total_tokens=total_tokens,
            chain_name=name,
        )

        # Log chain success
        diary_write(
            "pipeline_anamnese",
            f"[CHAIN OK] {name} agents={agent_names} duration={total_ms}ms",
        )

        # Knowledge graph
        if clinic_id:
            kg_add(
                f"clinic_{clinic_id}",
                f"chain_{name}_completed",
                f"agents={','.join(agent_names)} duration={total_ms}ms",
            )

        logger.info(
            "Chain '%s' completed: %d steps, %dms, tokens=%s",
            name, len(steps), total_ms, total_tokens,
        )

        return chain_result

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all cached agent instances with their skills."""
        return [
            {
                "name": agent.agent_name,
                "room": agent.palace_room,
                "description": agent.description,
                "skills": list(agent.get_skills().keys()),
            }
            for agent in self._agent_cache.values()
        ]
