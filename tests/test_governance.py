"""Integration tests do dominio governance (F1.8 do docs/BACKLOG_SCC.md).

Exercita o fluxo completo contra o Postgres real:

  upsert_association → create_RT → create_statute →
  create_capacity → check_sandbox_eligibility → refresh →
  build_dossier_data → render_dossier_markdown

Ao contrario dos testes unitarios (com mocks) em
test_governance_routes.py e test_governance_dossier.py, aqui a camada
de dados e exercitada de verdade — erros de schema/service/repo que
escapam aos mocks aparecem aqui.

Cada teste usa um tenant dedicado criado no setUp e drop de dados
governance no tearDown, para evitar interferencia com outros testes e
com o DB de desenvolvimento.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Iterator

import pytest

from src.infra.database import db_cursor
from src.repositories import governance_repository as repo
from src.services.governance_dossier import (
    build_dossier_data,
    render_dossier_markdown,
)
from src.services.governance_service import (
    ELIGIBLE_TENANT_TYPE,
    check_sandbox_eligibility,
    list_all_associations_summary,
    refresh_eligibility,
)


def _db_reachable() -> bool:
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        return False


# Skip do arquivo inteiro quando o Postgres de integracao nao esta acessivel
# (ex.: CI sem docker-compose do banco rodando).
pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="Postgres de integracao indisponivel — suba o docker cannabia-postgis",
)


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def tenant_association() -> Iterator[int]:
    """Cria um tenant 'association' valido (incorporation >=2 anos) e
    limpa governance records ao final (mantem o tenant para FKs que
    podem existir em outras tabelas criadas durante o teste)."""
    slug = f"test-gov-{uuid.uuid4().hex[:8]}"
    legal_name = f"Associacao Teste {slug}"

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            SELECT id FROM tenant_types WHERE slug = 'association' LIMIT 1
            """,
        )
        tt = cursor.fetchone()
        if tt is None:
            cursor.execute(
                "INSERT INTO tenant_types (slug, display_name) VALUES ('association', 'Associacao') RETURNING id",
            )
            tt = cursor.fetchone()
        tenant_type_id = tt["id"]

        cursor.execute(
            """
            INSERT INTO tenants (
                legal_name, display_name, slug, status,
                tenant_type_id, tenant_type, trade_name,
                incorporation_date, plan_tier
            )
            VALUES (%s, %s, %s, 'active', %s, 'association', %s, %s, 'basic')
            RETURNING id
            """,
            (
                legal_name, legal_name, slug, tenant_type_id,
                legal_name, date.today() - timedelta(days=365 * 3),
            ),
        )
        tenant_id = cursor.fetchone()["id"]
        conn.commit()

    try:
        yield tenant_id
    finally:
        with db_cursor() as (conn, cursor):
            # Ordem de deletes respeita FKs (filhas antes das pais)
            cursor.execute("DELETE FROM technical_operational_capacity WHERE tenant_id=%s", (tenant_id,))
            cursor.execute("DELETE FROM associations WHERE tenant_id=%s", (tenant_id,))
            cursor.execute("DELETE FROM technical_responsibles WHERE tenant_id=%s", (tenant_id,))
            cursor.execute("DELETE FROM institutional_documents WHERE tenant_id=%s", (tenant_id,))
            cursor.execute("DELETE FROM tenants WHERE id=%s", (tenant_id,))
            conn.commit()


@pytest.fixture
def tenant_clinic() -> Iterator[int]:
    """Variante de tenant do tipo 'clinic' — util para testar falhas de
    legal_nature."""
    slug = f"test-clinic-{uuid.uuid4().hex[:8]}"
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            "SELECT id FROM tenant_types WHERE slug = 'clinic' LIMIT 1"
        )
        tt = cursor.fetchone()
        if tt is None:
            cursor.execute(
                "INSERT INTO tenant_types (slug, display_name) VALUES ('clinic', 'Clinica') RETURNING id",
            )
            tt = cursor.fetchone()
        cursor.execute(
            """
            INSERT INTO tenants (
                legal_name, display_name, slug, status,
                tenant_type_id, tenant_type, plan_tier
            )
            VALUES (%s, %s, %s, 'active', %s, 'clinic', 'basic')
            RETURNING id
            """,
            (slug, slug, slug, tt["id"]),
        )
        tid = cursor.fetchone()["id"]
        conn.commit()

    try:
        yield tid
    finally:
        with db_cursor() as (conn, cursor):
            cursor.execute("DELETE FROM tenants WHERE id=%s", (tid,))
            conn.commit()


