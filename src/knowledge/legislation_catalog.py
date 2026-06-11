from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Iterable

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.knowledge.legislation_catalog")


def _manifest_map() -> dict[str, dict]:
    manifest_path = Path(__file__).resolve().parents[2] / "data" / "legislation" / "sources.json"
    if not manifest_path.exists():
        return {}

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to load legislation manifest at %s", manifest_path, exc_info=True)
        return {}

    if not isinstance(payload, list):
        return {}
    return {
        str(item["filename"]): item
        for item in payload
        if isinstance(item, dict) and item.get("filename")
    }


def _display_name(entry: dict) -> str:
    raw = (
        entry.get("display_name")
        or entry.get("filename")
        or entry.get("local_path")
        or entry.get("name")
        or "legislacao"
    )
    return Path(str(raw)).stem.strip() or "legislacao"


def _clean_title(value: str) -> str:
    title = re.sub(r"[_\-]+", " ", value).strip()
    return re.sub(r"\s+", " ", title)


def _format_lei_number(number: str) -> str:
    digits = re.sub(r"\D", "", number or "")
    if not digits:
        return ""
    if len(digits) > 5 and digits[-4:].startswith(("19", "20")):
        digits = digits[:-4]
    if len(digits) <= 3:
        return digits
    return f"{int(digits[:-3])}.{digits[-3:]}"


def infer_legislation_metadata(entry: dict) -> dict:
    title = _clean_title(_display_name(entry))
    normalized = title.lower()

    source = "manual_upload"
    norm_body = None
    norm_number = None

    if "rdc" in normalized or "anvisa" in normalized:
        source = "anvisa"
        norm_body = "ANVISA"

    if "cfm" in normalized or "conselho federal de medicina" in normalized:
        source = "cfm"
        norm_body = "CFM"

    if "lei" in normalized or "planalto" in normalized:
        source = "planalto"
        norm_body = norm_body or "Congresso Nacional"

    if match := re.search(r"\brdc\s*(\d+)(?:\D+(20\d{2}))?", normalized):
        number, year = match.groups()
        norm_number = f"RDC {int(number)}"
        if year:
            norm_number = f"{norm_number}/{year}"
        source = "anvisa"
        norm_body = "ANVISA"
    elif match := re.search(r"\blei\s*(\d[\d\.\s]*)?(?:\D+(19\d{2}|20\d{2}))?", normalized):
        number, year = match.groups()
        formatted = _format_lei_number(number or "")
        if formatted:
            norm_number = f"Lei {formatted}"
            if year:
                norm_number = f"{norm_number}/{year}"
        source = "planalto"
        norm_body = "Congresso Nacional"
    elif match := re.search(r"\bresolu(?:cao|ção)?\s*(\d+)(?:\D+(20\d{2}))?", normalized):
        number, year = match.groups()
        norm_number = f"Resolucao {int(number)}"
        if year:
            norm_number = f"{norm_number}/{year}"
        if source == "manual_upload":
            source = "cfm" if "cfm" in normalized else "manual_upload"
        if not norm_body and source == "cfm":
            norm_body = "CFM"
    elif match := re.search(r"\bportaria\s*(\d+)(?:\D+(20\d{2}))?", normalized):
        number, year = match.groups()
        norm_number = f"Portaria {int(number)}"
        if year:
            norm_number = f"{norm_number}/{year}"

    return {
        "title": title,
        "source": source,
        "norm_number": norm_number,
        "norm_body": norm_body,
    }


def _build_catalog_record(entry: dict, ingested_by: str, created_by: int | None = None) -> dict:
    local_path = entry.get("local_path")
    if local_path:
        local_path = os.path.abspath(local_path)

    filename = entry.get("filename")
    if not filename and local_path:
        filename = os.path.basename(local_path)
    if not filename:
        filename = entry.get("display_name") or entry.get("name") or _display_name(entry)

    manifest_entry = _manifest_map().get(filename, {})
    metadata = infer_legislation_metadata(entry)
    metadata = {
        "title": manifest_entry.get("title") or metadata["title"],
        "source": manifest_entry.get("source") or metadata["source"],
        "norm_number": manifest_entry.get("norm_number") or metadata["norm_number"],
        "norm_body": manifest_entry.get("norm_body") or metadata["norm_body"],
    }
    # Sprint 3 Leg.6 — popula norm_status do manifesto quando presente.
    # NAO inventa default: se sources.json nao declarou o campo, deixa None
    # para o catalogo (compatibilidade com normas ingeridas via outras
    # superficies, ex. upload manual nao-manifestado).
    #
    # `revoked_by` e `publication_date` ficam disponiveis no record dict
    # como metadados informativos (consumiveis por UI/auditoria), mas nao
    # sao gravados no `knowledge_catalog` ainda — a coluna `published_date`
    # existe na tabela mas o backfill amplo via manifest e' tarefa Sprint 4
    # (Frente C5). Aqui apenas garantimos que o dado nao se perca durante
    # a passagem pelo builder.
    norm_status = manifest_entry.get("norm_status")
    revoked_by = manifest_entry.get("revoked_by")
    publication_date = manifest_entry.get("publication_date")

    mime_type = entry.get("mime_type")
    if not mime_type:
        mime_type = mimetypes.guess_type(filename)[0] or "application/pdf"

    tags = ["legislation"]
    if metadata["source"] and metadata["source"] != "manual_upload":
        tags.append(metadata["source"])

    return {
        "created_by": created_by,
        "title": metadata["title"],
        "doc_type": "legislation",
        "source": metadata["source"],
        "source_url": manifest_entry.get("source_url"),
        "category": "cannabis_medicinal",
        "tags": tags,
        "authors": [],
        "language": "pt-BR",
        "norm_number": metadata["norm_number"],
        "norm_body": metadata["norm_body"],
        "norm_status": norm_status,
        "revoked_by": revoked_by,
        "publication_date": publication_date,
        "storage_type": "google_files",
        "google_file_uri": entry.get("uri"),
        "google_file_name": entry.get("name"),
        "local_path": local_path,
        "file_hash": entry.get("checksum"),
        "file_size_bytes": entry.get("size_bytes", 0),
        "mime_type": mime_type,
        "status": "indexed",
        "ingested_by": ingested_by,
        "filename": filename,
    }


