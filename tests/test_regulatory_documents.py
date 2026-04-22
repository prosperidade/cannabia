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


class TestRenderRegulatoryReport:
    @pytest.fixture
    def report_ctx(self) -> dict:
        return {
            "project": {
                "id": 1, "title": "PE-2026-001",
                "objective": None,
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 12, 31),
                "status": "concluded",
                "anvisa_reference": "ANV-X-001",
            },
            "tenant": {
                "id": 42, "legal_name": "Assoc X",
                "trade_name": "AX", "cnpj": "12345678000199",
                "incorporation_date": date(2023, 1, 1),
            },
            "technical_responsible": {
                "full_name": "Dra Ana", "professional_council": "CRM",
                "council_number": "12345", "council_state": "SP",
            },
            "linked_documents": [
                {"type": "eligibility_dossier", "title": "Dossie",
                 "version": "v1", "status": "approved",
                 "content_hash": "a" * 64,
                 "approved_at": datetime(2026, 2, 1, tzinfo=timezone.utc),
                 "approved_by_name": "admin"},
                {"type": "work_plan", "title": "Plano de Trabalho",
                 "version": "v1", "status": "approved",
                 "content_hash": "b" * 64,
                 "approved_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
                 "approved_by_name": "admin"},
            ],
            "indicators_summary": {
                "mandatory_count": 10, "complementary_count": 5,
                "periods_reported": 4,
            },
            "operational_summary": {
                "sops_count": 50, "sop_deviations": 2, "capa_actions": 2,
                "lab_analyses_count": 12, "dispensations_count": 120,
            },
            "pharmacovigilance": {
                "adverse_events_count": 3, "sanitary_risks_count": 8,
            },
            "anchors": {
                "total": 45,
                "networks": {"polygon": 40, "bitcoin_ots": 5},
                "verification_status_counts": {"confirmed": 42, "pending": 3},
            },
            "recommendations": ["Ampliar escala da segunda fase."],
            "limitations": ["Amostra regional limitada."],
            "next_steps": ["Submissao formal a ANVISA."],
            "attachments": ["Termo de Abertura"],
            "generated_at": "2026-04-21T00:00:00+00:00",
            "document_version": "v1",
        }

    def test_renderiza_com_documentos_vinculados(self, report_ctx):
        doc = render_template("final/regulatory_report", report_ctx, format="md")
        assert "# Relatorio Tecnico-Regulatorio Consolidado" in doc.content
        assert "ANV-X-001" in doc.content
        assert "Dossie" in doc.content
        assert "Plano de Trabalho" in doc.content
        # content_hash truncado no template
        assert "aaaaaaaaaaaa…aaaaaa" in doc.content
        assert "polygon: 40" in doc.content
        assert "Ampliar escala" in doc.content
        assert len(doc.content_hash) == 64

    def test_linked_documents_vazio_mostra_pendencia(self, report_ctx):
        ctx = copy.deepcopy(report_ctx)
        ctx["linked_documents"] = []
        doc = render_template("final/regulatory_report", ctx, format="md")
        assert "[pendencia: nenhum documento regulatorio aprovado" in doc.content

    def test_strict_undefined_pega_chave_ausente(self, report_ctx):
        ctx = copy.deepcopy(report_ctx)
        del ctx["anchors"]
        with pytest.raises(TemplateRenderError):
            render_template("final/regulatory_report", ctx, format="md")


