# src/knowledge/vector_store.py
from __future__ import annotations

import logging
from typing import Any, Dict, List

import chromadb
from chromadb.config import Settings

CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "cannabis_science"
logger = logging.getLogger("cannabia.knowledge")


class KnowledgeStore:
    """
    Wrapper sobre ChromaDB para a base de conhecimento científica.
    Persiste em disco em chroma_db/ (protegido pelo .gitignore).

    Uso:
        store = KnowledgeStore()
        store.add(chunk_id, embedding, text, metadata)
        resultados = store.query(query_embedding, n_results=5)
    """

    def __init__(self, path: str = CHROMA_PATH) -> None:
        self._client = chromadb.PersistentClient(
            path=path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "KnowledgeStore inicializado: %d chunks na coleção '%s'.",
            self._collection.count(),
            COLLECTION_NAME,
        )

    # ──────────────────────────────────────────────
    # ESCRITA
    # ──────────────────────────────────────────────

    def add(
        self,
        chunk_id: str,
        embedding: List[float],
        text: str,
        metadata: Dict[str, Any],
    ) -> None:
        """
        Insere ou atualiza um chunk no banco vetorial (upsert).
        Idempotente: reingerir o mesmo chunk_id apenas atualiza.
        """
        self._collection.upsert(
            ids=[chunk_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata],
        )

    # ──────────────────────────────────────────────
    # LEITURA / BUSCA SEMÂNTICA
    # ──────────────────────────────────────────────

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Busca os n chunks mais similares ao embedding da query.
        Retorna lista de dicts com 'text', 'metadata' e 'similarity_score'.
        """
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, self._collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        )

        chunks: List[Dict[str, Any]] = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text": doc,
                "metadata": meta,
                # Distância cosine: 0 = idêntico, 2 = oposto → invertemos para score
                "similarity_score": round(1 - dist, 4),
            })

        return chunks

    def count(self) -> int:
        """Retorna o número total de chunks armazenados."""
        return self._collection.count()
