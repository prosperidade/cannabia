"""
Knowledge base management API.

Prefixo: /api/v1/knowledge

Politica de acesso (P1 do progresso25):
  - A base de conhecimento e EXPLICITAMENTE GLOBAL — todos os tenants
    credenciados leem e adicionam num pool compartilhado. Nao existe
    `tenant_id` nem `clinic_id` em knowledge_catalog/knowledge_monitors
    (migration 040 removeu o vestigio que existia).
  - Leitura e adicao: Admin global, AdminClinica, Medico.
  - Recepcao, Financeiro e Paciente NAO acessam (decisao do produto:
    a base e curatorial-cientifica, restrita a quem tem expertise).
  - Gestao de monitors (criar/toggle): Admin global e AdminClinica.
  - DELETE de catalogo/monitor:
      * Admin global  -> deleta qualquer item
      * AdminClinica  -> deleta apenas o que ela mesma adicionou
      * Medico        -> deleta apenas o que ele mesmo adicionou
    Recorda-se de quem adicionou via `created_by` (migration 040).
"""
from __future__ import annotations

import logging
from typing import Optional

from flask import Blueprint, request
from flask_login import current_user
from psycopg2 import DatabaseError, OperationalError

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
from src.infra.security import get_effective_roles

logger = logging.getLogger("cannabia.knowledge_routes")
knowledge_bp = Blueprint("knowledge", __name__, url_prefix="/api/v1/knowledge")


# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------

def _current_user_id() -> Optional[int]:
    """Id do usuario autenticado ou None. Usado para gravar `created_by`."""
    try:
        if current_user.is_authenticated:
            return int(current_user.id)
    except (RuntimeError, AttributeError):  # pragma: no cover — flask_login fora do request context
        pass
    return None


def _is_admin_global() -> bool:
    """True se o usuario tem a role Admin global (super admin)."""
    return "Admin" in (get_effective_roles() or set())


def _can_delete(created_by: Optional[int]) -> bool:
    """Regra de DELETE: Admin global pode tudo; demais so o que criaram."""
    if _is_admin_global():
        return True
    user_id = _current_user_id()
    if user_id is None or created_by is None:
        return False
    return int(created_by) == int(user_id)


# ---------------------------------------------------------------------------
# Catalogo — leitura
# ---------------------------------------------------------------------------

@knowledge_bp.get("/catalog")
@api_role_required("Admin", "AdminClinica", "Medico")
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
                       status, ingested_by, ingested_at, created_at,
                       created_by
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
    except OperationalError:
        logger.error("DB unavailable on knowledge.list_catalog", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, TypeError, ValueError, KeyError):
        logger.error("Error listing catalog", exc_info=True)
        return _success([], meta={"page": page, "page_size": page_size, "total": 0})