class TestBuildRegulatoryReportData:
    def test_agrega_documents_e_anchors(self, monkeypatch):
        project_row = {
            "id": 7, "title": "PE-X", "status": "concluded",
            "submitted_at": None, "approved_at": None,
            "started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "concluded_at": datetime(2026, 12, 31, tzinfo=timezone.utc),
            "anvisa_reference": "ANV-7",
        }
        report_rows = [
            {"id": 1, "report_type": "eligibility_dossier", "version": "v1",
             "status": "approved", "content_hash": "a" * 64,
             "approved_at": datetime(2026, 2, 1, tzinfo=timezone.utc),
             "approved_by": 10, "approved_by_name": "admin"},
        ]
        anchor_rows = [
            {"n": 20, "blockchain_network": "polygon",
             "verification_status": "confirmed"},
            {"n": 2, "blockchain_network": "polygon",
             "verification_status": "pending"},
        ]
        responses = [
            _TENANT_ROW, [_RT_ROW], project_row,
            report_rows,
            {"n": 1}, {"n": 2},     # adverse + sanitary
            anchor_rows,
        ]
        _install_fake(monkeypatch, responses)

        data = rd.build_regulatory_report_data(7, 42)
        assert data["tenant"]["legal_name"] == "Assoc X"
        assert data["project"]["anvisa_reference"] == "ANV-7"
        assert len(data["linked_documents"]) == 1
        doc = data["linked_documents"][0]
        assert doc["type"] == "eligibility_dossier"
        assert doc["content_hash"] == "a" * 64
        assert doc["approved_by_name"] == "admin"
        assert data["anchors"]["total"] == 22
        assert data["anchors"]["networks"]["polygon"] == 22
        assert data["anchors"]["verification_status_counts"]["confirmed"] == 20

    def test_overrides_substituem_chaves(self, monkeypatch):
        project_row = {
            "id": 7, "title": "X", "status": "active",
            "submitted_at": None, "approved_at": None,
            "started_at": None, "concluded_at": None,
            "anvisa_reference": None,
        }
        _install_fake(monkeypatch, [
            _TENANT_ROW, [_RT_ROW], project_row,
            [], {"n": 0}, {"n": 0}, [],
        ])
        data = rd.build_regulatory_report_data(
            7, 42,
            overrides={
                "recommendations": ["manter"],
                "indicators_summary": {
                    "mandatory_count": 10, "complementary_count": 0,
                    "periods_reported": 1,
                },
            },
        )
        assert data["recommendations"] == ["manter"]
        assert data["indicators_summary"]["mandatory_count"] == 10

    def test_projeto_inexistente(self, monkeypatch):
        _install_fake(monkeypatch, [_TENANT_ROW, [_RT_ROW], None])
        with pytest.raises(ValueError, match="Projeto"):
            rd.build_regulatory_report_data(9999, 42)


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

# =====================================================================
# 3. F4.5 — cinco planos obrigatorios (doc 27 §4)
# =====================================================================

_ASSOCIATION_ROW = {
    "tenant_id": 42,
    "statute_document_id": 99,
    "directive_board": [
        {"name": "Carlos Presidente", "role": "Presidente"},
        {"name": "Maria Diretora", "role": "Diretora Tecnica"},
    ],
    "members_count": 120,
    "is_judicial_operation": False,
    "sandbox_application_status": "preparing",
}

_PROJECT_ROW = {
    "id": 7, "project_code": "PE-2026-001", "title": "PE-2026-001",
    "status": "active",
    "submitted_at": None, "approved_at": None,
    "started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    "concluded_at": None, "anvisa_reference": "ANV-X-001",
}


