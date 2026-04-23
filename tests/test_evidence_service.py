"""
Tests do Evidence Service (F4.1 do docs/BACKLOG_SCC.md).

Cobertura em duas camadas:

  1. Unit tests de classify_response_text — sem DB, deterministicos,
     cobrem o vocabulario PT-BR de outcome (improved/unchanged/worsened).

  2. Integration tests contra Postgres real:
     - inserem fixtures num clinic_id dedicado
     - exercitam o pipeline completo do service
     - cleanup transacional via session_replication_role='replica'
       (necessario porque scheduled_followups e symptom_diary tem
        FKs/triggers que precisam ser bypassados em DELETE de teste)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.infra.database import db_cursor
from src.services.evidence_service import (
    OUTCOME_IMPROVED,
    OUTCOME_UNCHANGED,
    OUTCOME_WORSENED,
    aggregate_longitudinal_by_condition,
    build_evidence_summary,
    classify_response_text,
    correlate_dose_effect,
    extract_outcome_from_followup,
    summarize_followup_responses,
)


# ===========================================================================
# Unit tests — classify_response_text (sem DB)
# ===========================================================================


class TestClassifyResponseText:
    @pytest.mark.parametrize(
        "text",
        [
            "Estou melhor",
            "Sinto melhora significativa nos sintomas",
            "Tive menos dor essa semana",
            "Ajudou muito, dormi melhor",
            "Estou otima, sem dor",
            "Sosseguei, melhorando aos poucos",
        ],
    )
    def test_improved(self, text: str) -> None:
        assert classify_response_text(text) == OUTCOME_IMPROVED

    @pytest.mark.parametrize(
        "text",
        [
            "Estou pior",
            "A dor piorou esses dias",
            "Sinto mais dor agora",
            "Tive efeito colateral, enjoo forte",
            "Nao funcionou para mim",
            "Sono pior, nao consigo dormir",
        ],
    )
    def test_worsened(self, text: str) -> None:
        assert classify_response_text(text) == OUTCOME_WORSENED

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            None,
            "Tudo na mesma",
            "Sem novidade",
            "Continuo igual",
        ],
    )
    def test_unchanged(self, text) -> None:
        assert classify_response_text(text) == OUTCOME_UNCHANGED

    def test_tie_breaks_to_unchanged(self) -> None:
        # Texto contendo 1 sinal de cada lado
        text = "Tive melhora pela manha mas piorou a noite"
        assert classify_response_text(text) == OUTCOME_UNCHANGED

    def test_more_improved_signals_wins(self) -> None:
        text = "Melhor, melhorando, sem dor — tive um pouco de tontura"
        # 3 improved vs 1 worsened
        assert classify_response_text(text) == OUTCOME_IMPROVED

    def test_case_insensitive(self) -> None:
        assert classify_response_text("MELHOR") == OUTCOME_IMPROVED
        assert classify_response_text("PIOR") == OUTCOME_WORSENED


# ===========================================================================
# Integration tests — DB real
# ===========================================================================


def _db_reachable() -> bool:
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark_db = pytest.mark.skipif(
    not _db_reachable(),
    reason="DB local nao alcancavel; integration tests pulados",
)


@pytest.fixture
def fixture_clinic_id() -> int:
    """
    Clinic dedicada para isolar dados de teste do DB de dev.

    Cria um tenant + clinic novos, retorna o clinic_id. Cleanup remove
    tudo o que foi inserido neste tenant/clinic.
    """
    suffix = uuid.uuid4().hex[:8]
    name = f"evidence_test_{suffix}"

    with db_cursor(dictionary=True) as (conn, cur):
        # Tenant minimo
        cur.execute(
            """
            INSERT INTO tenants (tenant_type_id, tenant_type, legal_name,
                                 display_name, slug, status)
            VALUES (
              (SELECT id FROM tenant_types WHERE slug='clinic' LIMIT 1),
              'clinic',
              %s, %s, %s, 'active'
            )
            RETURNING id
            """,
            (name, name, name),
        )
        tenant_row = cur.fetchone()
        tenant_id = tenant_row["id"]

        # Clinic alinhada (clinic.id NAO e necessariamente == tenant.id;
        # mas para Evidence Service usamos o clinic_id como tenant_id
        # nas queries, entao retornamos clinic_id).
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

    # Cleanup — bypass triggers append-only se houver
    with db_cursor() as (conn, cur):
        cur.execute("SET LOCAL session_replication_role = 'replica'")
        cur.execute("DELETE FROM symptom_diary WHERE clinic_id = %s", (clinic_id,))
        cur.execute("DELETE FROM scheduled_followups WHERE clinic_id = %s", (clinic_id,))
        cur.execute("DELETE FROM treatment_plans WHERE clinic_id = %s", (clinic_id,))
        cur.execute("DELETE FROM patients WHERE clinic_id = %s", (clinic_id,))
        cur.execute("DELETE FROM clinics WHERE id = %s", (clinic_id,))
        cur.execute(
            "DELETE FROM tenants WHERE id IN ("
            "SELECT tenant_id FROM clinics WHERE id = %s"
            ") OR legal_name LIKE %s",
            (clinic_id, f"evidence_test_%"),
        )
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
            (
                clinic_id,
                patient_id,
                plan_name,
                f"Plano para {plan_name}",
                dosage,
                cbd_thc_ratio,
                started_at,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return int(row["id"])


def _add_diary_entry(
    clinic_id: int,
    patient_id: int,
    *,
    overall_score: int,
    pain_level: int,
    when: datetime,
) -> None:
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            INSERT INTO symptom_diary
              (clinic_id, patient_id, overall_score, pain_level,
               sleep_quality, mood, side_effects, notes, created_at)
            VALUES (%s, %s, %s, %s, NULL, 'estavel', '[]', '', %s)
            """,
            (clinic_id, patient_id, overall_score, pain_level, when),
        )
        conn.commit()


