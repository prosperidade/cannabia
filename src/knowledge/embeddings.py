# src/knowledge/embeddings.py
from __future__ import annotations

import logging
import os
from typing import List

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("cannabia.knowledge")

# gemini-embedding-001: modelo de embedding disponível na conta (3072 dimensões)
EMBEDDING_MODEL = "gemini-embedding-001"

# task_type diferente para documento vs query melhora a relevância na busca semântica
# conforme benchmark e documentação oficial do Google
TASK_TYPE_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_TYPE_QUERY    = "RETRIEVAL_QUERY"


class EmbeddingClient:
    """
    Gera embeddings usando Google text-embedding-004 (768 dimensões).
    Usa o SDK oficial google-genai (substituição do google-generativeai).

    Uso:
        client = EmbeddingClient()
        vec = client.embed_document("texto do artigo científico...")
        vec = client.embed_query("canabidiol para dor crônica")
    """

    def __init__(self) -> None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY não configurada. "
                "Adicione ao .env antes de usar o módulo de conhecimento."
            )
        self._client = genai.Client(api_key=api_key)
        logger.info("EmbeddingClient inicializado com modelo '%s'.", EMBEDDING_MODEL)

    def embed_document(self, text: str) -> List[float]:
        """
        Gera embedding para um chunk de documento (usado na ingestão).
        task_type=RETRIEVAL_DOCUMENT otimiza para recuperação posterior.
        """
        if not text or not text.strip():
            raise ValueError("Texto vazio não pode ser vetorizado.")

        result = self._client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(task_type=TASK_TYPE_DOCUMENT),
        )
        return result.embeddings[0].values

    def embed_query(self, text: str) -> List[float]:
        """
        Gera embedding para uma query de busca (usado no RAG pipeline).
        task_type=RETRIEVAL_QUERY otimiza a relevância na busca semântica.
        """
        if not text or not text.strip():
            raise ValueError("Query vazia não pode ser vetorizada.")

        result = self._client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(task_type=TASK_TYPE_QUERY),
        )
        return result.embeddings[0].values