class TestRenderWorkPlan:
    @pytest.fixture
    def work_ctx(self) -> dict:
        return {
            "tenant": {
                "id": 42, "legal_name": "Associacao X",
                "trade_name": "AX", "cnpj": "12345678000199",
                "incorporation_date": date(2023, 1, 1),
            },
            "association": {
                "members_count": 120,
                "directive_board": [
                    {"name": "Carlos", "role": "Presidente"},
                ],
                "is_judicial_operation": False,
                "statute_document_id": 99,
            },
            "technical_responsible": {
                "full_name": "Dra Ana", "professional_council": "CRM",
                "council_number": "12345", "council_state": "SP",
            },
            "project": {
                "id": 7, "title": "PE-2026-001",
                "objective": "Reduzir desigualdade de acesso",
                "start_date": date(2026, 1, 1),
                "end_date": None, "status": "active",
            },
            "scope": {"activities": ["cultivo", "preparo", "dispensacao"]},
            "methodology": [
                {"phase": "Cultivo", "description": "Indoor controlado",
                 "records": "Batch record diario"},
            ],
            "quality_criteria": ["Perfil canabinoide validado por lab terceiro"],
            "infrastructure": {
                "summary": "Sala de cultivo 80m2 + laboratorio de preparo",
                "components": ["Estufa climatizada", "Bancada de extracao"],
            },
            "human_resources": [
                {"role": "Tecnico agricola", "count": 2,
                 "qualification": "Formacao tecnica"},
            ],
            "scale": {
                "members_benefited": 100, "production_volume": "2kg/trimestre",
                "dispensation_target": "500ml/mes",
            },
            "schedule": [
                {"phase": "Fase 1", "start": "2026-01-01",
                 "end": "2026-06-30", "deliverable": "Primeiro lote aprovado"},
            ],
            "interdependencies": ["Plano de Monitoramento §4.4"],
            "sops_summary": {"total": 12, "by_area": {"cultivo": 5, "preparo": 7}},
            "generated_at": "2026-04-22T00:00:00+00:00",
            "document_version": "v1",
        }

    def test_renderiza_secoes_principais(self, work_ctx):
        doc = render_template("project_plans/work_plan", work_ctx, format="md")
        assert "# Plano de Trabalho Geral e Criterios Tecnicos" in doc.content
        assert "Associacao X" in doc.content
        assert "Dra Ana" in doc.content
        assert "Reduzir desigualdade de acesso" in doc.content
        assert "| Cultivo | Indoor controlado" in doc.content
        assert "cultivo: 5" in doc.content
        assert "Plano de Monitoramento §4.4" in doc.content
        assert len(doc.content_hash) == 64

    def test_defaults_de_interdependencias(self, work_ctx):
        ctx = copy.deepcopy(work_ctx)
        ctx["interdependencies"] = []
        doc = render_template("project_plans/work_plan", ctx, format="md")
        # quando vazio, template lista os 4 outros planos como default
        assert "Plano de Comunicacao, Transparencia e Publicidade" in doc.content
        assert "Plano de Descontinuidade" in doc.content

    def test_strict_undefined_pega_tenant_ausente(self, work_ctx):
        ctx = copy.deepcopy(work_ctx)
        del ctx["tenant"]
        with pytest.raises(TemplateRenderError):
            render_template("project_plans/work_plan", ctx, format="md")


class TestRenderCommunicationPlan:
    @pytest.fixture
    def comms_ctx(self) -> dict:
        return {
            "tenant": {
                "id": 42, "legal_name": "Assoc X",
                "trade_name": "AX", "cnpj": "12345678000199",
            },
            "technical_responsible": {
                "full_name": "Dra Ana", "professional_council": "CRM",
                "council_number": "12345", "council_state": "SP",
            },
            "project": {"id": 7, "title": "PE-2026-001"},
            "principles": ["Veracidade"],
            "prohibitions": [],
            "official_channels": [
                {"name": "Site oficial", "url": "https://assoc.example",
                 "purpose": "Institucional"},
            ],
            "moderation_policy": {
                "summary": "RT aprova tudo antes de publicar.",
                "responsible_role": "Responsavel Tecnico",
                "review_sla_hours": 48,
                "escalation": "Diretoria para casos limitrofes.",
            },
            "member_comms": {
                "frequency": "Mensal",
                "channels": ["E-mail", "WhatsApp oficial"],
                "content_types": ["Avisos operacionais"],
            },
            "anvisa_comms": {
                "submission_types": ["Relatorio trimestral"],
                "cadence": "Trimestral",
                "responsible": "Dra Ana",
            },
            "public_comms": {
                "allowed_topics": ["Educacao sobre cannabis medicinal"],
                "forbidden_topics": ["Comparacao com medicamentos"],
            },
            "press_response": {
                "spokesperson": "Dra Ana",
                "approval_flow": "Solicitacao -> RT -> resposta.",
            },
            "review_cycle": {
                "frequency": "Anual",
                "responsible": "RT",
                "last_review": "2026-01-01",
                "next_review": "2027-01-01",
            },
            "generated_at": "2026-04-22T00:00:00+00:00",
            "document_version": "v1",
        }

    def test_renderiza_e_fixa_vedacoes_default(self, comms_ctx):
        ctx = copy.deepcopy(comms_ctx)
        ctx["prohibitions"] = []  # forca o fallback
        doc = render_template("project_plans/communication_plan", ctx, format="md")
        assert "# Plano de Comunicacao" in doc.content
        assert "nao sao medicamentos" in doc.content
        assert "Nao ha comercializacao" in doc.content
        assert "Nao ha publicidade" in doc.content

    def test_renderiza_com_prohibitions_customizadas(self, comms_ctx):
        ctx = copy.deepcopy(comms_ctx)
        ctx["prohibitions"] = ["regra customizada A", "regra customizada B"]
        doc = render_template("project_plans/communication_plan", ctx, format="md")
        assert "regra customizada A" in doc.content


