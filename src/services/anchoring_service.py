"""Anchoring service — F5.2 do SCC.

Ancoragem periodica em blockchain publica via Merkle tree, conforme
doc 25 §10 e doc 26 §5. Em F5.2 usamos um *mock* de OpenTimestamps —
a submissao real ao Bitcoin via protocolo OTS fica para F5.3.

Responsabilidades:

- Coletar eventos "ancoraveis" de um periodo para um tenant (ou
  globalmente): hoje cobre traceability_events, sop_evidences,
  regulatory_submissions e lab_analyses (unicas tabelas com coluna
  de hash populada hoje). adverse_events/dispensations entram quando
  ganharem coluna de hash.
- Construir arvore Merkle binaria (convencao Bitcoin: folha impar e
  duplicada) a partir dos hashes das folhas.
- Gerar e verificar prova de inclusao (merkle_path) para cada evento.
- Registrar em ``blockchain_anchors`` + ``anchor_event_mappings``
  (schema da migration 033).

API publica:

- :func:`build_merkle_root` / :func:`build_merkle_proof` /
  :func:`verify_merkle_proof` — core Merkle, puro e testavel sem DB.
- :func:`collect_anchorable_events` — SELECT agregador.
- :func:`submit_anchor_mock` — stub determinista do OTS.
- :func:`create_anchor` — pipeline completo de ancoragem.
- :func:`get_anchor` / :func:`get_mappings_for_event` — leitura.

Doc 26 §5.3 define tres redes (bitcoin_ots, polygon, ethereum). Em F5.2
todas sao tratadas pelo mesmo mock — a diferenciacao entra em F5.3.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.anchoring")


__all__ = [
    "AnchorableEvent",
    "MerkleProofStep",
    "NoEventsToAnchor",
    "AnchoringError",
    "EVENT_TABLES",
    "ANCHOR_SCOPES",
    "BLOCKCHAIN_NETWORKS",
    "sha256_hex",
    "build_merkle_root",
    "build_merkle_proof",
    "verify_merkle_proof",
    "collect_anchorable_events",
    "submit_anchor_mock",
    "create_anchor",
    "get_anchor",
    "get_mappings_for_event",
]


# ---------------------------------------------------------------------
# Constantes e validacao
# ---------------------------------------------------------------------

ANCHOR_SCOPES = frozenset({"global", "tenant", "project"})
BLOCKCHAIN_NETWORKS = frozenset({"bitcoin_ots", "polygon", "ethereum"})

# Tabelas ancoraveis hoje. Cada entrada declara a coluna da chave
# primaria, a coluna com o hash SHA-256 do evento e o predicado
# adicional de WHERE (None significa sem filtro extra). Ordem dos
# campos no dict importa apenas para introspeccao.
#
# NOTA: adverse_events (031) e dispensations (028) nao entram aqui —
# nao possuem coluna de hash populada. Ao adicioar a coluna em
# migration futura, basta estender esta tabela.
EVENT_TABLES: dict[str, dict[str, Any]] = {
    "traceability_events": {
        "pk": "id",
        "hash": "event_hash",
        "extra_where": None,
    },
    "sop_evidences": {
        "pk": "id",
        "hash": "event_hash",
        "extra_where": None,
    },
    "regulatory_submissions": {
        "pk": "id",
        "hash": "payload_hash",
        "extra_where": None,
    },
    "lab_analyses": {
        "pk": "id",
        "hash": "report_hash",
        # report_hash e NULLABLE — so ancorar se ja estiver populado.
        "extra_where": "report_hash IS NOT NULL",
    },
}


# ---------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------

class AnchoringError(Exception):
    """Erro generico do anchoring_service."""


class NoEventsToAnchor(AnchoringError):
    """Nenhum evento qualifica para ancoragem no periodo/escopo pedido."""


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class AnchorableEvent:
    """Evento normalizado, pronto para virar folha da arvore Merkle."""

    event_table: str
    event_id: int
    event_hash: str
    created_at: datetime


@dataclass(frozen=True)
class MerkleProofStep:
    """Um passo de merkle_path. Serializavel para JSONB."""

    sibling_hash: str
    side: str            # 'left' = sibling esta a esquerda do current

    def to_dict(self) -> dict[str, str]:
        return {"hash": self.sibling_hash, "side": self.side}


# ---------------------------------------------------------------------
# Core Merkle — puro, sem dependencia externa
# ---------------------------------------------------------------------

def sha256_hex(data: bytes) -> str:
    """SHA-256 hex, 64 chars."""
    return hashlib.sha256(data).hexdigest()


def _pair_hash(left_hex: str, right_hex: str) -> str:
    """Hash de concatenacao de dois nos (ordem importa — bitcoin-style)."""
    combined = bytes.fromhex(left_hex) + bytes.fromhex(right_hex)
    return sha256_hex(combined)


def _build_tree(leaves: list[str]) -> list[list[str]]:
    """Constroi arvore nivel a nivel.

    Convencao Bitcoin: em nivel com quantidade impar, a ultima folha e
    duplicada (auto-pair) antes de combinar.

    Retorna lista de niveis, do nivel de folhas ao nivel da raiz:
    ``tree[0]`` sao as folhas, ``tree[-1]`` tem um unico elemento (raiz).
    """
    if not leaves:
        raise AnchoringError("Nao e possivel construir arvore Merkle sem folhas.")
    levels: list[list[str]] = [list(leaves)]
    current = list(leaves)
    while len(current) > 1:
        if len(current) % 2 == 1:
            current = current + [current[-1]]
        next_level = [
            _pair_hash(current[i], current[i + 1])
            for i in range(0, len(current), 2)
        ]
        levels.append(next_level)
        current = next_level
    return levels


def build_merkle_root(leaves: list[str]) -> str:
    """Calcula a raiz Merkle de uma lista ordenada de hashes hex."""
    tree = _build_tree(leaves)
    return tree[-1][0]


def build_merkle_proof(leaves: list[str], index: int) -> list[MerkleProofStep]:
    """Gera a prova de inclusao para a folha em ``index``.

    A prova e uma lista de :class:`MerkleProofStep` ordenada do nivel
    das folhas ate o nivel abaixo da raiz. ``side='left'`` quer dizer
    que o sibling esta a esquerda do no atual (ou seja, ``new =
    hash(sibling || current)``); ``side='right'`` o contrario.

    Para arvore com uma unica folha, a prova e vazia (a propria folha
    ja e a raiz).
    """
    if not leaves:
        raise AnchoringError("Nao e possivel gerar prova sem folhas.")
    if not (0 <= index < len(leaves)):
        raise AnchoringError(
            f"Index {index} fora do intervalo [0, {len(leaves)})"
        )
    tree = _build_tree(leaves)
    path: list[MerkleProofStep] = []
    current_index = index
    for level in tree[:-1]:
        # Se o nivel tiver tamanho impar, duplica a ultima folha — a
        # mesma regra usada em _build_tree.
        effective = level + [level[-1]] if len(level) % 2 == 1 else level
        if current_index % 2 == 0:
            sibling = effective[current_index + 1]
            side = "right"
        else:
            sibling = effective[current_index - 1]
            side = "left"
        path.append(MerkleProofStep(sibling_hash=sibling, side=side))
        current_index //= 2
    return path


def verify_merkle_proof(
    leaf_hash: str,
    proof: Iterable[MerkleProofStep | dict[str, str]],
    expected_root: str,
) -> bool:
    """Reconstroi a raiz a partir de ``leaf_hash`` + ``proof`` e compara."""
    current = leaf_hash
    for step in proof:
        if isinstance(step, MerkleProofStep):
            sibling, side = step.sibling_hash, step.side
        else:
            sibling, side = step["hash"], step["side"]
        if side == "right":
            current = _pair_hash(current, sibling)
        elif side == "left":
            current = _pair_hash(sibling, current)
        else:
            raise AnchoringError(f"side invalido: {side!r}")
    return current == expected_root


# ---------------------------------------------------------------------
# Coletor de eventos
# ---------------------------------------------------------------------

def collect_anchorable_events(
    *,
    tenant_id: Optional[int],
    covered_from: datetime,
    covered_until: datetime,
) -> list[AnchorableEvent]:
    """Agrega eventos ancoraveis das tabelas declaradas em ``EVENT_TABLES``.

    Se ``tenant_id`` for ``None``, coleta eventos de todos os tenants
    (anchor_scope='global'). Caso contrario, filtra por ``tenant_id``.

    Ordem final: ordenada deterministicamente por
    ``(created_at ASC, event_table ASC, event_id ASC)`` para que a
    Merkle root seja reproducible a partir dos mesmos dados de entrada.
    """
    if covered_until < covered_from:
        raise AnchoringError(
            "covered_until < covered_from — janela invertida."
        )

    collected: list[AnchorableEvent] = []
    with db_cursor(dictionary=True) as (_, cursor):
        for table, spec in EVENT_TABLES.items():
            pk = spec["pk"]
            hash_col = spec["hash"]
            extra = spec.get("extra_where")
            params: list[Any] = [covered_from, covered_until]
            where = "created_at >= %s AND created_at < %s"
            if tenant_id is not None:
                where += " AND tenant_id = %s"
                params.append(tenant_id)
            if extra:
                where += f" AND {extra}"
            sql = (
                f"SELECT {pk} AS pk, {hash_col} AS hash, created_at "
                f"FROM {table} "
                f"WHERE {where} "
                f"ORDER BY created_at ASC, {pk} ASC"
            )
            cursor.execute(sql, tuple(params))
            for row in cursor.fetchall():
                collected.append(
                    AnchorableEvent(
                        event_table=table,
                        event_id=int(row["pk"]),
                        event_hash=row["hash"],
                        created_at=row["created_at"],
                    )
                )

    collected.sort(key=lambda e: (e.created_at, e.event_table, e.event_id))
    return collected


# ---------------------------------------------------------------------
# Submissao mock (F5.2) — F5.3 substitui por OTS real
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class MockAnchorReceipt:
    transaction_id: str
    proof_uri: str
    proof_hash: str


def submit_anchor_mock(
    merkle_root: str,
    network: str,
    *,
    now_epoch: Optional[int] = None,
) -> MockAnchorReceipt:
    """Simula submissao a ``network`` e devolve um receipt determinista.

    Formato do ``transaction_id``: ``"mock:<network>:<root-prefix>:<epoch>"``.
    O prefixo deixa claro em leitura de banco que e uma ancoragem mock
    (a migracao para F5.3 substitui por transaction_id real da rede).

    Em F5.3 este helper sera trocado por clientes reais (opentimestamps,
    web3.py/Polygon), mantendo a mesma assinatura.
    """
    if network not in BLOCKCHAIN_NETWORKS:
        raise AnchoringError(
            f"blockchain_network '{network}' invalido "
            f"(permitidos: {sorted(BLOCKCHAIN_NETWORKS)})"
        )
    if len(merkle_root) != 64:
        raise AnchoringError(
            f"merkle_root deve ter 64 chars hex; recebeu {len(merkle_root)}."
        )
    epoch = now_epoch if now_epoch is not None else int(time.time())
    transaction_id = f"mock:{network}:{merkle_root[:16]}:{epoch}"
    proof_uri = f"mock://{network}/anchors/{merkle_root}.proof"
    proof_hash = sha256_hex(f"mock-proof:{network}:{merkle_root}".encode("utf-8"))
    return MockAnchorReceipt(
        transaction_id=transaction_id,
        proof_uri=proof_uri,
        proof_hash=proof_hash,
    )


# ---------------------------------------------------------------------
# Repository helpers (reads + writes)
# ---------------------------------------------------------------------

def _insert_blockchain_anchor(
    cursor: Any,
    *,
    tenant_id: Optional[int],
    anchor_scope: str,
    covered_from: datetime,
    covered_until: datetime,
    events_count: int,
    merkle_root: str,
    blockchain_network: str,
    transaction_id: str,
    proof_uri: Optional[str],
    proof_hash: Optional[str],
) -> dict[str, Any]:
    cursor.execute(
        """
        INSERT INTO blockchain_anchors (
            tenant_id, anchor_scope, covered_from, covered_until,
            events_count, merkle_root, blockchain_network,
            transaction_id, proof_uri, proof_hash
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            tenant_id,
            anchor_scope,
            covered_from,
            covered_until,
            events_count,
            merkle_root,
            blockchain_network,
            transaction_id,
            proof_uri,
            proof_hash,
        ),
    )
    return cursor.fetchone()


