"""Testes dos context providers + renderizacao dos templates de F4.6.

Cobertura em 2 camadas:

1. **Renderizacao pura** — passamos dicts hand-crafted para
   ``template_engine.render(...)`` e validamos que os 4 templates
   novos (monitoring_opinion, consent_form, label_warning,
   sop_template) produzem Markdown com o esqueleto correto. Cobre
   tambem que StrictUndefined pega campo obrigatorio ausente.

2. **Providers** — monkeypatch de db_cursor para conferir que cada
   ``build_*`` retorna um dict com todas as chaves que o respectivo
   template referencia, sem tocar o banco.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone
from typing import Any

import pytest

from src.services import regulatory_documents as rd
from src.services.template_engine import (
    TemplateRenderError,
    render as render_template,
)


# ---------------------------------------------------------------------
# Fixtures comuns de DB fake
# ---------------------------------------------------------------------

class _FakeCursor:
    def __init__(self, responses: list[Any]):
        self._responses = list(responses)
        self.executes: list[tuple[str, tuple]] = []
        self._last = None

    def execute(self, sql: str, params: tuple = ()):
        self.executes.append((sql, tuple(params)))
        if self._responses:
            self._last = self._responses.pop(0)
        else:
            self._last = None

    def fetchone(self):
        if isinstance(self._last, list):
            # lista de rows: primeiro item para fetchone
            return self._last[0] if self._last else None
        return self._last

    def fetchall(self):
        if isinstance(self._last, list):
            return list(self._last)
        return [self._last] if self._last is not None else []


class _FakeCtx:
    def __init__(self, cursor: _FakeCursor):
        self.cursor = cursor

    def __enter__(self):
        return (None, self.cursor)

    def __exit__(self, *exc):
        return False


def _install_fake(monkeypatch, responses: list[Any]) -> _FakeCursor:
    """Instala db_cursor fake em regulatory_documents, retorna o cursor."""
    cursor = _FakeCursor(responses)
    monkeypatch.setattr(
        "src.services.regulatory_documents.db_cursor",
        lambda dictionary=True: _FakeCtx(cursor),
    )
    return cursor


# ---------------------------------------------------------------------
# Contextos hand-crafted minimos para cada template
# ---------------------------------------------------------------------

@pytest.fixture
def opinion_ctx() -> dict:
    return {
        "project": {
            "id": 1, "title": "PE-2026-001",
            "objective": "Reduzir desigualdade de acesso",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "status": "active",
        },
        "tenant": {
            "id": 42, "legal_name": "Associacao X",
            "trade_name": "AX", "cnpj": "12345678000199",
            "incorporation_date": date(2023, 1, 1),
        },
        "technical_responsible": {
            "full_name": "Dra Ana",
            "professional_council": "CRM",
            "council_number": "12345",
            "council_state": "SP",
        },
        "scope": {"activities": ["cultivo", "preparo"], "scale": "100 associados"},
        "schedule": {"planned": [], "executed": []},
        "indicators": {
            "mandatory": [
                {"code": "IND-01", "name": "Conformidade lab",
                 "period": "Q1", "value": "92%", "target": "90%",
                 "status": "atingido"},
            ],
            "complementary": [],
        },
        "operational_evidence": {
            "sops_count": 12, "sop_deviations": 1, "capa_actions": 1,
        },
        "clinical_evidence": {
            "consultations": 48, "prescriptions": 23,
            "outcomes": ["Reducao de dor em 70%"],
        },
        "pharmacovigilance": {
            "adverse_events_count": 2, "sanitary_risks_count": 5,
        },
        "anchors": {
            "total": 30,
            "networks": {"bitcoin_ots": 30},
            "verification_status_counts": {"confirmed": 28, "pending": 2},
        },
        "findings": ["Alta adesao"],
        "recommendations": ["Manter escopo restrito"],
        "limitations": ["Amostra pequena"],
        "financial": None,
        "attachments": [],
        "generated_at": "2026-04-21T00:00:00+00:00",
        "period_label": "Consolidacao Final",
        "document_version": "v1",
    }


@pytest.fixture
def consent_ctx() -> dict:
    return {
        "tenant": {"legal_name": "Assoc X", "cnpj": "12345678000199", "trade_name": "AX"},
        "member": {"full_name": "Joao Silva", "cpf": "11122233344", "rg": "1234567"},
        "project": {"title": "PE-2026-001", "sandbox_protocol": "ANV-X-001"},
        "technical_responsible": {"full_name": "Dra Ana", "council": "CRM 12345/SP"},
        "consent": {
            "lgpd_basis": "Consentimento especifico",
            "data_sharing_with_anvisa": True,
            "rights": ["direito 1", "direito 2"],
        },
        "known_risks": ["Risco A"],
        "known_benefits": ["Beneficio B"],
        "generated_at": "2026-04-21T00:00:00+00:00",
        "document_version": "v1",
    }


@pytest.fixture
def label_ctx() -> dict:
    return {
        "preparation": {
            "id": 7, "product_name": "CBD 10%",
            "dosage_form": "oleo", "batch_code": "LOT-2026-001",
            "prepared_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
            "cannabinoid_profile": {"CBD": "10%", "THC": "<0.2%"},
        },
        "tenant": {"legal_name": "Assoc X", "trade_name": "AX", "cnpj": "12345678000199"},
        "technical_responsible": {
            "full_name": "Dra Ana", "professional_council": "CRM",
            "council_number": "12345", "council_state": "SP",
        },
        "verification_url": "https://verify.cannabia.app/api/v1/public/anchors/42/verify",
        "qr_code_data": "lot:LOT-2026-001",
        "generated_at": "2026-04-21T00:00:00+00:00",
        "document_version": "v1",
    }


@pytest.fixture
def sop_ctx() -> dict:
    return {
        "sop": {
            "code": "POP-OP-001", "title": "Preparo de Oleo",
            "version": "1.0",
            "scope": "Estabelecer procedimento padronizado de preparo",
            "applicability": "Aplicavel em todos os lotes de oleo",
        },
        "tenant": {"legal_name": "Assoc X"},
        "definitions": [{"term": "CBD", "definition": "canabidiol"}],
        "responsibilities": [{"role": "Tecnico", "duty": "Executar preparo"}],
        "procedure_steps": [
            {"order": 1, "step": "Higienizar bancada", "record": "Checklist BP-01"},
        ],
        "generated_records": ["Batch record", "Checklist de higienizacao"],
        "references": ["RDC 1.014/2026", "ABNT NBR ISO 9001"],
        "approver": {"name": "Dra Ana", "role": "RT"},
        "revision_history": [],
        "generated_at": "2026-04-21T00:00:00+00:00",
        "document_version": "v1",
    }


# =====================================================================
# 1. Renderizacao dos templates
# =====================================================================

class TestRenderMonitoringOpinion:
    def test_renderiza_e_inclui_secoes(self, opinion_ctx):
        doc = render_template("final/monitoring_opinion", opinion_ctx, format="md")
        assert "# Parecer Final de Monitoramento" in doc.content
        assert "Associacao X" in doc.content
        assert "## 4. Desempenho dos indicadores obrigatorios" in doc.content
        assert "IND-01" in doc.content
        assert "bitcoin_ots: 30" in doc.content
        assert len(doc.content_hash) == 64

    def test_strict_undefined_pega_chave_ausente(self, opinion_ctx):
        ctx = copy.deepcopy(opinion_ctx)
        del ctx["tenant"]
        with pytest.raises(TemplateRenderError, match="ausente"):
            render_template("final/monitoring_opinion", ctx, format="md")


class TestRenderConsentForm:
    def test_renderiza_partes_obrigatorias(self, consent_ctx):
        doc = render_template("operational/consent_form", consent_ctx, format="md")
        assert "# Termo de Consentimento Informado" in doc.content
        assert "Joao Silva" in doc.content
        assert "nao sao medicamentos" in doc.content
        assert "LGPD" in doc.content

    def test_strict_undefined_pega_member_ausente(self, consent_ctx):
        ctx = copy.deepcopy(consent_ctx)
        del ctx["member"]
        with pytest.raises(TemplateRenderError):
            render_template("operational/consent_form", ctx, format="md")


class TestRenderLabelWarning:
    def test_renderiza_rotulo(self, label_ctx):
        doc = render_template("operational/label_warning", label_ctx, format="md")
        assert "CBD 10%" in doc.content
        assert "LOT-2026-001" in doc.content
        assert "NAO e medicamento" in doc.content
        assert "https://verify.cannabia.app" in doc.content
        assert "CRM 12345/SP" in doc.content


class TestRenderSopTemplate:
    def test_renderiza_estrutura_minima_de_pop(self, sop_ctx):
        doc = render_template("operational/sop_template", sop_ctx, format="md")
        assert "POP POP-OP-001" in doc.content
        assert "Preparo de Oleo" in doc.content
        assert "## 1. Objetivo" in doc.content
        assert "## 9. Aprovacao" in doc.content
        assert "Dra Ana" in doc.content


# =====================================================================
# 2. Providers — checam que dict resultante cobre as chaves do template
# =====================================================================

_TENANT_ROW = {
    "id": 42, "legal_name": "Assoc X", "display_name": "Assoc X",
    "trade_name": "AX", "cnpj": "12345678000199",
    "incorporation_date": date(2023, 1, 1),
    "tenant_type": "association", "status": "active",
}

_RT_ROW = {
    "id": 1, "full_name": "Dra Ana", "professional_council": "CRM",
    "council_number": "12345", "council_state": "SP",
    "habilitation_valid_until": date(2030, 1, 1), "is_active": True,
}


class TestBuildMonitoringOpinionData:
    def test_retorna_todas_as_chaves_esperadas(self, monkeypatch):
        project_row = {
            "id": 7, "title": "PE-2026-001", "status": "active",
            "submitted_at": None, "approved_at": None,
            "started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "concluded_at": None, "anvisa_reference": "ANV-X-001",
        }
        # Ordem de execute() em build_monitoring_opinion_data:
        # 1) SELECT tenants  2) SELECT technical_responsibles
        # 3) SELECT sandbox_projects  4) COUNT sop_evidences
        # 5) COUNT adverse_events    6) COUNT sanitary_risks
        # 7) GROUP anchors
        responses = [
            _TENANT_ROW,
            [_RT_ROW],
            project_row,
            {"n": 5},
            {"n": 2},
            {"n": 3},
            [
                {"n": 10, "blockchain_network": "bitcoin_ots",
                 "verification_status": "confirmed"},
                {"n": 2, "blockchain_network": "polygon",
                 "verification_status": "pending"},
            ],
        ]
        _install_fake(monkeypatch, responses)

        data = rd.build_monitoring_opinion_data(7, 42)
        expected_keys = {
            "project", "tenant", "technical_responsible", "scope",
            "schedule", "indicators", "operational_evidence",
            "clinical_evidence", "pharmacovigilance", "anchors",
            "findings", "recommendations", "limitations", "financial",
            "attachments", "generated_at", "period_label",
            "document_version",
        }
        assert expected_keys.issubset(data.keys())
        assert data["tenant"]["legal_name"] == "Assoc X"
        assert data["project"]["title"] == "PE-2026-001"
        assert data["technical_responsible"]["full_name"] == "Dra Ana"
        assert data["operational_evidence"]["sops_count"] == 5
        assert data["pharmacovigilance"]["adverse_events_count"] == 2
        assert data["anchors"]["total"] == 12
        assert data["anchors"]["networks"]["bitcoin_ots"] == 10

    def test_overrides_substituem_chaves(self, monkeypatch):
        project_row = {
            "id": 7, "title": "X", "status": "active",
            "submitted_at": None, "approved_at": None,
            "started_at": None, "concluded_at": None,
            "anvisa_reference": None,
        }
        _install_fake(monkeypatch, [
            _TENANT_ROW, [_RT_ROW], project_row,
            {"n": 0}, {"n": 0}, {"n": 0}, [],
        ])
        data = rd.build_monitoring_opinion_data(
            7, 42, overrides={"findings": ["override"], "financial": "Receita: 0"}
        )
        assert data["findings"] == ["override"]
        assert data["financial"] == "Receita: 0"

    def test_projeto_inexistente(self, monkeypatch):
        _install_fake(monkeypatch, [_TENANT_ROW, [_RT_ROW], None])
        with pytest.raises(ValueError, match="Projeto"):
            rd.build_monitoring_opinion_data(9999, 42)


class TestBuildConsentFormData:
    def test_monta_contexto_basico(self, monkeypatch):
        member_row = {
            "member_id": 5, "membership_number": "M-0001",
            "membership_status": "active",
            "full_name": "Joao Silva", "cpf": "11122233344",
        }
        project_row = {"id": 1, "title": "PE-2026-001", "anvisa_reference": "ANV-1"}
        _install_fake(monkeypatch, [
            _TENANT_ROW, [_RT_ROW], member_row, project_row,
        ])
        data = rd.build_consent_form_data(
            tenant_id=42, member_id=5, project_id=1
        )
        assert data["member"]["full_name"] == "Joao Silva"
        assert data["project"]["title"] == "PE-2026-001"
        assert data["technical_responsible"]["council"] == "CRM 12345/SP"
        assert data["consent"]["data_sharing_with_anvisa"] is True
        assert len(data["consent"]["rights"]) >= 3
        # renderiza sem erro com esse contexto
        doc = render_template("operational/consent_form", data, format="md")
        assert "Joao Silva" in doc.content

    def test_member_inexistente(self, monkeypatch):
        _install_fake(monkeypatch, [_TENANT_ROW, [_RT_ROW], None])
        with pytest.raises(ValueError, match="Associado"):
            rd.build_consent_form_data(tenant_id=42, member_id=999, project_id=1)


class TestBuildLabelWarningData:
    def test_monta_contexto_e_verification_url(self, monkeypatch):
        prep_row = {
            "id": 7, "preparation_code": "LOT-2026-001",
            "preparation_type": "oleo_cbd",
            "produced_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
            "unit_size_ml": 30, "qr_code": None,
        }
        _install_fake(monkeypatch, [_TENANT_ROW, [_RT_ROW], prep_row])
        data = rd.build_label_warning_data(
            tenant_id=42, preparation_id=7
        )
        assert "42" in data["verification_url"]
        assert "event_id=7" in data["verification_url"]
        # qr_code_data cai para verification_url quando preparation.qr_code e NULL
        assert data["qr_code_data"] == data["verification_url"]
        doc = render_template("operational/label_warning", data, format="md")
        assert "LOT-2026-001" in doc.content

    def test_preparation_inexistente(self, monkeypatch):
        _install_fake(monkeypatch, [_TENANT_ROW, [_RT_ROW], None])
        with pytest.raises(ValueError, match="Preparacao"):
            rd.build_label_warning_data(tenant_id=42, preparation_id=999)

    def test_qr_code_usa_valor_salvo_quando_presente(self, monkeypatch):
        prep_row = {
            "id": 7, "preparation_code": "LOT-X",
            "preparation_type": "oleo",
            "produced_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
            "unit_size_ml": 30, "qr_code": "qr:abcdef",
        }
        _install_fake(monkeypatch, [_TENANT_ROW, [_RT_ROW], prep_row])
        data = rd.build_label_warning_data(tenant_id=42, preparation_id=7)
        assert data["qr_code_data"] == "qr:abcdef"


class TestBuildSopTemplateData:
    def test_monta_contexto_com_parametros_livres(self, monkeypatch):
        _install_fake(monkeypatch, [_TENANT_ROW])
        data = rd.build_sop_template_data(
            tenant_id=42, code="POP-OP-001", title="Preparo de Oleo"
        )
        assert data["sop"]["code"] == "POP-OP-001"
        assert data["tenant"]["legal_name"] == "Assoc X"
        assert data["approver"]["name"] == "[pendencia]"
        # renderiza sem erro
        doc = render_template("operational/sop_template", data, format="md")
        assert "POP POP-OP-001" in doc.content

    def test_aprovador_customizado(self, monkeypatch):
        _install_fake(monkeypatch, [_TENANT_ROW])
        data = rd.build_sop_template_data(
            tenant_id=42, code="X", title="Y",
            approver={"name": "Dra Ana", "role": "RT"},
        )
        assert data["approver"]["name"] == "Dra Ana"


# =====================================================================
# 3. Smoke: o dossier continua renderizando apos o refactor
# =====================================================================

class TestDossierAindaRenderiza:
    def test_dossier_via_engine_produz_markdown(self):
        # Dados minimos do mesmo shape que render_dossier_markdown exige.
        # Reaproveita o caminho pendencias do test_governance_dossier.
        from src.services.governance_dossier import TEMPLATE_VERSION, render_dossier_markdown

        data = {
            "tenant": {"legal_name": "X", "trade_name": None, "cnpj": None,
                       "incorporation_date": None, "tenant_type": "association"},
            "association": None, "documents": [], "documents_by_type": {},
            "rts": [], "primary_rt": None, "presidente": None, "capacity": None,
            "eligibility": {"is_eligible": False, "has_warnings": True,
                            "checked_at": "2026-04-21T00:00:00+00:00"},
            "findings": [
                {"code": "legal_nature", "status": "pass", "message": "ok", "details": {}},
                {"code": "incorporation_time", "status": "fail",
                 "message": "sem data", "details": {}},
                {"code": "active_technical_responsible", "status": "fail",
                 "message": "sem RT", "details": {}},
                {"code": "technical_operational_capacity", "status": "fail",
                 "message": "sem capacity", "details": {}},
                {"code": "statute_document", "status": "warn",
                 "message": "sem estatuto", "details": {}},
            ],
            "findings_by_code": {},
            "fail_count": 3, "warn_count": 1,
            "template_version": TEMPLATE_VERSION,
            "generated_at": "2026-04-21T00:00:00+00:00",
        }
        md = render_dossier_markdown(42, data=data)
        assert "# Dossie de Elegibilidade" in md
        assert "Apto a submissao:** NAO" in md
