"""Job de upgrade de ancoragens pendentes (F5.7 do SCC).

Apos ``create_anchor`` (F5.2), cada linha em ``blockchain_anchors`` fica
com ``verification_status = 'pending'`` — a transacao foi submetida mas
ainda nao teve confirmacao on-chain:

- **OTS (F5.3):** commit entra em bloco Bitcoin ~1h depois da submissao
  ao calendar; o arquivo .ots recebe "upgrade" que incorpora o proof
  completo Bitcoin.
- **Polygon (F5.4):** tx precisa de ~10 blocos (~2-3 min) para
  confirmacao resistente a reorg.

Este modulo roda periodicamente (cron/systemd/airflow — ver
[docs/RUNBOOK_ANCHORING.md](../../docs/RUNBOOK_ANCHORING.md))
varrendo pendings e promovendo-os para 'confirmed' ou 'failed'.

Imutabilidade: apenas ``verification_status``, ``verified_at``,
``block_number``, ``block_timestamp`` e ``proof_uri``/``proof_hash``
mudam. Os campos que compoem a prova (merkle_root, transaction_id)
permanecem imutaveis — uma mudanca nesses seria sinal de corrupcao.

API:

- :func:`list_pending_anchors` — candidatos com idade minima.
- :func:`upgrade_anchor` — tenta promover uma ancoragem por id.
- :func:`run_upgrade_sweep` — varre e upgrada em lote.

Clients para OTS/Polygon sao injetaveis (mesmo padrao de F5.3/F5.4) —
testes nao dependem de rede.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.anchor_upgrade")


__all__ = [
    "UpgradeOutcome",
    "UpgradeStatus",
    "list_pending_anchors",
    "upgrade_anchor",
    "run_upgrade_sweep",
]


# ---------------------------------------------------------------------
# Cadencia padrao
# ---------------------------------------------------------------------

# Idade minima do anchor antes de tentar upgrade (evita spam cedo demais).
# OTS precisa de ~1h para o commit Bitcoin; Polygon de ~3min. Usamos o
# valor mais alto como minimo geral — upgrade redundante em Polygon
# (ja confirmado) ainda e idempotente.
MIN_AGE_SECONDS = 5 * 60          # 5 min — seguro para polygon tb
MAX_AGE_FAIL_SECONDS = 48 * 3600   # 48h sem confirmacao -> marca 'failed'


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

class UpgradeStatus:
    CONFIRMED = "confirmed"
    STILL_PENDING = "still_pending"     # underlying ainda nao confirmou
    FAILED = "failed"
    SKIPPED = "skipped"                 # idade insuficiente ou ja nao-pending


@dataclass(frozen=True)
class UpgradeOutcome:
    anchor_id: int
    previous_status: str
    new_status: str                     # um dos UpgradeStatus.*
    verified_at: Optional[datetime]
    block_number: Optional[int]
    block_timestamp: Optional[datetime]
    error: Optional[str] = None


# ---------------------------------------------------------------------
# Repository / leitura
# ---------------------------------------------------------------------

def list_pending_anchors(
    *,
    min_age_seconds: int = MIN_AGE_SECONDS,
    limit: int = 50,
    now: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Retorna ancoragens com status='pending' e idade >= ``min_age_seconds``.

    Ordenado por ``anchored_at ASC`` — mais velhos primeiro, evita
    starvation.
    """
    effective_now = now or datetime.now(timezone.utc)
    threshold = effective_now - timedelta(seconds=min_age_seconds)
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, tenant_id, anchor_scope, blockchain_network,
                   merkle_root, transaction_id, proof_uri, proof_hash,
                   anchored_at, verified_at, verification_status
              FROM blockchain_anchors
             WHERE verification_status = 'pending'
               AND anchored_at <= %s
             ORDER BY anchored_at ASC
             LIMIT %s
            """,
            (threshold, limit),
        )
        return [dict(r) for r in cursor.fetchall()]


# ---------------------------------------------------------------------
# Client probes
# ---------------------------------------------------------------------

# Cada "probe" recebe a row do anchor e retorna um dict com:
#   {'confirmed': bool, 'block_number': int|None,
#    'block_timestamp': datetime|None, 'proof_uri': str|None,
#    'proof_hash': str|None, 'error': str|None}
# Se 'confirmed' for False e 'error' None, significa still_pending.

ProbeFn = Callable[[dict[str, Any]], dict[str, Any]]


def _default_ots_probe(row: dict[str, Any]) -> dict[str, Any]:
    """Probe real via opentimestamps-client. Import lazy — se pacote
    nao instalado, retorna 'still_pending' com aviso no log."""
    try:
        from src.integrations.opentimestamps import (              # noqa: WPS433
            OtsUnavailableError,
            _load_real_client,
        )
    except ImportError:
        return {"confirmed": False, "error": "ots wrapper ausente"}

    try:
        _load_real_client()
    except OtsUnavailableError as exc:
        return {"confirmed": False, "error": str(exc)}
    # A logica efetiva (upgrade do .ots file via calendar + verificacao
    # on-chain) fica para ser plugada junto com a instalacao do pacote
    # no runbook. Por ora, reportamos "still_pending" com aviso.
    return {                                                        # pragma: no cover
        "confirmed": False,
        "error": "ots upgrade real nao plugado (F5.7 pendente)",
    }


def _default_polygon_probe(row: dict[str, Any]) -> dict[str, Any]:
    """Probe real via web3.py. Import lazy; caminho concreto e
    finalizado junto com o deploy em Amoy."""
    try:
        from src.integrations.polygon_anchor import (               # noqa: WPS433
            PolygonUnavailableError,
            _load_real_client,
        )
    except ImportError:
        return {"confirmed": False, "error": "polygon wrapper ausente"}

    try:
        _load_real_client()
    except PolygonUnavailableError as exc:
        return {"confirmed": False, "error": str(exc)}
    return {                                                        # pragma: no cover
        "confirmed": False,
        "error": "polygon probe real nao plugado (F5.7 pendente)",
    }


_DEFAULT_PROBES: dict[str, ProbeFn] = {
    "bitcoin_ots": _default_ots_probe,
    "polygon":     _default_polygon_probe,
    "ethereum":    _default_polygon_probe,   # same EVM surface
}


# ---------------------------------------------------------------------
# Upgrade de uma ancoragem
# ---------------------------------------------------------------------

def upgrade_anchor(
    anchor_id: int,
    *,
    probes: Optional[dict[str, ProbeFn]] = None,
    now: Optional[datetime] = None,
    max_age_fail_seconds: int = MAX_AGE_FAIL_SECONDS,
) -> UpgradeOutcome:
    """Tenta promover uma ancoragem para 'confirmed' ou 'failed'.

    Fluxo:

    1. Carrega o row atual (FOR UPDATE).
    2. Se ja nao esta 'pending', devolve SKIPPED.
    3. Chama o probe da rede (``bitcoin_ots`` | ``polygon`` | ...).
    4. probe.confirmed=True -> UPDATE para 'confirmed' + block info.
    5. probe.error + idade > max_age_fail -> UPDATE para 'failed'.
    6. Caso contrario -> STILL_PENDING (nenhuma mudanca no DB).
    """
    effective_now = now or datetime.now(timezone.utc)
    resolved_probes = probes or _DEFAULT_PROBES

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            SELECT id, blockchain_network, verification_status,
                   anchored_at, verified_at
              FROM blockchain_anchors
             WHERE id = %s FOR UPDATE
            """,
            (anchor_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Anchor {anchor_id} nao encontrado.")

        previous_status = row["verification_status"]
        if previous_status != "pending":
            return UpgradeOutcome(
                anchor_id=anchor_id, previous_status=previous_status,
                new_status=UpgradeStatus.SKIPPED,
                verified_at=None, block_number=None, block_timestamp=None,
                error=f"status atual '{previous_status}' nao e pending",
            )

        network = row["blockchain_network"]
        probe = resolved_probes.get(network)
        if probe is None:
            return UpgradeOutcome(
                anchor_id=anchor_id, previous_status=previous_status,
                new_status=UpgradeStatus.SKIPPED,
                verified_at=None, block_number=None, block_timestamp=None,
                error=f"sem probe registrado para network='{network}'",
            )

        # Busca a row completa para o probe (sem FOR UPDATE — ja locada)
        cursor.execute(
            "SELECT * FROM blockchain_anchors WHERE id = %s", (anchor_id,)
        )
        full_row = dict(cursor.fetchone())

        try:
            result = probe(full_row)
        except Exception as exc:
            result = {"confirmed": False, "error": f"probe exception: {exc}"}

        confirmed = bool(result.get("confirmed"))
        err = result.get("error")

        if confirmed:
            block_number = result.get("block_number")
            block_ts = result.get("block_timestamp")
            new_proof_uri = result.get("proof_uri") or full_row["proof_uri"]
            new_proof_hash = result.get("proof_hash") or full_row["proof_hash"]
            cursor.execute(
                """
                UPDATE blockchain_anchors
                   SET verification_status = 'confirmed',
                       verified_at = %s,
                       block_number = %s,
                       block_timestamp = %s,
                       proof_uri = %s,
                       proof_hash = %s
                 WHERE id = %s
                """,
                (effective_now, block_number, block_ts,
                 new_proof_uri, new_proof_hash, anchor_id),
            )
            conn.commit()
            logger.info(
                "anchor_confirmed id=%s network=%s block=%s",
                anchor_id, network, block_number,
            )
            return UpgradeOutcome(
                anchor_id=anchor_id, previous_status=previous_status,
                new_status=UpgradeStatus.CONFIRMED,
                verified_at=effective_now,
                block_number=block_number, block_timestamp=block_ts,
            )

        age = (effective_now - full_row["anchored_at"]).total_seconds()
        if err and age >= max_age_fail_seconds:
            cursor.execute(
                """
                UPDATE blockchain_anchors
                   SET verification_status = 'failed',
                       verified_at = %s
                 WHERE id = %s
                """,
                (effective_now, anchor_id),
            )
            conn.commit()
            logger.warning(
                "anchor_failed id=%s network=%s age=%.0fs err=%s",
                anchor_id, network, age, err,
            )
            return UpgradeOutcome(
                anchor_id=anchor_id, previous_status=previous_status,
                new_status=UpgradeStatus.FAILED,
                verified_at=effective_now,
                block_number=None, block_timestamp=None,
                error=err,
            )

        # still pending — nenhuma mudanca no DB
        return UpgradeOutcome(
            anchor_id=anchor_id, previous_status=previous_status,
            new_status=UpgradeStatus.STILL_PENDING,
            verified_at=None, block_number=None, block_timestamp=None,
            error=err,
        )


# ---------------------------------------------------------------------
# Sweep em lote
# ---------------------------------------------------------------------

def run_upgrade_sweep(
    *,
    probes: Optional[dict[str, ProbeFn]] = None,
    min_age_seconds: int = MIN_AGE_SECONDS,
    limit: int = 50,
    now: Optional[datetime] = None,
) -> list[UpgradeOutcome]:
    """Varre ancoragens pendentes e tenta upgrade em cada uma.

    Uso tipico: chamado por cron de 5 em 5 min (ver runbook).
    Retorna a lista de outcomes — uteis para telemetria/alerta.
    """
    outcomes: list[UpgradeOutcome] = []
    candidates = list_pending_anchors(
        min_age_seconds=min_age_seconds, limit=limit, now=now,
    )
    for row in candidates:
        try:
            outcome = upgrade_anchor(
                int(row["id"]), probes=probes, now=now,
            )
        except Exception as exc:
            outcome = UpgradeOutcome(
                anchor_id=int(row["id"]),
                previous_status=row["verification_status"],
                new_status=UpgradeStatus.STILL_PENDING,
                verified_at=None, block_number=None, block_timestamp=None,
                error=f"sweep exception: {exc}",
            )
            logger.error("anchor_sweep_error id=%s err=%s", row["id"], exc)
        outcomes.append(outcome)
    logger.info(
        "anchor_sweep_done candidates=%d confirmed=%d failed=%d pending=%d",
        len(outcomes),
        sum(1 for o in outcomes if o.new_status == UpgradeStatus.CONFIRMED),
        sum(1 for o in outcomes if o.new_status == UpgradeStatus.FAILED),
        sum(1 for o in outcomes if o.new_status == UpgradeStatus.STILL_PENDING),
    )
    return outcomes
