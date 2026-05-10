# src/web/routes/admin_agents.py
"""
Agent management and monitoring API.
Prefix: /api/v1/admin/agents
"""
from __future__ import annotations
import logging
from flask import Blueprint, request
from src.web.routes.api_v1 import _error, _success, _json_payload, _require_json_csrf, api_role_required

logger = logging.getLogger("cannabia.admin_agents")
admin_agents_bp = Blueprint("admin_agents", __name__, url_prefix="/api/v1/admin/agents")


@admin_agents_bp.get("/")
@api_role_required("Admin", "Medico")
def list_agents():
    """List all registered agents with their skills and status."""
    from src.ai.agents import (
        AgenteTriagem, AgenteAnamnese, AgenteTratamento, AgentePrescritor,
        AgenteCientifico, AgenteRegulatorio, AgenteFollowUp,
        AgenteExtrator,
    )

    agents_list = []
    agent_classes = [
        AgenteTriagem, AgenteAnamnese, AgenteTratamento, AgentePrescritor,
        AgenteCientifico, AgenteRegulatorio, AgenteFollowUp,
        AgenteExtrator,
    ]

    for cls in agent_classes:
        try:
            instance = cls()
            skills = []
            for name, skill in instance.get_skills().items():
                skills.append({
                    "name": name,
                    "description": skill.description,
                })

            # Try to get diary count
            diary_count = 0
            try:
                diary = instance.get_diary(last_n=100)
                diary_count = len(diary)
            except Exception:
                logger.debug(
                    "Diary count unavailable for %s (non-critical)",
                    cls.__name__,
                    exc_info=True,
                )

            agents_list.append({
                "name": instance.agent_name,
                "class": cls.__name__,
                "description": instance.description,
                "palace_room": instance.palace_room,
                "skills_count": len(skills),
                "skills": skills,
                "diary_entries": diary_count,
                "status": "active",
            })
        except Exception as e:
            agents_list.append({
                "name": cls.__name__,
                "class": cls.__name__,
                "description": "Error loading agent",
                "status": "error",
                "error": str(e),
            })

    return _success(agents_list)


@admin_agents_bp.get("/<agent_name>/diary")
@api_role_required("Admin", "Medico")
def get_agent_diary(agent_name: str):
    """Get recent diary entries for a specific agent."""
    from src.ai.agents import (
        AgenteTriagem, AgenteAnamnese, AgenteTratamento, AgentePrescritor,
        AgenteCientifico, AgenteRegulatorio, AgenteFollowUp,
        AgenteExtrator,
    )

    agent_map = {
        "triagem": AgenteTriagem,
        "anamnese": AgenteAnamnese,
        "tratamento": AgenteTratamento,
        "prescritor": AgentePrescritor,
        "cientifico": AgenteCientifico,
        "regulatorio": AgenteRegulatorio,
        "follow_up": AgenteFollowUp,
        "extrator": AgenteExtrator,
    }

    cls = agent_map.get(agent_name)
    if not cls:
        return _error("not_found", f"Agente '{agent_name}' nao encontrado.", 404)

    try:
        last_n = request.args.get("last_n", 20, type=int)
        instance = cls()
        diary = instance.get_diary(last_n=last_n)
        return _success(diary)
    except Exception as e:
        logger.error("Error fetching diary for %s: %s", agent_name, e)
        # FIXME(sprint-2): decidir entre 500 explicito vs empty data conforme
        # contrato com frontend (ver Track D do Sprint 1).
        return _success([])


@admin_agents_bp.get("/<agent_name>/skills")
@api_role_required("Admin", "Medico")
def get_agent_skills(agent_name: str):
    """Get detailed skills for a specific agent."""
    from src.ai.agents import (
        AgenteTriagem, AgenteAnamnese, AgenteTratamento, AgentePrescritor,
        AgenteCientifico, AgenteRegulatorio, AgenteFollowUp,
        AgenteExtrator,
    )

    agent_map = {
        "triagem": AgenteTriagem,
        "anamnese": AgenteAnamnese,
        "tratamento": AgenteTratamento,
        "prescritor": AgentePrescritor,
        "cientifico": AgenteCientifico,
        "regulatorio": AgenteRegulatorio,
        "follow_up": AgenteFollowUp,
        "extrator": AgenteExtrator,
    }

    cls = agent_map.get(agent_name)
    if not cls:
        return _error("not_found", f"Agente '{agent_name}' nao encontrado.", 404)

    try:
        instance = cls()
        skills = []
        for name, skill in instance.get_skills().items():
            skills.append({
                "name": name,
                "description": skill.description,
                "input_schema": skill.input_schema,
                "output_schema": skill.output_schema,
            })
        return _success({
            "agent": instance.agent_name,
            "palace_room": instance.palace_room,
            "description": instance.description,
            "skills": skills,
        })
    except Exception as e:
        logger.error("Error fetching skills for %s: %s", agent_name, e)
        return _error("internal_error", str(e), 500)


@admin_agents_bp.post("/<agent_name>/execute")
@api_role_required("Admin")
def execute_agent(agent_name: str):
    """Execute an agent with given parameters (admin testing)."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    from src.ai.agents import (
        AgenteTriagem, AgenteAnamnese, AgenteTratamento, AgentePrescritor,
        AgenteCientifico, AgenteRegulatorio, AgenteFollowUp,
        AgenteExtrator,
    )

    agent_map = {
        "triagem": AgenteTriagem,
        "anamnese": AgenteAnamnese,
        "tratamento": AgenteTratamento,
        "prescritor": AgentePrescritor,
        "cientifico": AgenteCientifico,
        "regulatorio": AgenteRegulatorio,
        "follow_up": AgenteFollowUp,
        "extrator": AgenteExtrator,
    }

    cls = agent_map.get(agent_name)
    if not cls:
        return _error("not_found", f"Agente '{agent_name}' nao encontrado.", 404)

    payload = _json_payload()

    try:
        instance = cls()
        result = instance.run(**payload)
        return _success({
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "duration_ms": result.duration_ms,
            "confidence": result.confidence,
            "skills_used": result.skills_used,
            "tokens": result.tokens,
        })
    except Exception as e:
        logger.error("Agent execution failed: %s", e, exc_info=True)
        return _error("internal_error", f"Falha ao executar agente: {str(e)}", 500)
