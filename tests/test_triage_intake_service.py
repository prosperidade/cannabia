from __future__ import annotations

from src.services import triage_intake_service


def _sample_triage_payload() -> dict:
    return {
        "identificacao": {
            "patient_name": "Ana Souza",
            "age": 42,
        },
        "motivo": {
            "objetivo_principal": "controle_ansiedade",
            "outros_motivos": ["insonia"],
        },
        "sintomas": [
            {
                "nome": "ansiedade",
                "intensidade": 8,
                "duracao": "1_6_meses",
                "descricao_adicional": "Crises no fim da tarde e dificuldade para dormir.",
            }
        ],
        "dados_fisicos": {
            "peso_kg": 62,
            "altura_cm": 168,
            "sexo_biologico": "feminino",
        },
        "estado_emocional": {
            "perde_foco": True,
            "problemas_memoria": False,
            "facilmente_irritado": True,
            "problemas_estresse": True,
            "episodios_panico": False,
            "diagnostico_esquizofrenia_psicose": False,
            "parente_esquizofrenia_psicose": False,
            "diagnostico_ansiedade_depressao": True,
        },
        "habitos": {
            "acorda_cansado": True,
            "fuma": False,
            "frequencia_fumo": "",
            "uso_alcool": False,
            "ja_usou_cannabis": True,
            "frequencia_cannabis": "uso esporadico anterior",
            "arritmia_cardiaca": False,
            "historico_psicose": False,
        },
        "historico": {
            "casado": True,
            "tem_filhos": False,
            "passou_por_aborto": False,
            "trabalha": True,
            "estuda": False,
            "pratica_atividade_fisica": True,
        },
    }


def test_build_triage_payload_maps_prescription_contract_fields():
    anamnesis_input, anamnesis_data = triage_intake_service.build_triage_payload(_sample_triage_payload())

    assert anamnesis_input.patient_name == "Ana Souza"
    assert anamnesis_input.age == 42
    assert "controle ansiedade" in anamnesis_input.main_complaint
    assert anamnesis_data["vital_signs"]["weight_kg"] == 62
    assert anamnesis_data["vital_signs"]["height_cm"] == 168
    assert anamnesis_data["prior_cannabis_use"] is True
    assert anamnesis_data["cannabis_history"]["prior_use"] is True
    assert anamnesis_data["chief_complaint"] == anamnesis_input.main_complaint


def test_submit_triage_intake_persists_report_and_returns_ready_contract(monkeypatch):
    saved: dict = {}
    events: list[dict] = []

    class FakeFlow:
        def run(self, anamnesis_input):
            saved["anamnesis_input"] = anamnesis_input
            return {
                "clinical_analysis": {
                    "risk_level": "moderado",
                    "probable_conditions": ["ansiedade"],
                },
                "treatment_plan": {},
                "scientific_report": {},
                "report_model": "fake-triage-model",
            }

    monkeypatch.setattr(triage_intake_service, "build_clinical_flow", lambda: FakeFlow())
    monkeypatch.setattr(triage_intake_service, "get_or_create_patient_by_name", lambda clinic_id, patient_name: 77)

    def fake_save_report(clinic_id, patient_id, patient_name, phone, anamnesis_data, report):
        saved["save_report"] = {
            "clinic_id": clinic_id,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "phone": phone,
            "anamnesis_data": anamnesis_data,
            "report": report,
        }
        return 123

    monkeypatch.setattr(triage_intake_service, "save_report", fake_save_report)
    monkeypatch.setattr(triage_intake_service, "create_event", lambda **kwargs: events.append(kwargs))

    result = triage_intake_service.submit_triage_intake(_sample_triage_payload(), clinic_id=5)

    assert result["report_id"] == 123
    assert result["patient_id"] == 77
    assert result["clinic_id"] == 5
    assert result["prescription_contract"]["ready"] is True
    assert saved["save_report"]["anamnesis_data"]["vital_signs"]["weight_kg"] == 62
    assert saved["save_report"]["anamnesis_data"]["prior_cannabis_use"] is True
    assert events[0]["event_type"] == "triage_completed"
