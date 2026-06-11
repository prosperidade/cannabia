# src/services/anamnesis_flow.py
from __future__ import annotations

import logging
from typing import Optional

from src.repositories.session_repository import delete_session, get_session, upsert_session
from src.repositories.patient_repository import (
    get_or_create_patient_by_name,
    update_patient_contact_if_missing,
)
from src.repositories.anamnesis_repository import save_report
from src.repositories.patient_timeline_repository import create_event
from src.integrations.whatsapp import send_whatsapp_text
from src.integrations.email import send_email_notification
from src.ai.clinical_flow import build_clinical_flow
from src.ai.schemas import AnamnesisInput

logger = logging.getLogger("cannabia.anamnesis")

# ── Definição das etapas e perguntas ─────────────────────────────────────────

STEPS = [
    ("awaiting_name",        "👋 Olá! Sou o assistente CannabIA.\n\nPrimeiro, qual é o seu *nome completo*?"),
    ("awaiting_age",         "Perfeito! Qual é a sua *idade*?"),
    ("awaiting_complaint",   "Qual é a sua *queixa principal*? Descreva o que está sentindo."),
    ("awaiting_symptoms",    "Quais *sintomas* você apresenta?\n(ex: dor, insônia, ansiedade)\nSepare por vírgulas."),
    ("awaiting_medications", "Está usando alguma *medicação atual*?\nSe não estiver, responda *Nenhuma*."),
    ("awaiting_allergies",   "Possui alguma *alergia* conhecida?\nSe não, responda *Nenhuma*."),
    ("awaiting_history",     "Por fim, descreva brevemente seu *histórico médico* relevante.\n(cirurgias, doenças crônicas, etc)\nSe não houver, responda *Sem histórico*."),
]

STEP_NAMES = [s[0] for s in STEPS]
STEP_QUESTIONS = dict(STEPS)

# Campos do AnamnesisInput na mesma ordem de STEPS
STEP_FIELDS = [
    "patient_name",
    "age",
    "main_complaint",
    "symptoms",
    "current_medications",
    "allergies",
    "medical_history",
]

TRIGGER_WORDS = (
    "oi", "olá", "oii", "ola", "bom dia", "boa tarde", "boa noite",
    "iniciar", "começar", "comecar", "anamnese", "consulta", "hello", "hi",
)


def _next_step(current_step: str) -> Optional[str]:
    """Retorna o próximo passo ou None se for o último."""
    if current_step not in STEP_NAMES:
        return STEP_NAMES[0]
    idx = STEP_NAMES.index(current_step)
    return STEP_NAMES[idx + 1] if idx + 1 < len(STEP_NAMES) else None


def _notify_doctor(patient_name: str, phone: str, report: dict) -> None:
    """Envia e-mail ao médico com o relatório clínico completo."""
    clinical   = report.get("clinical_analysis", {})
    treatment  = report.get("treatment_plan", {})
    scientific = report.get("scientific_report", {})
    rag_used   = report.get("rag_chunks_used", 0)
    model      = report.get("report_model", "N/A")

    conditions = ", ".join(clinical.get("probable_conditions", [])) or "N/A"
    red_flags  = ", ".join(clinical.get("red_flags", [])) or "Nenhum"
    precautions = "\n  ".join(treatment.get("precautions", [])) or "N/A"
    evidence    = "\n  ".join(scientific.get("supporting_evidence", [])) or "N/A"
    references  = "\n  ".join(scientific.get("references", [])) or "N/A"

    body = f"""
🌿 CANNAB'IA — Nova Anamnese Concluída
{'=' * 50}

Paciente:  {patient_name}
WhatsApp:  {phone}

── ANÁLISE CLÍNICA ────────────────────────────────
Condições prováveis:  {conditions}
Nível de risco:       {clinical.get('risk_level', 'N/A')}
Exames recomendados:  {", ".join(clinical.get('recommended_exams', [])) or 'N/A'}
Red flags:            {red_flags}

── PLANO TERAPÊUTICO ──────────────────────────────
Proporção canabinóide: {treatment.get('cannabinoid_ratio', 'N/A')}
Dosagem sugerida:      {treatment.get('suggested_dosage', 'N/A')}
Via de administração:  {treatment.get('administration_route', 'N/A')}
Monitoramento:         {treatment.get('monitoring_plan', 'N/A')}
Precauções:
  {precautions}

── RELATÓRIO CIENTÍFICO ───────────────────────────
{scientific.get('summary', 'N/A')}

Evidências:
  {evidence}

Referências:
  {references}

── METADADOS ──────────────────────────────────────
Artigos RAG utilizados: {rag_used}
Modelo do relatório:    {model}
{'=' * 50}
Este relatório foi gerado automaticamente pelo CannabIA.
Revise e valide todas as informações antes de prescrever.
""".strip()

    send_email_notification(
        subject=f"[CannabIA] Anamnese completa — {patient_name}",
        message=body,
    )
    logger.info("Notificação enviada ao médico para paciente '%s' (%s).", patient_name, phone)


