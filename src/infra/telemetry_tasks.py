# src/infra/telemetry_tasks.py
"""
Tarefas RQ para o motor de Telemetria Pós-Consulta.

Tarefas:
  1. schedule_daily_followups — Cronjob diário: lê consultas do dia e agenda D+3/D+7/D+15.
  2. dispatch_pending_followups — Cronjob periódico: processa follow-ups pendentes.

Worker:
  rq worker cannabia-telemetry --url $REDIS_URL

Scheduler (rq-scheduler ou cron externo):
  - schedule_daily_followups: executar 1x/dia às 09:00 UTC
  - dispatch_pending_followups: executar a cada 15 minutos
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict

logger = logging.getLogger("cannabia.telemetry_tasks")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TELEMETRY_QUEUE_NAME = "cannabia-telemetry"
TELEMETRY_RESULT_TTL = 3600       # 1h
TELEMETRY_FAILURE_TTL = 86400     # 24h
TELEMETRY_TIMEOUT = 120           # 2min por job


# ═══════════════════════════════════════════════════════════════════════════════
# CONEXÃO REDIS / FILA (reutiliza a conexão do tasks.py se disponível)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_telemetry_queue():
    """Retorna a fila RQ dedicada a telemetria."""
    from rq import Queue
    from src.infra.tasks import _get_redis
    return Queue(
        name=TELEMETRY_QUEUE_NAME,
        connection=_get_redis(),
        default_timeout=TELEMETRY_TIMEOUT,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TASK DEFINITIONS — Executadas pelo worker RQ
# ═══════════════════════════════════════════════════════════════════════════════

def _run_schedule_daily_followups() -> Dict[str, Any]:
    """
    Worker task: lê anamneses de hoje e agenda follow-ups D+3, D+7, D+15.
    Idempotente — pode rodar múltiplas vezes no dia sem duplicar.
    """
    start = time.time()

    from src.services.telemetry_crm_service import TelemetryCRMService

    service = TelemetryCRMService()
    result = service.schedule_followups_for_today()

    elapsed_ms = int((time.time() - start) * 1000)
    result["elapsed_ms"] = elapsed_ms

    logger.info("schedule_daily_followups concluído em %dms: %s", elapsed_ms, result)
    return result


def _run_dispatch_pending_followups() -> Dict[str, Any]:
    """
    Worker task: processa follow-ups pendentes e envia via WhatsApp.
    Seguro para execução concorrente (cada follow-up processado uma vez).
    """
    start = time.time()

    from src.services.telemetry_crm_service import TelemetryCRMService

    service = TelemetryCRMService()
    result = service.process_pending_followups(limit=50)

    elapsed_ms = int((time.time() - start) * 1000)
    result["elapsed_ms"] = elapsed_ms

    logger.info("dispatch_pending_followups concluído em %dms: %s", elapsed_ms, result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# API PÚBLICA — Enfileirar tarefas de telemetria
# ═══════════════════════════════════════════════════════════════════════════════

def enqueue_schedule_daily_followups() -> str:
    """
    Enfileira a tarefa de agendamento diário.
    Retorna job_id para rastreamento.

    Chamado por:
      - Cron externo (Render Cron Job, systemd timer, ou rq-scheduler)
      - Endpoint admin manual: POST /api/telemetry/admin/schedule-now
    """
    queue = _get_telemetry_queue()

    job = queue.enqueue(
        _run_schedule_daily_followups,
        result_ttl=TELEMETRY_RESULT_TTL,
        failure_ttl=TELEMETRY_FAILURE_TTL,
        description="Telemetry: schedule daily followups",
    )

    logger.info("Tarefa schedule_daily_followups enfileirada: job_id=%s", job.id)
    return job.id


def enqueue_dispatch_pending_followups() -> str:
    """
    Enfileira a tarefa de envio de follow-ups pendentes.
    Retorna job_id.

    Chamado a cada 15min por cron externo ou rq-scheduler.
    """
    queue = _get_telemetry_queue()

    job = queue.enqueue(
        _run_dispatch_pending_followups,
        result_ttl=TELEMETRY_RESULT_TTL,
        failure_ttl=TELEMETRY_FAILURE_TTL,
        description="Telemetry: dispatch pending followups",
    )

    logger.info("Tarefa dispatch_pending enfileirada: job_id=%s", job.id)
    return job.id


def get_telemetry_queue_stats() -> Dict[str, Any]:
    """Estatísticas da fila de telemetria."""
    try:
        queue = _get_telemetry_queue()
        return {
            "name": TELEMETRY_QUEUE_NAME,
            "queued": len(queue),
            "redis_connected": True,
        }
    except Exception as exc:
        return {
            "name": TELEMETRY_QUEUE_NAME,
            "error": str(exc),
            "redis_connected": False,
        }