class TestRenderDiscontinuityPlan:
    @pytest.fixture
    def disc_ctx(self) -> dict:
        return {
            "tenant": {"legal_name": "Assoc X", "cnpj": "12345678000199"},
            "technical_responsible": {
                "full_name": "Dra Ana", "professional_council": "CRM",
                "council_number": "12345", "council_state": "SP",
            },
            "project": {
                "id": 7, "title": "PE-2026-001", "objective": None,
                "start_date": None, "end_date": None, "status": "active",
            },
            "scenarios": [
                {"type": "Suspensao ANVISA",
                 "description": "Determinacao formal",
                 "activation_criteria": "Oficio ANVISA recebido"},
            ],
            "triggers": [
                {"scenario": "Suspensao", "condition": "Oficio",
                 "responsible": "Diretoria"},
            ],
            "cultivation_shutdown": {
                "steps": ["Colheita final", "Inativacao vegetal"],
                "timeframe_days": 30,
                "responsible": "RT",
            },
            "disposal": {
                "procedures": ["Incineracao controlada"],
                "oversight": "RT + auditor externo",
                "regulatory_reference": "POP-DE-001",
            },
            "transition": {
                "description": "Regime ordinario pos-sandbox",
                "target_regime": "RDC 327",
                "steps": ["Registro de produto"],
            },
            "member_communication": {
                "channels": ["E-mail", "Assembleia"],
                "notice_period_days": 30,
                "message_template": "Prezados, ...",
            },
            "care_continuity": {
                "description": "Encaminhamento para clinica parceira",
                "referral_partners": ["Clinica Y"],
            },
            "records_preservation": {
                "retention_years": 10,
                "storage_method": "Nuvem segregada + backup fisico",
                "access_policy": "RT + auditoria",
            },
            "responsibilities": [
                {"role": "RT", "duty": "Encerrar operacao tecnica"},
            ],
            "schedule": [
                {"phase": "Aviso", "duration_days": 30,
                 "description": "Comunicar associados"},
            ],
            "generated_at": "2026-04-22T00:00:00+00:00",
            "document_version": "v1",
        }

    def test_renderiza_com_cenarios_customizados(self, disc_ctx):
        doc = render_template("project_plans/discontinuity_plan", disc_ctx, format="md")
        assert "# Plano de Descontinuidade" in doc.content
        assert "Suspensao ANVISA" in doc.content
        assert "Incineracao controlada" in doc.content
        assert "Clinica Y" in doc.content

    def test_fallback_cenarios_padrao(self, disc_ctx):
        ctx = copy.deepcopy(disc_ctx)
        ctx["scenarios"] = []
        doc = render_template("project_plans/discontinuity_plan", ctx, format="md")
        assert "Descontinuidade natural" in doc.content
        assert "Descontinuidade por suspensao ANVISA" in doc.content


