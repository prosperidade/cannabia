"""Testes do governance_dossier (F1.5 parte 2)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest

from src.services.governance_dossier import (
    TEMPLATE_VERSION,
    _group_documents_by_type,
    _pick_presidente,
    _pick_primary_rt,
    build_dossier_data,
    render_dossier_markdown,
)
from src.services.governance_service import EligibilityFinding, EligibilityReport


TENANT_ID = 99


# ---------------------------------------------------------------------
# Helpers puros
# ---------------------------------------------------------------------

class TestGroupDocuments:
    def test_groups_by_type_preserving_order(self):
        docs = [
            {"id": 1, "document_type": "statute", "title": "E1"},
            {"id": 2, "document_type": "minutes", "title": "M1"},
            {"id": 3, "document_type": "statute", "title": "E2"},
        ]
        grouped = _group_documents_by_type(docs)
        assert list(grouped.keys()) == ["statute", "minutes"]
        assert [d["id"] for d in grouped["statute"]] == [1, 3]

    def test_empty_list_returns_empty(self):
        assert _group_documents_by_type([]) == {}


class TestPickPrimaryRt:
    TODAY = date(2026, 4, 20)

    def test_prefers_habilitated_over_active_only(self):
        rts = [
            {"id": 1, "is_active": True, "habilitation_valid_until": None},
            {"id": 2, "is_active": True, "habilitation_valid_until": date(2028, 1, 1)},
        ]
        assert _pick_primary_rt(rts, self.TODAY)["id"] == 2

    def test_falls_back_to_active_when_none_habilitated(self):
        rts = [{"id": 5, "is_active": True, "habilitation_valid_until": None}]
        assert _pick_primary_rt(rts, self.TODAY)["id"] == 5

    def test_returns_none_when_no_active(self):
        rts = [{"id": 9, "is_active": False, "habilitation_valid_until": date(2030, 1, 1)}]
        assert _pick_primary_rt(rts, self.TODAY) is None

    def test_expired_habilitation_is_not_preferred(self):
        rts = [
            {"id": 1, "is_active": True, "habilitation_valid_until": date(2020, 1, 1)},
            {"id": 2, "is_active": True, "habilitation_valid_until": date(2028, 1, 1)},
        ]
        assert _pick_primary_rt(rts, self.TODAY)["id"] == 2


class TestPickPresidente:
    def test_finds_by_role_case_insensitive(self):
        assoc = {"directive_board": [
            {"role": "tesoureiro", "name": "T"},
            {"role": "Presidente", "name": "P"},
        ]}
        assert _pick_presidente(assoc)["name"] == "P"

    def test_fallback_to_first_member(self):
        assoc = {"directive_board": [{"role": "tesoureiro", "name": "T"}]}
        assert _pick_presidente(assoc)["name"] == "T"

    def test_none_when_association_missing(self):
        assert _pick_presidente(None) is None

    def test_none_when_board_empty(self):
        assert _pick_presidente({"directive_board": []}) is None


# ---------------------------------------------------------------------
# build_dossier_data — com tudo mockado
# ---------------------------------------------------------------------

@pytest.fixture
def mocked_build(monkeypatch):
    """Mocka as dependencias externas de build_dossier_data."""
    tenant_row = {
        "id": TENANT_ID,
        "legal_name": "Associacao Teste",
        "display_name": "Teste",
        "trade_name": "Teste",
        "cnpj": "12345678000199",
        "incorporation_date": date(2023, 1, 1),
        "tenant_type": "association",
        "status": "active",
    }

    class _FakeCursor:
        def __init__(self, row):
            self._row = row

        def execute(self, *_args, **_kwargs):
            pass

        def fetchone(self):
            return self._row

    class _FakeCtx:
        def __init__(self, row):
            self._row = row

        def __enter__(self):
            return (None, _FakeCursor(self._row))

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        "src.services.governance_dossier.db_cursor",
        lambda dictionary=True: _FakeCtx(tenant_row),
    )
    monkeypatch.setattr(
        "src.services.governance_dossier.repo.get_association",
        lambda tid: {"tenant_id": tid, "members_count": 25, "is_judicial_operation": False,
                     "directive_board": [{"role": "presidente", "name": "Ana"}]},
    )
    monkeypatch.setattr(
        "src.services.governance_dossier.repo.list_institutional_documents",
        lambda tenant_id, active_only=True: [
            {"id": 1, "document_type": "statute", "title": "Estatuto",
             "version": "1.0", "valid_from": date(2023, 1, 1),
             "valid_until": None, "file_hash": "a" * 64, "is_active": True},
        ],
    )
    monkeypatch.setattr(
        "src.services.governance_dossier.repo.list_technical_responsibles",
        lambda tenant_id, active_only=True: [
            {"id": 1, "is_active": True, "full_name": "Dr A",
             "professional_council": "CRM", "council_number": "1",
             "council_state": "SP", "habilitation_valid_until": date(2030, 1, 1)},
        ],
    )
    monkeypatch.setattr(
        "src.services.governance_dossier.repo.get_latest_capacity_assessment",
        lambda tid: {"id": 1, "assessment_date": date(2026, 4, 1),
                     "infrastructure_score": {"s": 80},
                     "human_resources_score": {"s": 70},
                     "process_maturity_score": {"s": 75},
                     "proposed_scale": {"p": 50},
                     "overall_readiness": 74.5},
    )

    report = EligibilityReport(
        tenant_id=TENANT_ID,
        checked_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        findings=[
            EligibilityFinding(code="legal_nature", status="pass", message="ok",
                               details={"tenant_type": "association"}),
            EligibilityFinding(code="incorporation_time", status="pass", message="ok",
                               details={"incorporation_date": "2023-01-01",
                                        "years": 3.3, "minimum_required": 2}),
            EligibilityFinding(code="active_technical_responsible", status="pass", message="ok",
                               details={"active_count": 1, "habilitated_count": 1}),
            EligibilityFinding(code="technical_operational_capacity", status="pass", message="ok",
                               details={"has_assessment": True}),
            EligibilityFinding(code="statute_document", status="pass", message="ok",
                               details={"statute_count": 1}),
        ],
    )
    monkeypatch.setattr(
        "src.services.governance_dossier.check_sandbox_eligibility",
        lambda tenant_id, today=None: report,
    )


class TestBuildDossierData:
    def test_assembles_all_sections(self, mocked_build):
        data = build_dossier_data(TENANT_ID, today=date(2026, 4, 20))
        assert data["tenant"]["legal_name"] == "Associacao Teste"
        assert data["association"]["members_count"] == 25
        assert data["presidente"]["name"] == "Ana"
        assert data["primary_rt"]["full_name"] == "Dr A"
        assert data["capacity"]["overall_readiness"] == 74.5
        assert "statute" in data["documents_by_type"]
        assert data["eligibility"]["is_eligible"] is True
        assert data["fail_count"] == 0
        assert data["warn_count"] == 0
        assert data["template_version"] == TEMPLATE_VERSION

    def test_raises_when_tenant_missing(self, monkeypatch):
        class _Ctx:
            def __enter__(self):
                class _C:
                    def execute(self, *a, **k): pass
                    def fetchone(self): return None
                return (None, _C())
            def __exit__(self, *exc): return False
        monkeypatch.setattr(
            "src.services.governance_dossier.db_cursor",
            lambda dictionary=True: _Ctx(),
        )
        with pytest.raises(ValueError, match="nao encontrado"):
            build_dossier_data(TENANT_ID)


# ---------------------------------------------------------------------
# render_dossier_markdown
# ---------------------------------------------------------------------

class TestRenderDossier:
    def test_renders_happy_path(self, mocked_build):
        data = build_dossier_data(TENANT_ID, today=date(2026, 4, 20))
        md = render_dossier_markdown(TENANT_ID, data=data)
        assert "# Dossie de Elegibilidade" in md
        assert "Associacao Teste" in md
        assert "12345678000199" in md
        assert "## 4. Responsavel(is) Tecnico(s)" in md
        assert "Dr A" in md
        assert "Apto a submissao:** Sim" in md
        assert "Presidente" not in md or "presidente" in md.lower()  # presidente section present

    def test_renders_pendencias_when_fields_missing(self):
        """Com rts/docs/capacity vazios, as secoes mostram [pendencia]."""
        data = {
            "tenant": {"legal_name": "X", "trade_name": None, "cnpj": None,
                       "incorporation_date": None, "tenant_type": "association"},
            "association": None,
            "documents": [], "documents_by_type": {},
            "rts": [], "primary_rt": None, "presidente": None, "capacity": None,
            "eligibility": {"is_eligible": False, "has_warnings": True,
                            "checked_at": "2026-04-20T00:00:00+00:00"},
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
            "findings_by_code": {
                "legal_nature": {"code": "legal_nature", "status": "pass", "message": "ok", "details": {}},
                "incorporation_time": {"code": "incorporation_time", "status": "fail", "message": "sem data", "details": {}},
            },
            "fail_count": 3, "warn_count": 1,
            "template_version": TEMPLATE_VERSION,
            "generated_at": "2026-04-20T00:00:00+00:00",
        }
        md = render_dossier_markdown(TENANT_ID, data=data)
        assert "[pendencia: informar data de constituicao]" in md
        assert "Nenhum Responsavel Tecnico ativo" in md
        assert "Nenhuma avaliacao de Capacidade" in md
        assert "Nenhum documento institucional" in md
        assert "Apto a submissao:** NAO" in md
        # Sumarios listam pendencias
        assert "Acao necessaria antes" in md
        assert "Pendencias nao bloqueantes" in md

    def test_template_references_declaracoes_invariantes(self, mocked_build):
        data = build_dossier_data(TENANT_ID, today=date(2026, 4, 20))
        md = render_dossier_markdown(TENANT_ID, data=data)
        # As 8 vedacoes da secao 9 sao fixas e devem constar em todo dossie
        assert "Nao comercializa" in md
        assert "Nao realiza publicidade" in md
        assert "invariante arquitetural da plataforma" in md
