"""Service do dominio governance (F1.4 do docs/BACKLOG_SCC.md).

Responsavel pela **validacao automatica de elegibilidade** de uma
associacao ao Sandbox Compliance Core, conforme doc 23 §4.1:

  1. Pessoa juridica sem fins lucrativos (tenant_type == 'association')
  2. Minimo de 2 anos de constituicao (incorporation_date)
  3. Responsavel Tecnico legalmente habilitado (RT ativo nao vencido)
  4. Capacidade Tecnico-Operacional avaliada (assessment existe)

A verificacao produz um ``EligibilityReport`` com uma lista de
``EligibilityFinding``. Cada finding tem:

- ``code``    : chave estavel (consumida por frontend/agente/dossier)
- ``status``  : ``pass``/``fail``/``warn``
- ``message`` : texto legivel em pt-BR
- ``details`` : dict com valores observados (datas, contagens, ids)

Uma associacao e elegivel se **nenhum** finding esta em ``fail``.
``warn`` nao bloqueia mas sinaliza pendencia documental (ex.: estatuto
nao anexado — so necessario para a submissao final).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

from src.infra.database import db_cursor
from src.repositories import governance_repository as repo

logger = logging.getLogger("cannabia.governance_service")


# ---------------------------------------------------------------------
# Constantes regulatorias (doc 23 §4.1, RDC 1.014/2026)
# ---------------------------------------------------------------------

MIN_YEARS_OF_INCORPORATION = 2
ELIGIBLE_TENANT_TYPE = "association"
STATUTE_DOCUMENT_TYPE = "statute"


# ---------------------------------------------------------------------
# Modelos de retorno
# ---------------------------------------------------------------------

FindingStatus = Literal["pass", "fail", "warn"]


@dataclass(frozen=True)
class EligibilityFinding:
    code: str
    status: FindingStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EligibilityReport:
    tenant_id: int
    checked_at: datetime
    findings: list[EligibilityFinding]

    @property
    def is_eligible(self) -> bool:
        return not any(f.status == "fail" for f in self.findings)

    @property
    def has_warnings(self) -> bool:
        return any(f.status == "warn" for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "checked_at": self.checked_at.isoformat(),
            "is_eligible": self.is_eligible,
            "has_warnings": self.has_warnings,
            "findings": [asdict(f) for f in self.findings],
        }


# ---------------------------------------------------------------------
# Utilitarios internos
# ---------------------------------------------------------------------

def _get_tenant(tenant_id: int) -> Optional[dict[str, Any]]:
    """Le os campos de tenants necessarios para os checks de elegibilidade."""
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, tenant_type, incorporation_date, status, legal_name
              FROM tenants
             WHERE id = %s
            """,
            (tenant_id,),
        )
        return cursor.fetchone()


def _years_since(dt: date, reference: date) -> float:
    delta = reference - dt
    return delta.days / 365.25


def _is_rt_currently_habilitated(rt: dict[str, Any], today: date) -> bool:
    """Um RT esta habilitado se esta ativo E a validade do registro no
    conselho ou nao esta preenchida ou nao expirou. O campo NULL e
    interpretado como 'sem prazo conhecido' — tratado como pendencia
    documental, nao como invalidez. Retorna True apenas quando o RT
    comprovadamente esta dentro da vigencia."""
    if not rt.get("is_active", False):
        return False
    habilitation = rt.get("habilitation_valid_until")
    return habilitation is not None and habilitation >= today


# ---------------------------------------------------------------------
# Checks individuais (cada um retorna UM finding)
# ---------------------------------------------------------------------

def _check_legal_nature(tenant: dict[str, Any]) -> EligibilityFinding:
    tenant_type = tenant.get("tenant_type")
    if tenant_type == ELIGIBLE_TENANT_TYPE:
        return EligibilityFinding(
            code="legal_nature",
            status="pass",
            message="Tenant cadastrado como associacao (pessoa juridica sem fins lucrativos).",
            details={"tenant_type": tenant_type},
        )
    return EligibilityFinding(
        code="legal_nature",
        status="fail",
        message=(
            "RDC 1.014/2026 exige pessoa juridica sem fins lucrativos. "
            f"Tenant atual e do tipo '{tenant_type}'."
        ),
        details={"tenant_type": tenant_type, "expected": ELIGIBLE_TENANT_TYPE},
    )


def _check_incorporation_time(
    tenant: dict[str, Any], today: date
) -> EligibilityFinding:
    incorporation = tenant.get("incorporation_date")
    if incorporation is None:
        return EligibilityFinding(
            code="incorporation_time",
            status="fail",
            message="Data de constituicao nao informada.",
            details={"incorporation_date": None},
        )

    years = _years_since(incorporation, today)
    if years >= MIN_YEARS_OF_INCORPORATION:
        return EligibilityFinding(
            code="incorporation_time",
            status="pass",
            message=f"Tempo de constituicao: {years:.1f} anos.",
            details={
                "incorporation_date": incorporation.isoformat(),
                "years": round(years, 2),
                "minimum_required": MIN_YEARS_OF_INCORPORATION,
            },
        )

    return EligibilityFinding(
        code="incorporation_time",
        status="fail",
        message=(
            f"Tempo minimo de {MIN_YEARS_OF_INCORPORATION} anos nao atingido "
            f"(constituicao em {incorporation.isoformat()}, {years:.1f} anos)."
        ),
        details={
            "incorporation_date": incorporation.isoformat(),
            "years": round(years, 2),
            "minimum_required": MIN_YEARS_OF_INCORPORATION,
        },
    )


