"""REG-8 — relatório de prontidão regulatória por tenant (RDCs 2026).

Análogo a `check_sandbox_eligibility`: comunica ao tenant o que pode operar a
partir da vigência 04/08/2026 e o que segue condicionado/vedado, consumindo o
estado de REG-1..4 + o calendário (`regulatory_calendar`). Prontidão regulatória,
nunca aprovação — a Anvisa decide; o médico é o decisor clínico (B6).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

from src.services.regulatory_calendar import RDC_2026_VIGENCIA, is_rdc_2026_in_effect

# available = pode operar; conditioned = condicionado (ex.: condição grave);
# pending = aguarda vigência; blocked = vedado até a vigência.
ReadinessStatus = Literal["available", "conditioned", "pending", "blocked"]


@dataclass(frozen=True)
class ReadinessFinding:
    code: str
    status: ReadinessStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RegulatoryReadinessReport:
    tenant_id: int
    checked_at: datetime
    rdc_2026_in_effect: bool
    vigencia_date: str
    findings: list[ReadinessFinding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "checked_at": self.checked_at.isoformat(),
            "rdc_2026_in_effect": self.rdc_2026_in_effect,
            "vigencia_date": self.vigencia_date,
            "findings": [asdict(f) for f in self.findings],
        }


def check_regulatory_readiness(
    tenant_id: int, today: Optional[date] = None
) -> RegulatoryReadinessReport:
    """Monta o relatório de prontidão regulatória do tenant (REG-8)."""
    in_effect = is_rdc_2026_in_effect(today)
    vigencia = RDC_2026_VIGENCIA.isoformat()
    findings: list[ReadinessFinding] = []

    # 1. Vigência das RDCs de 2026 (REG-1/4/8)
    findings.append(ReadinessFinding(
        code="rdc_2026_vigencia",
        status="available" if in_effect else "pending",
        message=(
            "RDCs de 2026 em vigência — novas regras aplicáveis."
            if in_effect else
            f"RDCs de 2026 entram em vigência em {vigencia}; até lá vale o "
            "comportamento atual."
        ),
        details={"vigencia": vigencia},
    ))

    # 2. Via inalatória (REG-1)
    findings.append(ReadinessFinding(
        code="via_inalatoria",
        status="conditioned" if in_effect else "blocked",
        message=(
            "Via inalatória regulamentada, condicionada a condição grave/"
            "debilitante ou paliativa registrada (REG-3/REG-4)."
            if in_effect else
            "Via inalatória ainda não regulamentada (até a vigência 04/08/2026)."
        ),
    ))

    # 3. Via tópica/dermatológica (REG-2) — disponível no Rules Engine
    findings.append(ReadinessFinding(
        code="via_topica_dermatologica",
        status="available",
        message=(
            "Via tópica/dermatológica disponível no Rules Engine "
            "(protocolos de referência, ajustáveis pelo médico)."
        ),
    ))

    # 4. THC > 0,2% (REG-4)
    findings.append(ReadinessFinding(
        code="thc_acima_0_2",
        status="conditioned" if in_effect else "blocked",
        message=(
            "Produtos com THC > 0,2% permitidos para condição grave/debilitante "
            "ou paliativa registrada; contraindicado a <18, gestantes e lactantes."
            if in_effect else
            "Produtos com THC > 0,2% condicionados à vigência das RDCs de 2026."
        ),
    ))

    # 5. Prescritor habilitado + TCLE (RDC 1.015/2026, JÁ vigente)
    findings.append(ReadinessFinding(
        code="prescritor_tcle",
        status="available",
        message=(
            "RDC 1.015/2026 vigente: prescritor habilitado + TCLE vinculados à "
            "prescrição e auditados (prontidão mínima já no fluxo)."
        ),
    ))

    return RegulatoryReadinessReport(
        tenant_id=tenant_id,
        checked_at=datetime.now(timezone.utc),
        rdc_2026_in_effect=in_effect,
        vigencia_date=vigencia,
        findings=findings,
    )