def _seed_full_eligibility(tenant_id: int) -> dict:
    """Popula todos os 5 criterios (4 hard + estatuto). Retorna ids para
    deteccao em asserts."""
    doc = repo.create_institutional_document(
        tenant_id=tenant_id, document_type="statute",
        title="Estatuto", version="1.0",
        file_uri=f"s3://test/{tenant_id}/est.pdf",
        file_hash="a" * 64,
        valid_from=date.today() - timedelta(days=365),
    )
    rt = repo.create_technical_responsible(
        tenant_id=tenant_id,
        full_name="Dra Teste Integration",
        professional_council="CRM",
        # numero unico para nao colidir com UNIQUE (conselho,numero,uf)
        council_number=f"{tenant_id:06d}",
        council_state="RJ",
        habilitation_valid_until=date.today() + timedelta(days=365 * 3),
    )
    cap = repo.create_capacity_assessment(
        tenant_id=tenant_id,
        assessment_date=date.today(),
        infrastructure_score={"score": 80},
        human_resources_score={"score": 75},
        process_maturity_score={"score": 70},
        proposed_scale={"phase1": 100},
        overall_readiness=75.0,
    )
    repo.upsert_association(tenant_id=tenant_id, members_count=50)
    return {"doc_id": doc["id"], "rt_id": rt["id"], "cap_id": cap["id"]}


# ---------------------------------------------------------------------
# Fluxo completo — cadastro → elegibilidade → dossie
# ---------------------------------------------------------------------

class TestFullEligibilityFlow:
    def test_blank_association_fails_three_hard_criteria(self, tenant_association):
        """Tenant nu (association, inc >=2 anos) passa legal_nature +
        incorporation_time mas falha os 2 criterios que dependem de
        cadastro (RT, capacity). Estatuto vira warn."""
        report = check_sandbox_eligibility(tenant_association)
        codes = {f.code: f.status for f in report.findings}
        assert codes["legal_nature"] == "pass"
        assert codes["incorporation_time"] == "pass"
        assert codes["active_technical_responsible"] == "fail"
        assert codes["technical_operational_capacity"] == "fail"
        assert codes["statute_document"] == "warn"
        assert report.is_eligible is False

    def test_full_seed_achieves_eligibility(self, tenant_association):
        _seed_full_eligibility(tenant_association)
        report = check_sandbox_eligibility(tenant_association)
        assert report.is_eligible is True
        assert report.has_warnings is False
        assert all(f.status == "pass" for f in report.findings)

    def test_refresh_marks_validated_and_transitions_status(self, tenant_association):
        _seed_full_eligibility(tenant_association)

        # Estado inicial: sem validated, sem status.
        before = repo.get_association(tenant_association)
        assert before["eligibility_validated_at"] is None
        assert before["sandbox_application_status"] is None

        report = refresh_eligibility(tenant_association)
        assert report.is_eligible is True

        after = repo.get_association(tenant_association)
        assert after["eligibility_validated_at"] is not None
        assert after["sandbox_application_status"] == "preparing"

    def test_refresh_preserves_advanced_status(self, tenant_association):
        _seed_full_eligibility(tenant_association)
        repo.set_sandbox_application_status(tenant_association, "submitted")

        refresh_eligibility(tenant_association)

        assoc = repo.get_association(tenant_association)
        assert assoc["sandbox_application_status"] == "submitted"

    def test_refresh_noop_when_not_eligible(self, tenant_association):
        repo.upsert_association(tenant_id=tenant_association, members_count=10)
        report = refresh_eligibility(tenant_association)
        assert report.is_eligible is False
        assoc = repo.get_association(tenant_association)
        assert assoc["eligibility_validated_at"] is None


