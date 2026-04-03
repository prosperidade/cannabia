# src/services/campaign_service.py
"""
Motor de Campanhas Ativas com despacho assíncrono.

Responsável por:
  - CRUD de templates de campanha (WhatsApp, e-mail, SMS)
  - Interpolação de variáveis Mustache: {{patient_name}}, {{appointment_date}}
  - Criação de execuções com enfileiramento para task queue
  - Despacho rate-limited por destinatário individual
  - Rastreamento granular de status por recipient

Arquitetura de despacho:
  1. API chama `enqueue_campaign()` → cria execution com status 'queued'
  2. Task assíncrona `execute_campaign_task()` é enfileirada
  3. Worker processa cada recipient sequencialmente com rate limit
  4. Contadores (sent_count, failed_count) atualizados em tempo real
  5. Status final: 'completed' ou 'failed' com error_summary

Canais suportados:
  - whatsapp: via `src/integrations/whatsapp.py` (send_whatsapp_text)
  - email:    via `src/integrations/email.py` (send_email_notification)
  - sms:      reservado para integração futura
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

from src.infra.audit import log_audit_event
from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.campaigns")

# Rate limit padrão: máximo de mensagens por segundo por execução
DEFAULT_RATE_LIMIT_PER_SECOND = 5

# Variável de template: padrão Mustache {{nome_da_variavel}}
_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


# ═══════════════════════════════════════════════════════════════════════════
# Interpolação de variáveis
# ═══════════════════════════════════════════════════════════════════════════

def interpolate_template(template_body: str, variables: dict[str, str]) -> str:
    """
    Substitui variáveis Mustache no corpo do template.

    Variáveis não resolvidas permanecem como {{nome}} para rastreabilidade.
    Valores None são substituídos por string vazia.

    Exemplo:
        interpolate_template("Olá {{patient_name}}", {"patient_name": "Maria"})
        → "Olá Maria"
    """
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        value = variables.get(key)
        if value is None:
            return match.group(0)  # Mantém {{key}} se não resolvido
        return str(value)

    return _VAR_PATTERN.sub(replacer, template_body)


def extract_variable_names(template_body: str) -> list[str]:
    """Extrai nomes de variáveis únicas do template."""
    return list(dict.fromkeys(_VAR_PATTERN.findall(template_body)))


# ═══════════════════════════════════════════════════════════════════════════
# CRUD de Templates
# ═══════════════════════════════════════════════════════════════════════════

def create_template(
    tenant_id: int,
    clinic_id: int,
    name: str,
    template_body: str,
    channel: str = "whatsapp",
    *,
    description: Optional[str] = None,
    created_by: Optional[int] = None,
) -> dict[str, Any]:
    """
    Cria um novo template de campanha.

    Extrai automaticamente as variáveis do corpo do template e as armazena
    no campo JSONB `variables` para referência.

    Args:
        tenant_id:     ID do tenant proprietário
        clinic_id:     ID da clínica associada
        name:          Nome identificador do template
        template_body: Corpo com variáveis Mustache ({{patient_name}})
        channel:       Canal de envio (whatsapp, email, sms)
        description:   Descrição opcional
        created_by:    ID do usuário criador

    Returns:
        Dict com dados do template criado

    Raises:
        ValueError: se dados inválidos ou canal não suportado
    """
    if not name or not name.strip():
        raise ValueError("nome do template é obrigatório.")
    if not template_body or not template_body.strip():
        raise ValueError("corpo do template é obrigatório.")

    valid_channels = {"whatsapp", "email", "sms"}
    if channel not in valid_channels:
        raise ValueError(f"Canal inválido. Valores aceitos: {valid_channels}")

    variables = extract_variable_names(template_body)

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO campaign_templates
                (tenant_id, clinic_id, name, description, channel,
                 template_body, variables, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, 'draft', %s)
            RETURNING id, name, channel, status, variables, created_at
            """,
            (
                tenant_id, clinic_id, name.strip(), description,
                channel, template_body.strip(),
                json.dumps(variables), created_by,
            ),
        )
        template = cursor.fetchone()
        conn.commit()

    log_audit_event(
        action="campaign_template_created",
        resource_type="campaign_template",
        resource_id=str(template["id"]),
        details={"name": name, "channel": channel, "variables": variables},
    )

    return dict(template)