def _check_active_technical_responsible(
    tenant_id: int, today: date
) -> EligibilityFinding:
    rts = repo.list_technical_responsibles(tenant_id=tenant_id, active_only=True)
    if not rts:
        return EligibilityFinding(
            code="active_technical_responsible",
            status="fail",
            message="Nenhum Responsavel Tecnico ativo cadastrado.",
            details={"active_count": 0},
        )

    habilitated = [rt for rt in rts if _is_rt_currently_habilitated(rt, today)]
    if habilitated:
        rt = habilitated[0]
        return EligibilityFinding(
            code="active_technical_responsible",
            status="pass",
            message=(
                f"RT habilitado encontrado: {rt['full_name']} "
                f"({rt['professional_council']} {rt['council_number']}/{rt['council_state']})."
            ),
            details={
                "active_count": len(rts),
                "habilitated_count": len(habilitated),
                "habilitated_id": rt["id"],
            },
        )

    # RT(s) ativo(s) existem mas sem habilitacao vigente (vencida ou nula).
    return EligibilityFinding(
        code="active_technical_responsible",
        status="fail",
        message=(
            "Responsavel(is) Tecnico(s) ativos encontrados, mas sem vigencia "
            "de registro no conselho comprovada. Atualize "
            "habilitation_valid_until."
        ),
        details={
            "active_count": len(rts),
            "habilitated_count": 0,
            "active_ids": [rt["id"] for rt in rts],
        },
    )


def _check_technical_operational_capacity(tenant_id: int) -> EligibilityFinding:
    latest = repo.get_latest_capacity_assessment(tenant_id)
    if latest is None:
        return EligibilityFinding(
            code="technical_operational_capacity",
            status="fail",
            message="Matriz de Capacidade Tecnico-Operacional nao avaliada.",
            details={"has_assessment": False},
        )

    return EligibilityFinding(
        code="technical_operational_capacity",
        status="pass",
        message=(
            f"Avaliacao mais recente: {latest['assessment_date'].isoformat()} "
            f"(readiness={latest.get('overall_readiness')})."
        ),
        details={
            "has_assessment": True,
            "assessment_id": latest["id"],
            "assessment_date": latest["assessment_date"].isoformat(),
            "overall_readiness": (
                float(latest["overall_readiness"])
                if latest.get("overall_readiness") is not None
                else None
            ),
        },
    )


def _check_statute_document(tenant_id: int) -> EligibilityFinding:
    """Soft check: estatuto anexado. Warn nao bloqueia elegibilidade, mas o
    Dossie final (F1.5) nao sai sem estatuto em arquivo."""
    docs = repo.list_institutional_documents(
        tenant_id=tenant_id,
        document_type=STATUTE_DOCUMENT_TYPE,
        active_only=True,
    )
    if docs:
        return EligibilityFinding(
            code="statute_document",
            status="pass",
            message=f"Estatuto ativo anexado (v{docs[0]['version']}).",
            details={"statute_count": len(docs), "latest_id": docs[0]["id"]},
        )
    return EligibilityFinding(
        code="statute_document",
        status="warn",
        message=(
            "Nenhum estatuto ativo anexado. A elegibilidade nao fica bloqueada, "
            "mas a submissao final requer o estatuto em arquivo."
        ),
        details={"statute_count": 0},
    )


# ---------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------

def check_sandbox_eligibility(
    tenant_id: int,
    *,
    today: Optional[date] = None,
) -> EligibilityReport:
    """Executa os 5 checks e retorna o relatorio consolidado.

    ``today`` e opcional para facilitar testes com relogio fixo; em
    producao sempre cai no ``date.today()``.
    """
    effective_today = today or date.today()
    tenant = _get_tenant(tenant_id)
    if tenant is None:
        raise ValueError(f"Tenant {tenant_id} nao encontrado.")

    findings = [
        _check_legal_nature(tenant),
        _check_incorporation_time(tenant, effective_today),
        _check_active_technical_responsible(tenant_id, effective_today),
        _check_technical_operational_capacity(tenant_id),
        _check_statute_document(tenant_id),
    ]

    report = EligibilityReport(
        tenant_id=tenant_id,
        checked_at=datetime.now(timezone.utc),
        findings=findings,
    )
    logger.info(
        "eligibility_check tenant=%s eligible=%s fails=%d warns=%d",
        tenant_id,
        report.is_eligible,
        sum(1 for f in findings if f.status == "fail"),
        sum(1 for f in findings if f.status == "warn"),
    )
    return report


def refresh_eligibility(tenant_id: int) -> EligibilityReport:
    """Reavalia e, se elegivel, marca ``associations.eligibility_validated_at``
    e transiciona ``sandbox_application_status`` de None/not_started para
    ``preparing``. Transicoes apos ``preparing`` (submitted, approved, etc.)
    nao sao tocadas — elas sao orquestradas por operacoes de submissao.
    """
    report = check_sandbox_eligibility(tenant_id)
    if not report.is_eligible:
        return report

    repo.mark_eligibility_validated(tenant_id)

    association = repo.get_association(tenant_id)
    current_status = association.get("sandbox_application_status") if association else None
    if current_status in (None, "not_started"):
        repo.set_sandbox_application_status(tenant_id, "preparing")

    return report
