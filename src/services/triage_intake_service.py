from __future__ import annotations

from typing import Any

from src.ai.clinical_flow import build_clinical_flow
from src.ai.schemas import AnamnesisInput
from src.repositories.anamnesis_repository import save_report
from src.repositories.patient_repository import get_or_create_patient_by_name
from src.repositories.patient_timeline_repository import create_event
from src.services.prescription_contract import build_prescription_contract


EMOTIONAL_LABELS = {
    "perde_foco": "perde foco facilmente",
    "problemas_memoria": "problemas de memoria",
    "facilmente_irritado": "irritabilidade ou tristeza facil",
    "problemas_estresse": "estresse relevante",
    "episodios_panico": "episodios de panico",
    "diagnostico_esquizofrenia_psicose": "diagnostico de esquizofrenia/psicose",
    "parente_esquizofrenia_psicose": "historico familiar de psicose",
    "diagnostico_ansiedade_depressao": "ansiedade/depressao diagnosticada",
}

HISTORY_LABELS = {
    "casado": "casado(a)",
    "tem_filhos": "tem filhos",
    "passou_por_aborto": "passou por aborto",
    "trabalha": "trabalha",
    "estuda": "estuda",
    "pratica_atividade_fisica": "pratica atividade fisica",
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _humanize_token(value: Any) -> str:
    return _text(value).replace("_", " ")


def _require_text(value: Any, label: str) -> str:
    normalized = _text(value)
    if not normalized:
        raise ValueError(f"{label} e obrigatorio.")
    return normalized


def _require_int(value: Any, label: str) -> int:
    if value in (None, ""):
        raise ValueError(f"{label} e obrigatoria.")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} deve ser um numero inteiro.") from exc
    if normalized <= 0:
        raise ValueError(f"{label} deve ser maior que zero.")
    return normalized


def _require_float(value: Any, label: str) -> float:
    if value in (None, ""):
        raise ValueError(f"{label} e obrigatorio.")
    if isinstance(value, str):
        value = value.replace(",", ".")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} deve ser numerico.") from exc
    if normalized <= 0:
        raise ValueError(f"{label} deve ser maior que zero.")
    return normalized


def _truthy_labels(payload: dict[str, Any], labels: dict[str, str]) -> list[str]:
    return [label for key, label in labels.items() if payload.get(key) is True]


def _build_main_complaint(motivo: dict[str, Any]) -> str:
    principal = _humanize_token(motivo.get("objetivo_principal"))
    if not principal:
        raise ValueError("Objetivo principal e obrigatorio.")

    outros = [_humanize_token(item) for item in _as_list(motivo.get("outros_motivos")) if _text(item)]
    if not outros:
        return principal
    return f"{principal} ({', '.join(outros)})"


def _build_symptoms(motivo: dict[str, Any], sintomas: list[Any]) -> list[str]:
    principal = _humanize_token(motivo.get("objetivo_principal"))
    first_symptom = _as_dict(sintomas[0]) if sintomas else {}

    summary = _humanize_token(first_symptom.get("nome")) or principal
    details: list[str] = []

    intensidade = first_symptom.get("intensidade")
    if intensidade not in (None, ""):
        details.append(f"intensidade {intensidade}/10")

    duracao = _humanize_token(first_symptom.get("duracao"))
    if duracao:
        details.append(f"duracao {duracao}")

    if details:
        summary = f"{summary} ({'; '.join(details)})" if summary else "; ".join(details)

    descricao = _text(first_symptom.get("descricao_adicional"))

    normalized: list[str] = []
    for item in (summary, descricao):
        if item and item not in normalized:
            normalized.append(item)

    if not normalized:
        raise ValueError("Sintomas e obrigatorio.")
    return normalized


def _build_medical_history(
    emotional: dict[str, Any],
    habits: dict[str, Any],
    history: dict[str, Any],
) -> str:
    sections: list[str] = []

    emotional_findings = _truthy_labels(emotional, EMOTIONAL_LABELS)
    if emotional_findings:
        sections.append(f"Estado emocional: {', '.join(emotional_findings)}.")

    habit_details: list[str] = []
    if habits.get("acorda_cansado") is True:
        habit_details.append("acorda cansado(a)")
    if habits.get("fuma") is True:
        detail = "fuma"
        frequencia = _text(habits.get("frequencia_fumo"))
        if frequencia:
            detail = f"{detail} ({frequencia})"
        habit_details.append(detail)
    if habits.get("uso_alcool") is True:
        habit_details.append("uso de alcool")
    if habits.get("ja_usou_cannabis") is True:
        detail = "uso previo de cannabis"
        frequencia = _text(habits.get("frequencia_cannabis"))
        if frequencia:
            detail = f"{detail} ({frequencia})"
        habit_details.append(detail)
    if habits.get("arritmia_cardiaca") is True:
        habit_details.append("arritmia cardiaca")
    if habits.get("historico_psicose") is True:
        habit_details.append("historico de psicose")
    if habit_details:
        sections.append(f"Habitos e riscos: {', '.join(habit_details)}.")

    social_history = _truthy_labels(history, HISTORY_LABELS)
    if social_history:
        sections.append(f"Historico social: {', '.join(social_history)}.")

    return " ".join(sections).strip() or "Sem historico adicional informado."


