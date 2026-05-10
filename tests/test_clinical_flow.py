from src.ai.agents.base import AgentResult
from src.ai.clinical_flow import SpecialistClinicalFlow, build_clinical_flow
from src.ai.schemas import AnamnesisInput


# ── Fakes reutilizados pelos testes ─────────────────────────────────────────


def _make_fake_anamnese():
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
                        "risk_level": "moderado",
                        "recommended_exams": ["hemograma"],
                        "red_flags": [],
                    }
                },
                tokens={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            )

    return FakeAnamnese


def _make_fake_tratamento():
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

    return FakeTratamento


def _make_fake_prescritor(
    safety_clamp_applied=True,
    cyp450=("CBD inibe CYP2C9 — INR pode aumentar.",),
    contraind=("Contraindicacao absoluta para THC: psicose.",),
):
    class FakePrescritor:
        agent_name = "prescritor"
        calls = []

        def run(self, **kwargs):
            self.__class__.calls.append(kwargs)
            return AgentResult(
                success=True,
                data={
                    "prescription_result": {
                        "final_dosage": {
                            "cannabinoid_ratio": "20:1",
                            "spectrum": "full_spectrum",
                            "administration_route": "sublingual",
                            "concentration_mg_ml": 20.0,
                            "titration_protocol": [
                                {
                                    "phase": "inicial",
                                    "day_range": "Dias 1-3",
                                    "drops_per_dose": 2,
                                    "doses_per_day": 2,
                                    "concentration_mg_ml": 20.0,
                                    "total_daily_mg": 8.0,
                                }
                            ],
                            "max_daily_mg": 1500.0,
                            "clinical_rationale": "Protocolo conservador.",
                            "contraindications": [],
                            "drug_interactions": [],
                            "monitoring_checkpoints": ["7 dias: avaliar tolerancia"],
                            "confidence_score": 0.82,
                            "evidence_sources": [],
                        },
                        "safety_clamp_applied": safety_clamp_applied,
                        "safety_clamp_reason": (
                            "Dose ajustada por: 1 interacao(oes) CYP450 + 1 contraindicacao(oes)"
                            if safety_clamp_applied
                            else None
                        ),
                        "cyp450_interactions": list(cyp450),
                        "monitoring_alerts": list(contraind),
                        "rules_engine_summary": {
                            "max_cbd_daily_mg": 1500.0,
                            "max_thc_daily_mg": 40.0,
                            "age_adjustment": "adulto: protocolo padrao",
                            "recommended_ratio": "20:1",
                            "recommended_route": "sublingual",
                        },
                        "dosage_defaults_used": True,
                        "confidence_score": 0.82,
                    },
                    "recommendation": {"confidence_score": 0.82},
                    "treatment_plan": {"confidence_score": 0.82},
                },
                tokens={"input_tokens": 25, "output_tokens": 15, "total_tokens": 40},
            )

    return FakePrescritor


def _make_fake_cientifico():
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

    return FakeCientifico


def _patch_all_agents(monkeypatch, anamnese, tratamento, prescritor, cientifico):
    monkeypatch.setattr("src.ai.clinical_flow.AgenteAnamnese", anamnese)
    monkeypatch.setattr("src.ai.clinical_flow.AgenteTratamento", tratamento)
    monkeypatch.setattr("src.ai.clinical_flow.AgentePrescritor", prescritor)
    monkeypatch.setattr("src.ai.clinical_flow.AgenteCientifico", cientifico)


# ── Testes ─────────────────────────────────────────────────────────────────