def get_template(template_id: int, clinic_id: int) -> Optional[dict[str, Any]]:
    """Busca um template por ID, escopado pela clínica."""
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, tenant_id, clinic_id, name, description, channel,
                   template_body, variables, status, created_by, created_at, updated_at
            FROM campaign_templates
            WHERE id = %s AND clinic_id = %s
            """,
            (template_id, clinic_id),
        )
        return cursor.fetchone()


def list_templates(
    clinic_id: int,
    *,
    status: Optional[str] = None,
    channel: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lista templates da clínica com filtros opcionais."""
    conditions = ["clinic_id = %s"]
    params: list[Any] = [clinic_id]

    if status:
        conditions.append("status = %s")
        params.append(status)
    if channel:
        conditions.append("channel = %s")
        params.append(channel)

    params.append(limit)

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            f"""
            SELECT id, name, description, channel, status, variables, created_at, updated_at
            FROM campaign_templates
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            params,
        )
        return cursor.fetchall()


def update_template_status(template_id: int, clinic_id: int, status: str) -> dict[str, Any]:
    """Ativa ou arquiva um template de campanha."""
    valid = {"draft", "active", "archived"}
    if status not in valid:
        raise ValueError(f"Status inválido. Valores aceitos: {valid}")

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            UPDATE campaign_templates
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND clinic_id = %s
            RETURNING id, name, status, updated_at
            """,
            (status, template_id, clinic_id),
        )
        result = cursor.fetchone()
        if not result:
            raise ValueError("Template não encontrado.")
        conn.commit()

    return dict(result)


# ═══════════════════════════════════════════════════════════════════════════
# Resolução de destinatários
# ═══════════════════════════════════════════════════════════════════════════

def _resolve_recipients(
    clinic_id: int,
    channel: str,
    *,
    patient_ids: Optional[list[int]] = None,
) -> list[dict[str, Any]]:
    """
    Resolve a lista de destinatários da campanha.

    Se patient_ids for fornecido, filtra apenas esses pacientes.
    Caso contrário, seleciona todos os pacientes da clínica com endereço de canal válido.

    Returns:
        Lista de dicts com patient_id, patient_name e channel_address
    """
    address_column = "phone" if channel in ("whatsapp", "sms") else "email"

    conditions = ["clinic_id = %s", f"{address_column} IS NOT NULL", f"{address_column} != ''"]
    params: list[Any] = [clinic_id]

    if patient_ids:
        placeholders = ", ".join(["%s"] * len(patient_ids))
        conditions.append(f"id IN ({placeholders})")
        params.extend(patient_ids)

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            f"""
            SELECT id AS patient_id, name AS patient_name, {address_column} AS channel_address
            FROM patients
            WHERE {' AND '.join(conditions)}
            ORDER BY name
            """,
            params,
        )
        return cursor.fetchall()


# ═══════════════════════════════════════════════════════════════════════════
# Enfileiramento de Campanha
# ═══════════════════════════════════════════════════════════════════════════

