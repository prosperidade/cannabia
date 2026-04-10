"""
Knowledge base management API.
Prefix: /api/v1/knowledge
"""
from __future__ import annotations

import logging

from flask import Blueprint, g, request
from flask_login import current_user

from src.infra.database import db_cursor
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _paginate,
    _pagination_args,
    _require_json_csrf,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.knowledge_routes")
knowledge_bp = Blueprint("knowledge", __name__, url_prefix="/api/v1/knowledge")


@knowledge_bp.get("/catalog")
@api_role_required("Admin", "Medico")
def list_catalog():
    """List all documents in the knowledge catalog."""
    page, page_size = _pagination_args()
    doc_type = request.args.get("doc_type", "").strip()
    source = request.args.get("source", "").strip()
    status = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            where = ["1=1"]
            params = []

            if doc_type:
                where.append("doc_type = %s")
                params.append(doc_type)
            if source:
                where.append("source = %s")
                params.append(source)
            if status:
                where.append("status = %s")
                params.append(status)
            if search:
                where.append("(title ILIKE %s OR abstract ILIKE %s OR norm_number ILIKE %s)")
                like = f"%{search}%"
                params.extend([like, like, like])

            cursor.execute(
                f"""
                SELECT id, title, doc_type, source, source_url, doi,
                       category, tags, authors, journal, published_date,
                       norm_number, norm_body, norm_status,
                       storage_type, chromadb_chunks, google_file_uri,
                       status, ingested_by, ingested_at, created_at
                FROM knowledge_catalog
                WHERE {' AND '.join(where)}
                ORDER BY created_at DESC
                """,
                tuple(params),
            )
            rows = cursor.fetchall()

            # Stats
            cursor.execute("SELECT doc_type, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY doc_type")
            type_stats = {r["doc_type"]: r["cnt"] for r in cursor.fetchall()}

            cursor.execute("SELECT storage_type, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY storage_type")
            storage_stats = {r["storage_type"]: r["cnt"] for r in cursor.fetchall()}

            items, page_meta = _paginate(rows, page, page_size)
            meta = {**page_meta, "type_stats": type_stats, "storage_stats": storage_stats}
            return _success(items, meta=meta)
    except Exception:
        logger.error("Error listing catalog", exc_info=True)
        return _success([], meta={"page": page, "page_size": page_size, "total": 0})


@knowledge_bp.get("/catalog/<int:doc_id>")
@api_role_required("Admin", "Medico")
def get_catalog_item(doc_id: int):
    """Get a single catalog item with full details."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute("SELECT * FROM knowledge_catalog WHERE id = %s", (doc_id,))
            row = cursor.fetchone()
            if not row:
                return _error("not_found", "Documento nao encontrado.", 404)
            return _success(row)
    except Exception:
        logger.error("Error fetching catalog item", exc_info=True)
        return _error("internal_error", "Falha ao buscar documento.", 500)


@knowledge_bp.post("/auto-search")
@api_role_required("Admin", "Medico")
def trigger_auto_search():
    """Trigger automatic PubMed + legislation search."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    terms = payload.get("terms")  # Optional custom search terms
    max_per_term = payload.get("max_per_term", 5)

    try:
        from src.ai.agents.extrator import AgenteExtrator

        agent = AgenteExtrator()
        result = agent.run(action="auto_search", terms=terms, max_per_term=max_per_term)

        return _success({
            "success": result.success,
            "total_registered": result.data.get("total_registered", 0),
            "total_found": result.data.get("total_found", 0),
            "terms_searched": result.data.get("terms_searched", 0),
            "details": result.data.get("details", []),
            "duration_ms": result.duration_ms,
        })
    except Exception:
        logger.error("Auto-search failed", exc_info=True)
        return _error("internal_error", "Falha na busca automatica.", 500)


@knowledge_bp.post("/search-pubmed")
@api_role_required("Admin", "Medico")
def search_pubmed():
    """Search PubMed for specific articles."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    query = (payload.get("query") or "").strip()
    if not query:
        return _error("validation_error", "query e obrigatorio.", 422)

    try:
        from src.ai.agents.extrator import AgenteExtrator

        agent = AgenteExtrator()
        result = agent.run(action="search_pubmed", query=query, max_results=payload.get("max_results", 10))
        return _success(result.data)
    except Exception:
        logger.error("PubMed search failed", exc_info=True)
        return _error("internal_error", "Falha na busca PubMed.", 500)


@knowledge_bp.post("/classify")
@api_role_required("Admin", "Medico")
def classify_document():
    """Classify a document by type."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    try:
        from src.ai.agents.extrator import AgenteExtrator

        agent = AgenteExtrator()
        result = agent.run(
            action="classify",
            title=payload.get("title", ""),
            content=payload.get("content", ""),
            filename=payload.get("filename", ""),
        )
        return _success(result.data)
    except Exception:
        logger.error("Classification failed", exc_info=True)
        return _error("internal_error", "Falha na classificacao.", 500)


