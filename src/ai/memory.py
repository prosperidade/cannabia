# src/ai/memory.py
"""
MemPalace integration — persistent memory for AI agents.

Fire-and-forget design: ALL operations are wrapped in try/except.
If MemPalace is not installed or fails, agents continue running normally.

Usage:
    from src.ai.memory import diary_write, diary_read, kg_add, kg_query, search, recall_agent_context

    # Write diary entry (auto-logged by BaseAgent.run())
    diary_write("prescricao", "Calculou dosagem CBD 20:1 para fibromialgia. Confianca: 0.85")

    # Read recent diary
    entries = diary_read("prescricao", last_n=5)

    # Knowledge graph
    kg_add("CBD_20:1", "eficaz_para", "fibromialgia")
    facts = kg_query("CBD_20:1")

    # Semantic search
    results = search("fibromialgia feminino 50 anos", room="pipeline_prescricao", limit=5)

    # Full agent context recall
    context = recall_agent_context("prescricao", "fibromialgia CBD dosagem")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cannabia.memory")

WING = "cannabia_clinical"

# LGPD filter patterns — NEVER store PII in the palace
_PII_PATTERNS = [
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[CPF_REDACTED]"),          # CPF
    (re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"), "[CNPJ_REDACTED]"),    # CNPJ
    (re.compile(r"\b\d{4,5}-?\d{4}\b"), "[PHONE_REDACTED]"),                     # Phone suffix
    (re.compile(r"\b55\d{10,11}\b"), "[PHONE_REDACTED]"),                         # Full BR phone
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[EMAIL_REDACTED]"),  # Email
    (re.compile(r"\b(?:Rua|Av|Avenida|Alameda|Travessa)\s+[A-Z][a-zA-Z\s,]+\d+", re.IGNORECASE), "[ADDRESS_REDACTED]"),
]

# Patient name patterns — redact proper names near clinical data
_NAME_PATTERNS = [
    (re.compile(r"(?:paciente|patient|nome)\s*[:=]\s*[A-Z][a-záéíóúãõâêîôû]+(?:\s+[A-Z][a-záéíóúãõâêîôû]+)+", re.IGNORECASE), "[PATIENT_NAME_REDACTED]"),
]


def _sanitize_pii(text: str) -> str:
    """Remove PII from text before storing in MemPalace. LGPD compliance."""
    if not text:
        return text
    for pattern, replacement in _PII_PATTERNS + _NAME_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _get_palace():
    """Lazy import of mempalace. Returns None if not installed."""
    try:
        import mempalace
        return mempalace
    except ImportError:
        return None


def diary_write(room: str, content: str, hall: str = "hall_events") -> bool:
    """Write a diary entry for an agent. Returns True if successful."""
    try:
        mp = _get_palace()
        if mp is None:
            logger.debug("MemPalace not installed — diary_write skipped")
            return False

        sanitized = _sanitize_pii(content)
        mp.diary_write(wing=WING, room=room, content=sanitized, hall=hall)
        return True
    except Exception:
        logger.debug("diary_write failed (non-critical)", exc_info=True)
        return False


def diary_read(room: str, last_n: int = 10) -> List[Dict]:
    """Read recent diary entries for an agent."""
    try:
        mp = _get_palace()
        if mp is None:
            return []

        entries = mp.diary_read(wing=WING, room=room, last_n=last_n)
        return entries if entries else []
    except Exception:
        logger.debug("diary_read failed (non-critical)", exc_info=True)
        return []


def kg_add(subject: str, predicate: str, obj: str, confidence: str = "high") -> bool:
    """Add a fact to the knowledge graph."""
    try:
        mp = _get_palace()
        if mp is None:
            return False

        # Sanitize all parts
        subject = _sanitize_pii(subject)
        obj = _sanitize_pii(obj)

        mp.kg_add(
            wing=WING,
            subject=subject,
            predicate=predicate,
            object=obj,
            metadata={"confidence": confidence},
        )
        return True
    except Exception:
        logger.debug("kg_add failed (non-critical)", exc_info=True)
        return False


def kg_query(entity: str, limit: int = 10) -> List[Dict]:
    """Query the knowledge graph for facts about an entity."""
    try:
        mp = _get_palace()
        if mp is None:
            return []

        facts = mp.kg_query(wing=WING, entity=entity, limit=limit)
        return facts if facts else []
    except Exception:
        logger.debug("kg_query failed (non-critical)", exc_info=True)
        return []


def search(query: str, room: Optional[str] = None, limit: int = 5) -> List[Dict]:
    """Semantic search across the palace."""
    try:
        mp = _get_palace()
        if mp is None:
            return []

        results = mp.search(
            wing=WING,
            query=query,
            room=room,
            limit=limit,
        )
        return results if results else []
    except Exception:
        logger.debug("search failed (non-critical)", exc_info=True)
        return []


def save_to_room(room: str, content: str, hall: str = "hall_facts") -> bool:
    """Save content to a specific room/hall."""
    try:
        mp = _get_palace()
        if mp is None:
            return False

        sanitized = _sanitize_pii(content)
        mp.add_drawer(wing=WING, room=room, hall=hall, content=sanitized)
        return True
    except Exception:
        logger.debug("save_to_room failed (non-critical)", exc_info=True)
        return False


def recall_agent_context(room: str, query: str, diary_n: int = 5, search_n: int = 3) -> Dict[str, Any]:
    """
    Full context recall for an agent: recent diary + semantic search.

    Returns:
        {
            "recent_diary": [...],
            "search_results": [...],
            "has_memory": bool
        }
    """
    recent = diary_read(room, last_n=diary_n)
    results = search(query, room=room, limit=search_n)

    return {
        "recent_diary": recent,
        "search_results": results,
        "has_memory": bool(recent or results),
    }