@knowledge_bp.get("/catalog/<int:doc_id>")
@api_role_required("Admin", "AdminClinica", "Medico")
def get_catalog_item(doc_id: int):
    """Get a single catalog item with full details."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute("SELECT * FROM knowledge_catalog WHERE id = %s", (doc_id,))
            row = cursor.fetchone()
            if not row:
                return _error("not_found", "Documento nao encontrado.", 404)
            return _success(row)
    except OperationalError:
        logger.error("DB unavailable on knowledge.get_catalog_item", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except DatabaseError:
        logger.error("Error fetching catalog item", exc_info=True)
        return _error("internal_error", "Falha ao buscar documento.", 500)


@knowledge_bp.delete("/catalog/<int:doc_id>")
@api_role_required("Admin", "AdminClinica", "Medico")
def delete_catalog_item(doc_id: int):
    """Delete a catalog item.

    Admin global pode deletar qualquer item; AdminClinica e Medico
    apenas o que eles mesmos adicionaram.
    """
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute(
                "SELECT id, created_by FROM knowledge_catalog WHERE id = %s",
                (doc_id,),
            )
            row = cursor.fetchone()
            if not row:
                return _error("not_found", "Documento nao encontrado.", 404)

            if not _can_delete(row.get("created_by")):
                return _error(
                    "forbidden",
                    "Voce so pode deletar documentos que voce mesmo adicionou.",
                    403,
                )

            cursor.execute("DELETE FROM knowledge_catalog WHERE id = %s", (doc_id,))
            conn.commit()
            return _success({"deleted": True, "id": doc_id})
    except OperationalError:
        logger.error("DB unavailable on knowledge.delete_catalog_item", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, TypeError, ValueError):
        logger.error("Error deleting catalog item", exc_info=True)
        return _error("internal_error", "Falha ao deletar documento.", 500)


# ---------------------------------------------------------------------------
# Catalogo — adicao via agente (busca PubMed, auto-search, classificacao)
# ---------------------------------------------------------------------------

@knowledge_bp.post("/auto-search")
@api_role_required("Admin", "AdminClinica", "Medico")
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
        result = agent.run(
            action="auto_search",
            terms=terms,
            max_per_term=max_per_term,
            created_by=_current_user_id(),
        )

        return _success({
            "success": result.success,
            "total_registered": result.data.get("total_registered", 0),
            "total_found": result.data.get("total_found", 0),
            "terms_searched": result.data.get("terms_searched", 0),
            "details": result.data.get("details", []),
            "duration_ms": result.duration_ms,
        })
    except (RuntimeError, ValueError, KeyError, AttributeError):
        logger.error("Auto-search failed", exc_info=True)
        return _error("internal_error", "Falha na busca automatica.", 500)


@knowledge_bp.post("/search-pubmed")
@api_role_required("Admin", "AdminClinica", "Medico")
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
        result = agent.run(
            action="search_pubmed",
            query=query,
            max_results=payload.get("max_results", 10),
            created_by=_current_user_id(),
        )
        return _success(result.data)
    except (RuntimeError, ValueError, KeyError, AttributeError):
        logger.error("PubMed search failed", exc_info=True)
        return _error("internal_error", "Falha na busca PubMed.", 500)


@knowledge_bp.post("/classify")
@api_role_required("Admin", "AdminClinica", "Medico")
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
    except (RuntimeError, ValueError, KeyError, AttributeError):
        logger.error("Classification failed", exc_info=True)
        return _error("internal_error", "Falha na classificacao.", 500)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@knowledge_bp.get("/stats")
@api_role_required("Admin", "AdminClinica", "Medico")
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
        except (ImportError, RuntimeError, OSError, ValueError, AttributeError):
            # Sub-feature opcional: ChromaDB pode estar offline/nao instalado.
            # Stats degradam para 0 sem quebrar a rota.
            logger.debug("ChromaDB stats indisponivel (KnowledgeStore.count falhou)", exc_info=True)

        # Google Files stats
        google_files = 0
        try:
            from src.knowledge.google_files import list_uploaded_files

            google_files = len(list_uploaded_files())
        except (ImportError, RuntimeError, OSError, ValueError, AttributeError):
            # Sub-feature opcional: Google Files pode estar sem credencial/offline.
            logger.debug("Google Files stats indisponivel (list_uploaded_files falhou)", exc_info=True)

        return _success({
            "total_documents": total,
            "by_type": by_type,
            "by_source": by_source,
            "by_storage": by_storage,
            "by_status": by_status,
            "chromadb_chunks": chromadb_chunks,
            "google_files_count": google_files,
        })
    except OperationalError:
        logger.error("DB unavailable on knowledge.knowledge_stats", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, TypeError, ValueError, KeyError):
        logger.error("Error fetching knowledge stats", exc_info=True)
        return _success({
            "total_documents": 0,
            "by_type": [],
            "by_source": [],
            "by_storage": [],
            "by_status": [],
        })


# ---------------------------------------------------------------------------
# Monitors
# ---------------------------------------------------------------------------

@knowledge_bp.get("/monitors")
@api_role_required("Admin", "AdminClinica", "Medico")
def list_monitors():
    """List all knowledge source monitors."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT id, name, url, source_type, search_query,
                       check_interval_hours, max_items, is_active,
                       last_checked_at, items_found, created_at,
                       created_by
                FROM knowledge_monitors
                ORDER BY is_active DESC, last_checked_at ASC NULLS FIRST
                """
            )
            monitors = cursor.fetchall()
            return _success(monitors)
    except OperationalError:
        logger.error("DB unavailable on knowledge.list_monitors", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, TypeError, ValueError, KeyError):
        logger.error("Error listing monitors", exc_info=True)
        return _success([])


@knowledge_bp.post("/monitors")
@api_role_required("Admin", "AdminClinica")
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
                    (name, url, source_type, search_query, check_interval_hours,
                     max_items, is_active, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)
                RETURNING id, created_at
                """,
                (
                    name, url, source_type,
                    payload.get("search_query"),
                    payload.get("check_interval_hours", 24),
                    payload.get("max_items", 10),
                    _current_user_id(),
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return _success({"id": row["id"], "created_at": row["created_at"]}, status=201)
    except OperationalError:
        logger.error("DB unavailable on knowledge.create_monitor", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, TypeError, ValueError, KeyError):
        logger.error("Error creating monitor", exc_info=True)
        return _error("internal_error", "Falha ao criar monitor.", 500)


@knowledge_bp.patch("/monitors/<int:monitor_id>")
@api_role_required("Admin", "AdminClinica")
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
    except OperationalError:
        logger.error("DB unavailable on knowledge.toggle_monitor", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, TypeError, ValueError, KeyError):
        logger.error("Error toggling monitor", exc_info=True)
        return _error("internal_error", "Falha ao atualizar monitor.", 500)


@knowledge_bp.delete("/monitors/<int:monitor_id>")
@api_role_required("Admin", "AdminClinica")
def delete_monitor(monitor_id: int):
    """Delete a monitor.

    Admin global pode deletar qualquer; AdminClinica apenas o que ela
    mesma criou.
    """
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute(
                "SELECT id, created_by FROM knowledge_monitors WHERE id = %s",
                (monitor_id,),
            )
            row = cursor.fetchone()
            if not row:
                return _error("not_found", "Monitor nao encontrado.", 404)

            if not _can_delete(row.get("created_by")):
                return _error(
                    "forbidden",
                    "Voce so pode deletar monitores que voce mesmo criou.",
                    403,
                )

            cursor.execute("DELETE FROM knowledge_monitors WHERE id = %s", (monitor_id,))
            conn.commit()
            return _success({"deleted": True, "id": monitor_id})
    except OperationalError:
        logger.error("DB unavailable on knowledge.delete_monitor", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, TypeError, ValueError):
        logger.error("Error deleting monitor", exc_info=True)
        return _error("internal_error", "Falha ao deletar monitor.", 500)


@knowledge_bp.post("/monitors/run")
@api_role_required("Admin", "AdminClinica", "Medico")
def run_monitors():
    """Trigger all due monitors to check for new content."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    try:
        from src.ai.agents.extrator import AgenteExtrator
        agent = AgenteExtrator()
        result = agent.run(action="run_monitors", created_by=_current_user_id())
        return _success(result.data)
    except (RuntimeError, ValueError, KeyError, AttributeError):
        logger.error("Monitor run failed", exc_info=True)
        return _error("internal_error", "Falha ao executar monitores.", 500)
