# src/services/telemetry_crm_service.py
"""
TelemetryCRMService — Motor de Follow-up Pós-Consulta.

Responsabilidades:
  1. Ler consultas/anamneses geradas hoje no banco.
  2. Agendar disparos automáticos de WhatsApp em D+3, D+7 e D+15.
  3. Processar fila de follow-ups pendentes (executado pelo worker RQ).
  4. Registrar respostas dos pacientes para análise longitudinal.

Integração:
  - Usa Redis/RQ (src.infra.tasks) para agendamento assíncrono.
  - Usa WhatsApp API (src.integrations.whatsapp) para envio.
  - Persiste em scheduled_followups (src.repositories.telemetry_repository).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cannabia.telemetry_crm")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE FOLLOW-UP
# ═══════════════════════════════════════════════════════════════════════════════

FOLLOWUP_SCHEDULE: List[Dict[str, Any]] = [
    {
        "type": "d3",
        "delta_days": 3,
        "message": (
            "Olá {patient_name}, aqui é a equipe CannabIA. 🌿\n\n"
            "Já se passaram 3 dias desde sua consulta. "
            "Como você está se sentindo após o início do uso do CBD?\n\n"
            "Responda com:\n"
            "1️⃣ Muito melhor\n"
            "2️⃣ Um pouco melhor\n"
            "3️⃣ Sem mudanças\n"
            "4️⃣ Pior\n\n"
            "Sua resposta nos ajuda a ajustar seu tratamento."
        ),
    },
    {
        "type": "d7",
        "delta_days": 7,
        "message": (
            "Olá {patient_name}! 🌿\n\n"
            "Completou 1 semana de tratamento. "
            "Como está a qualidade do seu sono e o nível de dor?\n\n"
            "Responda livremente como se sente — "
            "nosso time médico acompanha cada resposta."
        ),
    },
    {
        "type": "d15",
        "delta_days": 15,
        "message": (
            "Olá {patient_name}! 🌿\n\n"
            "Já são 15 dias do seu plano terapêutico com CBD. "
            "Gostaríamos de saber:\n\n"
            "• Como está seu bem-estar geral?\n"
            "• Notou efeitos colaterais?\n"
            "• Está conseguindo seguir a dosagem recomendada?\n\n"
            "Sua resposta é fundamental para o acompanhamento médico. "
            "Se precisar de ajuste na dosagem, responda aqui."
        ),
    },
]

# Hora do dia para envio dos follow-ups (evita horários inconvenientes)
FOLLOWUP_SEND_HOUR = 10  # 10h da manhã


class TelemetryCRMService:
    """
    Serviço principal de CRM pós-consulta.

    Uso típico:
      service = TelemetryCRMService()
      created = service.schedule_followups_for_today()
      processed = service.process_pending_followups()
    """

    # ── Agendar follow-ups para anamneses do dia ────────────────────────────

    def get_todays_reports(self) -> List[Dict[str, Any]]:
        """
        Lê anamnesis_reports gerados hoje (status = 'pending' ou 'reviewed').
        Retorna lista com clinic_id, patient_id, patient_name, phone, report_id.
        """
        from src.infra.database import db_cursor

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        today_end = today_start + timedelta(days=1)

        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                """
                SELECT ar.id AS report_id,
                       ar.clinic_id,
                       ar.patient_id,
                       ar.patient_name,
                       ar.phone
                FROM anamnesis_reports ar
                WHERE ar.created_at >= %s
                  AND ar.created_at < %s
                  AND ar.phone IS NOT NULL
                """,
                (today_start, today_end),
            )
            return cur.fetchall()

    def schedule_followups_for_today(self) -> Dict[str, int]:
        """
        Lê todas as consultas de hoje e cria follow-ups D+3, D+7, D+15.
        Pula follow-ups já existentes (idempotente).

        Retorna: {"scheduled": N, "skipped": N}
        """
        from src.repositories.telemetry_repository import (
            create_followups_batch,
            list_followups_for_patient,
        )

        reports = self.get_todays_reports()
        scheduled = 0
        skipped = 0

        for report in reports:
            existing = list_followups_for_patient(
                clinic_id=report["clinic_id"],
                patient_id=report["patient_id"],
            )
            existing_types = {
                (f["followup_type"],)
                for f in existing
                if f.get("scheduled_at") and f["scheduled_at"].date() > datetime.now(timezone.utc).date()
            }

            batch: List[Dict[str, Any]] = []
            for sched in FOLLOWUP_SCHEDULE:
                if (sched["type"],) in existing_types:
                    skipped += 1
                    continue

                send_at = datetime.now(timezone.utc).replace(
                    hour=FOLLOWUP_SEND_HOUR, minute=0, second=0, microsecond=0,
                ) + timedelta(days=sched["delta_days"])

                message = sched["message"].format(
                    patient_name=report.get("patient_name", "Paciente"),
                )

                batch.append({
                    "clinic_id": report["clinic_id"],
                    "patient_id": report["patient_id"],
                    "phone": report["phone"],
                    "report_id": report["report_id"],
                    "followup_type": sched["type"],
                    "scheduled_at": send_at,
                    "message_text": message,
                })

            if batch:
                create_followups_batch(batch)
                scheduled += len(batch)

        logger.info(
            "Follow-ups agendados: %d criados, %d ignorados (já existiam)",
            scheduled, skipped,
        )
        return {"scheduled": scheduled, "skipped": skipped}

    # ── Processar follow-ups pendentes (chamado pelo worker) ────────────────

    def process_pending_followups(self, limit: int = 50) -> Dict[str, int]:
        """
        Busca follow-ups pendentes cuja hora já chegou e dispara via WhatsApp.

        Retorna: {"sent": N, "failed": N}
        """
        from src.repositories.telemetry_repository import (
            list_pending_followups,
            mark_followup_sent,
            mark_followup_failed,
        )
        from src.integrations.whatsapp import send_whatsapp_text

        now = datetime.now(timezone.utc)
        pending = list_pending_followups(before=now, limit=limit)

        sent = 0
        failed = 0

        for followup in pending:
            try:
                result = send_whatsapp_text(
                    recipient_phone=followup["phone"],
                    text=followup["message_text"],
                )

                # Meta API retorna "messages" se sucesso
                if "messages" in result:
                    mark_followup_sent(followup["id"])
                    sent += 1
                    logger.info(
                        "Follow-up %s enviado: patient_id=%s, type=%s",
                        followup["id"], followup["patient_id"],
                        followup["followup_type"],
                    )
                else:
                    error_msg = str(result.get("error", result))
                    mark_followup_failed(followup["id"], error_msg)
                    failed += 1
                    logger.warning(
                        "Follow-up %s falhou (API): %s", followup["id"], error_msg,
                    )

            except Exception as exc:
                mark_followup_failed(followup["id"], str(exc))
                failed += 1
                logger.error(
                    "Follow-up %s erro: %s", followup["id"], exc, exc_info=True,
                )

        logger.info("Processamento follow-ups: %d enviados, %d falharam", sent, failed)
        return {"sent": sent, "failed": failed}

    # ── Registrar resposta do paciente ──────────────────────────────────────

    def handle_patient_response(
        self,
        clinic_id: int,
        phone: str,
        response_text: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Registra a resposta do paciente no follow-up 'sent' mais recente.
        Chamado pelo webhook do WhatsApp quando a mensagem é recebida (CLI-1).
        Retorna {id, patient_id, followup_type} ou None se não havia follow-up
        aguardando resposta.
        """
        from src.repositories.telemetry_repository import record_patient_response

        followup = record_patient_response(
            clinic_id=clinic_id,
            phone=phone,
            response_text=response_text,
        )

        if followup:
            logger.info(
                "Resposta de follow-up registrada: followup_id=%s, type=%s, clinic=%s, phone=%s",
                followup["id"], followup.get("followup_type"), clinic_id, phone,
            )
        return followup