def _insert_event_mappings(
    cursor: Any,
    *,
    anchor_id: int,
    events: list[AnchorableEvent],
    tree_paths: list[list[MerkleProofStep]],
) -> int:
    """Insere um row por evento com seu merkle_path em JSONB."""
    count = 0
    for event, path in zip(events, tree_paths):
        merkle_path_json = json.dumps([step.to_dict() for step in path])
        cursor.execute(
            """
            INSERT INTO anchor_event_mappings
                (anchor_id, event_table, event_id, event_hash, merkle_path)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                anchor_id,
                event.event_table,
                event.event_id,
                event.event_hash,
                merkle_path_json,
            ),
        )
        count += 1
    return count


def get_anchor(anchor_id: int) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT * FROM blockchain_anchors WHERE id = %s",
            (anchor_id,),
        )
        return cursor.fetchone()


def get_mappings_for_event(
    event_table: str,
    event_id: int,
) -> list[dict[str, Any]]:
    """Retorna todas as ancoragens que cobrem um evento especifico.

    Usado pelo endpoint publico de verificacao em F5.5. Inclui campos
    suficientes do blockchain_anchors para reconstruir + verificar a
    raiz Merkle sem uma segunda query.
    """
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT m.anchor_id, m.event_table, m.event_id,
                   m.event_hash, m.merkle_path,
                   a.tenant_id, a.anchor_scope,
                   a.merkle_root, a.transaction_id,
                   a.blockchain_network, a.verification_status,
                   a.anchored_at, a.verified_at,
                   a.covered_from, a.covered_until
              FROM anchor_event_mappings m
              JOIN blockchain_anchors a ON a.id = m.anchor_id
             WHERE m.event_table = %s
               AND m.event_id = %s
             ORDER BY a.anchored_at DESC
            """,
            (event_table, event_id),
        )
        return list(cursor.fetchall())


