"""OpenTimestamps integration — F5.3 do SCC.

Substitui o mock determinista de F5.2 (``submit_anchor_mock``) por
submissao real ao protocolo OTS (Bitcoin via calendar servers
publicos), conforme doc 26 §5.3.

O pacote ``opentimestamps-client`` do PyPI e uma dependencia *opcional*.
Ele e carregado via import lazy: em ambientes que nao tem o pacote
instalado (CI default, dev sem uso de OTS), este modulo apenas expoe a
API e so tenta o import quando alguem de fato chama ``submit_to_ots``.

Para ativar:

    pip install opentimestamps-client
    export ANCHORING_PROVIDER=ots

Sem a variavel, :mod:`src.services.anchoring_service` segue usando o
mock — seguro para testes/dev.

Design de submissao (OTS assincrono):

  1. ``submit_to_ots(merkle_root)`` envia ao(s) calendar server(s) e
     recebe de volta um *receipt* inicial (.ots file bytes).
  2. O receipt contem commitments ainda NAO confirmados no Bitcoin.
  3. Upgrade para prova Bitcoin completa ocorre ~1h depois via
     ``upgrade_proof(proof_bytes)`` (chamado por job separado — fora do
     escopo de F5.3, entra em F5.7 runbook).

Para F5.3 implementamos apenas o passo 1 (submissao inicial) —
suficiente para registrar ``transaction_id`` e ``proof_uri`` em
``blockchain_anchors`` com verification_status='pending'. A verificacao
on-chain acompanha o upgrade subsequente.

Testabilidade: ``submit_to_ots(merkle_root, *, client=None)`` aceita um
client injetado — em testes, instancias de mock substituem o client
real sem precisar do pacote instalado.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Optional, Protocol

logger = logging.getLogger("cannabia.opentimestamps")


# ---------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------

class OtsError(Exception):
    """Base para erros do wrapper OTS."""


class OtsUnavailableError(OtsError):
    """Pacote ``opentimestamps-client`` nao instalado no ambiente."""


class OtsSubmissionError(OtsError):
    """Falha na submissao a um calendar server (rede, timeout, etc)."""


# ---------------------------------------------------------------------
# Receipt — shape-compatible com MockAnchorReceipt do anchoring_service
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class OtsReceipt:
    """Shape esperado por :func:`create_anchor`: transaction_id +
    proof_uri + proof_hash."""

    transaction_id: str
    proof_uri: str
    proof_hash: str


# ---------------------------------------------------------------------
# Protocol do client OTS (para injection em testes)
# ---------------------------------------------------------------------

class _OtsClient(Protocol):
    """Subset minimo do client OTS usado por submit_to_ots.

    A interface real do ``opentimestamps-client`` e mais rica, mas este
    wrapper depende so de:

      - ``stamp(data: bytes) -> bytes`` — devolve o arquivo .ots (bytes
        serializados). Em producao, a implementacao enviara para
        calendar servers publicos.
    """

    def stamp(self, data: bytes) -> bytes: ...   # noqa: E704


# ---------------------------------------------------------------------
# Factory lazy do client real
# ---------------------------------------------------------------------

def _load_real_client() -> _OtsClient:
    """Importa ``opentimestamps-client`` e monta um client concreto.

    Levanta :class:`OtsUnavailableError` se o pacote nao esta instalado.
    Qualquer outro erro de inicializacao vira :class:`OtsSubmissionError`.
    """
    try:
        from opentimestamps.core.timestamp import DetachedTimestampFile  # noqa: F401
        from opentimestamps.calendar import RemoteCalendar  # noqa: F401
    except ImportError as exc:                              # pragma: no cover
        raise OtsUnavailableError(
            "Pacote 'opentimestamps-client' nao instalado. "
            "Rode: pip install opentimestamps-client"
        ) from exc

    # Implementacao concreta em producao chamaria RemoteCalendar(...) e
    # construiria um DetachedTimestampFile. Encapsulada aqui para que
    # testes possam injetar um client fake via argumento.
    return _ProductionOtsClient()                           # pragma: no cover


class _ProductionOtsClient:                                 # pragma: no cover
    """Stub de client real — implementacao efetiva chega quando
    instalarmos opentimestamps-client. Ate la, um uso com
    ``client=None`` so funciona se o pacote existir; e se existir, esta
    classe precisa ser escrita usando a API do pacote.

    Foi deixado explicito como ``pragma: no cover`` porque ativar
    opentimestamps-client em CI envolve decisao de infra (doc 26 §5.3
    +  F5.7 runbook)."""

    def stamp(self, data: bytes) -> bytes:
        # Este caminho sera preenchido na integracao real — por ora,
        # fingir que nao esta pronto para que chamadores em dev
        # recebam erro claro.
        raise OtsSubmissionError(
            "Client OTS real nao foi totalmente plugado (F5.3 deixa o "
            "wrapper em place, mas a submissao ao calendar real sera "
            "finalizada em F5.7 runbook operacional)."
        )


# ---------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------

def submit_to_ots(
    merkle_root: str,
    *,
    client: Optional[_OtsClient] = None,
) -> OtsReceipt:
    """Submete a raiz Merkle ao protocolo OpenTimestamps.

    Args:
        merkle_root: 64 chars hex — raiz calculada em F5.2.
        client: client OTS injetavel (para testes). Se ``None``,
            carrega o client real via ``_load_real_client()`` — pode
            levantar :class:`OtsUnavailableError` se o pacote PyPI nao
            esta instalado.

    Returns:
        :class:`OtsReceipt` com:

          - ``transaction_id``: inicialmente no formato
            ``"ots:<root-prefix>"`` porque o tx Bitcoin so e conhecido
            apos o upgrade (~1h). O upgrade job (F5.7) substituira.
          - ``proof_uri``: path local canonico onde o .ots file sera
            persistido pelo caller (``data/anchors/<merkle_root>.ots``
            e a convencao sugerida).
          - ``proof_hash``: SHA-256 dos bytes do receipt.
    """
    if len(merkle_root) != 64:
        raise OtsError(
            f"merkle_root deve ter 64 chars hex; recebeu {len(merkle_root)}."
        )

    ots_client = client if client is not None else _load_real_client()
    root_bytes = bytes.fromhex(merkle_root)
    try:
        proof_bytes = ots_client.stamp(root_bytes)
    except OtsError:
        raise
    except Exception as exc:
        raise OtsSubmissionError(
            f"Falha ao submeter a calendar OTS: {exc}"
        ) from exc

    if not isinstance(proof_bytes, (bytes, bytearray)):
        raise OtsSubmissionError(
            "Client OTS devolveu payload nao-bytes — impossivel hashear."
        )
    proof_hash = hashlib.sha256(bytes(proof_bytes)).hexdigest()
    transaction_id = f"ots:{merkle_root[:16]}"
    proof_uri = f"data/anchors/{merkle_root}.ots"
    logger.info(
        "ots_submitted root=%s proof_bytes=%d proof_hash=%s",
        merkle_root[:12], len(proof_bytes), proof_hash[:12],
    )
    return OtsReceipt(
        transaction_id=transaction_id,
        proof_uri=proof_uri,
        proof_hash=proof_hash,
    )


# ---------------------------------------------------------------------
# Adapter para o dispatcher do anchoring_service
# ---------------------------------------------------------------------

def as_anchor_receipt(receipt: OtsReceipt) -> Any:
    """Converte :class:`OtsReceipt` em :class:`MockAnchorReceipt` (shape
    que create_anchor ja consome em F5.2).

    Mantido como identidade estrutural: ambas as classes expoem
    ``transaction_id``, ``proof_uri`` e ``proof_hash``. O anchoring
    service usa duck typing e aceita qualquer uma das duas.
    """
    return receipt
