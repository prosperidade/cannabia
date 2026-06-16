# src/web/routes/regulatory.py
"""
Regulatory/legislation query API.
Uses Google Files API for full-document analysis.
"""
from __future__ import annotations

import logging
from flask import Blueprint, g

from src.knowledge.legislation_catalog import sync_legislation_catalog
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _require_json_csrf,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.regulatory")

regulatory_bp = Blueprint("regulatory", __name__, url_prefix="/api/v1/regulatory")


@regulatory_bp.get("/readiness")
@api_role_required("Admin", "Medico")
def regulatory_readiness():
    """REG-8 — relatório de prontidão regulatória do tenant (RDCs 2026).

    O que o tenant pode operar a partir de 04/08/2026 e o que segue
    condicionado/vedado (consome REG-1..4 + vigência). Prontidão, nunca aprovação.
    """
    from src.services.regulatory_readiness import check_regulatory_readiness

    tenant_id = getattr(g, "tenant_id", None) or getattr(g, "clinic_id", None) or 0
    report = check_regulatory_readiness(int(tenant_id))
    return _success(report.to_dict())


@regulatory_bp.get("/files")
@api_role_required("Admin", "Medico")
def list_files():
    """List all uploaded legislation files."""
    try:
        from src.knowledge.google_files import list_uploaded_files
        files = list_uploaded_files()
        return _success(files)
    except (ImportError, OSError, RuntimeError):
        # ImportError: google_files opcional; OSError: cache fs; RuntimeError: Google API
        logger.error("Error listing legislation files", exc_info=True)
        return _success([])


@regulatory_bp.post("/upload")
@api_role_required("Admin")
def upload_files():
    """Upload all legislation files from the data/legislation directory."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    try:
        from src.knowledge.google_files import upload_all_legislation

        results = upload_all_legislation()
        from flask_login import current_user
        try:
            created_by = int(current_user.id) if current_user.is_authenticated else None
        except RuntimeError:
            # flask_login fora do request context
            created_by = None
        catalog_summary = sync_legislation_catalog(
            results,
            ingested_by="manual_upload",
            created_by=created_by,
        )
        return _success({
            "uploaded": len(results),
            "catalog_created": catalog_summary["created"],
            "catalog_updated": catalog_summary["updated"],
            "catalog_total": catalog_summary["total"],
            "files": [{"name": r["display_name"], "size": r.get("size_bytes", 0)} for r in results],
        })
    except Exception:
        logger.error("Error uploading legislation files", exc_info=True)
        return _error("internal_error", "Falha ao enviar arquivos de legislacao.", 500)


@regulatory_bp.post("/query")
@api_role_required("Admin", "Medico")
def query_legislation():
    """Query legislation documents with full context."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    question = (payload.get("question") or "").strip()

    if not question:
        return _error("validation_error", "question e obrigatorio.", 422)

    file_names = payload.get("files")  # Optional: specific files to query
    structured = payload.get("structured", False)

    try:
        if structured:
            from src.knowledge.google_files import query_legislation_structured
            result, usage = query_legislation_structured(question, file_names)
            return _success({"result": result, "usage": usage})
        else:
            from src.knowledge.google_files import query_legislation
            answer, usage = query_legislation(question, file_names)
            return _success({"answer": answer, "usage": usage})
    except ValueError as e:
        return _error("no_files", str(e), 422)
    except Exception:
        logger.error("Error querying legislation", exc_info=True)
        return _error("internal_error", "Falha ao consultar legislacao.", 500)