def sync_legislation_catalog(
    entries: Iterable[dict],
    ingested_by: str = "manual_upload",
    created_by: int | None = None,
) -> dict:
    summary = {"created": 0, "updated": 0, "total": 0, "items": []}
    entries = list(entries or [])
    if not entries:
        return summary

    with db_cursor(dictionary=True) as (conn, cursor):
        for entry in entries:
            record = _build_catalog_record(entry, ingested_by=ingested_by, created_by=created_by)
            conditions = []
            params = []

            # Chaves de IDENTIDADE do documento. source_url foi REMOVIDO (A5
            # follow-up): normas distintas compartilham legitimamente a mesma
            # pagina-fonte (ex.: indice de RDCs da Anvisa), entao usa-lo como
            # chave colapsava varias normas numa unica linha. Identidade real =
            # arquivo (local_path/hash) ou referencia do provedor (uri/name);
            # o fallback por (source, norm_number)/(source, title) cobre o resto.
            for column in ("local_path", "file_hash", "google_file_uri", "google_file_name"):
                value = record.get(column)
                if value:
                    conditions.append(f"{column} = %s")
                    params.append(value)

            existing = None
            if conditions:
                cursor.execute(
                    f"""
                    SELECT id
                    FROM knowledge_catalog
                    WHERE doc_type = 'legislation' AND ({' OR '.join(conditions)})
                    ORDER BY id
                    LIMIT 1
                    """,
                    tuple(params),
                )
                existing = cursor.fetchone()

            if not existing and record.get("norm_number") and record.get("source"):
                cursor.execute(
                    """
                    SELECT id
                    FROM knowledge_catalog
                    WHERE doc_type = 'legislation' AND source = %s AND norm_number = %s
                    ORDER BY id
                    LIMIT 1
                    """,
                    (record["source"], record["norm_number"]),
                )
                existing = cursor.fetchone()

            if not existing and record.get("title") and record.get("source"):
                cursor.execute(
                    """
                    SELECT id
                    FROM knowledge_catalog
                    WHERE doc_type = 'legislation' AND source = %s AND title = %s
                    ORDER BY id
                    LIMIT 1
                    """,
                    (record["source"], record["title"]),
                )
                existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE knowledge_catalog
                    SET title = %s,
                        source = %s,
                        source_url = %s,
                        category = %s,
                        tags = %s::jsonb,
                        authors = %s::jsonb,
                        language = %s,
                        norm_number = %s,
                        norm_body = %s,
                        norm_status = %s,
                        storage_type = %s,
                        google_file_uri = %s,
                        google_file_name = %s,
                        local_path = %s,
                        file_hash = %s,
                        file_size_bytes = %s,
                        mime_type = %s,
                        status = %s,
                        error_message = NULL,
                        ingested_by = %s,
                        ingested_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                    """,
                    (
                        record["title"],
                        record["source"],
                        record["source_url"],
                        record["category"],
                        json.dumps(record["tags"]),
                        json.dumps(record["authors"]),
                        record["language"],
                        record["norm_number"],
                        record["norm_body"],
                        record["norm_status"],
                        record["storage_type"],
                        record["google_file_uri"],
                        record["google_file_name"],
                        record["local_path"],
                        record["file_hash"],
                        record["file_size_bytes"],
                        record["mime_type"],
                        record["status"],
                        record["ingested_by"],
                        existing["id"],
                    ),
                )
                row = cursor.fetchone()
                summary["updated"] += 1
                action = "updated"
            else:
                cursor.execute(
                    """
                    INSERT INTO knowledge_catalog
                        (title, doc_type, source, source_url,
                         category, tags, authors, language,
                         norm_number, norm_body, norm_status,
                         storage_type, google_file_uri, google_file_name,
                         local_path, file_hash, file_size_bytes, mime_type,
                         status, ingested_by, ingested_at, created_by)
                    VALUES
                        (%s, %s, %s, %s,
                         %s, %s::jsonb, %s::jsonb, %s,
                         %s, %s, %s,
                         %s, %s, %s,
                         %s, %s, %s, %s,
                         %s, %s, NOW(), %s)
                    RETURNING id
                    """,
                    (
                        record["title"],
                        record["doc_type"],
                        record["source"],
                        record["source_url"],
                        record["category"],
                        json.dumps(record["tags"]),
                        json.dumps(record["authors"]),
                        record["language"],
                        record["norm_number"],
                        record["norm_body"],
                        record["norm_status"],
                        record["storage_type"],
                        record["google_file_uri"],
                        record["google_file_name"],
                        record["local_path"],
                        record["file_hash"],
                        record["file_size_bytes"],
                        record["mime_type"],
                        record["status"],
                        record["ingested_by"],
                        record.get("created_by"),
                    ),
                )
                row = cursor.fetchone()
                summary["created"] += 1
                action = "created"

            summary["items"].append(
                {
                    "catalog_id": row["id"],
                    "filename": record["filename"],
                    "title": record["title"],
                    "norm_number": record["norm_number"],
                    "action": action,
                }
            )

        conn.commit()

    summary["total"] = len(entries)
    return summary
