# src/ai/agents/regulatorio.py
"""Agente Regulatorio — verifica compliance ANVISA/CFM usando Google Files
API + skill de elegibilidade ao Sandbox (F1.6 do docs/BACKLOG_SCC.md) +
skill de triagem de eventos adversos (F3.4 do docs/BACKLOG_SCC.md)."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from src.ai.agents.base import AgentResult, BaseAgent

logger = logging.getLogger("cannabia.regulatorio_agent")


# ===========================================================================
# F3.4 — triagem heuristica de eventos adversos
# ===========================================================================
#
# Abordagem deterministica PT-BR (sem LLM no caminho), alinhada com a
# decisao tomada em F4.1 (classify_response_text): auditavel, reproduzivel,
# sem custo de AI. Pode ser substituida por um modelo com a mesma
# interface sem quebrar consumidores — o shape de saida e estavel e
# versionado via `TRIAGE_MODEL_VERSION`.

TRIAGE_MODEL_VERSION: str = "regulatorio-triage-v1-heuristic"

# Ordem canonica das severidades, alinhada com a whitelist da migration 031
# e com `SEVERITY_CHOICES` do `adverse_event_service`.
_TRIAGE_SEVERITY_ORDER: tuple[str, ...] = (
    "mild",
    "moderate",
    "severe",
    "life_threatening",
    "fatal",
)
_TRIAGE_SEVERITY_RANK: dict[str, int] = {
    s: i for i, s in enumerate(_TRIAGE_SEVERITY_ORDER, 1)
}

# Whitelist de severidades que disparam notificacao regulatoria automatica.
# Espelha `NOTIFIABLE_SEVERITIES` do adverse_event_service — duplicada aqui
# para manter o agente independente do service (teste de unidade puro).
_TRIAGE_NOTIFIABLE: frozenset[str] = frozenset(
    {"severe", "life_threatening", "fatal"}
)

# Padroes PT-BR por nivel de severidade implicada. Lista expandivel sem
# alterar o algoritmo de max-rank.
_TRIAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fatal": (
        r"\b[óo]bito\b",
        r"\bfalecim",
        r"\bmorreu\b",
        r"\bmorte\b",
    ),
    "life_threatening": (
        r"\bparada\s+card",
        r"\bparada\s+resp",
        r"\banafila",
        r"\bchoque\s+anaf",
        r"\bcoma\b",
        r"\binconsci",
        r"\bconvuls",
        r"\boverdose\b",
        r"\bsuicid",
        r"\bUTI\b",
        r"\bintub",
        r"\bentub",
    ),
    "severe": (
        r"\binternad",
        r"\bhospitaliz",
        r"\bemerg[êe]nc",
        r"\bpronto[-\s]socorro",
        r"\bUPA\b",
        r"\bpsicose\b",
        r"\balucina",
        r"\barritmia",
        r"\btaquicardia\s+(severa|intensa|importante)",
        r"\bpress[ãa]o\s+(muito\s+)?alt",
    ),
    "moderate": (
        r"\bv[ôo]mitos?\s+(repetid|freq)",
        r"\btontura\s+(forte|intensa)",
        r"\bconfus[ãa]o\s+mental",
        r"\bpalpita[cç][ãa]o",
        r"\bvis[ãa]o\s+turva",
        r"\bcrise\s+(de|forte|intensa)",
    ),
}

_TRIAGE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    level: tuple(re.compile(p, re.IGNORECASE) for p in patterns)
    for level, patterns in _TRIAGE_KEYWORDS.items()
}


def _read_attr(report: Any, name: str) -> Any:
    """Le um campo de `report`, aceitando dict ou objeto com atributos.

    Util para deixar a skill consumir tanto um payload cru
    (ex.: vindo de blueprint/webhook) quanto a dataclass
    `AdverseEvent` do `adverse_event_service`.
    """
    if report is None:
        return None
    if isinstance(report, dict):
        return report.get(name)
    return getattr(report, name, None)


def check_anvisa(prescription: dict) -> dict:
    """
    Verificação determinística de conformidade ANVISA de uma prescrição
    (CLI-3 / 29.2 R3). Norma condicionada à vigência: RDC 327/2019 (pré-04/08/2026)
    → RDC 1.015/2026 (pós; revoga a 327, Art. 76); RDC 660/2022 segue vigente.

    **Não bloqueia** a emissão — é um *warning auditado*: o médico é o decisor
    final e a aprovação regulatória é prerrogativa da Anvisa. Retorna
    {compliant, issues, checked_norms}.
    """
    from src.services.regulatory_calendar import is_rdc_2026_in_effect

    ratio = prescription.get("cannabinoid_ratio", "") or ""
    route = prescription.get("administration_route", "") or ""
    thc_mg = prescription.get("max_daily_mg", 0)
    regulatory_condition = (prescription.get("regulatory_condition") or "nenhuma")

    rdc_2026 = is_rdc_2026_in_effect()
    issues = []
    if "thc" in ratio.lower() and float(thc_mg or 0) > 40:
        # REG-7 — citação do marco condicionada à vigência (327 revogada pela 1.015).
        _norma_thc = "RDC 1.015/2026" if rdc_2026 else "RDC 327/2019 Art. 8"
        issues.append(f"THC > 40mg/dia requer justificativa especial ({_norma_thc})")

    # REG-1 — via inalatória condicionada à vigência das RDCs de 2026 (04/08/2026).
    # Antes da vigência: mantém o aviso atual ("não regulamentada"). A partir da
    # vigência: regulamentada, porém condicionada a condição grave/debilitante ou
    # paliativa registrada (REG-3/REG-4). Em qualquer caso é WARNING auditado —
    # NUNCA bloqueia a emissão (B6: o médico é o decisor).
    if route == "inalatorio":
        if not rdc_2026:
            issues.append("Via inalatoria nao regulamentada pela ANVISA para cannabis medicinal")
        elif regulatory_condition == "nenhuma":
            issues.append(
                "Via inalatoria exige condicao grave/debilitante ou paliativa "
                "registrada (RDCs 2026)"
            )

    # Pós-vigência a RDC 327/2019 é revogada pela 1.015/2026 (Art. 76); 660/2022
    # segue vigente.
    checked_norms = ["RDC 1.015/2026" if rdc_2026 else "RDC 327/2019", "RDC 660/2022"]

    return {
        "compliant": len(issues) == 0,
        "issues": issues,
        "checked_norms": checked_norms,
    }


def validate_prescriber_habilitation(
    doctor_crm: Optional[str], doctor_user_id: Optional[int] = None
) -> dict:
    """
    Validação MÍNIMA de prescritor habilitado para a RDC 1.015/2026 (já em vigor)
    — REG-1015. Mínimo vigente verificável no fluxo atual: CRM presente.

    A validação plena (conselho/UF, situação ativa no CFM, vínculo do prescritor)
    fica como PENDÊNCIA DE REVALIDAÇÃO contra o inteiro teor da RDC 1.015 (PDF
    escaneado lido via RAG). Não bloqueia a emissão — é prontidão auditada.
    """
    crm = (doctor_crm or "").strip()
    habilitado = bool(crm)
    return {
        "habilitado": habilitado,
        "reason": "CRM do prescritor presente" if habilitado else "CRM do prescritor ausente",
        "norm_ref": "RDC 1.015/2026",
        "pending_revalidation": True,
    }


class AgenteRegulatorio(BaseAgent):
    agent_name = "regulatorio"
    description = "Verifica compliance regulatoria ANVISA/CFM + elegibilidade Sandbox"

    def _register_skills(self):
        self.register_skill(
            "check_anvisa_compliance",
            self._check_anvisa,
            "Verifica se prescricao atende RDC 1.015/2026 e normas ANVISA",
        )
        self.register_skill(
            "query_legislation",
            self._query_legislation,
            "Consulta legislacao com contexto completo via Google Files API",
        )
        self.register_skill(
            "check_sandbox_eligibility",
            self._check_sandbox_eligibility,
            "Valida elegibilidade da associacao ao Sandbox Regulatorio (RDC 1.014/2026)",
        )
        self.register_skill(
            "triage_adverse_event",
            self._triage_adverse_event,
            "Triagem heuristica de evento adverso: severidade sugerida + notify_required",
        )

    # =====================================================================
    # Skills existentes
    # =====================================================================

    def _check_anvisa(self, prescription: dict, **kwargs) -> dict:
        return check_anvisa(prescription)

    def _query_legislation(self, question: str, **kwargs) -> dict:
        try:
            from src.knowledge.google_files import query_legislation_structured

            result, usage = query_legislation_structured(question, kwargs.get("file_names"))
            return {"result": result, "usage": usage, "source": "google_files_api"}
        except Exception as e:
            return {
                "result": {"answer": f"Erro ao consultar legislacao: {e}", "citations": []},
                "usage": {},
                "source": "error",
            }

    # =====================================================================
    # Skill nova: elegibilidade Sandbox (F1.6)
    # =====================================================================

    def _check_sandbox_eligibility(
        self,
        tenant_id: Optional[int] = None,
        association: Optional[dict] = None,
        **_kwargs,
    ) -> dict:
        """Executa a validacao formal de elegibilidade ao Sandbox e empacota
        o resultado num formato que o Orchestrador e o usuario final podem
        consumir: veredicto + blockers acionaveis + warnings.

        Aceita ``tenant_id`` direto ou um dict ``association`` contendo
        ``tenant_id`` — assinatura do BACKLOG permite qualquer uma.
        """
        resolved_tenant_id = tenant_id
        if resolved_tenant_id is None and association:
            resolved_tenant_id = association.get("tenant_id") or association.get("id")
        if resolved_tenant_id is None:
            return {
                "ok": False,
                "error": "tenant_id obrigatorio (ou association com tenant_id).",
            }

        try:
            from src.services.governance_service import check_sandbox_eligibility
        except ImportError as exc:  # pragma: no cover
            return {"ok": False, "error": f"Servico indisponivel: {exc}"}

        try:
            report = check_sandbox_eligibility(int(resolved_tenant_id))
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "tenant_id": resolved_tenant_id}

        findings_summary = [
            {"code": f.code, "status": f.status, "message": f.message}
            for f in report.findings
        ]
        blockers = [
            {"code": f.code, "action": self._action_for(f.code, f.message)}
            for f in report.findings
            if f.status == "fail"
        ]
        warnings = [
            {"code": f.code, "message": f.message}
            for f in report.findings
            if f.status == "warn"
        ]

        # Audit trail via MemPalace foi extirpado em Track C.2 — eventos
        # operacionais que precisam de auditoria devem usar audit_trail
        # (migrations/008_audit_trail.sql) explicitamente.

        return {
            "ok": True,
            "tenant_id": int(resolved_tenant_id),
            "is_eligible": report.is_eligible,
            "has_warnings": report.has_warnings,
            "findings": findings_summary,
            "blockers": blockers,
            "warnings": warnings,
            "checked_norm": "RDC 1.014/2026",
        }

    @staticmethod
    def _action_for(code: str, fallback_message: str) -> str:
        """Traduz o code de um finding fail em uma acao operacional clara
        para a associacao. O fallback e a mensagem do proprio finding."""
        ACTIONS: dict[str, str] = {
            "legal_nature": (
                "Atualize o cadastro para tenant_type='association'. "
                "Clinicas e medicos independentes nao sao elegiveis."
            ),
            "incorporation_time": (
                "Preencha incorporation_date no cadastro institucional. "
                "A RDC exige pelo menos 2 anos de constituicao."
            ),
            "active_technical_responsible": (
                "Cadastre ao menos um Responsavel Tecnico ativo em "
                "/api/v1/governance/rts com habilitation_valid_until futura."
            ),
            "technical_operational_capacity": (
                "Registre uma avaliacao de capacidade em "
                "/api/v1/governance/capacity (scores de infraestrutura, "
                "RH, processos e escala proposta)."
            ),
        }
        return ACTIONS.get(code, fallback_message)

    # =====================================================================
    # Skill nova: triagem de evento adverso (F3.4)
    # =====================================================================

    def _triage_adverse_event(
        self,
        report: Optional[dict] = None,
        *,
        persist: bool = False,
        event_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
        triaged_by: Optional[int] = None,
        **_kwargs: Any,
    ) -> dict:
        """Classifica um evento adverso em severidade sugerida + necessidade
        de notificacao regulatoria a partir do texto livre e da severidade
        reportada.

        Algoritmo deterministico (regex PT-BR sobre `description`):
          1. `severity_reported` = normalizado para a whitelist.
          2. Para cada nivel de `_TRIAGE_PATTERNS`, marca hit se bate.
          3. `severity_suggested` = max(reportada, maior nivel com hit).
          4. `notify_required` = severity_suggested em `_TRIAGE_NOTIFIABLE`.
          5. `escalated` = severity_suggested > severity_reported.

        Persistencia opt-in: quando `persist=True`, grava o shape completo
        em `adverse_events.ai_triage_result` via
        `adverse_event_service.record_triage_result`. Requer `event_id` e
        `tenant_id`.

        Aceita `report` como dict ou qualquer objeto com atributos
        `description`/`severity` (ex.: dataclass `AdverseEvent`).
        """
        if report is None:
            return {"ok": False, "error": "report obrigatorio"}

        description = _read_attr(report, "description")
        severity_reported = _read_attr(report, "severity")

        if not description or not str(description).strip():
            return {
                "ok": False,
                "error": "report.description ausente ou vazio",
                "model_version": TRIAGE_MODEL_VERSION,
            }
        if severity_reported not in _TRIAGE_SEVERITY_RANK:
            return {
                "ok": False,
                "error": (
                    f"report.severity invalido: {severity_reported!r}. "
                    f"Esperado um de {_TRIAGE_SEVERITY_ORDER}"
                ),
                "model_version": TRIAGE_MODEL_VERSION,
            }

        reported_rank = _TRIAGE_SEVERITY_RANK[severity_reported]
        matched: dict[str, list[str]] = {}
        max_rank = reported_rank
        for level, patterns in _TRIAGE_PATTERNS.items():
            hits: list[str] = []
            for pat in patterns:
                m = pat.search(description)
                if m:
                    hits.append(m.group(0).lower())
            if hits:
                matched[level] = hits
                level_rank = _TRIAGE_SEVERITY_RANK[level]
                if level_rank > max_rank:
                    max_rank = level_rank

        severity_suggested = _TRIAGE_SEVERITY_ORDER[max_rank - 1]
        escalated = max_rank > reported_rank
        notify_required = severity_suggested in _TRIAGE_NOTIFIABLE

        red_flags = sorted({flag for flags in matched.values() for flag in flags})

        if escalated:
            reasoning = (
                f"Severidade escalada de {severity_reported!r} para "
                f"{severity_suggested!r} por red flags detectados na "
                f"descricao: {red_flags}."
            )
        elif red_flags:
            reasoning = (
                f"Red flags detectados ({red_flags}) sao compativeis com "
                f"a severidade reportada ({severity_reported!r}); mantida."
            )
        else:
            reasoning = (
                f"Sem red flags na descricao; severidade mantida em "
                f"{severity_reported!r}."
            )

        output: dict[str, Any] = {
            "ok": True,
            "severity_reported": severity_reported,
            "severity_suggested": severity_suggested,
            "escalated": escalated,
            "notify_required": notify_required,
            "red_flags": red_flags,
            "matched_by_level": matched,
            "reasoning": reasoning,
            "model_version": TRIAGE_MODEL_VERSION,
        }

        # Audit trail via MemPalace foi extirpado em Track C.2; resultado
        # da triagem volta intacto pra caller que persiste em
        # adverse_events.ai_triage_result quando opt-in.

        # Persistencia opt-in em adverse_events.ai_triage_result.
        if persist:
            if event_id is None or tenant_id is None:
                output["persist_error"] = (
                    "persist=True requer event_id e tenant_id"
                )
            else:
                try:
                    from src.services.adverse_event_service import (
                        record_triage_result,
                    )

                    updated = record_triage_result(
                        int(event_id),
                        tenant_id=int(tenant_id),
                        ai_triage_result=output,
                        triaged_by=triaged_by,
                    )
                    output["persisted"] = updated is not None
                    if updated is None:
                        output["persist_error"] = (
                            f"evento {event_id} nao encontrado para tenant "
                            f"{tenant_id}"
                        )
                except Exception as exc:  # pragma: no cover — defensivo
                    logger.warning(
                        "triage_adverse_event: falha ao persistir %s", exc
                    )
                    output["persist_error"] = str(exc)

        return output

    # =====================================================================
    # Execute
    # =====================================================================

    def execute(self, **kwargs: Any) -> AgentResult:
        prescription = kwargs.get("prescription", kwargs.get("recommendation", {}))
        question = kwargs.get("question")
        tenant_id = kwargs.get("tenant_id")
        association = kwargs.get("association")

        skills_used: list[str] = []

        if prescription:
            compliance = self.invoke_skill("check_anvisa_compliance", prescription=prescription)
            skills_used.append("check_anvisa_compliance")
            # Compliance issues sao retornadas no compliance dict; diary
            # via MemPalace foi extirpado em Track C.2.
        else:
            compliance = {"compliant": True, "issues": [], "checked_norms": []}

        legislation_result = None
        if question:
            legislation_result = self.invoke_skill("query_legislation", question=question)
            skills_used.append("query_legislation")

        eligibility_result = None
        if tenant_id is not None or association:
            eligibility_result = self.invoke_skill(
                "check_sandbox_eligibility",
                tenant_id=tenant_id,
                association=association,
            )
            skills_used.append("check_sandbox_eligibility")

        # Confidence composta: compliance sozinho calibra 0.9/0.6 como antes.
        # Se houve check de elegibilidade e ela falhou, rebaixa para 0.5.
        confidence = 0.9 if compliance["compliant"] else 0.6
        if eligibility_result and eligibility_result.get("ok") and not eligibility_result.get("is_eligible"):
            confidence = min(confidence, 0.5)

        return AgentResult(
            success=True,
            data={
                "compliance": compliance,
                "legislation": legislation_result,
                "sandbox_eligibility": eligibility_result,
            },
            confidence=confidence,
            skills_used=skills_used,
        )