def _add_followup(
    clinic_id: int,
    patient_id: int,
    *,
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
                    'Como esta se sentindo?', %s, %s)
            RETURNING id
            """,
            (
                clinic_id,
                patient_id,
                followup_type,
                scheduled_at,
                scheduled_at,
                status,
                response_text,
                responded_at,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return int(row["id"])


@pytestmark_db
class TestExtractOutcomeFromFollowup:
    def test_returns_none_for_missing_id(self) -> None:
        assert extract_outcome_from_followup(999_999_999) is None

    def test_returns_none_for_unresponded(self, fixture_clinic_id: int) -> None:
        patient_id = _create_patient(fixture_clinic_id, "Paciente A")
        sent_at = datetime.now(timezone.utc) - timedelta(days=3)
        fid = _add_followup(
            fixture_clinic_id,
            patient_id,
            followup_type="d3",
            scheduled_at=sent_at,
            response_text=None,
            responded_at=None,
            status="sent",
        )
        assert extract_outcome_from_followup(fid) is None

    def test_classifies_responded(self, fixture_clinic_id: int) -> None:
        patient_id = _create_patient(fixture_clinic_id, "Paciente B")
        sent_at = datetime.now(timezone.utc) - timedelta(days=3)
        responded_at = datetime.now(timezone.utc) - timedelta(days=2)
        fid = _add_followup(
            fixture_clinic_id,
            patient_id,
            followup_type="d3",
            scheduled_at=sent_at,
            response_text="Estou melhor, menos dor",
            responded_at=responded_at,
        )
        outcome = extract_outcome_from_followup(fid)
        assert outcome is not None
        assert outcome.classified_outcome == OUTCOME_IMPROVED
        assert outcome.followup_type == "d3"
        assert outcome.patient_id == patient_id


@pytestmark_db
class TestSummarizeFollowupResponses:
    def test_empty_period_returns_zeros(self, fixture_clinic_id: int) -> None:
        s = summarize_followup_responses(fixture_clinic_id, period_days=30)
        assert s.total_sent == 0
        assert s.total_responded == 0
        assert s.response_rate == 0.0

    def test_aggregates_by_type(self, fixture_clinic_id: int) -> None:
        patient_id = _create_patient(fixture_clinic_id, "Paciente C")
        now = datetime.now(timezone.utc)

        # 3 D+3 (2 improved, 1 worsened), 2 D+7 (1 improved, 1 unchanged)
        for text in ["Melhor demais", "Melhorando", "Pior, mais dor"]:
            _add_followup(
                fixture_clinic_id,
                patient_id,
                followup_type="d3",
                scheduled_at=now - timedelta(days=5),
                response_text=text,
                responded_at=now - timedelta(days=4),
            )
        for text in ["Sem dor agora", "Tudo igual"]:
            _add_followup(
                fixture_clinic_id,
                patient_id,
                followup_type="d7",
                scheduled_at=now - timedelta(days=10),
                response_text=text,
                responded_at=now - timedelta(days=9),
            )

        s = summarize_followup_responses(fixture_clinic_id, period_days=30)
        assert s.total_responded == 5
        assert s.total_sent >= 5  # responded e considerado sent

        d3 = s.by_type_outcomes["d3"]
        assert d3[OUTCOME_IMPROVED] == 2
        assert d3[OUTCOME_WORSENED] == 1
        assert d3[OUTCOME_UNCHANGED] == 0

        d7 = s.by_type_outcomes["d7"]
        assert d7[OUTCOME_IMPROVED] == 1
        assert d7[OUTCOME_UNCHANGED] == 1

    def test_response_rate_computed(self, fixture_clinic_id: int) -> None:
        patient_id = _create_patient(fixture_clinic_id, "Paciente D")
        now = datetime.now(timezone.utc)

        # 1 enviado sem resposta + 1 respondido em D+3 -> taxa = 0.5
        _add_followup(
            fixture_clinic_id, patient_id,
            followup_type="d3",
            scheduled_at=now - timedelta(days=4),
            response_text=None,
            responded_at=None,
            status="sent",
        )
        _add_followup(
            fixture_clinic_id, patient_id,
            followup_type="d3",
            scheduled_at=now - timedelta(days=4),
            response_text="Melhorando",
            responded_at=now - timedelta(days=3),
            status="responded",
        )

        s = summarize_followup_responses(fixture_clinic_id, period_days=30)
        assert s.by_type_response_rate["d3"] == pytest.approx(0.5)
        assert s.response_rate == pytest.approx(0.5)


@pytestmark_db
class TestCorrelateDoseEffect:
    def test_skips_patients_without_diary(self, fixture_clinic_id: int) -> None:
        patient_id = _create_patient(fixture_clinic_id, "Paciente E")
        _create_treatment_plan(
            fixture_clinic_id,
            patient_id,
            "Lombalgia cronica",
            started_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        points = correlate_dose_effect(
            fixture_clinic_id, "Lombalgia"
        )
        # Sem diary entries, ponto e pulado
        assert points == []

    def test_computes_baseline_post_delta(self, fixture_clinic_id: int) -> None:
        patient_id = _create_patient(fixture_clinic_id, "Paciente F")
        plan_started = datetime.now(timezone.utc) - timedelta(days=60)

        plan_id = _create_treatment_plan(
            fixture_clinic_id,
            patient_id,
            "Lombalgia cronica",
            started_at=plan_started,
            dosage="40mg/dia",
            cbd_thc_ratio="10:1",
        )

        # Baseline: 3 entradas com pain_level alto (~7) na janela [-30, 0)
        for offset in [25, 15, 5]:
            _add_diary_entry(
                fixture_clinic_id, patient_id,
                overall_score=4,
                pain_level=7,
                when=plan_started - timedelta(days=offset),
            )

        # Post: 3 entradas com pain_level baixo (~3) na janela [+30, +90)
        for offset in [35, 50, 70]:
            _add_diary_entry(
                fixture_clinic_id, patient_id,
                overall_score=8,
                pain_level=3,
                when=plan_started + timedelta(days=offset),
            )

        points = correlate_dose_effect(
            fixture_clinic_id, "Lombalgia",
            metric="pain_level",
        )
        assert len(points) == 1
        p = points[0]
        assert p.patient_id == patient_id
        assert p.plan_id == plan_id
        assert p.dose_label == "40mg/dia"
        assert p.cbd_thc_ratio == "10:1"
        assert p.baseline_n == 3
        assert p.post_n == 3
        assert p.baseline_mean == pytest.approx(7.0)
        assert p.post_mean == pytest.approx(3.0)
        # Negative delta = improvement (pain went down)
        assert p.score_delta == pytest.approx(-4.0)


@pytestmark_db
class TestAggregateLongitudinalByCondition:
    def test_pooled_means_weighted_by_n(self, fixture_clinic_id: int) -> None:
        plan_started = datetime.now(timezone.utc) - timedelta(days=60)

        # Patient 1: 2 baseline pain=8, 4 post pain=4
        p1 = _create_patient(fixture_clinic_id, "P1")
        _create_treatment_plan(
            fixture_clinic_id, p1, "Lombalgia cronica",
            started_at=plan_started, dosage="20mg",
        )
        for offset in [20, 10]:
            _add_diary_entry(
                fixture_clinic_id, p1,
                overall_score=3, pain_level=8,
                when=plan_started - timedelta(days=offset),
            )
        for offset in [35, 50, 60, 70]:
            _add_diary_entry(
                fixture_clinic_id, p1,
                overall_score=7, pain_level=4,
                when=plan_started + timedelta(days=offset),
            )

        # Patient 2: 1 baseline pain=6, 1 post pain=2
        p2 = _create_patient(fixture_clinic_id, "P2")
        _create_treatment_plan(
            fixture_clinic_id, p2, "Lombalgia cronica",
            started_at=plan_started, dosage="40mg",
        )
        _add_diary_entry(
            fixture_clinic_id, p2, overall_score=4, pain_level=6,
            when=plan_started - timedelta(days=10),
        )
        _add_diary_entry(
            fixture_clinic_id, p2, overall_score=8, pain_level=2,
            when=plan_started + timedelta(days=40),
        )

        cohort = aggregate_longitudinal_by_condition(
            fixture_clinic_id, "Lombalgia"
        )
        assert cohort.n_patients == 2
        assert cohort.n_treatment_plans == 2
        # Pooled baseline = (8*2 + 6*1) / 3 = 22/3 ~ 7.33
        assert cohort.pooled_baseline_pain_mean == pytest.approx(22 / 3)
        # Pooled post = (4*4 + 2*1) / 5 = 18/5 = 3.6
        assert cohort.pooled_post_pain_mean == pytest.approx(3.6)
        assert cohort.pooled_pain_delta == pytest.approx(3.6 - (22 / 3))


@pytestmark_db
class TestBuildEvidenceSummary:
    def test_smoke_full_pipeline(self, fixture_clinic_id: int) -> None:
        plan_started = datetime.now(timezone.utc) - timedelta(days=60)

        patient_id = _create_patient(fixture_clinic_id, "Smoke Patient")
        _create_treatment_plan(
            fixture_clinic_id, patient_id, "Ansiedade generalizada",
            started_at=plan_started,
        )
        _add_diary_entry(
            fixture_clinic_id, patient_id,
            overall_score=3, pain_level=2,
            when=plan_started - timedelta(days=15),
        )
        _add_diary_entry(
            fixture_clinic_id, patient_id,
            overall_score=8, pain_level=1,
            when=plan_started + timedelta(days=45),
        )
        _add_followup(
            fixture_clinic_id, patient_id,
            followup_type="d7",
            scheduled_at=plan_started + timedelta(days=7),
            response_text="Melhor, dormi melhor essa semana",
            responded_at=plan_started + timedelta(days=8),
        )

        summary = build_evidence_summary(
            fixture_clinic_id, "Ansiedade", period_days=120
        )

        assert summary.condition_name == "Ansiedade"
        assert summary.period_days == 120
        assert summary.cohort.n_patients == 1
        assert len(summary.dose_effect_points) == 1
        assert summary.followup_summary.total_responded == 1
        # Sample inclui o outcome classificado
        assert len(summary.sample_outcomes) == 1
        assert summary.sample_outcomes[0].classified_outcome == OUTCOME_IMPROVED
