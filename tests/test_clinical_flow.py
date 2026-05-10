from src.ai.agents.base import AgentResult
from src.ai.clinical_flow import SpecialistClinicalFlow, build_clinical_flow
from src.ai.schemas import AnamnesisInput


def test_specialist_clinical_flow_composes_specialists(monkeypatch):
    class FakeAnamnese:
        agent_name = "anamnese"
        calls = []

        def run(self, **kwargs):
            self.__class__.calls.append(kwargs)
            return AgentResult(
                success=True,
                data={
                    "clinical_analysis": {
                        "probable_conditions": ["dor cronica"],
                        "risk_level": "medio",
                        "recommended_exams": ["hemograma"],
                        "red_flags": [],
                    }
                },
                tokens={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            )

    class FakeTratamento:
        agent_name = "tratamento"
        calls = []

        def run(self, **kwargs):
            self.__class__.calls.append(kwargs)
            return AgentResult(
                success=True,
                data={
                    "treatment_plan": {
                        "cannabinoid_ratio": "10:1",
                        "suggested_dosage": "2 gotas 2x/dia",
                        "administration_route": "sublingual",
                        "monitoring_plan": "Reavaliar em 14 dias",
                        "precautions": ["Monitorar sonolencia"],
                    }
                },
                tokens={"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            )

    class FakeCientifico:
        agent_name = "cientifico"
        calls = []

        def run(self, **kwargs):
            self.__class__.calls.append(kwargs)
            return AgentResult(
                success=True,
                data={
                    "scientific_report": {
                        "summary": "Relatorio com suporte cientifico.",
                        "supporting_evidence": ["Estudo A"],
                        "references": ["PMID:123"],
                    },
                    "chunks_used": 3,
                    "model": "gemini-1.5-flash",
                },
                tokens={"input_tokens": 30, "output_tokens": 12, "total_tokens": 42},
            )

    monkeypatch.setattr("src.ai.clinical_flow.AgenteAnamnese", FakeAnamnese)
    monkeypatch.setattr("src.ai.clinical_flow.AgenteTratamento", FakeTratamento)
    monkeypatch.setattr("src.ai.clinical_flow.AgenteCientifico", FakeCientifico)

    flow = SpecialistClinicalFlow()
    result = flow.run(
        AnamnesisInput(
            patient_name="Paciente Teste",
            age=45,
            main_complaint="Dor lombar cronica",
            symptoms=["dor", "insonia"],
            current_medications=["paracetamol"],
            allergies=["nenhuma"],
            medical_history="sem historico relevante",
        )
    )

    assert result["execution_mode"] == "specialists"
    assert result["specialists_used"] == ["anamnese", "tratamento", "cientifico"]
    assert result["rag_chunks_used"] == 3
    assert result["report_model"] == "gemini-1.5-flash"
    assert result["token_usage"] == {"input": 60, "output": 27, "total": 87}
    assert result["clinical_analysis"]["probable_conditions"] == ["dor cronica"]
    assert result["treatment_plan"]["cannabinoid_ratio"] == "10:1"
    assert result["scientific_report"]["references"] == ["PMID:123"]
    assert FakeAnamnese.calls[0]["patient_data"]["patient_name"] == "Paciente Teste"
    assert FakeTratamento.calls[0]["clinical_analysis"]["risk_level"] == "medio"
    assert FakeCientifico.calls[0]["treatment_plan"]["administration_route"] == "sublingual"

    # Sprint 1 Track B.3 — timings_ms populado por etapa (clinical/treatment/report)
    assert "timings_ms" in result
    assert set(result["timings_ms"].keys()) == {"clinical", "treatment", "report"}
    for stage, elapsed in result["timings_ms"].items():
        assert isinstance(elapsed, int), f"timings_ms[{stage}] deve ser int (ms)"
        assert elapsed >= 0, f"timings_ms[{stage}] deve ser >= 0"


def test_build_clinical_flow_prefers_specialists(monkeypatch):
    class FakeAnamnese:
        agent_name = "anamnese"

        def run(self, **kwargs):
            return AgentResult(success=True)

    class FakeTratamento:
        agent_name = "tratamento"

        def run(self, **kwargs):
            return AgentResult(success=True)

    class FakeCientifico:
        agent_name = "cientifico"

        def run(self, **kwargs):
            return AgentResult(success=True)

    monkeypatch.setenv("AI_EXECUTION_MODE", "specialists")
    monkeypatch.setattr("src.ai.clinical_flow.AgenteAnamnese", FakeAnamnese)
    monkeypatch.setattr("src.ai.clinical_flow.AgenteTratamento", FakeTratamento)
    monkeypatch.setattr("src.ai.clinical_flow.AgenteCientifico", FakeCientifico)

    flow = build_clinical_flow()
    assert isinstance(flow, SpecialistClinicalFlow)