def enqueue_campaign(
    template_id: int,
    clinic_id: int,
    *,
    triggered_by: Optional[int] = None,
    patient_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    """
    Prepara e enfileira uma execução de campanha para processamento assíncrono.

    Fluxo:
      1. Valida que o template existe e está ativo
      2. Resolve destinatários (todos ou subset por patient_ids)
      3. Cria execution com status 'queued'
      4. Insere campaign_recipients individuais com status 'pending'
      5. Despacha task assíncrona para o worker

    Args:
        template_id:  ID do template a executar
        clinic_id:    ID da clínica
        triggered_by: ID do usuário que disparou
        patient_ids:  Lista opcional de IDs de pacientes (None = todos)

    Returns:
        Dict com execution_id, target_count e status

    Raises:
        ValueError: template inválido, inativo, ou sem destinatários
    """
    template = get_template(template_id, clinic_id)
    if not template:
        raise ValueError("Template não encontrado.")
    if template["status"] != "active":
        raise ValueError(
            f"Template não está ativo (status: {template['status']}). "
            "Ative o template antes de disparar."
        )

    recipients = _resolve_recipients(clinic_id, template["channel"], patient_ids=patient_ids)
    if not recipients:
        raise ValueError(
            "Nenhum destinatário encontrado com endereço de "
            f"'{template['channel']}' válido."
        )

    # Cria execução + recipients em transação
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO campaign_executions
                (template_id, tenant_id, clinic_id, target_count, status, triggered_by)
            VALUES (%s, %s, %s, %s, 'queued', %s)
            RETURNING id
            """,
            (template_id, template["tenant_id"], clinic_id, len(recipients), triggered_by),
        )
        execution = cursor.fetchone()
        execution_id = execution["id"]

        # Insere recipients em batch
        values = []
        params: list[Any] = []
        for r in recipients:
            values.append("(%s, %s, %s, 'pending')")
            params.extend([execution_id, r["patient_id"], r["channel_address"]])

        if values:
            cursor.execute(
                f"""
                INSERT INTO campaign_recipients (execution_id, patient_id, channel_address, status)
                VALUES {', '.join(values)}
                """,
                params,
            )

        conn.commit()

    log_audit_event(
        action="campaign_enqueued",
        resource_type="campaign_execution",
        resource_id=str(execution_id),
        details={
            "template_id": template_id,
            "template_name": template["name"],
            "channel": template["channel"],
            "target_count": len(recipients),
            "triggered_by": triggered_by,
        },
    )

    # Despacha para task queue
    _dispatch_to_queue(execution_id)

    logger.info(
        "Campanha enfileirada: execution_id=%d template=%s recipients=%d",
        execution_id, template["name"], len(recipients),
    )

    return {
        "execution_id": execution_id,
        "template_id": template_id,
        "target_count": len(recipients),
        "status": "queued",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Despacho para Task Queue
# ═══════════════════════════════════════════════════════════════════════════

def _dispatch_to_queue(execution_id: int) -> None:
    """
    Enfileira a execução para processamento assíncrono.

    Tenta usar Redis/RQ se disponível. Em caso de falha na conexão com Redis,
    faz fallback para execução síncrona (modo degradado — útil em dev).
    """
    try:
        from redis import Redis
        from rq import Queue

        redis_conn = Redis()
        queue = Queue("campaigns", connection=redis_conn)
        queue.enqueue(
            "src.services.campaign_service.execute_campaign_task",
            execution_id,
            job_timeout="10m",
            result_ttl=86400,
        )
        logger.info("Task enfileirada no RQ: execution_id=%d", execution_id)
    except Exception as exc:
        logger.warning(
            "Redis/RQ indisponível (%s). Executando campanha de forma síncrona.",
            exc,
        )
        execute_campaign_task(execution_id)


# ═══════════════════════════════════════════════════════════════════════════
# Worker: Execução de Campanha
# ═══════════════════════════════════════════════════════════════════════════

def execute_campaign_task(execution_id: int) -> dict[str, Any]:
    """
    Task principal do worker: processa todos os recipients de uma execução.

    Chamada pelo RQ worker ou em modo síncrono como fallback.

    Fluxo:
      1. Marca execution como 'sending'
      2. Carrega template e recipients pendentes
      3. Para cada recipient:
         a. Interpola variáveis no template
         b. Despacha pelo canal correto
         c. Atualiza status do recipient (sent/failed)
         d. Aplica rate limit entre envios
      4. Atualiza contadores da execution
      5. Marca execution como 'completed' ou 'failed'

    Returns:
        Dict com resumo da execução (sent, failed, status)
    """
    logger.info("Iniciando execução de campanha: execution_id=%d", execution_id)

    # Marca como 'sending'
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            UPDATE campaign_executions
            SET status = 'sending', started_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING template_id, tenant_id, clinic_id
            """,
            (execution_id,),
        )
        execution = cursor.fetchone()
        conn.commit()

    if not execution:
        logger.error("Execution %d não encontrada.", execution_id)
        return {"error": "execution_not_found"}

    # Carrega template
    template = get_template(execution["template_id"], execution["clinic_id"])
    if not template:
        _mark_execution_failed(execution_id, "Template não encontrado durante execução.")
        return {"error": "template_not_found"}

    # Carrega recipients pendentes
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT cr.id, cr.patient_id, cr.channel_address, p.name AS patient_name
            FROM campaign_recipients cr
            JOIN patients p ON p.id = cr.patient_id
            WHERE cr.execution_id = %s AND cr.status = 'pending'
            ORDER BY cr.id
            """,
            (execution_id,),
        )
        recipients = cursor.fetchall()

    sent_count = 0
    failed_count = 0
    errors: list[str] = []

    for recipient in recipients:
        try:
            # Monta variáveis de contexto para interpolação
            context_vars = {
                "patient_name": recipient["patient_name"] or "",
                "clinic_name": template.get("name", ""),
            }

            # Interpola o template
            message = interpolate_template(template["template_body"], context_vars)

            # Despacha pelo canal
            _send_to_channel(
                channel=template["channel"],
                address=recipient["channel_address"],
                message=message,
                subject=template["name"],
            )

            # Marca como enviado
            _update_recipient_status(recipient["id"], "sent")
            sent_count += 1

        except Exception as exc:
            error_msg = f"patient_id={recipient['patient_id']}: {exc}"
            logger.warning("Falha ao enviar para recipient %d: %s", recipient["id"], exc)
            _update_recipient_status(recipient["id"], "failed", error_detail=str(exc))
            failed_count += 1
            errors.append(error_msg)

        # Rate limit entre envios
        time.sleep(1.0 / DEFAULT_RATE_LIMIT_PER_SECOND)

    # Atualiza contadores e finaliza
    final_status = "completed" if failed_count == 0 else ("failed" if sent_count == 0 else "completed")
    error_summary = "; ".join(errors[:10]) if errors else None  # Limita a 10 erros no resumo

    with db_cursor() as (conn, cursor):
        cursor.execute(
            """
            UPDATE campaign_executions
            SET sent_count = %s,
                failed_count = %s,
                status = %s,
                error_summary = %s,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (sent_count, failed_count, final_status, error_summary, execution_id),
        )
        conn.commit()

    logger.info(
        "Campanha finalizada: execution_id=%d sent=%d failed=%d status=%s",
        execution_id, sent_count, failed_count, final_status,
    )

    return {
        "execution_id": execution_id,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "status": final_status,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Despacho por Canal
# ═══════════════════════════════════════════════════════════════════════════

def _send_to_channel(
    channel: str,
    address: str,
    message: str,
    subject: str = "",
) -> None:
    """
    Despacha uma mensagem individual pelo canal especificado.

    Raises:
        ValueError: canal não suportado
        Exception: falha no envio (propagada para tratamento no caller)
    """
    if channel == "whatsapp":
        from src.integrations.whatsapp import send_whatsapp_text
        send_whatsapp_text(recipient_phone=address, text=message)

    elif channel == "email":
        from src.integrations.email import send_email_notification
        send_email_notification(subject=subject, message=message, to_email=address)

    elif channel == "sms":
        raise NotImplementedError(
            "Canal SMS ainda não integrado. "
            "Aguardando provedor de SMS configurado."
        )
    else:
        raise ValueError(f"Canal de envio não suportado: {channel}")


# ═══════════════════════════════════════════════════════════════════════════
# Helpers internos
# ═══════════════════════════════════════════════════════════════════════════

def _update_recipient_status(
    recipient_id: int,
    status: str,
    *,
    error_detail: Optional[str] = None,
) -> None:
    """Atualiza o status de um recipient individual."""
    with db_cursor() as (conn, cursor):
        if status == "sent":
            cursor.execute(
                """
                UPDATE campaign_recipients
                SET status = %s, sent_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (status, recipient_id),
            )
        else:
            cursor.execute(
                """
                UPDATE campaign_recipients
                SET status = %s, error_detail = %s
                WHERE id = %s
                """,
                (status, error_detail, recipient_id),
            )
        conn.commit()


def _mark_execution_failed(execution_id: int, error_summary: str) -> None:
    """Marca uma execução inteira como falha."""
    with db_cursor() as (conn, cursor):
        cursor.execute(
            """
            UPDATE campaign_executions
            SET status = 'failed', error_summary = %s, completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (error_summary, execution_id),
        )
        conn.commit()

    logger.error("Execução %d marcada como falha: %s", execution_id, error_summary)


# ═══════════════════════════════════════════════════════════════════════════
# Consultas de Status
# ═══════════════════════════════════════════════════════════════════════════

def get_execution_status(execution_id: int, clinic_id: int) -> Optional[dict[str, Any]]:
    """Retorna status detalhado de uma execução de campanha."""
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                ce.id AS execution_id,
                ce.template_id,
                ct.name AS template_name,
                ct.channel,
                ce.target_count,
                ce.sent_count,
                ce.failed_count,
                ce.status,
                ce.error_summary,
                ce.started_at,
                ce.completed_at,
                ce.created_at,
                ce.triggered_by
            FROM campaign_executions ce
            JOIN campaign_templates ct ON ct.id = ce.template_id
            WHERE ce.id = %s AND ce.clinic_id = %s
            """,
            (execution_id, clinic_id),
        )
        return cursor.fetchone()


def list_executions(
    clinic_id: int,
    *,
    template_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Lista execuções de campanha da clínica com filtros opcionais."""
    conditions = ["ce.clinic_id = %s"]
    params: list[Any] = [clinic_id]

    if template_id:
        conditions.append("ce.template_id = %s")
        params.append(template_id)
    if status:
        conditions.append("ce.status = %s")
        params.append(status)

    params.append(limit)

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            f"""
            SELECT
                ce.id AS execution_id,
                ce.template_id,
                ct.name AS template_name,
                ct.channel,
                ce.target_count,
                ce.sent_count,
                ce.failed_count,
                ce.status,
                ce.started_at,
                ce.completed_at,
                ce.created_at
            FROM campaign_executions ce
            JOIN campaign_templates ct ON ct.id = ce.template_id
            WHERE {' AND '.join(conditions)}
            ORDER BY ce.created_at DESC
            LIMIT %s
            """,
            params,
        )
        return cursor.fetchall()
