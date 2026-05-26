# src/infra/tasks.py
"""
Fila assíncrona para processamento de IA via Redis + RQ.

Arquitetura:
  - O endpoint HTTP enfileira a tarefa e retorna imediatamente um `task_id`.
  - Um worker RQ separado processa a tarefa em background.
  - O resultado fica armazenado no Redis por 24h (configurável).
  - Polling via GET /api/v1/ai/tasks/<task_id> retorna status e resultado.

Variáveis de ambiente:
  REDIS_URL           — URL de conexão ao Redis (padrão: redis://localhost:6379/0)
  TASK_RESULT_TTL     — TTL dos resultados em segundos (padrão: 86400 = 24h)
  TASK_FAILURE_TTL    — TTL de tarefas com falha em segundos (padrão: 172800 = 48h)
  TASK_DEFAULT_TIMEOUT — Timeout máximo por tarefa em segundos (padrão: 300 = 5min)
  TASK_MAX_RETRIES    — Número máximo de retentativas (padrão: 3)

Worker:
  Iniciar com: rq worker cannabia-ai --url $REDIS_URL
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger("cannabia.tasks")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = "cannabia-ai"
RESULT_TTL = int(os.getenv("TASK_RESULT_TTL", "86400"))         # 24h
FAILURE_TTL = int(os.getenv("TASK_FAILURE_TTL", "172800"))       # 48h
DEFAULT_TIMEOUT = int(os.getenv("TASK_DEFAULT_TIMEOUT", "300"))  # 5min
MAX_RETRIES = int(os.getenv("TASK_MAX_RETRIES", "3"))


class TaskStatus(Enum):
    QUEUED = "queued"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"
    DEFERRED = "deferred"


@dataclass
class TaskInfo:
    """Representação serializada do estado de uma tarefa."""
    task_id: str
    status: str
    created_at: Optional[float] = None
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retries_left: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


# ═══════════════════════════════════════════════════════════════════════════════
# CONEXÃO REDIS (LAZY)
# ═══════════════════════════════════════════════════════════════════════════════

_redis_conn = None


def _get_redis():
    """Conexão lazy ao Redis. Importa redis apenas quando necessário."""
    global _redis_conn
    if _redis_conn is None:
        from redis import Redis
        _redis_conn = Redis.from_url(REDIS_URL)
        logger.info("Conexão Redis estabelecida: %s", REDIS_URL)
    return _redis_conn


def _get_queue():
    """Retorna a fila RQ configurada."""
    from rq import Queue
    return Queue(
        name=QUEUE_NAME,
        connection=_get_redis(),
        default_timeout=DEFAULT_TIMEOUT,
    )


def redis_available() -> bool:
    """Verifica se o Redis está acessível (para health check)."""
    try:
        return _get_redis().ping()
    except Exception:
        # Health check é borda: qualquer falha (ImportError do pacote, rede,
        # auth, config) significa "Redis indisponivel agora". Log em debug
        # para investigacao sem poluir logs em dev sem Redis local.
        logger.debug("Redis indisponivel para ping (health check)", exc_info=True)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# TASK DEFINITIONS — Funções executadas pelo worker RQ
# ═══════════════════════════════════════════════════════════════════════════════

def _execute_ai_pipeline(
    data: Dict[str, Any],
    clinic_id: int,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Função executada pelo worker RQ.
    Importa o pipeline sob demanda para evitar dependências circulares.
    """
    from src.ai.clinical_flow import build_clinical_flow
    from src.ai.schemas import AnamnesisInput
    from src.ai.guardrails import validate_input
    from src.ai.validators import normalize_anamnesis_payload

    start = time.time()

    # Validação de segurança (guardrails)
    guardrail_result = validate_input(data)
    if not guardrail_result.passed:
        raise ValueError(
            f"Guardrail bloqueou input [{guardrail_result.blocked_by.value}]: "
            f"{guardrail_result.reason}"
        )

    # Normalização e validação estrutural
    normalized = normalize_anamnesis_payload(data)
    anamnesis = AnamnesisInput(**normalized)

    # Execução do pipeline
    flow = build_clinical_flow()
    result = flow.run(anamnesis)

    elapsed_ms = int((time.time() - start) * 1000)
    result["total_time_ms"] = elapsed_ms
    result["clinic_id"] = clinic_id
    result["user_id"] = user_id
    result["request_id"] = request_id

    logger.info(
        "Pipeline assíncrono concluído em %dms (clinic_id=%s, request_id=%s)",
        elapsed_ms, clinic_id, request_id,
    )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# API PÚBLICA — Enfileirar e consultar tarefas
# ═══════════════════════════════════════════════════════════════════════════════

def enqueue_ai_task(
    data: Dict[str, Any],
    clinic_id: int,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> str:
    """
    Enfileira uma tarefa de processamento de IA.
    Retorna o task_id para polling posterior.

    Retry com backoff é configurado via RQ Retry.
    """
    from rq import Retry

    queue = _get_queue()

    job = queue.enqueue(
        _execute_ai_pipeline,
        kwargs={
            "data": data,
            "clinic_id": clinic_id,
            "user_id": user_id,
            "request_id": request_id,
        },
        result_ttl=RESULT_TTL,
        failure_ttl=FAILURE_TTL,
        retry=Retry(max=MAX_RETRIES, interval=[10, 30, 60]),
        description=f"AI pipeline clinic={clinic_id} req={request_id}",
    )

    logger.info(
        "Tarefa enfileirada: job_id=%s, clinic_id=%s, request_id=%s",
        job.id, clinic_id, request_id,
    )

    return job.id


def get_task_status(task_id: str) -> TaskInfo:
    """
    Consulta o status de uma tarefa pelo ID.
    Retorna TaskInfo com estado atual e resultado (se concluído).
    """
    from rq.job import Job
    from rq.exceptions import NoSuchJobError

    try:
        job = Job.fetch(task_id, connection=_get_redis())
    except NoSuchJobError:
        return TaskInfo(
            task_id=task_id,
            status="not_found",
            error="Tarefa não encontrada ou expirada.",
        )

    status_map = {
        "queued": TaskStatus.QUEUED.value,
        "started": TaskStatus.STARTED.value,
        "finished": TaskStatus.FINISHED.value,
        "failed": TaskStatus.FAILED.value,
        "deferred": TaskStatus.DEFERRED.value,
    }

    job_status = status_map.get(job.get_status(), job.get_status())

    info = TaskInfo(
        task_id=task_id,
        status=job_status,
        created_at=job.enqueued_at.timestamp() if job.enqueued_at else None,
        started_at=job.started_at.timestamp() if job.started_at else None,
        ended_at=job.ended_at.timestamp() if job.ended_at else None,
        retries_left=getattr(job, "retries_left", 0),
    )

    if job_status == TaskStatus.FINISHED.value:
        info.result = job.result
    elif job_status == TaskStatus.FAILED.value:
        info.error = str(job.exc_info) if job.exc_info else "Erro desconhecido"

    return info


def get_queue_stats() -> Dict[str, Any]:
    """Retorna estatísticas da fila (para health check e métricas)."""
    try:
        from rq import Queue
        queue = _get_queue()
        return {
            "name": QUEUE_NAME,
            "queued": len(queue),
            "redis_connected": redis_available(),
        }
    except Exception as exc:
        return {
            "name": QUEUE_NAME,
            "error": str(exc),
            "redis_connected": False,
        }
