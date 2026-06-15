"""Calendário regulatório — vigência das RDCs de 2026 (Onda 2 / Track REG).

Fonte única da decisão "as RDCs de 2026 já estão em vigência?" para os itens
REG-1/REG-4/REG-8. As RDCs 1.011–1.015/2026 (DOU 03/02/2026) têm vigência em
**04/08/2026** (cultivo/sandbox/vias de administração/THC > 0,2%). A 1.015
(prescrição/TCLE) já vigora desde a publicação e é tratada à parte (REG-1015);
este gate cobre o conjunto cuja vigência é 04/08/2026.

Antes da vigência, o comportamento regulatório atual é mantido. A flag é por
DATA (global), com override por env para testes e habilitação antecipada —
prontidão regulatória, nunca aprovação (a Anvisa decide).
"""
from __future__ import annotations

import os
from datetime import date

# Vigência das RDCs de 2026 (vias de administração, THC > 0,2%, cultivo/sandbox).
RDC_2026_VIGENCIA = date(2026, 8, 4)

_FORCE_ENV = "FF_RDC_2026_FORCE"
_TRUE = {"1", "true", "on", "yes", "sim"}
_FALSE = {"0", "false", "off", "no", "nao", "não"}


def is_rdc_2026_in_effect(today: date | None = None) -> bool:
    """True se as RDCs de 2026 com vigência 04/08/2026 já estão em vigor.

    Override por env ``FF_RDC_2026_FORCE`` (testes / habilitação antecipada):
    valores em ``_TRUE`` forçam em vigência; em ``_FALSE`` forçam fora. Sem
    override, compara ``today`` (default ``date.today()``) com 04/08/2026.
    """
    force = os.getenv(_FORCE_ENV, "").strip().lower()
    if force in _TRUE:
        return True
    if force in _FALSE:
        return False
    return (today or date.today()) >= RDC_2026_VIGENCIA