# ---------------------------------------------------------------------
# Legal nature
# ---------------------------------------------------------------------

class TestLegalNature:
    def test_clinic_fails_legal_nature(self, tenant_clinic):
        report = check_sandbox_eligibility(tenant_clinic)
        ln = next(f for f in report.findings if f.code == "legal_nature")
        assert ln.status == "fail"
        assert ln.details["tenant_type"] != ELIGIBLE_TENANT_TYPE


# ---------------------------------------------------------------------
# Incorporation time
# ---------------------------------------------------------------------

class TestIncorporationTime:
    def test_recent_association_fails(self, tenant_association):
        # tenant criado com 3 anos — sobrescreve para 1 ano
        with db_cursor() as (conn, cursor):
            cursor.execute(
                "UPDATE tenants SET incorporation_date = %s WHERE id = %s",
                (date.today() - timedelta(days=365), tenant_association),
            )
            conn.commit()

        report = check_sandbox_eligibility(tenant_association)
        inc = next(f for f in report.findings if f.code == "incorporation_time")
        assert inc.status == "fail"
        assert inc.details["years"] < 2

    def test_null_incorporation_fails(self, tenant_association):
        with db_cursor() as (conn, cursor):
            cursor.execute(
                "UPDATE tenants SET incorporation_date = NULL WHERE id = %s",
                (tenant_association,),
            )
            conn.commit()

        report = check_sandbox_eligibility(tenant_association)
        inc = next(f for f in report.findings if f.code == "incorporation_time")
        assert inc.status == "fail"
        assert inc.details["incorporation_date"] is None


# ---------------------------------------------------------------------
# Technical Responsibles
# ---------------------------------------------------------------------

class TestTechnicalResponsibles:
    def test_expired_habilitation_fails_rt_check(self, tenant_association):
        repo.create_technical_responsible(
            tenant_id=tenant_association,
            full_name="Dr Expirado",
            professional_council="CRM",
            council_number=f"exp-{tenant_association}",
            council_state="MG",
            habilitation_valid_until=date.today() - timedelta(days=30),
        )
        report = check_sandbox_eligibility(tenant_association)
        rt = next(f for f in report.findings if f.code == "active_technical_responsible")
        assert rt.status == "fail"
        assert rt.details["active_count"] == 1
        assert rt.details["habilitated_count"] == 0

    def test_null_habilitation_fails_rt_check(self, tenant_association):
        repo.create_technical_responsible(
            tenant_id=tenant_association,
            full_name="Dr Sem Validade",
            professional_council="CRF",
            council_number=f"nv-{tenant_association}",
            council_state="SP",
            habilitation_valid_until=None,
        )
        report = check_sandbox_eligibility(tenant_association)
        rt = next(f for f in report.findings if f.code == "active_technical_responsible")
        # RT ativo existe, mas sem validade conhecida nao conta como habilitado.
        assert rt.status == "fail"

    def test_deactivated_rt_does_not_count(self, tenant_association):
        rt = repo.create_technical_responsible(
            tenant_id=tenant_association,
            full_name="Dr Futuro Desativado",
            professional_council="CRM",
            council_number=f"dez-{tenant_association}",
            council_state="SP",
            habilitation_valid_until=date.today() + timedelta(days=365),
        )
        repo.deactivate_technical_responsible(rt["id"])

        report = check_sandbox_eligibility(tenant_association)
        rt_finding = next(f for f in report.findings if f.code == "active_technical_responsible")
        assert rt_finding.status == "fail"
        assert rt_finding.details["active_count"] == 0

    def test_unique_constraint_council_surfaces_integrity_error(self, tenant_association):
        common_kwargs = dict(
            professional_council="CRM",
            council_number=f"dup-{tenant_association}",
            council_state="SP",
            habilitation_valid_until=date.today() + timedelta(days=365),
        )
        repo.create_technical_responsible(
            tenant_id=tenant_association,
            full_name="Primeiro",
            **common_kwargs,
        )
        # Tentar outro com mesmo conselho/numero/uf → IntegrityError.
        import psycopg2

        with pytest.raises(psycopg2.IntegrityError):
            repo.create_technical_responsible(
                tenant_id=tenant_association,
                full_name="Duplicado",
                **common_kwargs,
            )