def test_specialist_clinical_flow_composes_four_specialists(monkeypatch):
    """Sprint 1 Track C.1: Prescritor entra como 4o stage entre Tratamento
    e Cientifico. Cientifico continua consumindo treatment_plan (nao
    prescription_result) — contrato inalterado."""
    Anamnese = _make_fake_anamnese()
    Tratamento = _make_fake_tratamento()
    Prescritor = _make_fake_prescritor()
    Cientifico = _make_fake_cientifico()
    _patch_all_agents(monkeypatch, Anamnese, Tratamento, Prescritor, Cientifico)

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
    assert result["specialists_used"] == [
        "anamnese", "tratamento", "prescritor", "cientifico",
    ]
    assert result["rag_chunks_used"] == 3
    assert result["report_model"] == "gemini-1.5-flash"

    # 4 stages somam: anamnese 15 + tratamento 30 + prescritor 40 + cientifico 42
    assert result["token_usage"] == {"input": 85, "output": 42, "total": 127}

    # treatment_plan e prescription_result ambos no return — paralelos
    assert result["treatment_plan"]["cannabinoid_ratio"] == "10:1"
    assert "prescription_result" in result
    assert result["prescription_result"]["final_dosage"]["cannabinoid_ratio"] == "20:1"

    # CRITICO: Cientifico recebe treatment_plan, NAO prescription_result
    assert Cientifico.calls[0]["treatment_plan"]["administration_route"] == "sublingual"
    assert "prescription_result" not in Cientifico.calls[0]

    # Prescritor recebe dosage_input construido de patient_data + clinical_analysis
    pres_kwargs = Prescritor.calls[0]
    assert pres_kwargs["dosage_input"]["patient_name"] == "Paciente Teste"
    assert pres_kwargs["dosage_input"]["conditions"] == ["dor cronica"]
    assert pres_kwargs["dosage_input"]["risk_level"] == "moderado"
    # AnamnesisInput nao tem weight_kg/prior_cannabis_use — defaults aplicados
    assert pres_kwargs["dosage_input"]["weight_kg"] == 70.0
    assert pres_kwargs["dosage_input"]["prior_cannabis_use"] is False
    assert pres_kwargs["_dosage_defaults_used"] is True

    # timings_ms inclui prescription
    assert set(result["timings_ms"].keys()) == {
        "clinical", "treatment", "prescription", "report",
    }
    for stage, elapsed in result["timings_ms"].items():
        assert isinstance(elapsed, int) and elapsed >= 0

    # tokens_per_stage inclui prescription com modelo gpt-4o-mini
    assert set(result["tokens_per_stage"].keys()) == {
        "clinical", "treatment", "prescription", "report",
    }
    assert result["tokens_per_stage"]["prescription"]["model"] == "gpt-4o-mini"
    assert result["tokens_per_stage"]["prescription"]["tokens"] == {
        "input": 25, "output": 15,
    }


def test_prescription_result_shape_and_safety_signals(monkeypatch):
    """prescription_result expoe campos esperados pelo frontend C.1.4:
    badges (safety_clamp_applied, dosage_defaults_used) + listas
    (cyp450_interactions, monitoring_alerts) + rules_engine_summary."""
    _patch_all_agents(
        monkeypatch,
        _make_fake_anamnese(),
        _make_fake_tratamento(),
        _make_fake_prescritor(),
        _make_fake_cientifico(),
    )

    flow = SpecialistClinicalFlow()
    result = flow.run(
        AnamnesisInput(
            patient_name="Paciente",
            age=50,
            main_complaint="Dor",
            symptoms=["dor"],
        )
    )

    pr = result["prescription_result"]
    # Shape obrigatorio
    expected_keys = {
        "final_dosage", "safety_clamp_applied", "safety_clamp_reason",
        "cyp450_interactions", "monitoring_alerts", "rules_engine_summary",
        "dosage_defaults_used", "confidence_score",
    }
    assert expected_keys.issubset(pr.keys())

    # Sinais para badges UI
    assert pr["safety_clamp_applied"] is True
    assert pr["safety_clamp_reason"] is not None
    assert "CYP450" in pr["safety_clamp_reason"]
    assert pr["dosage_defaults_used"] is True

    # rules_engine_summary serializavel (sem enums vazando)
    summary = pr["rules_engine_summary"]
    assert isinstance(summary["recommended_route"], str)  # nao enum
    assert summary["recommended_ratio"] == "20:1"


