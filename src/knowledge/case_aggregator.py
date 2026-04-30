# src/knowledge/case_aggregator.py
"""
Agregador de casos clinicos longitudinais (C7).

Le anamnesis_reports do tenant, quantiza idade/dose/ratio, agrupa por
(condicao, faixa etaria, faixa de dose, classe ratio) e — quando o grupo
satisfaz k-anonymity (>= MIN_K pacientes distintos) — gera um "caso
agregado anonimizado" que vai para knowledge_catalog com
doc_type='case_aggregate'.

Garantias LGPD:
  - nenhum patient_id, nome, telefone, email entra no abstract ou no
    case_aggregate_metadata
  - threshold k-anonymity (default 5, configuravel via env CASE_AGGREGATE_MIN_K)
  - quantizacao de idade em faixas e dose em ranges para evitar valores
    que isoladamente identifiquem o individuo

Pipeline e idempotente: case_aggregate ja indexado para a mesma chave
(condition, age_range, dose_range, ratio_class) e mesmo periodo nao
e duplicado — o registro existente vira "stale" e e substituido.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

logger = logging.getLogger("cannabia.knowledge.case_aggregator")


# k-anonymity threshold. Configuravel via env para subir/descer sem deploy
# (LGPD/HIPAA reference: k=5 e o padrao de mercado para health data).
MIN_K = int(os.getenv("CASE_AGGREGATE_MIN_K", "5"))

# Janela retroativa default da agregacao.
DEFAULT_LOOKBACK_DAYS = 180


# ─────────────────────────────────────────────────────────────────
# Anonimizadores puros (testaveis)
# ─────────────────────────────────────────────────────────────────


AGE_RANGES = [
    (0, 17, "0-17"),
    (18, 29, "18-29"),
    (30, 49, "30-49"),
    (50, 69, "50-69"),
    (70, 200, "70+"),
]


def quantize_age(age: Any) -> str:
    """Mapeia idade para uma das 5 faixas seguras. Inputs invalidos -> 'unknown'."""
    try:
        if age is None:
            return "unknown"
        years = int(float(age))
    except (TypeError, ValueError):
        return "unknown"
    if years < 0 or years > 130:
        return "unknown"
    for low, high, label in AGE_RANGES:
        if low <= years <= high:
            return label
    return "unknown"


def _extract_dose_mg(dose_str: Optional[str]) -> Optional[float]:
    """Tenta extrair dose em mg do texto livre. Retorna None se nao parsear."""
    if not dose_str:
        return None
    text = dose_str.lower().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*mg", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


DOSE_RANGES = [
    (0.0, 5.0, "<5mg"),
    (5.0, 10.0, "5-10mg"),
    (10.0, 20.0, "10-20mg"),
    (20.0, 50.0, "20-50mg"),
    (50.0, float("inf"), ">50mg"),
]


def quantize_dose(dose_str: Optional[str]) -> str:
    mg = _extract_dose_mg(dose_str)
    if mg is None:
        return "unknown"
    for low, high, label in DOSE_RANGES:
        if low <= mg < high:
            return label
    return "unknown"


def _parse_ratio(ratio_str: Optional[str]) -> Optional[tuple[float, float]]:
    """Tenta extrair (CBD, THC) de strings tipo '20:1', 'CBD 20:1 THC', '1:1'."""
    if not ratio_str:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)", ratio_str)
    if not match:
        return None
    try:
        a = float(match.group(1))
        b = float(match.group(2))
    except ValueError:
        return None
    if a == 0 and b == 0:
        return None
    text = ratio_str.lower()
    # Heuristica: se "thc" aparece antes do ratio, a ordem e invertida.
    if "thc" in text and "cbd" in text:
        if text.find("thc") < text.find("cbd"):
            return (b, a)
    return (a, b)


def classify_ratio(ratio_str: Optional[str]) -> str:
    parsed = _parse_ratio(ratio_str)
    if parsed is None:
        return "unknown"
    cbd, thc = parsed
    if thc <= 0:
        return "cbd_dominante"
    cbd_thc = cbd / thc if thc else float("inf")
    if cbd_thc >= 5:
        return "cbd_dominante"
    if cbd_thc <= 0.5:
        return "thc_dominante"
    return "balanceado"


# Mapeamento canonical das condicoes mais comuns. Strings que nao casam
# nenhum padrao caem em "outro" (nao "unknown" — paciente tem queixa,
# so nao foi classificavel).
CONDITION_PATTERNS = [
    ("epilepsia", "epilepsia"),
    ("convulsao", "epilepsia"),
    ("dor cronica", "dor_cronica"),
    ("dor neuropatica", "dor_cronica"),
    ("fibromialgia", "fibromialgia"),
    ("ansiedade", "ansiedade"),
    ("transtorno de ansiedade", "ansiedade"),
    ("insonia", "insonia"),
    ("disturbio do sono", "insonia"),
    ("transtorno do sono", "insonia"),
    ("autismo", "autismo"),
    ("tea ", "autismo"),
    ("parkinson", "parkinson"),
    ("alzheimer", "alzheimer"),
    ("demencia", "alzheimer"),
    ("esclerose multipla", "esclerose_multipla"),
    ("esclerose", "esclerose_multipla"),
    ("cancer", "cancer"),
    ("oncolog", "cancer"),
    ("nausea", "cancer"),  # tipica indicacao oncologica
    ("ptsd", "tept"),
    ("estresse pos", "tept"),
    ("depressao", "depressao"),
    ("enxaqueca", "enxaqueca"),
    ("migran", "enxaqueca"),
]


def canonicalize_condition(text: Optional[str]) -> str:
    if not text:
        return "outro"
    norm = text.lower().strip()
    norm = (
        norm.replace("á", "a").replace("â", "a").replace("ã", "a")
            .replace("é", "e").replace("ê", "e")
            .replace("í", "i").replace("î", "i")
            .replace("ó", "o").replace("ô", "o").replace("õ", "o")
            .replace("ú", "u").replace("ç", "c")
    )
    for needle, label in CONDITION_PATTERNS:
        if needle in norm:
            return label
    return "outro"


# ─────────────────────────────────────────────────────────────────
# Tipos
# ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CaseGroupKey:
    condition: str
    age_range: str
    dose_range: str
    ratio_class: str


@dataclass(frozen=True)
class CaseAggregate:
    """Caso clinico anonimizado, pronto para entrar em knowledge_catalog."""

    key: CaseGroupKey
    n_patients: int            # k-anonymity n
    period_start: str          # ISO date
    period_end: str            # ISO date
    tenants_contributing: int  # quantos tenants distintos compoem o grupo
    median_dose_mg: Optional[float]
    title: str
    abstract: str
    tags: list[str]


# ─────────────────────────────────────────────────────────────────
# Renderizacao do caso (texto indexavel + metadata estruturada)
# ─────────────────────────────────────────────────────────────────


def _condition_label(canonical: str) -> str:
    labels = {
        "epilepsia": "Epilepsia",
        "dor_cronica": "Dor cronica",
        "fibromialgia": "Fibromialgia",
        "ansiedade": "Transtorno de ansiedade",
        "insonia": "Insonia",
        "autismo": "Transtorno do espectro autista",
        "parkinson": "Doenca de Parkinson",
        "alzheimer": "Alzheimer / demencia",
        "esclerose_multipla": "Esclerose multipla",
        "cancer": "Cancer / oncologia",
        "tept": "Transtorno de estresse pos-traumatico",
        "depressao": "Depressao",
        "enxaqueca": "Enxaqueca / cefaleia",
        "outro": "Quadro nao classificado",
    }
    return labels.get(canonical, canonical)


def _ratio_label(ratio_class: str) -> str:
    return {
        "cbd_dominante": "CBD dominante",
        "thc_dominante": "THC dominante",
        "balanceado": "balanceado CBD:THC",
        "unknown": "ratio nao informado",
    }.get(ratio_class, ratio_class)


def _build_case_text(agg: CaseAggregate) -> tuple[str, str]:
    """Gera (title, abstract) do caso agregado em PT-BR."""
    cond = _condition_label(agg.key.condition)
    age = agg.key.age_range
    dose = agg.key.dose_range
    ratio = _ratio_label(agg.key.ratio_class)
    title = f"{cond} | {age} anos | {dose} | {ratio} (n={agg.n_patients})"

    median_str = (
        f"{agg.median_dose_mg:.1f}mg" if agg.median_dose_mg is not None else "nao registrada"
    )

    abstract = (
        f"Coorte clinica anonimizada de {agg.n_patients} pacientes na faixa de {age} anos com "
        f"{cond.lower()}, recebendo cannabis medicinal {ratio.lower()} na faixa de dose {dose}. "
        f"Dose mediana registrada: {median_str}. "
        f"Periodo: {agg.period_start} a {agg.period_end}. "
        f"Tenants contribuintes: {agg.tenants_contributing}. "
        f"Caso agregado gerado pelo pipeline interno C7 — nenhum identificador "
        f"de paciente esta presente neste registro."
    )
    return title, abstract


# ─────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────


def aggregate_clinical_cases(
    *,
    min_group_size: int = MIN_K,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    now: Optional[datetime] = None,
) -> list[CaseAggregate]:
    """Roda a agregacao end-to-end.

    Le anamnesis_reports recentes, quantiza, agrupa, filtra por k>=min,
    materializa CaseAggregate. NAO faz INSERT — o caller decide onde
    persistir (em knowledge_catalog ou em outra fonte para auditoria).
    """
    from src.infra.database import db_cursor

    now = now or datetime.now(tz=timezone.utc)
    period_start = (now - _delta_days(lookback_days)).date().isoformat()
    period_end = now.date().isoformat()

    sql = """
        SELECT
            ar.patient_id,
            ar.clinic_id,
            ar.anamnesis_data,
            ar.clinical_analysis,
            ar.treatment_plan,
            c.tenant_id,
            ar.created_at
        FROM anamnesis_reports ar
        JOIN clinics c ON c.id = ar.clinic_id
        WHERE ar.created_at >= NOW() - (%s || ' days')::interval
          AND ar.status IN ('pendente', 'revisado')
    """
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(sql, (lookback_days,))
        rows = cur.fetchall() or []

    return _aggregate_in_memory(
        rows,
        min_group_size=min_group_size,
        period_start=period_start,
        period_end=period_end,
    )


def _aggregate_in_memory(
    rows: Iterable[dict],
    *,
    min_group_size: int,
    period_start: str,
    period_end: str,
) -> list[CaseAggregate]:
    """Logica de agregacao isolada em funcao pura para facilitar testes."""
    # Cada chave armazena listas/conjuntos de coisas anonimizadas.
    groups: dict[CaseGroupKey, dict] = {}

    for row in rows:
        anamnesis = _coerce_jsonb(row.get("anamnesis_data")) or {}
        analysis = _coerce_jsonb(row.get("clinical_analysis")) or {}
        plan = _coerce_jsonb(row.get("treatment_plan")) or {}
        tenant_id = row.get("tenant_id")
        patient_id = row.get("patient_id")

        # Sem patient_id ou tenant_id, nao da pra agregar com integridade.
        if patient_id is None or tenant_id is None:
            continue

        age_range = quantize_age(anamnesis.get("age"))
        probable = analysis.get("probable_conditions") or []
        cond_raw = probable[0] if probable else (anamnesis.get("main_complaint") or "")
        condition = canonicalize_condition(cond_raw)
        dose_range = quantize_dose(plan.get("suggested_dosage"))
        ratio_class = classify_ratio(plan.get("cannabinoid_ratio"))

        # Nao agrega quando age + dose + ratio simultaneamente desconhecidos
        # — o registro nao traz informacao util.
        if age_range == "unknown" and dose_range == "unknown" and ratio_class == "unknown":
            continue

        key = CaseGroupKey(
            condition=condition,
            age_range=age_range,
            dose_range=dose_range,
            ratio_class=ratio_class,
        )
        bucket = groups.setdefault(
            key,
            {"patient_ids": set(), "tenants": set(), "doses_mg": []},
        )
        bucket["patient_ids"].add(int(patient_id))
        bucket["tenants"].add(int(tenant_id))
        dose_mg = _extract_dose_mg(plan.get("suggested_dosage"))
        if dose_mg is not None:
            bucket["doses_mg"].append(dose_mg)

    aggregates: list[CaseAggregate] = []
    for key, bucket in groups.items():
        n = len(bucket["patient_ids"])
        if n < min_group_size:
            continue
        doses = sorted(bucket["doses_mg"])
        median_dose: Optional[float] = None
        if doses:
            mid = len(doses) // 2
            if len(doses) % 2 == 1:
                median_dose = doses[mid]
            else:
                median_dose = (doses[mid - 1] + doses[mid]) / 2

        agg = CaseAggregate(
            key=key,
            n_patients=n,
            period_start=period_start,
            period_end=period_end,
            tenants_contributing=len(bucket["tenants"]),
            median_dose_mg=median_dose,
            title="",  # preenchidos na proxima passada
            abstract="",
            tags=[],
        )
        title, abstract = _build_case_text(agg)
        tags = [
            "case_aggregate",
            f"condition:{key.condition}",
            f"age:{key.age_range}",
            f"dose:{key.dose_range}",
            f"ratio:{key.ratio_class}",
        ]
        aggregates.append(
            CaseAggregate(
                key=key,
                n_patients=n,
                period_start=period_start,
                period_end=period_end,
                tenants_contributing=len(bucket["tenants"]),
                median_dose_mg=median_dose,
                title=title,
                abstract=abstract,
                tags=tags,
            )
        )

    aggregates.sort(key=lambda a: (-a.n_patients, a.key.condition))
    return aggregates


# ─────────────────────────────────────────────────────────────────
# Persistencia em knowledge_catalog
# ─────────────────────────────────────────────────────────────────


def case_aggregate_to_doc_data(agg: CaseAggregate) -> dict[str, Any]:
    """Serializa um CaseAggregate como doc_data aceitavel pelo
    register_article_in_catalog (auto_ingest.py)."""
    return {
        "title": agg.title,
        "doc_type": "case_aggregate",
        "source": "internal_clinical_aggregate",
        "source_url": None,
        "doi": None,
        "category": "casos_clinicos_internos",
        "tags": agg.tags,
        "authors": [],
        "journal": "Cannab'IA - Coortes Clinicas Internas",
        "published_date": agg.period_end,
        "language": "pt",
        "abstract": agg.abstract,
        "storage_type": "case_aggregate",
        "status": "indexed",
        "ingested_by": "case_aggregator_pipeline",
        # Campos exclusivos do case_aggregate:
        "case_aggregate_metadata": {
            "k_anonymity_n": agg.n_patients,
            "condition": agg.key.condition,
            "age_range": agg.key.age_range,
            "dose_range": agg.key.dose_range,
            "ratio_class": agg.key.ratio_class,
            "period_start": agg.period_start,
            "period_end": agg.period_end,
            "tenants_contributing": agg.tenants_contributing,
            "median_dose_mg": agg.median_dose_mg,
        },
    }


def persist_aggregates_to_catalog(
    aggregates: Iterable[CaseAggregate],
    *,
    user_id: Optional[int] = None,
) -> dict[str, int]:
    """Insere cada CaseAggregate em knowledge_catalog.

    A chave de unicidade aqui NAO usa o dedup padrao do auto_ingest
    (DOI/URL nao se aplicam). Para idempotencia: antes de inserir,
    apaga linhas existentes com mesmo title E mesmo periodo, evitando
    duplicar entre rodadas.
    """
    from src.infra.database import db_cursor

    inserted = 0
    refreshed = 0

    with db_cursor(dictionary=True) as (conn, cur):
        for agg in aggregates:
            doc = case_aggregate_to_doc_data(agg)
            # Idempotencia: remove versoes anteriores deste mesmo "slot"
            # (mesmo titulo + mesmo periodo) antes de inserir a nova.
            cur.execute(
                """
                DELETE FROM knowledge_catalog
                WHERE doc_type = 'case_aggregate'
                  AND title = %s
                  AND case_aggregate_metadata @> %s::jsonb
                """,
                (
                    doc["title"],
                    json.dumps(
                        {
                            "period_start": agg.period_start,
                            "period_end": agg.period_end,
                        }
                    ),
                ),
            )
            stale = cur.rowcount or 0
            if stale > 0:
                refreshed += stale

            cur.execute(
                """
                INSERT INTO knowledge_catalog
                    (title, doc_type, source, source_url, doi,
                     category, tags, authors, journal, published_date, language,
                     abstract, storage_type, status, ingested_by, ingested_at,
                     created_by, case_aggregate_metadata)
                VALUES
                    (%s, %s, %s, %s, %s,
                     %s, %s::jsonb, %s::jsonb, %s, %s, %s,
                     %s, %s, %s, %s, NOW(),
                     %s, %s::jsonb)
                """,
                (
                    doc["title"],
                    doc["doc_type"],
                    doc["source"],
                    None,
                    None,
                    doc["category"],
                    json.dumps(doc["tags"]),
                    json.dumps(doc["authors"]),
                    doc["journal"],
                    doc["published_date"],
                    doc["language"],
                    doc["abstract"],
                    doc["storage_type"],
                    doc["status"],
                    doc["ingested_by"],
                    user_id,
                    json.dumps(doc["case_aggregate_metadata"]),
                ),
            )
            inserted += 1
        conn.commit()

    return {"inserted": inserted, "refreshed_stale": refreshed}


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────


def _coerce_jsonb(value: Any) -> Optional[dict]:
    """Aceita dict (psycopg2 com jsonb) ou str (algumas bibliotecas) e devolve dict."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _delta_days(days: int):
    from datetime import timedelta
    return timedelta(days=days)


def aggregate_summary_dict(aggregates: list[CaseAggregate]) -> dict[str, Any]:
    """Devolve metadados agregados sem PII para auditoria/log."""
    return {
        "groups_total": len(aggregates),
        "patients_covered": sum(a.n_patients for a in aggregates),
        "min_k": MIN_K,
        "groups": [
            {
                **asdict(a.key),
                "n": a.n_patients,
                "tenants": a.tenants_contributing,
            }
            for a in aggregates[:50]
        ],
    }
