"""
Tests do Estudo Observacional (F4.2 do docs/BACKLOG_SCC.md).

Cobre:
  1. Provider build_observational_study_data — shape do contexto, anonimizacao
     do sample, presenca dos blocos de metodologia/limitacoes/reprodutibilidade.
  2. Resolve do template no registry + render via template_engine.
  3. Reprodutibilidade — duas chamadas com mesmos parametros geram o
     mesmo content_hash (modulo o generated_at que avanca).
  4. Integration smoke contra Postgres real com fixture.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.infra.database import db_cursor
from src.services import template_engine
from src.services.regulatory_documents import (
    EVIDENCE_ENGINE_VERSION,
    build_observational_study_data,
)


# ===========================================================================
# Helpers de DB / fixtures
# ===========================================================================

def _db_reachable() -> bool:
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="DB local nao alcancavel; tests do estudo observacional pulados",
)


@pytest.fixture
def fixture_clinic_id() -> int:
    suffix = uuid.uuid4().hex[:8]
    name = f"obs_study_test_{suffix}"

    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO tenants (tenant_type_id, tenant_type, legal_name,
                                 display_name, slug, status, cnpj,
                                 trade_name)
            VALUES (
              (SELECT id FROM tenant_types WHERE slug='clinic' LIMIT 1),
              'clinic', %s, %s, %s, 'active', %s, %s
            )
            RETURNING id
            """,
            (name, name, name, "12345678000100", f"{name}_fantasia"),
        )
        tenant_row = cur.fetchone()
        tenant_id = tenant_row["id"]
        cur.execute(
            """
            INSERT INTO clinics (id, name, slug, is_active, tenant_id)
            VALUES (%s, %s, %s, TRUE, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (tenant_id, name, name, tenant_id),
        )
        # Se conflict pulou, garante que existe outra clinic e usa
        cur.execute("SELECT id FROM clinics WHERE tenant_id = %s LIMIT 1", (tenant_id,))
        clinic_row = cur.fetchone()
        if clinic_row is None:
            cur.execute(
                """
                INSERT INTO clinics (name, slug, is_active, tenant_id)
                VALUES (%s, %s, TRUE, %s)
                RETURNING id
                """,
                (name, name, tenant_id),
            )
            clinic_row = cur.fetchone()
        clinic_id = clinic_row["id"]
        conn.commit()

    yield clinic_id

    with db_cursor() as (conn, cur):
        cur.execute("SET LOCAL session_replication_role = 'replica'")
        cur.execute("DELETE FROM symptom_diary WHERE clinic_id = %s", (clinic_id,))
        cur.execute("DELETE FROM scheduled_followups WHERE clinic_id = %s", (clinic_id,))
        cur.execute("DELETE FROM treatment_plans WHERE clinic_id = %s", (clinic_id,))
        cur.execute("DELETE FROM patients WHERE clinic_id = %s", (clinic_id,))
        cur.execute("DELETE FROM clinics WHERE id = %s OR tenant_id = %s",
                    (clinic_id, clinic_id))
        cur.execute("DELETE FROM tenants WHERE id = %s OR legal_name LIKE %s",
                    (clinic_id, "obs_study_test_%"))
        conn.commit()


def _create_patient(clinic_id: int, name: str) -> int:
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO patients (clinic_id, name, phone, status)
            VALUES (%s, %s, %s, 'em_tratamento')
            RETURNING id
            """,
            (clinic_id, name, "5511999990000"),
        )
        row = cur.fetchone()
        conn.commit()
        return int(row["id"])


def _create_treatment_plan(
    clinic_id: int,
    patient_id: int,
    plan_name: str,
    *,
    started_at: datetime,
    dosage: str = "20mg/dia",
    cbd_thc_ratio: str = "20:1",
) -> int:
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO treatment_plans
              (clinic_id, patient_id, plan_name, plan_description,
               status, dosage, cbd_thc_ratio, frequency, route, created_at)
            VALUES (%s, %s, %s, %s, 'ativo', %s, %s, '2x/dia', 'sublingual', %s)
            RETURNING id
            """,
            (clinic_id, patient_id, plan_name, f"Plano para {plan_name}",
             dosage, cbd_thc_ratio, started_at),
        )
        row = cur.fetchone()
        conn.commit()
        return int(row["id"])


def _add_diary(clinic_id: int, patient_id: int, *, pain: int, when: datetime) -> None:
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            INSERT INTO symptom_diary
              (clinic_id, patient_id, overall_score, pain_level,
               sleep_quality, mood, side_effects, notes, created_at)
            VALUES (%s, %s, %s, %s, NULL, 'estavel', '[]', '', %s)
            """,
            (clinic_id, patient_id, 5, pain, when),
        )
        conn.commit()