# ---------------------------------------------------------------------
# Documents (estatuto)
# ---------------------------------------------------------------------

class TestDocuments:
    def test_active_statute_turns_warn_into_pass(self, tenant_association):
        before = check_sandbox_eligibility(tenant_association)
        st_before = next(f for f in before.findings if f.code == "statute_document")
        assert st_before.status == "warn"

        repo.create_institutional_document(
            tenant_id=tenant_association, document_type="statute",
            title="Estatuto", version="1.0",
            file_uri="s3://test.pdf", file_hash="b" * 64,
            valid_from=date.today() - timedelta(days=100),
        )

        after = check_sandbox_eligibility(tenant_association)
        st_after = next(f for f in after.findings if f.code == "statute_document")
        assert st_after.status == "pass"

    def test_deactivated_statute_reverts_to_warn(self, tenant_association):
        doc = repo.create_institutional_document(
            tenant_id=tenant_association, document_type="statute",
            title="Estatuto", version="1.0",
            file_uri="s3://test.pdf", file_hash="c" * 64,
            valid_from=date.today() - timedelta(days=100),
        )
        repo.deactivate_institutional_document(doc["id"])

        report = check_sandbox_eligibility(tenant_association)
        st = next(f for f in report.findings if f.code == "statute_document")
        assert st.status == "warn"

    def test_non_statute_documents_do_not_satisfy_statute_check(self, tenant_association):
        # Um documento ativo mas de outro tipo nao satisfaz o check.
        repo.create_institutional_document(
            tenant_id=tenant_association, document_type="minutes",
            title="Ata de Assembleia", version="1.0",
            file_uri="s3://ata.pdf", file_hash="d" * 64,
            valid_from=date.today() - timedelta(days=50),
        )
        report = check_sandbox_eligibility(tenant_association)
        st = next(f for f in report.findings if f.code == "statute_document")
        assert st.status == "warn"


# ---------------------------------------------------------------------
# Dossier end-to-end
# ---------------------------------------------------------------------

class TestDossierIntegration:
    def test_dossier_reflects_partial_state(self, tenant_association):
        """Sem RT/capacity/estatuto, o dossie deve mostrar pendencias
        textuais em cada secao correspondente."""
        data = build_dossier_data(tenant_association)
        md = render_dossier_markdown(tenant_association, data=data)

        assert "Nenhum Responsavel Tecnico ativo" in md
        assert "Nenhuma avaliacao de Capacidade" in md
        assert "Nenhum documento institucional" in md
        assert "Apto a submissao:** NAO" in md

    def test_dossier_fully_seeded_shows_apto(self, tenant_association):
        _seed_full_eligibility(tenant_association)
        data = build_dossier_data(tenant_association)
        md = render_dossier_markdown(tenant_association, data=data)

        assert "Apto a submissao:** Sim" in md
        assert "Dra Teste Integration" in md
        assert "CRM" in md
        # Capacity seccao com readiness numerico.
        assert "75.0" in md or "75" in md
        # Estatuto listado por tipo na secao 6.
        assert "### 6." in md and "statute" in md


# ---------------------------------------------------------------------
# Multi-tenant admin overview
# ---------------------------------------------------------------------

class TestAdminMultiTenantOverview:
    def test_summary_includes_created_association_with_correct_counts(
        self, tenant_association
    ):
        _seed_full_eligibility(tenant_association)

        rows = list_all_associations_summary()
        match = next((r for r in rows if r["tenant_id"] == tenant_association), None)
        assert match is not None, "Tenant de teste nao aparece no resumo"
        assert match["rt_count"] == 1
        assert match["has_capacity"] is True
        assert match["has_statute"] is True
        assert match["members_count"] == 50

    def test_clinic_is_excluded_from_summary(self, tenant_clinic):
        rows = list_all_associations_summary()
        tids = {r["tenant_id"] for r in rows}
        assert tenant_clinic not in tids