def build_triage_payload(payload: dict[str, Any]) -> tuple[AnamnesisInput, dict[str, Any]]:
    identificacao = _as_dict(payload.get("identificacao"))
    motivo = _as_dict(payload.get("motivo"))
    dados_fisicos = _as_dict(payload.get("dados_fisicos"))
    estado_emocional = _as_dict(payload.get("estado_emocional"))
    habitos = _as_dict(payload.get("habitos"))
    historico = _as_dict(payload.get("historico"))
    sintomas = _as_list(payload.get("sintomas"))

    patient_name = _require_text(identificacao.get("patient_name"), "Nome do paciente")
    age = _require_int(identificacao.get("age"), "Idade")
    main_complaint = _build_main_complaint(motivo)
    symptoms = _build_symptoms(motivo, sintomas)
    weight_kg = _require_float(dados_fisicos.get("peso_kg"), "Peso")
    height_cm = _require_float(dados_fisicos.get("altura_cm"), "Altura")
    prior_cannabis_use = habitos.get("ja_usou_cannabis") is True
    medical_history = _build_medical_history(estado_emocional, habitos, historico)

    anamnesis_input = AnamnesisInput(
        patient_name=patient_name,
        age=age,
        main_complaint=main_complaint,
        symptoms=symptoms,
        current_medications=[],
        allergies=[],
        medical_history=medical_history,
        weight_kg=weight_kg,
        height_cm=height_cm,
        prior_cannabis_use=prior_cannabis_use,
    )

    anamnesis_data = {
        "patient_name": patient_name,
        "age": age,
        "main_complaint": main_complaint,
        "chief_complaint": main_complaint,
        "symptoms": symptoms,
        "current_medications": [],
        "allergies": [],
        "medical_history": medical_history,
        "vital_signs": {
            "weight_kg": weight_kg,
            "height_cm": height_cm,
        },
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "sexo_biologico": dados_fisicos.get("sexo_biologico"),
        "prior_cannabis_use": prior_cannabis_use,
        "cannabis_history": {
            "prior_use": prior_cannabis_use,
            "frequency": _text(habitos.get("frequencia_cannabis")) or None,
        },
        "lifestyle": {
            "acorda_cansado": habitos.get("acorda_cansado") is True,
            "fuma": habitos.get("fuma") is True,
            "frequencia_fumo": _text(habitos.get("frequencia_fumo")) or None,
            "uso_alcool": habitos.get("uso_alcool") is True,
            "arritmia_cardiaca": habitos.get("arritmia_cardiaca") is True,
            "historico_psicose": habitos.get("historico_psicose") is True,
        },
        "triage": {
            "identificacao": identificacao,
            "motivo": motivo,
            "sintomas": sintomas,
            "dados_fisicos": dados_fisicos,
            "estado_emocional": estado_emocional,
            "habitos": habitos,
            "historico": historico,
        },
    }

    return anamnesis_input, anamnesis_data


def submit_triage_intake(
    payload: dict[str, Any],
    clinic_id: int,
    *,
    token_context: dict[str, Any] | None = None,
    raw_token: str | None = None,
    remote_ip: str | None = None,
) -> dict[str, Any]:
    """Submete a triagem. Se token_context vier com appointment_id, vincula automaticamente."""
    token_context = token_context or {}
    appointment_id: int | None = token_context.get("appointment_id")
    link_id: int | None = token_context.get("link_id")

    anamnesis_input, anamnesis_data = build_triage_payload(payload)

    patient_id = get_or_create_patient_by_name(clinic_id, anamnesis_input.patient_name)
    flow = build_clinical_flow()
    report = flow.run(anamnesis_input)

    report_id = save_report(
        clinic_id,
        patient_id,
        anamnesis_input.patient_name,
        "",
        anamnesis_data,
        report,
    )

    # Vincular report ao agendamento e ao link de triagem
    if appointment_id or link_id:
        from src.repositories.anamnesis_repository import link_report_to_appointment

        link_report_to_appointment(
            report_id,
            appointment_id=appointment_id,
            triage_link_id=link_id,
        )

    # Consumir o link (uso unico)
    if raw_token:
        from src.services.triage_link_service import consume_triage_link

        consume_triage_link(raw_token, report_id=report_id, remote_ip=remote_ip)

    create_event(
        clinic_id=clinic_id,
        patient_id=patient_id,
        event_type="triage_completed",
        journey_stage="triagem_concluida",
        title="Triagem digital concluida",
        description="Formulario de intake estruturado finalizado no frontend.",
        source_type="anamnesis_report",
        source_id=report_id,
        metadata={
            "main_complaint": anamnesis_input.main_complaint,
            "report_model": report.get("report_model"),
            "risk_level": report.get("clinical_analysis", {}).get("risk_level"),
            "appointment_id": appointment_id,
        },
    )

    contract = build_prescription_contract(
        report={
            "id": report_id,
            "patient_id": patient_id,
            "patient_name": anamnesis_input.patient_name,
            "anamnesis_data": anamnesis_data,
            "clinical_analysis": report.get("clinical_analysis", {}),
        }
    )

    result: dict[str, Any] = {
        "report_id": report_id,
        "patient_id": patient_id,
        "clinic_id": clinic_id,
        "patient_name": anamnesis_input.patient_name,
        "status": "pending",
        "prescription_contract": contract,
    }
    if appointment_id:
        result["appointment_id"] = appointment_id

    return result