class TestRenderMonitoringPlan:
    @pytest.fixture
    def mon_ctx(self) -> dict:
        return {
            "tenant": {"legal_name": "Assoc X", "cnpj": "12345678000199"},
            "technical_responsible": {
                "full_name": "Dra Ana", "professional_council": "CRM",
                "council_number": "12345", "council_state": "SP",
            },
            "project": {
                "id": 7, "title": "PE-2026-001", "objective": None,
                "start_date": None, "end_date": None, "status": "active",
            },
            "mandatory_indicators": [
                {"code": "IND-01", "name": "Custo por paciente",
                 "unit": "BRL", "formula": "sum(expenses)/count(members)",
                 "frequency": "quarterly", "target": 500,
                 "data_source": "billing + association_members"},
            ],
            "complementary_indicators": [
                {"code": "IND-99", "name": "Satisfacao", "unit": "%",
                 "frequency": "annual"},
            ],
            "collection_infrastructure": {
                "systems": ["CannabIA plataforma"],
                "ingestion_cadence": "Real-time",
            },
            "validation_process": {
                "steps": ["Conferencia", "Recalculo"],
                "responsible": "Dra Ana",
                "frequency": "Mensal",
            },
            "delivery_format": {
                "to_anvisa": "PDF/A", "to_internal": "Dashboard",
                "reporting_template": "final/regulatory_report",
            },
            "deviation_criteria": [
                {"indicator": "IND-01", "threshold": ">600 BRL",
                 "response": "CAPA"},
            ],
            "governance": {
                "review_committee": ["RT", "Diretoria"],
                "review_cadence": "Trimestral",
            },
            "generated_at": "2026-04-22T00:00:00+00:00",
            "document_version": "v1",
        }

    def test_renderiza_indicadores(self, mon_ctx):
        doc = render_template("project_plans/monitoring_plan", mon_ctx, format="md")
        assert "# Plano de Monitoramento" in doc.content
        assert "IND-01" in doc.content
        assert "Custo por paciente" in doc.content
        assert "sum(expenses)/count(members)" in doc.content
        assert "Satisfacao" in doc.content

    def test_sem_indicadores_mostra_pendencia(self, mon_ctx):
        ctx = copy.deepcopy(mon_ctx)
        ctx["mandatory_indicators"] = []
        ctx["complementary_indicators"] = []
        doc = render_template("project_plans/monitoring_plan", ctx, format="md")
        assert "[pendencia: indicadores obrigatorios nao cadastrados" in doc.content


class TestRenderRiskManagementPlan:
    @pytest.fixture
    def risk_ctx(self) -> dict:
        return {
            "tenant": {"legal_name": "Assoc X", "cnpj": "12345678000199"},
            "technical_responsible": {
                "full_name": "Dra Ana", "professional_council": "CRM",
                "council_number": "12345", "council_state": "SP",
            },
            "project": {
                "id": 7, "title": "PE-2026-001", "objective": None,
                "start_date": None, "end_date": None, "status": "active",
            },
            "methodology": {
                "description": "Matriz 5x5 classificada em 4 niveis",
                "scales": {"probabilidade": "very_low..very_high"},
            },
            "risks": [
                {"id": 1, "code": "R-001", "category": "cultivo",
                 "description": "Contaminacao de lote",
                 "probability": "medium", "impact": "high",
                 "risk_level": "high", "is_active": True},
            ],
            "controls": [
                {"risk_code": "R-001",
                 "description": "Amostragem de agua semanal",
                 "control_type": "preventive",
                 "responsible": "tecnico1",
                 "related_sop": "POP-CT-001",
                 "verification_status": "effective"},
            ],
            "responsibles": [
                {"risk_code": "R-001", "responsible": "Dra Ana"},
            ],
            "verification": {
                "method": "Auditoria interna trimestral",
                "frequency": "Trimestral",
                "last_review": "2026-03-01",
            },
            "review_cycle": {"frequency": "Trimestral", "responsible": "Dra Ana"},
            "pharmacovigilance": {
                "adverse_events_count": 3, "sanitary_risks_count": 5,
                "reporting_policy": None,
            },
            "capa_integration": {
                "open_capa_count": 2, "resolved_capa_count": 10,
                "policy": None,
            },
            "governance": {
                "committee": ["RT", "Diretoria", "Consultoria juridica"],
                "cadence": "Trimestral",
            },
            "generated_at": "2026-04-22T00:00:00+00:00",
            "document_version": "v1",
        }

    def test_renderiza_matriz_de_riscos(self, risk_ctx):
        doc = render_template(
            "project_plans/risk_management_plan", risk_ctx, format="md"
        )
        assert "# Plano de Gerenciamento e Mitigacao de Riscos" in doc.content
        assert "R-001" in doc.content
        assert "Contaminacao de lote" in doc.content
        assert "POP-CT-001" in doc.content
        assert "Eventos adversos notificados: **3**" in doc.content
        assert "CAPAs em andamento: **2**" in doc.content

    def test_sem_riscos_mostra_pendencia(self, risk_ctx):
        ctx = copy.deepcopy(risk_ctx)
        ctx["risks"] = []
        ctx["controls"] = []
        ctx["responsibles"] = []
        ctx["pharmacovigilance"]["sanitary_risks_count"] = 0
        doc = render_template(
            "project_plans/risk_management_plan", ctx, format="md"
        )
        assert "[pendencia: matriz de riscos ativa nao cadastrada" in doc.content