# ---------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------

def _validate_scope_and_tenant(
    anchor_scope: str,
    tenant_id: Optional[int],
) -> None:
    if anchor_scope not in ANCHOR_SCOPES:
        raise AnchoringError(
            f"anchor_scope '{anchor_scope}' invalido "
            f"(permitidos: {sorted(ANCHOR_SCOPES)})"
        )
    if anchor_scope == "global" and tenant_id is not None:
        raise AnchoringError(
            "anchor_scope='global' nao aceita tenant_id (agregacao entre tenants)."
        )
    if anchor_scope in ("tenant", "project") and tenant_id is None:
        raise AnchoringError(
            f"anchor_scope='{anchor_scope}' exige tenant_id."
        )


def create_anchor(
    *,
    tenant_id: Optional[int],
    anchor_scope: str,
    covered_from: datetime,
    covered_until: datetime,
    blockchain_network: str = "bitcoin_ots",
    events: Optional[list[AnchorableEvent]] = None,
    now_epoch: Optional[int] = None,
) -> dict[str, Any]:
    """Ancora os eventos do periodo em uma rede e persiste.

    Fluxo:
    1. Valida escopo + tenant.
    2. Coleta eventos (ou usa ``events`` injetado — util para project scope
       e para testes).
    3. Constroi arvore Merkle + provas.
    4. Submete ao mock da rede (F5.3 troca por client real).
    5. Persiste em blockchain_anchors + anchor_event_mappings em uma
       unica transacao.

    Retorna o row de ``blockchain_anchors`` recem-inserido, acrescido
    de ``events`` (lista) e ``merkle_root`` para conveniencia.

    Levanta :class:`NoEventsToAnchor` se o periodo nao tem eventos.
    """
    _validate_scope_and_tenant(anchor_scope, tenant_id)

    if blockchain_network not in BLOCKCHAIN_NETWORKS:
        raise AnchoringError(
            f"blockchain_network '{blockchain_network}' invalido."
        )

    if covered_until < covered_from:
        raise AnchoringError("covered_until < covered_from.")

    if events is None:
        events = collect_anchorable_events(
            tenant_id=tenant_id,
            covered_from=covered_from,
            covered_until=covered_until,
        )

    if not events:
        raise NoEventsToAnchor(
            f"Nenhum evento ancoravel em {covered_from.isoformat()} → "
            f"{covered_until.isoformat()} para tenant={tenant_id} "
            f"scope={anchor_scope}."
        )

    leaf_hashes = [e.event_hash for e in events]
    merkle_root = build_merkle_root(leaf_hashes)
    proofs = [build_merkle_proof(leaf_hashes, idx) for idx in range(len(events))]

    receipt = submit_anchor_mock(merkle_root, blockchain_network, now_epoch=now_epoch)

    with db_cursor(dictionary=True) as (conn, cursor):
        anchor_row = _insert_blockchain_anchor(
            cursor,
            tenant_id=tenant_id,
            anchor_scope=anchor_scope,
            covered_from=covered_from,
            covered_until=covered_until,
            events_count=len(events),
            merkle_root=merkle_root,
            blockchain_network=blockchain_network,
            transaction_id=receipt.transaction_id,
            proof_uri=receipt.proof_uri,
            proof_hash=receipt.proof_hash,
        )
        anchor_id = int(anchor_row["id"])
        inserted = _insert_event_mappings(
            cursor,
            anchor_id=anchor_id,
            events=events,
            tree_paths=proofs,
        )
        conn.commit()

    logger.info(
        "anchor_created id=%s scope=%s tenant=%s events=%d network=%s root=%s",
        anchor_id, anchor_scope, tenant_id, inserted,
        blockchain_network, merkle_root[:12],
    )
    return {
        **anchor_row,
        "events": events,
        "merkle_root": merkle_root,
    }
