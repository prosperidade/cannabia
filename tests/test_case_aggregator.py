"""Tests do agregador de casos clinicos (C7).

Foco:
  - quantizadores puros (idade, dose, ratio, condicao)
  - logica de agregacao in-memory com k-anonymity
  - serializacao para knowledge_catalog
  - garantia LGPD: nenhum identificador de paciente sobrevive ao pipeline
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.knowledge.case_aggregator import (
    CaseAggregate,
    CaseGroupKey,
    _aggregate_in_memory,
    _build_case_text,
    _extract_dose_mg,
    _parse_ratio,
    aggregate_summary_dict,
    canonicalize_condition,
    case_aggregate_to_doc_data,
    classify_ratio,
    quantize_age,
    quantize_dose,
)


# ─────────────────────────────────────────────────────────────────
# quantize_age
# ─────────────────────────────────────────────────────────────────


def test_quantize_age_ranges():
    assert quantize_age(5) == "0-17"
    assert quantize_age(17) == "0-17"
    assert quantize_age(18) == "18-29"
    assert quantize_age(29) == "18-29"
    assert quantize_age(30) == "30-49"
    assert quantize_age(49) == "30-49"
    assert quantize_age(50) == "50-69"
    assert quantize_age(69) == "50-69"
    assert quantize_age(70) == "70+"
    assert quantize_age(120) == "70+"


def test_quantize_age_invalid():
    assert quantize_age(None) == "unknown"
    assert quantize_age("abc") == "unknown"
    assert quantize_age(-5) == "unknown"
    assert quantize_age(200) == "unknown"


def test_quantize_age_string_number():
    assert quantize_age("35") == "30-49"


# ─────────────────────────────────────────────────────────────────
# quantize_dose
# ─────────────────────────────────────────────────────────────────


def test_extract_dose_mg_handles_variants():
    assert _extract_dose_mg("5mg/dia") == 5.0
    assert _extract_dose_mg("CBD 7,5 mg duas vezes") == 7.5
    assert _extract_dose_mg("12mg") == 12.0
    assert _extract_dose_mg("nada de mg") is None
    assert _extract_dose_mg(None) is None


def test_quantize_dose_ranges():
    assert quantize_dose("3mg") == "<5mg"
    assert quantize_dose("5mg") == "5-10mg"
    assert quantize_dose("9.9mg") == "5-10mg"
    assert quantize_dose("10mg") == "10-20mg"
    assert quantize_dose("19mg") == "10-20mg"
    assert quantize_dose("20mg") == "20-50mg"
    assert quantize_dose("100mg") == ">50mg"


def test_quantize_dose_unparseable():
    assert quantize_dose("conforme orientacao medica") == "unknown"
    assert quantize_dose(None) == "unknown"
    assert quantize_dose("") == "unknown"


# ─────────────────────────────────────────────────────────────────
# classify_ratio
# ─────────────────────────────────────────────────────────────────


def test_parse_ratio_basic():
    assert _parse_ratio("20:1") == (20.0, 1.0)
    assert _parse_ratio("1:1") == (1.0, 1.0)


def test_parse_ratio_with_thc_first_inverts():
    """'THC 1:20 CBD' deve interpretar 20 CBD para 1 THC."""
    parsed = _parse_ratio("THC 1:20 CBD")
    assert parsed == (20.0, 1.0)


def test_classify_ratio_classes():
    assert classify_ratio("20:1") == "cbd_dominante"
    assert classify_ratio("5:1") == "cbd_dominante"
    assert classify_ratio("1:1") == "balanceado"
    assert classify_ratio("2:1") == "balanceado"
    assert classify_ratio("1:5") == "thc_dominante"
    assert classify_ratio("1:20") == "thc_dominante"


def test_classify_ratio_invalid():
    assert classify_ratio(None) == "unknown"
    assert classify_ratio("") == "unknown"
    assert classify_ratio("sem ratio") == "unknown"


def test_classify_ratio_zero_thc_is_cbd_dominante():
    assert classify_ratio("100:0") == "cbd_dominante"


# ─────────────────────────────────────────────────────────────────
# canonicalize_condition
# ─────────────────────────────────────────────────────────────────


def test_canonicalize_condition_known_patterns():
    assert canonicalize_condition("Epilepsia refrataria") == "epilepsia"
    assert canonicalize_condition("Dor cronica lombar") == "dor_cronica"
    assert canonicalize_condition("Fibromialgia primaria") == "fibromialgia"
    assert canonicalize_condition("Transtorno de ansiedade generalizada") == "ansiedade"
    assert canonicalize_condition("Insonia cronica") == "insonia"
    assert canonicalize_condition("Cancer de mama") == "cancer"
    assert canonicalize_condition("Enxaqueca cronica") == "enxaqueca"


def test_canonicalize_condition_handles_accents():
    assert canonicalize_condition("Insônia crônica") == "insonia"
    assert canonicalize_condition("Depressão maior") == "depressao"


def test_canonicalize_condition_unknown_falls_to_outro():
    assert canonicalize_condition("Indigestao recorrente") == "outro"
    assert canonicalize_condition("") == "outro"
    assert canonicalize_condition(None) == "outro"


# ─────────────────────────────────────────────────────────────────
# _aggregate_in_memory
# ─────────────────────────────────────────────────────────────────


def _row(*, patient_id: int, tenant_id: int = 1, age=35,
         condition="Epilepsia refrataria", dose="7mg/dia", ratio="20:1") -> dict:
    return {
        "patient_id": patient_id,
        "clinic_id": 1,
        "tenant_id": tenant_id,
        "anamnesis_data": {"age": age, "main_complaint": condition},
        "clinical_analysis": {"probable_conditions": [condition]},
        "treatment_plan": {"suggested_dosage": dose, "cannabinoid_ratio": ratio},
        "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
    }


def test_aggregate_in_memory_filters_below_k_anonymity():
    """Grupo com 4 pacientes nao publica quando min=5."""
    rows = [_row(patient_id=i) for i in range(1, 5)]
    aggregates = _aggregate_in_memory(
        rows, min_group_size=5, period_start="2026-01-01", period_end="2026-04-29",
    )
    assert aggregates == []


def test_aggregate_in_memory_publishes_when_k_satisfied():
    rows = [_row(patient_id=i) for i in range(1, 7)]
    aggregates = _aggregate_in_memory(
        rows, min_group_size=5, period_start="2026-01-01", period_end="2026-04-29",
    )
    assert len(aggregates) == 1
    agg = aggregates[0]
    assert agg.n_patients == 6
    assert agg.key.condition == "epilepsia"
    assert agg.key.age_range == "30-49"
    assert agg.key.dose_range == "5-10mg"
    assert agg.key.ratio_class == "cbd_dominante"


def test_aggregate_dedups_same_patient_multiple_reports():
    """Mesmo paciente aparecendo em multiplos reports conta uma vez para k."""
    rows = [_row(patient_id=1) for _ in range(10)]
    aggregates = _aggregate_in_memory(
        rows, min_group_size=2, period_start="2026-01-01", period_end="2026-04-29",
    )
    # 10 reports do mesmo paciente -> n=1 -> nao satisfaz k=2.
    assert aggregates == []


def test_aggregate_counts_distinct_tenants():
    rows = (
        [_row(patient_id=i, tenant_id=10) for i in range(1, 4)]
        + [_row(patient_id=i, tenant_id=20) for i in range(4, 7)]
    )
    aggregates = _aggregate_in_memory(
        rows, min_group_size=5, period_start="2026-01-01", period_end="2026-04-29",
    )
    assert len(aggregates) == 1
    assert aggregates[0].tenants_contributing == 2


def test_aggregate_computes_median_dose():
    rows = [
        _row(patient_id=1, dose="5mg"),
        _row(patient_id=2, dose="6mg"),
        _row(patient_id=3, dose="7mg"),
        _row(patient_id=4, dose="8mg"),
        _row(patient_id=5, dose="9mg"),
    ]
    aggregates = _aggregate_in_memory(
        rows, min_group_size=5, period_start="2026-01-01", period_end="2026-04-29",
    )
    assert aggregates[0].median_dose_mg == 7.0


def test_aggregate_skips_records_with_all_quantizers_unknown():
    """Sem age, dose, ratio uteis o registro e descartado."""
    rows = [
        {
            "patient_id": i,
            "tenant_id": 1,
            "clinic_id": 1,
            "anamnesis_data": {"age": None, "main_complaint": "x"},
            "clinical_analysis": {"probable_conditions": ["zzz"]},
            "treatment_plan": {"suggested_dosage": "qbd", "cannabinoid_ratio": "??"},
        }
        for i in range(1, 7)
    ]
    aggregates = _aggregate_in_memory(
        rows, min_group_size=5, period_start="2026-01-01", period_end="2026-04-29",
    )
    assert aggregates == []


def test_aggregate_skips_rows_without_patient_id():
    rows = [_row(patient_id=i) for i in range(1, 4)] + [
        {
            "patient_id": None,
            "tenant_id": 1,
            "clinic_id": 1,
            "anamnesis_data": {"age": 30},
            "clinical_analysis": {"probable_conditions": ["epilepsia"]},
            "treatment_plan": {"suggested_dosage": "7mg", "cannabinoid_ratio": "20:1"},
        }
    ]
    aggregates = _aggregate_in_memory(
        rows, min_group_size=3, period_start="2026-01-01", period_end="2026-04-29",
    )
    # 3 com patient_id valido, 1 descartado.
    assert aggregates[0].n_patients == 3


# ─────────────────────────────────────────────────────────────────
# LGPD: nenhum identificador de paciente vaza
# ─────────────────────────────────────────────────────────────────


def test_aggregate_output_contains_no_pii():
    rows = [
        {
            "patient_id": i,
            "tenant_id": 1,
            "clinic_id": 1,
            "anamnesis_data": {
                "age": 35,
                "patient_name": f"Paciente Real {i}",  # PII embutida
                "phone": f"+551199999{i:04d}",
                "main_complaint": "epilepsia refrataria",
            },
            "clinical_analysis": {"probable_conditions": ["epilepsia refrataria"]},
            "treatment_plan": {"suggested_dosage": "7mg", "cannabinoid_ratio": "20:1"},
        }
        for i in range(1, 7)
    ]
    aggregates = _aggregate_in_memory(
        rows, min_group_size=5, period_start="2026-01-01", period_end="2026-04-29",
    )
    assert len(aggregates) == 1
    agg = aggregates[0]

    serialized = (
        agg.title + " " + agg.abstract + " " + " ".join(agg.tags)
    )
    # NENHUM nome ou telefone de paciente pode aparecer na saida.
    for i in range(1, 7):
        assert f"Paciente Real {i}" not in serialized
        assert f"+551199999{i:04d}" not in serialized

    # patient_id tambem nao aparece.
    for pid in range(1, 7):
        assert f"patient_id={pid}" not in serialized
        assert f"id:{pid}" not in serialized


def test_doc_data_serialization_drops_pii_fields():
    """case_aggregate_to_doc_data nao deve carregar nenhum campo PII."""
    agg = CaseAggregate(
        key=CaseGroupKey(
            condition="epilepsia",
            age_range="30-49",
            dose_range="5-10mg",
            ratio_class="cbd_dominante",
        ),
        n_patients=8,
        period_start="2026-01-01",
        period_end="2026-04-29",
        tenants_contributing=2,
        median_dose_mg=7.0,
        title="t",
        abstract="a",
        tags=["case_aggregate"],
    )
    doc = case_aggregate_to_doc_data(agg)
    metadata = doc["case_aggregate_metadata"]

    forbidden = {"patient_id", "patient_ids", "phone", "email", "name", "cpf"}
    assert forbidden.isdisjoint(metadata.keys())
    assert metadata["k_anonymity_n"] == 8
    assert metadata["condition"] == "epilepsia"


def test_summary_dict_omits_per_patient_data():
    aggs = [
        CaseAggregate(
            key=CaseGroupKey(condition="epilepsia", age_range="30-49",
                             dose_range="5-10mg", ratio_class="cbd_dominante"),
            n_patients=6, period_start="2026-01-01", period_end="2026-04-29",
            tenants_contributing=2, median_dose_mg=7.0,
            title="t", abstract="a", tags=["x"],
        )
    ]
    summary = aggregate_summary_dict(aggs)
    serialized = str(summary)
    # Garante nenhum campo PII no preview.
    for term in ("patient_name", "phone", "email", "cpf", "patient_id"):
        assert term not in serialized


# ─────────────────────────────────────────────────────────────────
# _build_case_text — formato de saida
# ─────────────────────────────────────────────────────────────────


def test_build_case_text_includes_n_and_period():
    agg = CaseAggregate(
        key=CaseGroupKey(
            condition="dor_cronica", age_range="50-69",
            dose_range="10-20mg", ratio_class="balanceado",
        ),
        n_patients=12, period_start="2025-10-01", period_end="2026-04-29",
        tenants_contributing=3, median_dose_mg=15.0,
        title="", abstract="", tags=[],
    )
    title, abstract = _build_case_text(agg)
    assert "n=12" in title
    assert "Dor cronica" in title
    assert "50-69" in title
    assert "12 pacientes" in abstract
    assert "2025-10-01" in abstract
    assert "2026-04-29" in abstract
    assert "nenhum identificador" in abstract.lower()
