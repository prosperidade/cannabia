"""Testes da Camada 4 de guardrails (Sprint 1 Track B.1).

Cobre:
  - apply_to_output_dict com fixture clinico legitimo (passa sem mutacao).
  - apply_to_output_dict com tentativa de exfiltracao em string-leaf
    (sanitiza recursivamente, retorna result com passed=False).
  - _sanitize_string_leaves preserva tipos: dict, list, tuple, scalars.
  - apply_to_output_dict tolera nao-dict (defensive).
"""

from src.ai.guardrails import (
    GuardrailLayer,
    _sanitize_string_leaves,
    apply_to_output_dict,
    sanitize_output,
)


def _legitimate_clinical_result() -> dict:
    """Fixture com a forma de retorno real do SpecialistClinicalFlow."""
    return {
        "clinical_analysis": {
            "probable_conditions": ["Dor lombar cronica", "Insonia secundaria"],
            "risk_level": "medio",
            "recommended_exams": ["Ressonancia lombar", "Polissonografia"],
            "red_flags": [],
        },
        "treatment_plan": {
            "cannabinoid_ratio": "10:1",
            "suggested_dosage": "2 gotas 2x/dia, sublingual",
            "administration_route": "sublingual",
            "monitoring_plan": "Reavaliar em 14 dias",
            "precautions": ["Monitorar sonolencia"],
        },
        "scientific_report": {
            "summary": "Relato com suporte na literatura: CBD demonstrou eficacia em dor cronica.",
            "supporting_evidence": ["Russo 2019", "Cochrane 2020"],
            "references": ["PMID:12345", "DOI:10.1016/j.pain.2019.02"],
        },
        "rag_chunks_used": 3,
        "report_model": "gemini-1.5-flash",
        "execution_mode": "specialists",
    }


def test_legitimate_output_passes_unmodified():
    original = _legitimate_clinical_result()
    sanitized, result = apply_to_output_dict(original)

    assert result.passed is True
    # Sem mutacao no caminho passed
    assert sanitized == original
    # Sanity: identidade de objeto preservada (zero-copy quando passa)
    assert sanitized is original


def test_exfiltration_attempt_in_summary_is_sanitized():
    # Pattern 6 do _OUTPUT_DANGER_PATTERNS — captura nome+valor completo:
    # (api[_-]?key|password|secret[_-]?key|token)\s*[:=]\s*['\"]?\w{8,}
    output = _legitimate_clinical_result()
    output["scientific_report"]["summary"] = (
        "Relato cientifico api_key=secretactualcontentleak1234 embedded."
    )

    sanitized, result = apply_to_output_dict(output)

    assert result.passed is False
    assert result.blocked_by == GuardrailLayer.OUTPUT
    # Pattern capturou nome+valor: tudo virou [REDACTED]
    assert "[REDACTED]" in sanitized["scientific_report"]["summary"]
    assert "api_key" not in sanitized["scientific_report"]["summary"].lower()
    assert "secretactualcontentleak1234" not in sanitized["scientific_report"]["summary"]
    # Estrutura preservada
    assert sanitized["clinical_analysis"]["probable_conditions"] == [
        "Dor lombar cronica",
        "Insonia secundaria",
    ]
    assert sanitized["treatment_plan"]["cannabinoid_ratio"] == "10:1"
    # Output original NAO mutado (sanitize retorna estrutura nova)
    assert "api_key=secretactualcontentleak1234" in output["scientific_report"]["summary"]


def test_exfiltration_in_nested_list_is_sanitized():
    # Usa pattern 6 (api_key|password|secret_key|token) que captura valor
    # completo. Valor precisa ser \w{8,} continuo (sem hyphens — \w nao casa).
    output = _legitimate_clinical_result()
    output["scientific_report"]["supporting_evidence"] = [
        "Russo 2019",
        "token=bearerleakedrealsecret9999",
    ]

    sanitized, result = apply_to_output_dict(output)

    assert result.passed is False
    cleaned_evidences = sanitized["scientific_report"]["supporting_evidence"]
    assert cleaned_evidences[0] == "Russo 2019"
    assert "[REDACTED]" in cleaned_evidences[1]
    assert "bearerleakedrealsecret9999" not in cleaned_evidences[1]


def test_known_regex_gap_env_var_name_pattern_leaves_value():
    # GAP CONHECIDO: pattern 7 (OPENAI_API_KEY|GOOGLE_API_KEY|DATABASE_URL|
    # SECRET_KEY)\s*[:=] so captura ate o `=`, deixando o valor. Detecta o
    # ataque (passed=False) mas a sanitizacao e parcial.
    # FIXME(sprint-2): estender o pattern para incluir \s*['\"]?\w{8,}
    # alinhado com pattern 6, OU promover pattern 7 a bloqueio total.
    output = {"summary": "OPENAI_API_KEY=sk-proj-abc12345xyz embedded"}

    sanitized, result = apply_to_output_dict(output)

    # Detectou (passed=False) — comportamento correto.
    assert result.passed is False
    # Nome da env var foi redacted.
    assert "OPENAI_API_KEY" not in sanitized["summary"]
    # GAP: valor permanece. Documentado como divida pra Sprint 2.
    assert "sk-proj-abc12345xyz" in sanitized["summary"]


def test_script_tag_in_message_is_sanitized():
    # Padrao XSS — outro vetor da Camada 4
    output = {
        "report_text": "Resumo clinico <script>alert('xss')</script> resto do texto",
        "tags": ["normal"],
    }

    sanitized, result = apply_to_output_dict(output)

    assert result.passed is False
    assert "<script" not in sanitized["report_text"].lower()
    assert "[REDACTED]" in sanitized["report_text"]
    assert sanitized["tags"] == ["normal"]


def test_sanitize_string_leaves_preserves_types():
    payload = {
        "string": "hello",
        "int": 42,
        "float": 3.14,
        "bool": True,
        "none": None,
        "list_of_str": ["a", "b"],
        "list_of_int": [1, 2, 3],
        "tuple": ("x", "y"),
        "nested": {"deep": {"deeper": "value"}},
    }

    cleaned = _sanitize_string_leaves(payload)

    assert cleaned["string"] == "hello"
    assert cleaned["int"] == 42
    assert cleaned["float"] == 3.14
    assert cleaned["bool"] is True
    assert cleaned["none"] is None
    assert cleaned["list_of_str"] == ["a", "b"]
    assert cleaned["list_of_int"] == [1, 2, 3]
    assert isinstance(cleaned["tuple"], tuple)
    assert cleaned["tuple"] == ("x", "y")
    assert cleaned["nested"]["deep"]["deeper"] == "value"


def test_sanitize_string_leaves_strips_zero_width_chars():
    # zero-width characters no string-leaf sao removidos
    payload = {"summary": "texto​limpo‌‍ aqui"}
    cleaned = _sanitize_string_leaves(payload)
    assert cleaned["summary"] == "textolimpo aqui"


def test_apply_to_non_dict_returns_unchanged():
    # Defensive: caller manda algo que nao e dict
    not_a_dict = ["lista", "de", "coisas"]
    out, result = apply_to_output_dict(not_a_dict)  # type: ignore[arg-type]
    assert out is not_a_dict
    assert result.passed is True


def test_sanitize_output_module_function_works_independently():
    # Sanity: sanitize_output sozinho (chamado por _sanitize_string_leaves)
    # continua funcionando
    cleaned = sanitize_output("<script>alert(1)</script> ola")
    assert "<script" not in cleaned.lower()
    assert "ola" in cleaned