def test_risk_level_invalid_falls_back_to_moderado(monkeypatch):
    """clinical_flow normaliza risk_level antes de passar pra DosageInput
    (que so aceita baixo/moderado/alto). Anamnese as vezes retorna 'medio'
    ou 'high' — fallback evita ValidationError no Prescritor."""
    class WeirdAnamnese:
        agent_name = "anamnese"

        def run(self, **kwargs):
            return AgentResult(
                success=True,
                data={
                    "clinical_analysis": {
                        "probable_conditions": ["ansiedade"],
                        "risk_level": "medio",  # nao eh baixo/moderado/alto
                        "recommended_exams": [],
                        "red_flags": [],
                    }
                },
                tokens={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            )

    Prescritor = _make_fake_prescritor(
        safety_clamp_applied=False, cyp450=(), contraind=(),
    )
    _patch_all_agents(
        monkeypatch,
        WeirdAnamnese,
        _make_fake_tratamento(),
        Prescritor,
        _make_fake_cientifico(),
    )

    flow = SpecialistClinicalFlow()
    flow.run(
        AnamnesisInput(
            patient_name="Paciente",
            age=30,
            main_complaint="Ansiedade",
            symptoms=["ansiedade"],
        )
    )

    # 'medio' nao eh valido → cai em moderado
    assert Prescritor.calls[0]["dosage_input"]["risk_level"] == "moderado"


def test_cost_aggregation_sums_four_stages():
    """service.py soma calculate_cost por stage de tokens_per_stage. Sprint
    1 Track C.1 adicionou 'prescription' ao dict — o sum() agora cobre 4
    stages, nao 3. Custo dobra quando stages rodam tokens iguais."""
    from src.ai.pricing import calculate_cost

    tokens_per_stage = {
        "clinical":     {"model": "gpt-4o-mini",     "tokens": {"input": 1000, "output": 1000}},
        "treatment":    {"model": "gpt-4o-mini",     "tokens": {"input": 1000, "output": 1000}},
        "prescription": {"model": "gpt-4o-mini",     "tokens": {"input": 1000, "output": 1000}},
        "report":       {"model": "gemini-1.5-flash", "tokens": {"input": 1000, "output": 1000}},
    }

    estimated_cost = round(
        sum(
            calculate_cost(
                info["model"],
                info["tokens"]["input"],
                info["tokens"]["output"],
            )
            for info in tokens_per_stage.values()
        ),
        6,
    )

    # gpt-4o-mini: 0.00075 por 1k+1k → 3 stages = 0.00225
    # gemini-1.5-flash: 0.000375 por 1k+1k = 0.000375
    # total: 0.002625
    assert estimated_cost == 0.002625

    # Sanity: 4 stages > 3 stages (regressao)
    three_stage = round(
        sum(
            calculate_cost(info["model"], info["tokens"]["input"], info["tokens"]["output"])
            for k, info in tokens_per_stage.items() if k != "prescription"
        ),
        6,
    )
    assert estimated_cost > three_stage


def test_prescription_result_pii_is_redacted_by_audit_sanitizer():
    """A.3 sanitize_clinical_payload eh estrutural — walk recursivo cobre
    qualquer dict aninhado. prescription_result herda protecao sem codigo
    extra no Prescritor. Regressao: dosagem detalhada nao pode vazar
    nome de paciente em campo clinical_rationale."""
    from src.ai.audit_redaction import sanitize_clinical_payload

    output_payload = {
        "treatment_plan": {"cannabinoid_ratio": "10:1"},
        "prescription_result": {
            "final_dosage": {
                "cannabinoid_ratio": "20:1",
                "clinical_rationale": (
                    "Joao Silva (CPF 123.456.789-00) responde bem a CBD."
                ),
            },
            "monitoring_alerts": [
                "Monitorar INR. Email medico: dr.maria@example.com.",
            ],
            "patient_name": "Joao Silva",  # se vazar aqui, key sensivel pega
        },
    }

    sanitized = sanitize_clinical_payload(output_payload)

    pr = sanitized["prescription_result"]
    rationale = pr["final_dosage"]["clinical_rationale"]
    # CPF inline em string-leaf → regex pega
    assert "[CPF_REDACTED]" in rationale
    assert "123.456.789-00" not in rationale
    # Email em monitoring_alerts → regex pega
    assert "[EMAIL_REDACTED]" in pr["monitoring_alerts"][0]
    assert "dr.maria@example.com" not in pr["monitoring_alerts"][0]
    # Key sensivel patient_name → redacted integral
    assert pr["patient_name"] == "[REDACTED:key]"


def test_dosage_defaults_used_false_when_anamnesis_complete(monkeypatch):
    """Sprint 2 Track AI: AnamnesisInput agora aceita weight_kg + height_cm +
    prior_cannabis_use (Optional). Quando wizard de triagem alimenta os 3
    campos, defaults_used=False e o Prescritor recebe os valores reais."""
    Anamnese = _make_fake_anamnese()
    Tratamento = _make_fake_tratamento()
    Prescritor = _make_fake_prescritor()
    Cientifico = _make_fake_cientifico()
    _patch_all_agents(monkeypatch, Anamnese, Tratamento, Prescritor, Cientifico)

    flow = SpecialistClinicalFlow()
    flow.run(
        AnamnesisInput(
            patient_name="Paciente Completo",
            age=40,
            main_complaint="Dor cronica",
            symptoms=["dor"],
            weight_kg=80.0,
            height_cm=175.0,
            prior_cannabis_use=True,
        )
    )

    pres_kwargs = Prescritor.calls[0]
    assert pres_kwargs["dosage_input"]["weight_kg"] == 80.0
    assert pres_kwargs["dosage_input"]["height_cm"] == 175.0
    assert pres_kwargs["dosage_input"]["prior_cannabis_use"] is True
    # Conservador: ambos campos populados → defaults nao usados
    assert pres_kwargs["_dosage_defaults_used"] is False


def test_build_clinical_flow_prefers_specialists(monkeypatch):
    monkeypatch.setenv("AI_EXECUTION_MODE", "specialists")
    _patch_all_agents(
        monkeypatch,
        _make_fake_anamnese(),
        _make_fake_tratamento(),
        _make_fake_prescritor(),
        _make_fake_cientifico(),
    )

    flow = build_clinical_flow()
    assert isinstance(flow, SpecialistClinicalFlow)