# =====================================================================
# 4. F4.5 — providers
# =====================================================================

class TestBuildWorkPlanData:
    def test_agrega_sops_e_associacao(self, monkeypatch):
        sop_rows = [
            {"area": "cultivo", "n": 5},
            {"area": "preparo", "n": 7},
        ]
        responses = [
            _TENANT_ROW, [_RT_ROW], _PROJECT_ROW, _ASSOCIATION_ROW, sop_rows,
        ]
        _install_fake(monkeypatch, responses)

        data = rd.build_work_plan_data(7, 42)
        assert data["tenant"]["legal_name"] == "Assoc X"
        assert data["project"]["title"] == "PE-2026-001"
        assert data["association"]["members_count"] == 120
        assert data["sops_summary"]["total"] == 12
        assert data["sops_summary"]["by_area"]["cultivo"] == 5
        # renderiza sem erro com esse contexto
        doc = render_template("project_plans/work_plan", data, format="md")
        assert "Assoc X" in doc.content

    def test_overrides_substituem_methodology(self, monkeypatch):
        _install_fake(monkeypatch, [
            _TENANT_ROW, [_RT_ROW], _PROJECT_ROW, _ASSOCIATION_ROW, [],
        ])
        data = rd.build_work_plan_data(
            7, 42,
            overrides={
                "methodology": [{"phase": "X", "description": "Y", "records": "Z"}],
            },
        )
        assert data["methodology"] == [
            {"phase": "X", "description": "Y", "records": "Z"}
        ]

    def test_projeto_inexistente(self, monkeypatch):
        _install_fake(monkeypatch, [_TENANT_ROW, [_RT_ROW], None])
        with pytest.raises(ValueError, match="Projeto"):
            rd.build_work_plan_data(9999, 42)


class TestBuildCommunicationPlanData:
    def test_monta_contexto_basico(self, monkeypatch):
        _install_fake(monkeypatch, [
            _TENANT_ROW, [_RT_ROW], _PROJECT_ROW,
        ])
        data = rd.build_communication_plan_data(7, 42)
        assert data["tenant"]["legal_name"] == "Assoc X"
        assert data["anvisa_comms"]["responsible"] == "Dra Ana"
        # renderiza sem erro
        doc = render_template(
            "project_plans/communication_plan", data, format="md"
        )
        assert "Plano de Comunicacao" in doc.content
        # como prohibitions e [], template usa fallback com vedacoes default
        assert "nao sao medicamentos" in doc.content


class TestBuildDiscontinuityPlanData:
    def test_le_protocolo_vigente(self, monkeypatch):
        protocol_row = {
            "protocol_version": "1.0",
            "discontinuity_plan": {
                "scenarios": [
                    {"type": "Natural", "description": "fim do ciclo",
                     "activation_criteria": "conclusao"},
                ],
                "cultivation_shutdown": {
                    "steps": ["Passo 1"], "timeframe_days": 30,
                    "responsible": "RT",
                },
            },
            "effective_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        _install_fake(monkeypatch, [
            _TENANT_ROW, [_RT_ROW], _PROJECT_ROW, protocol_row,
        ])
        data = rd.build_discontinuity_plan_data(7, 42)
        assert len(data["scenarios"]) == 1
        assert data["scenarios"][0]["type"] == "Natural"
        assert data["cultivation_shutdown"]["timeframe_days"] == 30
        # renderiza
        doc = render_template(
            "project_plans/discontinuity_plan", data, format="md"
        )
        assert "Natural" in doc.content

    def test_sem_protocolo_usa_defaults(self, monkeypatch):
        _install_fake(monkeypatch, [
            _TENANT_ROW, [_RT_ROW], _PROJECT_ROW, None,
        ])
        data = rd.build_discontinuity_plan_data(7, 42)
        assert data["scenarios"] == []
        assert data["cultivation_shutdown"]["steps"] == []
        doc = render_template(
            "project_plans/discontinuity_plan", data, format="md"
        )
        # template usa fallback com 3 cenarios default
        assert "Descontinuidade natural" in doc.content


