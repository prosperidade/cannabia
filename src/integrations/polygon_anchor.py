"""Polygon Anchor integration — F5.4 do SCC.

Wrapper para submissao ao smart contract ``SandboxAnchor`` deployado
em Polygon (Amoy testnet inicialmente; mainnet apos homologacao).
Contrato em [contracts/SandboxAnchor.sol](../../contracts/SandboxAnchor.sol).

Decisao de rede (2026-04-21): **Polygon** escolhido como backbone de
ancoragem. Bitcoin OTS (F5.3) permanece disponivel como alternativa
auditavel — o dispatcher em ``anchoring_service.submit_anchor`` seleciona
via ``ANCHORING_PROVIDER``.

O pacote ``web3`` do PyPI e uma dependencia **opcional**: carregado via
import lazy em ``_load_real_client``. Testes usam client injetado
(Protocol com ``anchor()`` e ``wait_for_receipt()``).

Configuracao em producao:

    pip install web3
    export POLYGON_RPC_URL="https://rpc-amoy.polygon.technology"
    export POLYGON_DEPLOYER_PRIVATE_KEY="0x..."
    export POLYGON_SANDBOX_ANCHOR_ADDRESS="0x..."
    export ANCHORING_PROVIDER=polygon

Fluxo de submissao:

  1. ``submit_to_polygon(merkle_root, scope, scope_id, period_start,
     period_end)`` chama o contrato.
  2. Receipt inicial contem tx_hash (``transaction_id``).
  3. Confirmacao completa apos ~10 blocos (~2-3 min). Verificacao de
     status final vai em F5.7 (runbook / job de upgrade).

Comparando com OTS (F5.3):

  - OTS: sem contrato, calendar servers publicos, upgrade ~1h.
  - Polygon: contrato explicito, confirmacao minutos, eventos indexados
    consultaveis via Polygonscan.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional, Protocol

logger = logging.getLogger("cannabia.polygon_anchor")


# ---------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------

class PolygonError(Exception):
    """Base para erros do wrapper Polygon."""


class PolygonUnavailableError(PolygonError):
    """Pacote ``web3`` nao instalado, ou envs de RPC/chave ausentes."""


class PolygonSubmissionError(PolygonError):
    """Falha na submissao on-chain (revert, timeout, etc)."""


# ---------------------------------------------------------------------
# Receipt (shape-compatible com MockAnchorReceipt/OtsReceipt)
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class PolygonReceipt:
    transaction_id: str     # '0x...' — tx hash Polygon
    proof_uri: str          # 'polygon://<network>/tx/<hash>'
    proof_hash: str         # SHA-256 de (tx_hash + merkle_root)


# ---------------------------------------------------------------------
# Protocol do client (para injection em testes)
# ---------------------------------------------------------------------

class _PolygonClient(Protocol):
    """Subset minimo do client usado por :func:`submit_to_polygon`.

    - ``anchor(scope, scope_id, merkle_root, period_start, period_end)``
      submete a transacao e devolve o ``tx_hash`` ('0x...').

    A implementacao real usa web3.py + ABI do ``SandboxAnchor``.
    """

    def anchor(
        self,
        scope: str,
        scope_id: bytes,
        merkle_root: bytes,
        period_start: int,
        period_end: int,
    ) -> str: ...                                                # noqa: E704


# ---------------------------------------------------------------------
# Helpers de conversao
# ---------------------------------------------------------------------

_SCOPES = frozenset({"global", "tenant", "project"})


def scope_id_to_bytes32(
    scope: str,
    tenant_id: Optional[int],
    project_id: Optional[int] = None,
) -> bytes:
    """Converte (scope, tenant_id, project_id) em ``bytes32`` para o
    contrato. Convencoes:

      - 'global'  -> bytes32(0)
      - 'tenant'  -> int(tenant_id).to_bytes(32, 'big')
      - 'project' -> int(project_id).to_bytes(32, 'big')
    """
    if scope not in _SCOPES:
        raise PolygonError(
            f"scope '{scope}' invalido (permitidos: {sorted(_SCOPES)})."
        )
    if scope == "global":
        return b"\x00" * 32
    if scope == "tenant":
        if tenant_id is None:
            raise PolygonError("scope='tenant' exige tenant_id.")
        return int(tenant_id).to_bytes(32, "big", signed=False)
    # project
    if project_id is None:
        raise PolygonError("scope='project' exige project_id.")
    return int(project_id).to_bytes(32, "big", signed=False)


def _merkle_root_to_bytes32(merkle_root: str) -> bytes:
    if len(merkle_root) != 64:
        raise PolygonError(
            f"merkle_root deve ter 64 chars hex; recebeu {len(merkle_root)}."
        )
    return bytes.fromhex(merkle_root)


# ---------------------------------------------------------------------
# Factory lazy do client real
# ---------------------------------------------------------------------

_ENV_RPC = "POLYGON_RPC_URL"
_ENV_KEY = "POLYGON_DEPLOYER_PRIVATE_KEY"
_ENV_ADDR = "POLYGON_SANDBOX_ANCHOR_ADDRESS"
_ENV_NETWORK = "POLYGON_NETWORK"     # 'amoy' (default) | 'mainnet' — para proof_uri


def _load_real_client() -> _PolygonClient:
    """Importa web3 e monta client concreto. Pode levantar
    :class:`PolygonUnavailableError` se algo falta."""
    try:
        from web3 import Web3                                    # noqa: F401
    except ImportError as exc:                                   # pragma: no cover
        raise PolygonUnavailableError(
            "Pacote 'web3' nao instalado. Rode: pip install web3"
        ) from exc

    rpc = os.environ.get(_ENV_RPC)
    key = os.environ.get(_ENV_KEY)
    addr = os.environ.get(_ENV_ADDR)
    missing = [k for k, v in (
        (_ENV_RPC, rpc), (_ENV_KEY, key), (_ENV_ADDR, addr),
    ) if not v]
    if missing:                                                  # pragma: no cover
        raise PolygonUnavailableError(
            f"Envs ausentes para client real: {missing}. "
            "Setar POLYGON_RPC_URL, POLYGON_DEPLOYER_PRIVATE_KEY, "
            "POLYGON_SANDBOX_ANCHOR_ADDRESS."
        )
    return _ProductionPolygonClient(rpc, key, addr)              # pragma: no cover


class _ProductionPolygonClient:                                  # pragma: no cover
    """Stub da implementacao real web3.py.

    F5.4 deixa o wrapper em place — a invocacao concreta do contrato
    (eth_sendRawTransaction + wait_for_receipt + parse do Anchored
    event) sera finalizada junto com o deploy na sessao de runbook
    operacional (F5.7)."""

    def __init__(self, rpc_url: str, private_key: str, contract_address: str):
        self.rpc_url = rpc_url
        self.private_key = private_key
        self.contract_address = contract_address

    def anchor(self, scope, scope_id, merkle_root, period_start, period_end):
        raise PolygonSubmissionError(
            "Client Polygon real nao esta plugado em F5.4. "
            "Deploy + web3 tx signing sao finalizados em F5.7 runbook."
        )


# ---------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------

def submit_to_polygon(
    merkle_root: str,
    *,
    scope: str,
    tenant_id: Optional[int] = None,
    project_id: Optional[int] = None,
    period_start: int,
    period_end: int,
    client: Optional[_PolygonClient] = None,
) -> PolygonReceipt:
    """Submete a raiz Merkle ao contrato ``SandboxAnchor`` em Polygon.

    Args:
        merkle_root: 64 chars hex.
        scope: 'global' | 'tenant' | 'project'.
        tenant_id: obrigatorio para scope='tenant'.
        project_id: obrigatorio para scope='project'.
        period_start/period_end: unix timestamps (UTC) da janela
            coberta.
        client: client injetavel (testes). Se ``None``, carrega real
            via ``_load_real_client`` (pode levantar
            :class:`PolygonUnavailableError`).

    Returns:
        :class:`PolygonReceipt` com tx hash + proof_uri + proof_hash.
    """
    if period_end < period_start:
        raise PolygonError("period_end < period_start")

    scope_id = scope_id_to_bytes32(scope, tenant_id, project_id)
    root_bytes = _merkle_root_to_bytes32(merkle_root)

    poly_client = client if client is not None else _load_real_client()
    try:
        tx_hash = poly_client.anchor(
            scope, scope_id, root_bytes, int(period_start), int(period_end),
        )
    except PolygonError:
        raise
    except Exception as exc:
        raise PolygonSubmissionError(
            f"Falha ao submeter ao contrato SandboxAnchor: {exc}"
        ) from exc

    if not isinstance(tx_hash, str) or not tx_hash.startswith("0x"):
        raise PolygonSubmissionError(
            f"Client devolveu tx_hash invalido: {tx_hash!r}"
        )

    network_label = os.environ.get(_ENV_NETWORK, "amoy")
    proof_uri = f"polygon://{network_label}/tx/{tx_hash}"
    proof_hash = hashlib.sha256(
        (tx_hash + merkle_root).encode("utf-8")
    ).hexdigest()
    logger.info(
        "polygon_submitted scope=%s root=%s tx=%s network=%s",
        scope, merkle_root[:12], tx_hash[:12], network_label,
    )
    return PolygonReceipt(
        transaction_id=tx_hash,
        proof_uri=proof_uri,
        proof_hash=proof_hash,
    )
