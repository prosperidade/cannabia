# src/services/evidence_service.py
"""
Evidence Engine — F4.1 do docs/BACKLOG_SCC.md.

Agregacao longitudinal por condicao clinica + correlacao dose-efeito +
extracao de desfechos da telemetria pos-consulta (D+3/D+7/D+15).

Saida deterministica e auditavel (sem AI no caminho), pronta para
alimentar templates regulatorios e estudos observacionais (F4.2).

Princípios:
  - Classificacao de outcome via keyword whitelist em portugues. AI fica
    para iteracao posterior (F4.2 ou refinamento de F4.1).
  - Janelas temporais explicitas (baseline_window, post_window) para
    permitir comparacao reproduzivel — registradas no EvidenceSummary.
  - Dataclasses frozen para garantir imutabilidade do snapshot gerado.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.repositories import evidence_repository as repo

logger = logging.getLogger("cannabia.svc.evidence")


# ===========================================================================
# Outcome classification — keyword-based, deterministico
# ===========================================================================

# Padroes em portugues coloquial brasileiro. Lista expandivel sem
# alterar o algoritmo de scoring.
_OUTCOME_KEYWORDS: dict[str, list[str]] = {
    "improved": [
        r"\bmelhor",
        r"\bmelhora\b",
        r"\bmelhorando\b",
        r"\bmenos dor",
        r"\bsem dor",
        r"\bajudou",
        r"\botim[oa]",
        r"\bexcelente",
        r"\bdormi melhor",
        r"\btranquil[oa]",
        r"\bsosseg[ao]",
    ],
    "worsened": [
        r"\bpior",
        r"\bpiorou",
        r"\bmais dor",
        r"\befeito colateral",
        r"\bn[aã]o funcion",
        r"\bn[aã]o ajud",
        r"\benjo[ao]",
        r"\btontur",
        r"\bsono pior",
        r"\bn[aã]o consigo dormir",
    ],
}

_OUTCOME_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    label: [re.compile(p, re.IGNORECASE) for p in patterns]
    for label, patterns in _OUTCOME_KEYWORDS.items()
}

OUTCOME_IMPROVED = "improved"
OUTCOME_UNCHANGED = "unchanged"
OUTCOME_WORSENED = "worsened"


def classify_response_text(text: Optional[str]) -> str:
    """
    Classifica resposta livre de follow-up em improved/unchanged/worsened.

    Determinístico: scoring por keywords. Em empate ou ausencia de sinal,
    retorna 'unchanged'.
    """
    if not text or not text.strip():
        return OUTCOME_UNCHANGED

    scores = {label: 0 for label in _OUTCOME_PATTERNS}
    for label, patterns in _OUTCOME_PATTERNS.items():
        for pat in patterns:
            if pat.search(text):
                scores[label] += 1

    if scores[OUTCOME_IMPROVED] > scores[OUTCOME_WORSENED]:
        return OUTCOME_IMPROVED
    if scores[OUTCOME_WORSENED] > scores[OUTCOME_IMPROVED]:
        return OUTCOME_WORSENED
    return OUTCOME_UNCHANGED


# ===========================================================================
# Dataclasses de saida
# ===========================================================================

@dataclass(frozen=True)
class OutcomeRecord:
    """Um followup respondido + classificacao deterministica."""
    followup_id: int
    patient_id: int
    patient_name: Optional[str]
    followup_type: str            # 'd3' | 'd7' | 'd15'
    responded_at: datetime
    response_text: str
    classified_outcome: str       # OUTCOME_IMPROVED | OUTCOME_UNCHANGED | OUTCOME_WORSENED
    plan_name: Optional[str]


@dataclass(frozen=True)
class DoseEffectPoint:
    """
    Ponto na correlacao dose-efeito. score_delta = post_mean - baseline_mean.

    Para `pain_level` (0-10), score_delta NEGATIVO indica MELHORA.
    """
    patient_id: int
    plan_id: int
    dose_label: Optional[str]              # treatment_plans.dosage texto livre
    cbd_thc_ratio: Optional[str]
    plan_started_at: datetime
    metric: str                            # 'pain_level' | 'overall_score' | 'sleep_quality'
    baseline_mean: Optional[float]
    baseline_n: int
    post_mean: Optional[float]
    post_n: int
    score_delta: Optional[float]


@dataclass(frozen=True)
class FollowupSummary:
    """Agregados de followups respondidos por tipo (D+3/D+7/D+15)."""
    period_days: int
    total_sent: int
    total_responded: int
    response_rate: float                   # responded / sent (0..1)
    by_type_outcomes: dict[str, dict[str, int]]    # {'d3': {'improved': 5, ...}, ...}
    by_type_response_rate: dict[str, float]        # {'d3': 0.62, ...}


@dataclass(frozen=True)
class CohortSummary:
    """Agregado da cohort de pacientes em tratamento para uma condicao."""
    tenant_id: int
    condition_name: str
    period_days: int
    n_patients: int
    n_treatment_plans: int
    pooled_baseline_pain_mean: Optional[float]
    pooled_post_pain_mean: Optional[float]
    pooled_pain_delta: Optional[float]


@dataclass(frozen=True)
class EvidenceSummary:
    """Top-level — snapshot completo pronto para template/estudo observacional."""
    tenant_id: int
    condition_name: str
    period_days: int
    generated_at: datetime
    baseline_window_days: int
    post_window_start_days: int
    post_window_end_days: int
    cohort: CohortSummary
    dose_effect_points: tuple[DoseEffectPoint, ...]
    followup_summary: FollowupSummary
    sample_outcomes: tuple[OutcomeRecord, ...]


# ===========================================================================
# Helpers
# ===========================================================================

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_outcome(row: dict) -> OutcomeRecord:
    return OutcomeRecord(
        followup_id=int(row["followup_id"]),
        patient_id=int(row["patient_id"]),
        patient_name=row.get("patient_name"),
        followup_type=str(row["followup_type"]),
        responded_at=row["responded_at"],
        response_text=str(row.get("response_text") or ""),
        classified_outcome=classify_response_text(row.get("response_text")),
        plan_name=row.get("latest_plan_name"),
    )


# ===========================================================================
# Funcoes publicas
# ===========================================================================

def extract_outcome_from_followup(followup_id: int) -> Optional[OutcomeRecord]:
    """
    Carrega 1 followup pelo id e classifica em outcome. Retorna None se
    o followup nao existir ou nao tiver responded_at preenchido.
    """
    row = repo.get_followup_by_id(followup_id)
    if not row:
        return None
    if not row.get("responded_at"):
        return None
    # Adapta o shape de get_followup_by_id (sem latest_plan_name) para
    # _row_to_outcome.
    row = {**row, "latest_plan_name": None}
    return _row_to_outcome(row)


def summarize_followup_responses(
    tenant_id: int,
    *,
    period_days: int = 90,
    plan_name_like: Optional[str] = None,
) -> FollowupSummary:
    """
    Agrega outcomes dos followups respondidos no periodo, particionados
    por followup_type (D+3/D+7/D+15) com response rate por tipo.
    """
    now = _utcnow()
    since = now - timedelta(days=period_days)

    responded = repo.list_responded_followups(
        tenant_id,
        since=since,
        until=now,
        plan_name_like=plan_name_like,
    )

    # Outcomes por tipo
    by_type_outcomes: dict[str, dict[str, int]] = {}
    for row in responded:
        outcome = classify_response_text(row.get("response_text"))
        ftype = str(row["followup_type"])
        by_type_outcomes.setdefault(
            ftype, {OUTCOME_IMPROVED: 0, OUTCOME_UNCHANGED: 0, OUTCOME_WORSENED: 0}
        )
        by_type_outcomes[ftype][outcome] += 1

    # Counts globais para response_rate (independem do plan_name_like
    # porque o universo de "enviados" precisa cobrir tudo)
    counts = repo.count_followups_by_status(tenant_id, since=since, until=now)

    # counts shape: {'d3::sent': N, 'd3::responded': M, ...}
    sent_total = 0
    responded_total = 0
    by_type_response_rate: dict[str, float] = {}
    sent_by_type: dict[str, int] = {}
    responded_by_type: dict[str, int] = {}
    for key, n in counts.items():
        ftype, status = key.split("::", 1)
        # 'sent', 'responded', 'failed', 'cancelled' contam como enviados;
        # 'pending' nao conta como tentativa concluida.
        if status != "pending":
            sent_by_type[ftype] = sent_by_type.get(ftype, 0) + n
            sent_total += n
        if status == "responded":
            responded_by_type[ftype] = responded_by_type.get(ftype, 0) + n
            responded_total += n

    for ftype, sent_n in sent_by_type.items():
        if sent_n > 0:
            by_type_response_rate[ftype] = responded_by_type.get(ftype, 0) / sent_n
        else:
            by_type_response_rate[ftype] = 0.0

    overall_rate = (responded_total / sent_total) if sent_total else 0.0

    return FollowupSummary(
        period_days=period_days,
        total_sent=sent_total,
        total_responded=responded_total,
        response_rate=overall_rate,
        by_type_outcomes=by_type_outcomes,
        by_type_response_rate=by_type_response_rate,
    )


def correlate_dose_effect(
    tenant_id: int,
    condition_name: str,
    *,
    metric: str = "pain_level",
    baseline_window_days: int = 30,
    post_window_start_days: int = 30,
    post_window_end_days: int = 90,
) -> list[DoseEffectPoint]:
    """
    Para cada treatment_plan ativo cujo plan_name/description menciona
    `condition_name`, computa baseline e post de uma metrica do diario.

    Janela:
      - baseline = [plan_started_at - baseline_window_days, plan_started_at)
      - post     = [plan_started_at + post_window_start_days,
                    plan_started_at + post_window_end_days)

    Pacientes sem nenhum dado de baseline OU post sao pulados (nao
    representam ponto valido de correlacao).
    """
    plans = repo.list_treatment_plans_by_condition(
        tenant_id, condition_name, only_active=True
    )

    points: list[DoseEffectPoint] = []
    for plan in plans:
        plan_started: datetime = plan["plan_started_at"]

        baseline_since = plan_started - timedelta(days=baseline_window_days)
        baseline = repo.aggregate_diary_metric(
            patient_id=plan["patient_id"],
            since=baseline_since,
            until=plan_started,
            metric=metric,
        )

        post_since = plan_started + timedelta(days=post_window_start_days)
        post_until = plan_started + timedelta(days=post_window_end_days)
        post = repo.aggregate_diary_metric(
            patient_id=plan["patient_id"],
            since=post_since,
            until=post_until,
            metric=metric,
        )

        if baseline["n"] == 0 and post["n"] == 0:
            # Sem dado nenhum — nao gera ponto de correlacao.
            continue

        delta: Optional[float] = None
        if baseline["mean"] is not None and post["mean"] is not None:
            delta = float(post["mean"]) - float(baseline["mean"])

        points.append(
            DoseEffectPoint(
                patient_id=int(plan["patient_id"]),
                plan_id=int(plan["plan_id"]),
                dose_label=plan.get("dosage"),
                cbd_thc_ratio=plan.get("cbd_thc_ratio"),
                plan_started_at=plan_started,
                metric=metric,
                baseline_mean=baseline["mean"],
                baseline_n=baseline["n"],
                post_mean=post["mean"],
                post_n=post["n"],
                score_delta=delta,
            )
        )

    return points


def aggregate_longitudinal_by_condition(
    tenant_id: int,
    condition_name: str,
    *,
    period_days: int = 180,
    metric: str = "pain_level",
    baseline_window_days: int = 30,
    post_window_start_days: int = 30,
    post_window_end_days: int = 90,
) -> CohortSummary:
    """
    Agregado pooled da cohort: medias agregadas de baseline e post + N
    pacientes/planos.

    Computa internamente os mesmos pontos de correlate_dose_effect e
    pondera as medias pelo N de cada paciente (mean ponderada).
    """
    points = correlate_dose_effect(
        tenant_id,
        condition_name,
        metric=metric,
        baseline_window_days=baseline_window_days,
        post_window_start_days=post_window_start_days,
        post_window_end_days=post_window_end_days,
    )
    n_plans = len(points)
    n_patients = len({p.patient_id for p in points})

    # Mean ponderada por N de amostras
    def _weighted_mean(values_with_n: list[tuple[float, int]]) -> Optional[float]:
        weighted = [(v * n, n) for v, n in values_with_n if v is not None and n > 0]
        if not weighted:
            return None
        total_w = sum(n for _, n in weighted)
        if total_w == 0:
            return None
        return sum(num for num, _ in weighted) / total_w

    baseline_pairs = [
        (p.baseline_mean, p.baseline_n) for p in points if p.baseline_mean is not None
    ]
    post_pairs = [
        (p.post_mean, p.post_n) for p in points if p.post_mean is not None
    ]

    baseline_pool = _weighted_mean(baseline_pairs)
    post_pool = _weighted_mean(post_pairs)
    pooled_delta: Optional[float] = None
    if baseline_pool is not None and post_pool is not None:
        pooled_delta = post_pool - baseline_pool

    return CohortSummary(
        tenant_id=tenant_id,
        condition_name=condition_name,
        period_days=period_days,
        n_patients=n_patients,
        n_treatment_plans=n_plans,
        pooled_baseline_pain_mean=baseline_pool,
        pooled_post_pain_mean=post_pool,
        pooled_pain_delta=pooled_delta,
    )


def build_evidence_summary(
    tenant_id: int,
    condition_name: str,
    *,
    period_days: int = 180,
    metric: str = "pain_level",
    baseline_window_days: int = 30,
    post_window_start_days: int = 30,
    post_window_end_days: int = 90,
    sample_outcomes_n: int = 10,
) -> EvidenceSummary:
    """
    Snapshot completo: cohort + dose_effect + followup_summary + sample
    de outcomes ilustrativos. Saida pronta para template regulatorio.
    """
    cohort = aggregate_longitudinal_by_condition(
        tenant_id,
        condition_name,
        period_days=period_days,
        metric=metric,
        baseline_window_days=baseline_window_days,
        post_window_start_days=post_window_start_days,
        post_window_end_days=post_window_end_days,
    )
    dose_points = correlate_dose_effect(
        tenant_id,
        condition_name,
        metric=metric,
        baseline_window_days=baseline_window_days,
        post_window_start_days=post_window_start_days,
        post_window_end_days=post_window_end_days,
    )
    followup_sum = summarize_followup_responses(
        tenant_id,
        period_days=period_days,
        plan_name_like=condition_name,
    )

    # Sample de outcomes — primeiros N do periodo, filtrados pela condicao
    now = _utcnow()
    since = now - timedelta(days=period_days)
    responded = repo.list_responded_followups(
        tenant_id, since=since, until=now, plan_name_like=condition_name
    )
    sample = tuple(_row_to_outcome(r) for r in responded[:sample_outcomes_n])

    return EvidenceSummary(
        tenant_id=tenant_id,
        condition_name=condition_name,
        period_days=period_days,
        generated_at=now,
        baseline_window_days=baseline_window_days,
        post_window_start_days=post_window_start_days,
        post_window_end_days=post_window_end_days,
        cohort=cohort,
        dose_effect_points=tuple(dose_points),
        followup_summary=followup_sum,
        sample_outcomes=sample,
    )
