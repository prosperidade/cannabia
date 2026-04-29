# src/knowledge/auto_ingest.py
"""
Helpers de ingestao automatica na base de conhecimento.

Centraliza a logica de INSERT em knowledge_catalog com dedup por DOI/URL,
para que tanto o AgenteExtrator (auto_search manual) quanto qualquer outro
agente (ex.: AgenteCientifico ingerindo PubMed durante atendimento) usem
a mesma fonte da verdade.

Tambem oferece is_quality_acceptable() — politica de curadoria leve para
evitar lixo entrar na base via gancho automatico durante atendimento (C6).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("cannabia.knowledge.auto_ingest")


def register_article_in_catalog(doc_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insere um documento em knowledge_catalog com dedup por DOI e source_url.

    doc_data segue o mesmo shape ja usado pelo AgenteExtrator:
      title, doc_type, source, source_url, doi, category, tags (list),
      authors (list), journal, published_date, language, abstract,
      norm_number, norm_body, norm_status,
      storage_type, chromadb_chunks, google_file_uri, google_file_name,
      file_hash, file_size_bytes, mime_type,
      status, ingested_by, created_by

    Retorna:
      {"registered": bool, "catalog_id": int|None,
       "reason": "duplicate_doi"|"duplicate_url"|"db_error"|None,
       "error": str|None}
    """
    try:
        from src.infra.database import db_cursor

        with db_cursor(dictionary=True) as (conn, cursor):
            doi = (doc_data.get("doi") or "").strip()
            url = (doc_data.get("source_url") or "").strip()

            if doi:
                cursor.execute(
                    "SELECT id FROM knowledge_catalog WHERE doi = %s LIMIT 1",
                    (doi,),
                )
                if cursor.fetchone():
                    return {"registered": False, "reason": "duplicate_doi", "doi": doi, "catalog_id": None}

            if url:
                cursor.execute(
                    "SELECT id FROM knowledge_catalog WHERE source_url = %s LIMIT 1",
                    (url,),
                )
                if cursor.fetchone():
                    return {"registered": False, "reason": "duplicate_url", "url": url, "catalog_id": None}

            cursor.execute(
                """
                INSERT INTO knowledge_catalog
                    (title, doc_type, source, source_url, doi,
                     category, tags, authors, journal, published_date, language,
                     abstract, norm_number, norm_body, norm_status,
                     storage_type, chromadb_chunks, google_file_uri, google_file_name,
                     file_hash, file_size_bytes, mime_type,
                     status, ingested_by, ingested_at, created_by)
                VALUES
                    (%s, %s, %s, %s, %s,
                     %s, %s::jsonb, %s::jsonb, %s, %s, %s,
                     %s, %s, %s, %s,
                     %s, %s, %s, %s,
                     %s, %s, %s,
                     %s, %s, NOW(), %s)
                RETURNING id
                """,
                (
                    doc_data.get("title", "Untitled"),
                    doc_data.get("doc_type", "article"),
                    doc_data.get("source", "manual_upload"),
                    url or None,
                    doi or None,
                    doc_data.get("category", "cannabis_medicinal"),
                    json.dumps(doc_data.get("tags", [])),
                    json.dumps(doc_data.get("authors", [])),
                    doc_data.get("journal"),
                    doc_data.get("published_date"),
                    doc_data.get("language", "en"),
                    doc_data.get("abstract"),
                    doc_data.get("norm_number"),
                    doc_data.get("norm_body"),
                    doc_data.get("norm_status"),
                    doc_data.get("storage_type", "pending"),
                    doc_data.get("chromadb_chunks", 0),
                    doc_data.get("google_file_uri"),
                    doc_data.get("google_file_name"),
                    doc_data.get("file_hash"),
                    doc_data.get("file_size_bytes", 0),
                    doc_data.get("mime_type", "application/pdf"),
                    doc_data.get("status", "indexed"),
                    doc_data.get("ingested_by", "agent_auto"),
                    doc_data.get("created_by"),
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return {"registered": True, "catalog_id": row["id"], "reason": None}

    except Exception as e:
        logger.error("Catalog registration failed: %s", e)
        return {"registered": False, "reason": "db_error", "error": str(e), "catalog_id": None}


# Limites para curadoria leve no gancho automatico (C6) — evita inflar a
# base com itens de baixo valor durante atendimento.
MIN_TITLE_LENGTH = 20
MIN_ABSTRACT_LENGTH = 80


def is_quality_acceptable(article: Dict[str, Any]) -> bool:
    """
    Politica leve de qualidade para ingestao automatica via atendimento.

    Aceita o artigo se tem titulo de tamanho razoavel E abstract de tamanho
    razoavel E ao menos um dos identificadores externos (DOI ou source_url).
    Itens fora desses minimos nao entram pelo caminho automatico — se forem
    relevantes, o curador adiciona via fluxo manual.
    """
    title = (article.get("title") or "").strip()
    abstract = (article.get("abstract") or "").strip()
    doi = (article.get("doi") or "").strip()
    source_url = (article.get("source_url") or "").strip()

    if len(title) < MIN_TITLE_LENGTH:
        return False
    if len(abstract) < MIN_ABSTRACT_LENGTH:
        return False
    if not doi and not source_url:
        return False
    return True
