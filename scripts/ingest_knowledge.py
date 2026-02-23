#!/usr/bin/env python
# scripts/ingest_knowledge.py
"""
CannabIA — CLI de ingestão de artigos científicos no banco vetorial.

Comandos disponíveis:
  ingest   Processa um PDF e insere os chunks no ChromaDB
  status   Exibe quantos chunks estão armazenados no banco

Exemplos:
  python scripts/ingest_knowledge.py status
  python scripts/ingest_knowledge.py ingest --file artigo.pdf --title "Cannabidiol e Epilepsia"
  python scripts/ingest_knowledge.py ingest --file artigo.pdf --title "CBD e Dor" --doi "10.1234/abc" --source "JAMA"
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys

# Garante que src/ seja resolvido sem instalação de pacote
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fitz  # PyMuPDF

from src.knowledge.vector_store import KnowledgeStore
from src.knowledge.embeddings import EmbeddingClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("cannabia.ingest")

# ──────────────────────────────────────────────
# CONFIGURAÇÃO DE CHUNKING
# ──────────────────────────────────────────────
CHUNK_SIZE    = 500   # caracteres por chunk (~125 tokens — confortável para o modelo)
CHUNK_OVERLAP = 80    # overlap para preservar contexto entre chunks adjacentes


# ──────────────────────────────────────────────
# EXTRAÇÃO E CHUNKING
# ──────────────────────────────────────────────

def _extract_text_from_pdf(path: str) -> str:
    """Extrai o texto completo de um PDF usando PyMuPDF."""
    doc = fitz.open(path)
    pages = [page.get_text("text") for page in doc]
    doc.close()
    full_text = "\n".join(pages)
    logger.info("Extraídos %d caracteres de %d páginas.", len(full_text), len(pages))
    return full_text


def _split_into_chunks(text: str) -> list[str]:
    """
    Divide o texto em chunks com overlap.
    Estratégia simples e sem dependências externas.
    Chunks curtos são descartados para evitar ruído.
    """
    chunks: list[str] = []
    text = text.strip()
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end].strip()
        # Descarta chunks muito pequenos (provavelmente cabeçalhos/rodapés)
        if len(chunk) > 60:
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


# ──────────────────────────────────────────────
# INGESTÃO PRINCIPAL
# ──────────────────────────────────────────────

def ingest_pdf(
    file_path: str,
    title: str,
    doi: str = "",
    source: str = "",
) -> int:
    """
    Pipeline de ingestão:
      1. Extrai texto do PDF
      2. Divide em chunks
      3. Gera embeddings via Google text-embedding-004
      4. Armazena no ChromaDB (upsert idempotente)

    Retorna o número de chunks inseridos.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    text = _extract_text_from_pdf(file_path)
    if not text.strip():
        raise ValueError(
            "Nenhum texto extraído. "
            "O PDF pode ser escaneado (imagem). Use um PDF com camada de texto."
        )

    chunks = _split_into_chunks(text)
    logger.info("%d chunks gerados para '%s'.", len(chunks), title)

    embedder = EmbeddingClient()
    store    = KnowledgeStore()

    # Hash SHA-256 do arquivo → namespace único para evitar ID collision
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()[:12]

    inserted = 0
    for i, chunk in enumerate(chunks):
        chunk_id = f"{file_hash}_chunk_{i:04d}"
        metadata = {
            "title":     title,
            "doi":       doi    or "N/A",
            "source":    source or os.path.basename(file_path),
            "chunk_idx": i,
            "file_hash": file_hash,
        }
        embedding = embedder.embed_document(chunk)
        store.add(
            chunk_id=chunk_id,
            embedding=embedding,
            text=chunk,
            metadata=metadata,
        )
        inserted += 1
        if inserted % 10 == 0:
            logger.info("  Progresso: %d/%d chunks inseridos...", inserted, len(chunks))

    logger.info("✅ Ingestão concluída: %d chunks de '%s' salvo no ChromaDB.", inserted, title)
    return inserted


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CannabIA — Ingestão de artigos científicos no banco vetorial",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── ingest ──
    ingest_p = subparsers.add_parser("ingest", help="Ingere um PDF no ChromaDB")
    ingest_p.add_argument("--file",   required=True, help="Caminho para o arquivo PDF")
    ingest_p.add_argument("--title",  required=True, help="Título do artigo científico")
    ingest_p.add_argument("--doi",    default="",    help="DOI do artigo (opcional)")
    ingest_p.add_argument("--source", default="",    help="Fonte / Journal (opcional)")

    # ── status ──
    subparsers.add_parser("status", help="Exibe quantos chunks estão no banco")

    args = parser.parse_args()

    if args.command == "ingest":
        try:
            count = ingest_pdf(
                file_path=args.file,
                title=args.title,
                doi=args.doi,
                source=args.source,
            )
            print(f"\n✅  {count} chunks inseridos com sucesso no ChromaDB.")
        except (FileNotFoundError, ValueError) as e:
            print(f"\n❌  Erro: {e}")
            sys.exit(1)

    elif args.command == "status":
        try:
            store = KnowledgeStore()
            print(f"\n📚  Banco vetorial CannabIA: {store.count()} chunks armazenados.")
        except Exception as e:
            print(f"\n❌  Erro ao acessar o banco: {e}")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
