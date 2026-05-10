"""
Tests do A.3 — PII redaction estrutural em ai_audit_logs.

Cobre:
1. Fixture clinico realista (anamnesis full nested) — keys sensiveis
   value-redacted, payload preserva schema.
2. Free-text com PII inline (CPF/RG/email/phone/CRM/address) — regex
   pega em string-leaves de keys nao sensiveis.
3. Fail-safe — sanitize_clinical_payload NUNCA raise: payload custom
   que quebra walk vira {"_redaction_failed": True, ...}.
4. Repository integration — save_ai_audit_log persiste payload
   sanitizado tanto no branch success quanto no billing_blocked.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# =====================================================
# 1. Anamnesis nested — keys sensiveis redacted
# =====================================================

def test_sanitize_anamnesis_full_payload_redacts_sensitive_keys():
    """Payload realista de anamnesis: PII em keys top-level + nested
    vira [REDACTED:key]; campos clinicos free-text preservam conteudo
    exceto onde regex encontra PII embutido."""
    from src.ai.audit_redaction import sanitize_clinical_payload

    payload = {
        "patient_name": "Joao Silva Santos",
        "age": 45,
        "main_complaint": "Dor cronica lombar ha 6 meses",
        "symptoms": ["dor lombar persistente", "dificuldade pra dormir"],
        "current_medications": ["Paracetamol 500mg", "Dipirona"],
        "allergies": ["Nenhuma conhecida"],
        "medical_history": "Historico de artrite. Mae com fibromialgia.",
        "patient_data": {
            "cpf": "123.456.789-00",
            "email": "joao@example.com",
            "phone": "(62) 98281-0427",
            "address": "Rua Exemplo 123",
        },
        "doctor_info": {
            "doctor_name": "Dr. Maria",
            "crm": "CRM/SP 12345",
        },
    }

    result = sanitize_clinical_payload(payload)

    # Keys top-level sensiveis: redacted integral
    assert result["patient_name"] == "[REDACTED:key]"

    # Nested patient_data: todos os campos PII redacted
    assert result["patient_data"]["cpf"] == "[REDACTED:key]"
    assert result["patient_data"]["email"] == "[REDACTED:key]"
    assert result["patient_data"]["phone"] == "[REDACTED:key]"
    assert result["patient_data"]["address"] == "[REDACTED:key]"

    # Nested doctor_info: identificacao profissional redacted
    assert result["doctor_info"]["doctor_name"] == "[REDACTED:key]"
    assert result["doctor_info"]["crm"] == "[REDACTED:key]"

    # Campos clinicos free-text preservam conteudo (sao DADOS auditaveis)
    assert result["age"] == 45
    assert result["main_complaint"] == "Dor cronica lombar ha 6 meses"
    assert result["medical_history"] == (
        "Historico de artrite. Mae com fibromialgia."
    )
    # Lista de strings preservada
    assert result["symptoms"] == [
        "dor lombar persistente",
        "dificuldade pra dormir",
    ]


# =====================================================
# 2. Free-text com PII inline — regex em string-leaves
# =====================================================

def test_sanitize_string_leaves_catches_inline_pii():
    """PII embutido em campos clinicos free-text (key NAO sensivel)
    eh capturado pelo regex em string-leaves."""
    from src.ai.audit_redaction import sanitize_clinical_payload

    payload = {
        "main_complaint": (
            "Paciente: Joao Silva. CPF 123.456.789-00, fone 62 98281-0427. "
            "Mora na Rua das Flores 42."
        ),
        "medical_history": (
            "Email: joao@example.com. RG 12.345.678-9. "
            "Cartao SUS 123456789012345."
        ),
        "doctor_referral": (
            "Encaminhado por Dr. Maria CRM/SP 12345. "
            "Tel: (11) 99999-1234."
        ),
        "free_notes": [
            "Nada relevante aqui.",
            "CPF do dependente: 987.654.321-00",
        ],
    }

    result = sanitize_clinical_payload(payload)

    main = result["main_complaint"]
    assert "[CPF_REDACTED]" in main
    assert "[PHONE_REDACTED]" in main
    assert "[ADDRESS_REDACTED]" in main
    assert "123.456.789-00" not in main
    assert "Joao Silva" not in main  # pego por _PATIENT_NAME pattern

    history = result["medical_history"]
    assert "[EMAIL_REDACTED]" in history
    assert "[RG_REDACTED]" in history
    assert "[SUS_CARD_REDACTED]" in history
    assert "joao@example.com" not in history

    referral = result["doctor_referral"]
    assert "[PROFESSIONAL_ID_REDACTED]" in referral
    assert "[PHONE_REDACTED]" in referral

    # Lista: cada item recursivamente sanitizado
    assert "[CPF_REDACTED]" in result["free_notes"][1]
    assert result["free_notes"][0] == "Nada relevante aqui."


def test_sanitize_sus_regex_requires_explicit_context():
    """Coordenador (2026-05-10): \\b\\d{15}\\b solto da falso positivo.
    SUS regex SO redact com contexto explicito (SUS/CNS/cartao)."""
    from src.ai.audit_redaction import sanitize_clinical_payload

    payload = {
        "lab_result": "Marcador biologico 123456789012345 detectado.",
        "sus_field": "Cartao SUS 123456789012345 do paciente.",
    }

    result = sanitize_clinical_payload(payload)

    # Sem contexto SUS: NAO redacted (evita falso positivo em codigo de exame)
    assert "123456789012345" in result["lab_result"]
    assert "[SUS_CARD_REDACTED]" not in result["lab_result"]

    # Com contexto explicito: redacted
    assert "[SUS_CARD_REDACTED]" in result["sus_field"]
    assert "123456789012345" not in result["sus_field"]


# =====================================================
# 3. Fail-safe — sanitizer NUNCA raise
# =====================================================

def test_sanitize_fail_safe_returns_redaction_failed_marker():
    """Se algo dar errado durante walk, sanitizer NAO raise — devolve
    dict marcador com _redaction_failed=True. Audit log nunca desaparece."""
    from src.ai.audit_redaction import sanitize_clinical_payload

    payload = {"patient_name": "Joao", "data": {"nested": "value"}}

    # Patch _walk pra simular erro interno
    with patch("src.ai.audit_redaction._walk", side_effect=RuntimeError("boom")):
        result = sanitize_clinical_payload(payload)

    assert isinstance(result, dict)
    assert result["_redaction_failed"] is True
    assert result["_payload_type"] == "dict"
    # Top-level keys preservadas pra auditoria/debug
    assert set(result["_payload_keys"]) == {"patient_name", "data"}
    assert "boom" in result["_error"]


def test_sanitize_handles_none_payload():
    """None passa intacto — caller usa em early-exit branches
    (billing_blocked, security_blocked, validation_error)."""
    from src.ai.audit_redaction import sanitize_clinical_payload

    assert sanitize_clinical_payload(None) is None


# =====================================================
# 5. Idempotencia — pre-requisito do purge in-place (Sprint 2 LGPD)
# =====================================================
#
# O script scripts/purge_audit_pii_pre_a3.py aplica sanitize_clinical_payload
# in-place em rows ja gravadas pre-A.3. Para que purge seja seguro contra
# replays/resume, a funcao precisa ser IDEMPOTENTE: f(f(x)) == f(x). Caso
# contrario, rodar o purge duas vezes pode danificar dados (ex: marcadores
# como [REDACTED:key] sendo reinterpretados como string-leaves e gerando
# transformacoes secundarias).

def test_sanitize_idempotent_on_clean_payload():
    """Payload simples sem PII: f(f(x)) == f(x). Garante que sanitize
    em payload ja-limpo nao introduz mudancas."""
    from src.ai.audit_redaction import sanitize_clinical_payload

    payload = {
        "age": 45,
        "main_complaint": "Dor cronica lombar ha 6 meses",
        "symptoms": ["dor persistente", "insonia"],
        "cannabinoid_ratio": "1:1",
        "confidence_score": 0.85,
        "tokens_used": 1234,
    }

    r1 = sanitize_clinical_payload(payload)
    r2 = sanitize_clinical_payload(r1)

    assert r1 == r2, "sanitize precisa ser idempotente em payload limpo"


def test_sanitize_idempotent_with_redacted_markers():
    """Payload com PII: sanitize -> re-sanitize -> mesmo resultado.
    Garante que marcadores como [REDACTED:key], [CPF_REDACTED], etc.
    nao sao reinterpretados em passes subsequentes."""
    from src.ai.audit_redaction import sanitize_clinical_payload

    payload = {
        "patient_name": "Joao Silva Santos",
        "main_complaint": "Paciente com dor. CPF 123.456.789-00. Email: x@y.com",
        "patient_data": {
            "cpf": "111.222.333-44",
            "email": "test@example.com",
            "phone": "(62) 98281-0427",
        },
        "free_notes": [
            "Telefone (11) 99999-1234.",
            "Endereco: Rua Exemplo 42.",
        ],
    }

    r1 = sanitize_clinical_payload(payload)
    r2 = sanitize_clinical_payload(r1)

    assert r1 == r2, (
        "sanitize precisa ser idempotente em payload com marcadores de "
        "redaction. Diff: r1=%r r2=%r" % (r1, r2)
    )


def test_sanitize_preserves_clinical_metadata():
    """Keys NAO sensiveis (cannabinoid_ratio, confidence_score, etc.)
    sobrevivem intactas tanto no primeiro quanto no segundo pass.
    Critico pra dashboards/relatorios que dependem desses campos."""
    from src.ai.audit_redaction import sanitize_clinical_payload

    payload = {
        "patient_name": "Joao Silva",  # sera redacted
        "cannabinoid_ratio": "20:1 CBD:THC",
        "confidence_score": 0.92,
        "recommended_dosage_mg": 25,
        "treatment_response": "Boa resposta",
        "stage_timings_ms": {
            "clinical": 1200,
            "treatment": 800,
            "report": 1500,
        },
        "cost_per_stage_usd": [0.001, 0.002, 0.003],
    }

    r1 = sanitize_clinical_payload(payload)
    r2 = sanitize_clinical_payload(r1)

    # Metadata clinica preservada nos dois passes
    for result in (r1, r2):
        assert result["cannabinoid_ratio"] == "20:1 CBD:THC"
        assert result["confidence_score"] == 0.92
        assert result["recommended_dosage_mg"] == 25
        assert result["treatment_response"] == "Boa resposta"
        assert result["stage_timings_ms"] == {
            "clinical": 1200,
            "treatment": 800,
            "report": 1500,
        }
        assert result["cost_per_stage_usd"] == [0.001, 0.002, 0.003]
        # patient_name continua redacted
        assert result["patient_name"] == "[REDACTED:key]"

    # Idempotencia garantida tambem no agregado
    assert r1 == r2


# =====================================================
# 4. Repository integration — DB roundtrip
# =====================================================

@pytest.fixture
def _ensure_test_patient(db_connection):
    """Garante patient com id conhecido pra FKs do ai_audit_logs.
    Roda dentro da transacao isolada do db_connection (rollback automatico)."""
    cursor = db_connection.cursor()
    cursor.execute(
        "INSERT INTO patients (id, clinic_id, name) "
        "VALUES (99999, 1, 'Test Patient') "
        "ON CONFLICT (id) DO NOTHING"
    )
    db_connection.commit()
    yield 99999
    cursor.execute("DELETE FROM ai_audit_logs WHERE patient_id = 99999")
    cursor.execute("DELETE FROM patients WHERE id = 99999")
    db_connection.commit()
    cursor.close()


def test_repository_sanitizes_input_and_output_payloads(
    _ensure_test_patient,
):
    """Integracao: save_ai_audit_log com payloads contendo PII -->
    inspecionar registro no DB confirma redaction tanto em
    input_payload quanto output_payload."""
    from src.repositories.ai_audit_repository import save_ai_audit_log
    from src.infra.database import db_cursor

    patient_id = _ensure_test_patient
    request_id = "test-redact-001"

    save_ai_audit_log(
        clinic_id=1,
        patient_id=patient_id,
        request_id=request_id,
        endpoint="/test/redaction",
        user_id="test-user",
        input_payload={
            "patient_name": "Joao Silva",
            "main_complaint": "Dor lombar. CPF 123.456.789-00.",
        },
        output_payload={
            "clinical_analysis": {
                "summary": "Email contato: joao@example.com",
            },
        },
        status="success",
        error_message=None,
        model="test-model",
        prompt_version="v1",
        prompt_hash="hash",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        clinical_time_ms=100,
        treatment_time_ms=100,
        report_time_ms=100,
        total_time_ms=300,
        estimated_cost_usd=0.001,
    )

    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT input_payload, output_payload FROM ai_audit_logs "
            "WHERE request_id = %s",
            (request_id,),
        )
        row = cur.fetchone()
        # Cleanup imediato (fora da transacao do fixture pra nao deixar lixo
        # caso o fixture rollback nao limpe esta linha — repository commita)
        cur.execute(
            "DELETE FROM ai_audit_logs WHERE request_id = %s", (request_id,)
        )
        cur.connection.commit()

    assert row is not None, "registro nao foi gravado em ai_audit_logs"
    input_payload, output_payload = row

    # input: patient_name redacted, CPF inline tambem
    assert input_payload["patient_name"] == "[REDACTED:key]"
    assert "Joao Silva" not in str(input_payload)
    assert "[CPF_REDACTED]" in input_payload["main_complaint"]
    assert "123.456.789-00" not in input_payload["main_complaint"]

    # output: email inline redacted (clinical_analysis nao eh sensitive key)
    summary = output_payload["clinical_analysis"]["summary"]
    assert "[EMAIL_REDACTED]" in summary
    assert "joao@example.com" not in summary