class TestBuildMonitoringPlanData:
    def test_separa_mandatory_de_complementary(self, monkeypatch):
        indicator_rows = [
            {"indicator_code": "IND-01", "indicator_name": "Custo",
             "calculation_formula": "sum/count", "unit": "BRL",
             "target_value": 500, "reporting_frequency": "quarterly",
             "is_mandatory": True},
            {"indicator_code": "IND-99", "indicator_name": "Satisfacao",
             "calculation_formula": "media", "unit": "%",
             "target_value": None, "reporting_frequency": "annual",
             "is_mandatory": False},
        ]
        _install_fake(monkeypatch, [
            _TENANT_ROW, [_RT_ROW], _PROJECT_ROW, indicator_rows,
        ])
        data = rd.build_monitoring_plan_data(7, 42)
        assert len(data["mandatory_indicators"]) == 1
        assert data["mandatory_indicators"][0]["code"] == "IND-01"
        assert len(data["complementary_indicators"]) == 1
        assert data["complementary_indicators"][0]["code"] == "IND-99"
        doc = render_template(
            "project_plans/monitoring_plan", data, format="md"
        )
        assert "IND-01" in doc.content
        assert "IND-99" in doc.content


class TestBuildRiskManagementPlanData:
    def test_agrega_matriz_controles_farma_capa(self, monkeypatch):
        risk_rows = [
            {"id": 1, "risk_code": "R-001", "category": "cultivo",
             "description": "Contaminacao", "probability": "medium",
             "impact": "high", "risk_level": "high", "is_active": True},
        ]
        control_rows = [
            {"risk_id": 1,
             "control_description": "Amostragem semanal",
             "control_type": "preventive",
             "verification_status": "effective",
             "related_sop_id": 42,
             "responsible_name": "tecnico1",
             "related_sop_code": "POP-CT-001"},
        ]
        responses = [
            _TENANT_ROW, [_RT_ROW], _PROJECT_ROW,
            risk_rows,
            control_rows,
            {"n": 3},
            {"open_n": 2, "resolved_n": 10},
        ]
        _install_fake(monkeypatch, responses)

        data = rd.build_risk_management_plan_data(7, 42)
        assert len(data["risks"]) == 1
        assert data["risks"][0]["code"] == "R-001"
        assert len(data["controls"]) == 1
        assert data["controls"][0]["related_sop"] == "POP-CT-001"
        assert data["pharmacovigilance"]["adverse_events_count"] == 3
        assert data["capa_integration"]["open_capa_count"] == 2
        assert data["capa_integration"]["resolved_capa_count"] == 10
        doc = render_template(
            "project_plans/risk_management_plan", data, format="md"
        )
        assert "R-001" in doc.content
        assert "POP-CT-001" in doc.content

    def test_sem_riscos_pula_query_de_controles(self, monkeypatch):
        responses = [
            _TENANT_ROW, [_RT_ROW], _PROJECT_ROW,
            [],
            {"n": 0},
            {"open_n": 0, "resolved_n": 0},
        ]
        _install_fake(monkeypatch, responses)

        data = rd.build_risk_management_plan_data(7, 42)
        assert data["risks"] == []
        assert data["controls"] == []
        assert data["responsibles"] == []
        assert data["pharmacovigilance"]["sanitary_risks_count"] == 0
        # renderiza com fallback [pendencia]
        doc = render_template(
            "project_plans/risk_management_plan", data, format="md"
        )
        assert "[pendencia: matriz de riscos ativa" in doc.content


# =====================================================================
# 5. Smoke: o dossier continua renderizando apos o refactor
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
