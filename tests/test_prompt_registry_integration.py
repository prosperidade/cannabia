"""
Sprint 2 Track Reg — testes de integracao do prompt_registry.

Cobre:
  1. Fallback hardcoded quando DB nao tem entrada.
  2. Cache invalidation forca re-fetch do DB.
  3. Chave inexistente lanca KeyError.
  4. clinical_flow.run() popula result["prompts_used"] com 4 stages.
  5. service.py grava prompt_version + prompt_hash REAIS no audit_log
     (nao mais o placeholder antigo "v1.0" + sha256("v1.0")).

Os testes mockam o DB via monkeypatch em _load_from_db e os agentes via
fakes ja existentes em test_clinical_flow.py.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from src.ai import prompt_registry
from src.ai.prompt_registry import (
    _HARDCODED_PROMPTS,
    PromptVersion,
    get_prompt,
    invalidate_cache,
)


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture(autouse=True)
def _reset_registry_cache():
    """Cada teste comeca com cache limpo pra evitar cross-test pollution."""
    invalidate_cache()
    yield
    invalidate_cache()


# ──────────────────────────────────────────────────────────────────────────
# 1. Fallback hardcoded quando DB esta vazio
# ──────────────────────────────────────────────────────────────────────────

def test_registry_returns_hardcoded_when_db_empty(monkeypatch):
    """Sem entrada no DB, get_prompt retorna o snapshot hardcoded com hash
    deterministico (sha256 do conteudo)."""
    monkeypatch.setattr(prompt_registry, "_load_from_db", lambda key: None)

    result = get_prompt("anamnesis")

    assert isinstance(result, PromptVersion)
    assert result.key == "anamnesis"
    assert result.source == "hardcoded"
    assert result.version == "hardcoded"
    assert result.text == _HARDCODED_PROMPTS["anamnesis"]
    assert result.hash == _sha256(_HARDCODED_PROMPTS["anamnesis"])


# ──────────────────────────────────────────────────────────────────────────
# 2. Cache invalidation forca re-fetch
# ──────────────────────────────────────────────────────────────────────────

def test_registry_cache_invalidation(monkeypatch):
    """Apos invalidate_cache, get_prompt chama _load_from_db de novo."""
    call_count = {"n": 0}

    def fake_load(key):
        call_count["n"] += 1
        return None  # forca fallback hardcoded

    monkeypatch.setattr(prompt_registry, "_load_from_db", fake_load)

    # 1a chamada -> miss cache -> chama DB
    get_prompt("anamnesis")
    assert call_count["n"] == 1

    # 2a chamada -> hit cache -> NAO chama DB
    get_prompt("anamnesis")
    assert call_count["n"] == 1

    # invalidate -> proxima chamada vai re-fetchar
    invalidate_cache("anamnesis")

    get_prompt("anamnesis")
    assert call_count["n"] == 2


# ──────────────────────────────────────────────────────────────────────────
# 3. Chave inexistente
# ──────────────────────────────────────────────────────────────────────────

def test_get_prompt_unknown_key_raises(monkeypatch):
    """Chave que nao existe nem no DB nem no hardcoded -> KeyError."""
    monkeypatch.setattr(prompt_registry, "_load_from_db", lambda key: None)

    with pytest.raises(KeyError) as exc_info:
        get_prompt("chave_que_nao_existe_xyz")

    assert "chave_que_nao_existe_xyz" in str(exc_info.value)


# ──────────────────────────────────────────────────────────────────────────
# 4. clinical_flow popula prompts_used
# ──────────────────────────────────────────────────────────────────────────

def test_clinical_flow_populates_prompts_used(monkeypatch):
    """SpecialistClinicalFlow.run() agrega snapshot dos 4 prompts (anamnese,
    tratamento, prescritor, cientifico) em result["prompts_used"]."""
    # Forca fallback hardcoded pra todos os get_prompt do flow
    monkeypatch.setattr(prompt_registry, "_load_from_db", lambda key: None)

    # Importa fakes do test_clinical_flow.py via import direto
    from tests.test_clinical_flow import (
        _make_fake_anamnese,
        _make_fake_tratamento,
        _make_fake_prescritor,
        _make_fake_cientifico,
        _patch_all_agents,
    )
    from src.ai.clinical_flow import SpecialistClinicalFlow
    from src.ai.schemas import AnamnesisInput

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
            patient_name="Paciente Teste",
            age=40,
            main_complaint="Dor",
            symptoms=["dor"],
        )
    )

    assert "prompts_used" in result
    pu = result["prompts_used"]

    # 4 stages: anamnese, tratamento, prescritor, cientifico
    assert set(pu.keys()) == {"anamnese", "tratamento", "prescritor", "cientifico"}

    for stage, meta in pu.items():
        assert "key" in meta and meta["key"], f"stage {stage} sem key"
        assert "version" in meta and meta["version"], f"stage {stage} sem version"
        assert "hash" in meta and meta["hash"], f"stage {stage} sem hash"
        # Source eh hardcoded (mockamos _load_from_db retornando None)
        assert meta["source"] == "hardcoded", f"stage {stage} esperava hardcoded"

    # FakeCientifico tem chunks_used=3 -> usa scientific_report_rag
    assert pu["cientifico"]["key"] == "scientific_report_rag"
    assert pu["anamnese"]["key"] == "anamnesis"
    assert pu["tratamento"]["key"] == "treatment_plan"
    assert pu["prescritor"]["key"] == "prescriber_system"


def test_clinical_flow_uses_scientific_report_when_no_rag(monkeypatch):
    """Se cientifico_result.chunks_used == 0, snapshot usa
    scientific_report (nao scientific_report_rag)."""
    monkeypatch.setattr(prompt_registry, "_load_from_db", lambda key: None)

    from tests.test_clinical_flow import (
        _make_fake_anamnese,
        _make_fake_tratamento,
        _make_fake_prescritor,
        _patch_all_agents,
    )
    from src.ai.agents.base import AgentResult
    from src.ai.clinical_flow import SpecialistClinicalFlow
    from src.ai.schemas import AnamnesisInput

    class FakeCientificoNoRag:
        agent_name = "cientifico"

        def run(self, **kwargs):
            return AgentResult(
                success=True,
                data={
                    "scientific_report": {
                        "summary": "x",
                        "supporting_evidence": [],
                        "references": [],
                    },
                    "chunks_used": 0,  # <-- zero chunks
                    "model": "gpt-4o-mini",
                },
                tokens={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            )

    _patch_all_agents(
        monkeypatch,
        _make_fake_anamnese(),
        _make_fake_tratamento(),
        _make_fake_prescritor(),
        FakeCientificoNoRag,
    )

    flow = SpecialistClinicalFlow()
    result = flow.run(
        AnamnesisInput(
            patient_name="P",
            age=30,
            main_complaint="x",
            symptoms=["x"],
        )
    )

    assert result["prompts_used"]["cientifico"]["key"] == "scientific_report"


# ──────────────────────────────────────────────────────────────────────────
# 5. service.py grava prompt_version REAL no audit_log
# ──────────────────────────────────────────────────────────────────────────

def test_service_writes_real_prompt_version_in_audit(monkeypatch):
    """service.process_patient_case grava prompt_version + prompt_hash
    derivados do snapshot real, NAO o placeholder antigo "v1.0" +
    sha256("v1.0")."""
    from src.ai import service
    from src.ai.service import CannabIAService

    # Captura tudo que save_ai_audit_log recebeu
    captured: Dict[str, Any] = {}

    def fake_save(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(service, "save_ai_audit_log", fake_save)

    # patient_repo + billing nao tem efeito real
    monkeypatch.setattr(service, "get_or_create_patient_by_name", lambda c, n: 99)
    monkeypatch.setattr(
        service,
        "check_ai_allowance",
        lambda c: MagicMock(allowed=True, message=None),
    )
    monkeypatch.setattr(
        service,
        "record_ai_usage",
        lambda **k: None,
    )

    # Guardrails passam
    monkeypatch.setattr(
        service,
        "validate_input",
        lambda d: MagicMock(passed=True, blocked_by=MagicMock(value="none"), reason=None),
    )
    monkeypatch.setattr(
        service,
        "apply_to_output_dict",
        lambda r: (r, MagicMock(passed=True, reason=None)),
    )

    # Mock build_clinical_flow pra retornar flow que devolve prompts_used real
    fake_flow = MagicMock()
    fake_flow.run.return_value = {
        "clinical_analysis": {},
        "treatment_plan": {},
        "prescription_result": {},
        "scientific_report": {},
        "rag_chunks_used": 0,
        "report_model": "gpt-4o-mini",
        "token_usage": {"input": 10, "output": 5, "total": 15},
        "tokens_per_stage": {
            "clinical": {"model": "gpt-4o-mini", "tokens": {"input": 1, "output": 1}},
        },
        "timings_ms": {"clinical": 1, "treatment": 1, "prescription": 1, "report": 1},
        "execution_mode": "specialists",
        "specialists_used": [],
        "prompts_used": {
            "anamnese":   {"key": "anamnesis",         "version": "v1.0.0",     "hash": "a" * 64, "source": "hardcoded"},
            "tratamento": {"key": "treatment_plan",    "version": "v1.0.0",     "hash": "b" * 64, "source": "hardcoded"},
            "prescritor": {"key": "prescriber_system", "version": "v1.0.0",     "hash": "c" * 64, "source": "hardcoded"},
            "cientifico": {"key": "scientific_report", "version": "hardcoded",  "hash": "d" * 64, "source": "hardcoded"},
        },
    }
    monkeypatch.setattr(
        service, "build_clinical_flow",
        lambda mode=None: fake_flow,
    )

    # Flask g context: substitui o objeto inteiro no modulo pra evitar
    # werkzeug LocalProxy resolution durante patch.object.
    fake_g = MagicMock()
    fake_g.request_id = "req-test"
    fake_g.user_id = "user-test"
    fake_g.clinic_id = 1
    monkeypatch.setattr(service, "g", fake_g)

    svc = CannabIAService()
    svc.process_patient_case({
        "patient_name": "P",
        "age": 40,
        "main_complaint": "Dor",
        "symptoms": ["dor"],
    })

    # ASSERT: prompt_version NAO eh "v1.0" (o placeholder antigo)
    pv = captured["prompt_version"]
    assert pv != "v1.0", f"placeholder antigo persistiu: {pv}"
    # Deve agregar os 4 stages
    assert "anamnese:v1.0.0" in pv
    assert "tratamento:v1.0.0" in pv
    assert "prescritor:v1.0.0" in pv
    assert "cientifico:hardcoded" in pv

    # ASSERT: prompt_hash NAO eh sha256("v1.0") (placeholder antigo)
    ph = captured["prompt_hash"]
    placeholder_hash = _sha256("v1.0")
    assert ph != placeholder_hash, f"placeholder hash persistiu: {ph}"
    # Deve ser sha256 da concat ordenada dos 4 hashes individuais
    expected_hash = _sha256("|".join(sorted(["a" * 64, "b" * 64, "c" * 64, "d" * 64])))
    assert ph == expected_hash


def test_service_writes_na_when_pre_flow_blocks(monkeypatch):
    """billing_blocked path grava "n/a" em prompt_version + prompt_hash —
    nao mente com snapshot pra erros que ocorrem antes do flow rodar."""
    from src.ai import service
    from src.ai.service import CannabIAService
    from src.services.billing_service import BillingLimitExceeded

    captured: Dict[str, Any] = {}

    def fake_save(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(service, "save_ai_audit_log", fake_save)
    monkeypatch.setattr(service, "get_or_create_patient_by_name", lambda c, n: 99)
    monkeypatch.setattr(
        service,
        "check_ai_allowance",
        lambda c: MagicMock(
            allowed=False,
            message="Limite excedido",
            requests_used=100,
            requests_limit=100,
        ),
    )
    monkeypatch.setattr(service, "build_clinical_flow", lambda mode=None: MagicMock())

    fake_g = MagicMock()
    fake_g.request_id = "req-test"
    fake_g.user_id = "user-test"
    fake_g.clinic_id = 1
    monkeypatch.setattr(service, "g", fake_g)

    svc = CannabIAService()
    with pytest.raises(BillingLimitExceeded):
        svc.process_patient_case({
            "patient_name": "P",
            "age": 40,
            "main_complaint": "Dor",
            "symptoms": ["dor"],
        })

    # Pre-flow path: nao mente com snapshot
    assert captured["prompt_version"] == "n/a"
    assert captured["prompt_hash"] == "n/a"
    assert captured["status"] == "billing_blocked"