def process_message(
    clinic_id: int,
    phone: str,
    contact_name: str,
    text: str,
    tenant_id: Optional[int] = None,
) -> None:
    """
    Ponto de entrada principal do fluxo de anamnese.
    Recebe cada mensagem do paciente, avança a máquina de estados
    e dispara o pipeline ao completar todas as perguntas.

    `tenant_id` (COM-3 / 29.3 RM5) é repassado ao outbound para usar a credencial
    WhatsApp do tenant resolvido; quando None, cai no fallback global.
    """
    def _reply(message: str) -> dict:
        return send_whatsapp_text(phone, message, tenant_id=tenant_id)

    text_clean = (text or "").strip()
    text_lower = text_clean.lower()

    session      = get_session(clinic_id, phone)
    current_step = session["step"] if session else "idle"
    data         = dict(session["data"]) if session else {}

    # ── Gatilho: inicia nova anamnese ────────────────────────────────────────
    if current_step in ("idle", "completed") and any(t in text_lower for t in TRIGGER_WORDS):
        first_step, first_question = STEPS[0]
        upsert_session(clinic_id, phone, first_step, {})
        _reply(
f"📋 Vamos iniciar sua anamnese! Isso levará apenas alguns minutos.\n\n{first_question}",
        )
        return

    # ── Paciente inativo fora do fluxo ────────────────────────────────────────
    if current_step == "idle":
        _reply(
"Olá! 👋 Para iniciar sua avaliação médica, envie *Oi* ou *Iniciar*.",
        )
        return

    # ── Pipeline em andamento (aguarda processamento) ─────────────────────────
    if current_step == "processing":
        _reply(
"⏳ Sua anamnese está sendo processada. Por favor, aguarde alguns instantes.",
        )
        return

    # ── Sessão concluída: NÃO deletar (CLI-1 / 29.2 R1) ──────────────────────
    # Respostas de follow-up já foram interceptadas em message_service; aqui só
    # restam mensagens avulsas de quem já concluiu — oferece reinício sem perder
    # a sessão (antes caíam em "estado desconhecido" e eram deletadas).
    if current_step == "completed":
        _reply(
            "Sua anamnese já foi concluída ✅.\n"
            "Para iniciar uma nova avaliação, envie *Oi* ou *Iniciar*."
        )
        return

    # ── Coleta da resposta e avanço de etapa ─────────────────────────────────
    if current_step not in STEP_NAMES:
        logger.warning("Estado desconhecido '%s' para %s — resetando.", current_step, phone)
        delete_session(clinic_id, phone)
        return

    field_idx  = STEP_NAMES.index(current_step)
    field_name = STEP_FIELDS[field_idx]

    # Pós-processamento por tipo de campo
    if field_name == "patient_name":
        if not text_clean:
            _reply("Por favor, informe seu nome completo para continuar.")
            return
        data[field_name] = text_clean
    elif field_name == "age":
        digits = "".join(filter(str.isdigit, text_clean))
        if not digits:
            _reply("Por favor, informe sua idade em números. Ex: *35*")
            return
        data[field_name] = int(digits)
    elif field_name in ("symptoms", "current_medications", "allergies"):
        # Aceita lista separada por vírgulas ou resposta única
        items = [s.strip() for s in text_clean.split(",") if s.strip()]
        data[field_name] = items if items else [text_clean]
    else:
        data[field_name] = text_clean

    if field_name == "patient_name":
        patient_id = get_or_create_patient_by_name(clinic_id, data["patient_name"])
        update_patient_contact_if_missing(clinic_id, patient_id, phone=phone)
        create_event(
            clinic_id=clinic_id,
            patient_id=patient_id,
            event_type="journey_started",
            journey_stage="anamnese_em_andamento",
            title="Paciente iniciou anamnese via WhatsApp",
            description="Identificação inicial registrada no fluxo conversacional.",
            source_type="whatsapp_session",
            metadata={"phone": phone},
        )

    next_step = _next_step(current_step)

    # ── Última pergunta respondida → dispara o pipeline ───────────────────────
    if next_step is None:
        upsert_session(clinic_id, phone, "processing", data)

        _reply(
"✅ Anamnese concluída! Nossa IA médica está analisando suas informações.\n\n"
            "Seu médico receberá o relatório completo em instantes. 🌿\n\n"
            "_Não compartilhamos seus dados clínicos via WhatsApp por segurança._",
        )

        patient_id = None
        try:
            patient_name = data.get("patient_name", contact_name)
            patient_id = get_or_create_patient_by_name(clinic_id, patient_name)
            update_patient_contact_if_missing(clinic_id, patient_id, phone=phone)

            anamnesis = AnamnesisInput(
                patient_name=patient_name,
                age=int(data.get("age", 0)),
                main_complaint=data.get("main_complaint", ""),
                symptoms=data.get("symptoms", []),
                current_medications=data.get("current_medications", []),
                allergies=data.get("allergies", []),
                medical_history=data.get("medical_history", ""),
                # WhatsApp ainda nao coleta peso/altura/uso previo —
                # back-compat com defaults conservadores em clinical_flow.
                weight_kg=None,
                height_cm=None,
                prior_cannabis_use=None,
            )

            flow = build_clinical_flow()
            report = flow.run(anamnesis)

            # Persiste no banco para o dashboard do médico
            report_id = save_report(
                clinic_id,
                patient_id,
                anamnesis.patient_name,
                phone,
                data,
                report,
            )

            create_event(
                clinic_id=clinic_id,
                patient_id=patient_id,
                event_type="anamnesis_completed",
                journey_stage="anamnese_concluida",
                title="Anamnese assistida concluída",
                description="Fluxo do WhatsApp finalizado com relatório clínico gerado pela IA.",
                source_type="anamnesis_report",
                source_id=report_id,
                metadata={
                    "phone": phone,
                    "risk_level": report.get("clinical_analysis", {}).get("risk_level"),
                    "report_model": report.get("report_model"),
                    "rag_chunks_used": report.get("rag_chunks_used", 0),
                },
            )

            _notify_doctor(anamnesis.patient_name, phone, report)
            upsert_session(clinic_id, phone, "completed", data)
            logger.info("Pipeline concluído com sucesso para '%s'.", patient_name)

        except Exception:
            logger.exception("Erro no pipeline de anamnese para %s", phone)
            if patient_id is not None:
                create_event(
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    event_type="anamnesis_processing_failed",
                    journey_stage="anamnese_com_falha",
                    title="Falha no processamento da anamnese",
                    description="O pipeline clínico não concluiu o relatório automatizado.",
                    source_type="whatsapp_session",
                    metadata={"phone": phone},
                )
            _reply(
                "⚠️ Ocorreu um erro inesperado ao processar sua anamnese.\n"
                "Nossa equipe foi notificada. Por favor, tente novamente mais tarde.",
            )
            # Reseta sessão para permitir nova tentativa
            delete_session(clinic_id, phone)

        return

    # ── Avança para o próximo passo ───────────────────────────────────────────
    upsert_session(clinic_id, phone, next_step, data)
    _reply(STEP_QUESTIONS[next_step])