@knowledge_bp.get("/stats")
@api_role_required("Admin", "Medico")
def knowledge_stats():
    """Get knowledge base statistics."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute("SELECT COUNT(*) AS total FROM knowledge_catalog")
            total = cursor.fetchone()["total"]

            cursor.execute(
                "SELECT doc_type, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY doc_type ORDER BY cnt DESC"
            )
            by_type = cursor.fetchall()

            cursor.execute(
                "SELECT source, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY source ORDER BY cnt DESC"
            )
            by_source = cursor.fetchall()

            cursor.execute(
                "SELECT storage_type, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY storage_type ORDER BY cnt DESC"
            )
            by_storage = cursor.fetchall()

            cursor.execute(
                "SELECT status, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY status ORDER BY cnt DESC"
            )
            by_status = cursor.fetchall()

        # ChromaDB stats
        chromadb_chunks = 0
        try:
            from src.knowledge.vector_store import KnowledgeStore

            store = KnowledgeStore()
            chromadb_chunks = store.count()
        except Exception:
            pass

        # Google Files stats
        google_files = 0
        try:
            from src.knowledge.google_files import list_uploaded_files

            google_files = len(list_uploaded_files())
        except Exception:
            pass

        return _success({
            "total_documents": total,
            "by_type": by_type,
            "by_source": by_source,
            "by_storage": by_storage,
            "by_status": by_status,
            "chromadb_chunks": chromadb_chunks,
            "google_files_count": google_files,
        })
    except Exception:
        logger.error("Error fetching knowledge stats", exc_info=True)
        return _success({
            "total_documents": 0,
            "by_type": [],
            "by_source": [],
            "by_storage": [],
            "by_status": [],
        })


@knowledge_bp.get("/monitors")
@api_role_required("Admin", "Medico")
def list_monitors():
    """List all knowledge source monitors."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT id, name, url, source_type, search_query,
                       check_interval_hours, max_items, is_active,
                       last_checked_at, items_found, created_at
                FROM knowledge_monitors
                ORDER BY is_active DESC, last_checked_at ASC NULLS FIRST
                """
            )
            monitors = cursor.fetchall()
            return _success(monitors)
    except Exception:
        logger.error("Error listing monitors", exc_info=True)
        return _success([])


@knowledge_bp.post("/monitors")
@api_role_required("Admin")
def create_monitor():
    """Create a new knowledge source monitor."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    name = (payload.get("name") or "").strip()
    url = (payload.get("url") or "").strip()
    source_type = (payload.get("source_type") or "html_page").strip()

    if not name or not url:
        return _error("validation_error", "name e url sao obrigatorios.", 422)

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute(
                """
                INSERT INTO knowledge_monitors
                    (name, url, source_type, search_query, check_interval_hours, max_items, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id, created_at
                """,
                (
                    name, url, source_type,
                    payload.get("search_query"),
                    payload.get("check_interval_hours", 24),
                    payload.get("max_items", 10),
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return _success({"id": row["id"], "created_at": row["created_at"]}, status=201)
    except Exception:
        logger.error("Error creating monitor", exc_info=True)
        return _error("internal_error", "Falha ao criar monitor.", 500)


@knowledge_bp.patch("/monitors/<int:monitor_id>")
@api_role_required("Admin")
def toggle_monitor(monitor_id: int):
    """Toggle monitor active/inactive."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    is_active = payload.get("is_active")

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute(
                "UPDATE knowledge_monitors SET is_active = %s, updated_at = NOW() WHERE id = %s RETURNING id, is_active",
                (bool(is_active), monitor_id),
            )
            row = cursor.fetchone()
            if not row:
                return _error("not_found", "Monitor nao encontrado.", 404)
            conn.commit()
            return _success(row)
    except Exception:
        logger.error("Error toggling monitor", exc_info=True)
        return _error("internal_error", "Falha ao atualizar monitor.", 500)


@knowledge_bp.post("/monitors/run")
@api_role_required("Admin", "Medico")
def run_monitors():
    """Trigger all due monitors to check for new content."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    try:
        from src.ai.agents.extrator import AgenteExtrator
        agent = AgenteExtrator()
        result = agent.run(action="run_monitors")
        return _success(result.data)
    except Exception:
        logger.error("Monitor run failed", exc_info=True)
        return _error("internal_error", "Falha ao executar monitores.", 500)