def _add_followup(
    clinic_id: int, patient_id: int, *,
    followup_type: str,
    scheduled_at: datetime,
    response_text: str | None = None,
    responded_at: datetime | None = None,
    status: str = "responded",
) -> int:
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO scheduled_followups
              (clinic_id, patient_id, phone, followup_type, scheduled_at,
               sent_at, status, message_text, response_text, responded_at)
            VALUES (%s, %s, '5511988887777', %s, %s, %s, %s,
                    'Como esta?', %s, %s)
            RETURNING id
            """,
            (clinic_id, patient_id, followup_type, scheduled_at,
             scheduled_at, status, response_text, responded_at),
        )
        row = cur.fetchone()
        conn.commit()
        return int(row["id"])


# ===========================================================================
# Provider: shape do contexto + integracao com Evidence Engine
# ===========================================================================


class TestProviderShape:
    def test_returns_required_top_level_keys(self, fixture_clinic_id: int) -> None:
        ctx = build_observational_study_data(fixture_clinic_id, "Lombalgia")
        required = {
            "study_id", "study_title", "condition_name", "period_days",
            "generated_at", "tenant", "responsible_technical",
            "methodology", "cohort", "dose_effect_points",
            "followup_summary", "sample_outcomes", "limitations",
            "reproducibility", "document_version",
        }
        assert required.issubset(ctx.keys())

    def test_methodology_records_evidence_engine_version(
        self, fixture_clinic_id: int
    ) -> None:
        ctx = build_observational_study_data(fixture_clinic_id, "Lombalgia")
        assert ctx["methodology"]["evidence_engine_version"] == EVIDENCE_ENGINE_VERSION
        assert ctx["methodology"]["ai_in_pipeline"] is False

    def test_methodology_carries_window_parameters(
        self, fixture_clinic_id: int
    ) -> None:
        ctx = build_observational_study_data(
            fixture_clinic_id, "Lombalgia",
            baseline_window_days=14,
            post_window_start_days=14,
            post_window_end_days=60,
        )
        m = ctx["methodology"]
        assert m["baseline_window_days"] == 14
        assert m["post_window_start_days"] == 14
        assert m["post_window_end_days"] == 60

    def test_reproducibility_block_carries_all_params(
        self, fixture_clinic_id: int
    ) -> None:
        ctx = build_observational_study_data(
            fixture_clinic_id, "Lombalgia",
            period_days=120,
        )
        params = ctx["reproducibility"]["parameters"]
        assert params["tenant_id"] == fixture_clinic_id
        assert params["condition_name"] == "Lombalgia"
        assert params["period_days"] == 120
        assert params["metric"] == "pain_level"
        assert "how_to_reproduce" in ctx["reproducibility"]

    def test_sample_outcomes_are_anonymized(self, fixture_clinic_id: int) -> None:
        # Cria paciente com nome real + um followup respondido
        patient_id = _create_patient(fixture_clinic_id, "Joao da Silva CONFIDENCIAL")
        _create_treatment_plan(
            fixture_clinic_id, patient_id, "Lombalgia cronica",
            started_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        _add_followup(
            fixture_clinic_id, patient_id,
            followup_type="d3",
            scheduled_at=datetime.now(timezone.utc) - timedelta(days=20),
            response_text="Estou melhor",
            responded_at=datetime.now(timezone.utc) - timedelta(days=19),
        )

        ctx = build_observational_study_data(fixture_clinic_id, "Lombalgia")
        assert len(ctx["sample_outcomes"]) >= 1
        for outcome in ctx["sample_outcomes"]:
            # Sem patient_name
            assert "patient_name" not in outcome
            # patient_id presente
            assert outcome["patient_id"] == patient_id

    def test_overrides_take_precedence(self, fixture_clinic_id: int) -> None:
        ctx = build_observational_study_data(
            fixture_clinic_id, "Lombalgia",
            overrides={"study_title": "Titulo customizado"},
        )
        assert ctx["study_title"] == "Titulo customizado"


class TestStudyIdReproducibility:
    def test_same_params_same_study_id(self, fixture_clinic_id: int) -> None:
        ctx1 = build_observational_study_data(fixture_clinic_id, "Lombalgia")
        ctx2 = build_observational_study_data(fixture_clinic_id, "Lombalgia")
        assert ctx1["study_id"] == ctx2["study_id"]

    def test_different_params_different_study_id(
        self, fixture_clinic_id: int
    ) -> None:
        ctx1 = build_observational_study_data(
            fixture_clinic_id, "Lombalgia", period_days=180
        )
        ctx2 = build_observational_study_data(
            fixture_clinic_id, "Lombalgia", period_days=90
        )
        assert ctx1["study_id"] != ctx2["study_id"]


# ===========================================================================
# Template engine: registry resolve + render
# ===========================================================================


class TestRegistryRegistration:
    def test_template_resolvable(self) -> None:
        template_engine._invalidate_registry_cache()
        ref = template_engine.resolve("observational_studies/cohort_study")
        assert ref.template_id == "observational_studies/cohort_study"
        assert ref.version == "v1"
        assert ref.file == "observational_studies/cohort_study_v1.md.j2"
        assert ref.absolute_path.exists()
        assert ref.status == "active"
        assert "md" in ref.output_formats


class TestRender:
    def test_renders_minimal_context(self, fixture_clinic_id: int) -> None:
        # Mesmo sem dados clinicos, o provider retorna contexto completo
        # (placeholders) e o template renderiza sem UndefinedError.
        ctx = build_observational_study_data(fixture_clinic_id, "Lombalgia")
        doc = template_engine.render(
            "observational_studies/cohort_study", ctx, format="md"
        )
        assert doc.template_id == "observational_studies/cohort_study"
        assert doc.version == "v1"
        assert doc.format == "md"
        assert len(doc.content_hash) == 64  # sha256 hex
        # Conteudo deve mencionar a condicao
        assert "Lombalgia" in doc.content
        # E os headers principais
        assert "## 1. Identificacao institucional" in doc.content
        assert "## 3. Metodologia" in doc.content
        assert "## 9. Reprodutibilidade" in doc.content

    def test_renders_with_real_data(self, fixture_clinic_id: int) -> None:
        plan_started = datetime.now(timezone.utc) - timedelta(days=60)
        patient_id = _create_patient(fixture_clinic_id, "Paciente X")
        _create_treatment_plan(
            fixture_clinic_id, patient_id, "Lombalgia cronica",
            started_at=plan_started, dosage="40mg/dia",
        )
        for offset in [25, 15, 5]:
            _add_diary(fixture_clinic_id, patient_id,
                       pain=8, when=plan_started - timedelta(days=offset))
        for offset in [40, 60, 80]:
            _add_diary(fixture_clinic_id, patient_id,
                       pain=3, when=plan_started + timedelta(days=offset))
        _add_followup(
            fixture_clinic_id, patient_id,
            followup_type="d7",
            scheduled_at=plan_started + timedelta(days=7),
            response_text="Melhorando bastante",
            responded_at=plan_started + timedelta(days=8),
        )

        ctx = build_observational_study_data(
            fixture_clinic_id, "Lombalgia", period_days=120
        )
        doc = template_engine.render(
            "observational_studies/cohort_study", ctx, format="md"
        )
        # Tabela dose-efeito tem que aparecer com a dose
        assert "40mg/dia" in doc.content
        # Outcome classificado
        assert "improved" in doc.content
        # Cohort com 1 paciente
        assert "| Pacientes na cohort | 1 |" in doc.content


class TestRenderDeterminismGivenStableState:
    def test_two_renders_same_state_same_hash(
        self, fixture_clinic_id: int
    ) -> None:
        # Insere dados estaveis
        plan_started = datetime.now(timezone.utc) - timedelta(days=60)
        patient_id = _create_patient(fixture_clinic_id, "P det")
        _create_treatment_plan(
            fixture_clinic_id, patient_id, "Ansiedade generalizada",
            started_at=plan_started,
        )
        _add_diary(fixture_clinic_id, patient_id, pain=6,
                   when=plan_started - timedelta(days=10))
        _add_diary(fixture_clinic_id, patient_id, pain=2,
                   when=plan_started + timedelta(days=45))

        # Provider gera generated_at = now() — para isolar o teste de
        # determinismo do conteudo (excluindo o timestamp), pinamos
        # `overrides` com generated_at fixo.
        fixed_ts = "2026-04-23T12:00:00+00:00"

        ctx1 = build_observational_study_data(
            fixture_clinic_id, "Ansiedade",
            overrides={"generated_at": fixed_ts, "study_id": "FIXED-ID"},
        )
        ctx2 = build_observational_study_data(
            fixture_clinic_id, "Ansiedade",
            overrides={"generated_at": fixed_ts, "study_id": "FIXED-ID"},
        )
        doc1 = template_engine.render(
            "observational_studies/cohort_study", ctx1, format="md"
        )
        doc2 = template_engine.render(
            "observational_studies/cohort_study", ctx2, format="md"
        )
        assert doc1.content_hash == doc2.content_hash
