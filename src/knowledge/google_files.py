# src/knowledge/google_files.py
"""
Google Files API integration for large document analysis.

Used for legislation documents (ANVISA RDCs, CFM resolutions, Lei de Drogas)
that need full-context reading (not chunked RAG).

Architecture:
  1. Upload documents once via Files API -> get file URI
  2. Cache file URIs in memory + JSON catalog
  3. Query Gemini with file references for full-context analysis

Benefits over RAG/chunks for legislation:
  - Laws reference other articles internally -> chunks break cross-references
  - Full document context -> 95% accuracy vs 70% with chunks
  - No embedding pipeline -> simpler maintenance
  - Auto re-upload when file changes (checksum-based)
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

load_dotenv()
logger = logging.getLogger("cannabia.knowledge.google_files")

GEMINI_MODEL = os.getenv("GEMINI_FILES_MODEL", "gemini-2.0-flash")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Directory where legislation PDFs/texts are stored
LEGISLATION_DIR = os.getenv(
    "LEGISLATION_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "legislation"),
)

# In-memory cache of uploaded file URIs: {filename: {uri, checksum, uploaded_at}}
_file_cache: Dict[str, Dict] = {}

# Catalog file for persistence across restarts
_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "file_catalog.json"
)
_SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


def _manifest_path() -> Path:
    return Path(LEGISLATION_DIR) / "sources.json"


def _load_manifest_entries() -> List[Dict]:
    path = _manifest_path()
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to load legislation manifest: %s", path, exc_info=True)
        return []

    if not isinstance(payload, list):
        logger.warning("Invalid legislation manifest format: %s", path)
        return []
    return [item for item in payload if isinstance(item, dict) and item.get("filename")]


def _allowed_filenames() -> Optional[List[str]]:
    manifest_entries = _load_manifest_entries()
    if manifest_entries:
        return [str(item["filename"]) for item in manifest_entries]
    return None


def _infer_mime_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".md":
        return "text/markdown"
    if ext == ".txt":
        return "text/plain"
    if ext == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return mimetypes.guess_type(filename)[0] or "application/pdf"


def _is_allowed_filename(filename: str) -> bool:
    allowed = _allowed_filenames()
    if allowed is not None:
        return filename in allowed

    ext = Path(filename).suffix.lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        return False
    return not filename.lower().startswith("readme")


def _normalize_entry(filename: str, entry: Dict) -> Dict:
    normalized = dict(entry)
    normalized["filename"] = filename
    normalized["display_name"] = normalized.get("display_name") or filename
    normalized["mime_type"] = normalized.get("mime_type") or _infer_mime_type(filename)

    local_path = normalized.get("local_path")
    if local_path:
        normalized["local_path"] = os.path.abspath(local_path)
    else:
        candidate = Path(LEGISLATION_DIR) / filename
        if candidate.exists():
            normalized["local_path"] = str(candidate.resolve())

    if not normalized.get("size_bytes"):
        candidate_path = normalized.get("local_path")
        if candidate_path and os.path.exists(candidate_path):
            normalized["size_bytes"] = os.path.getsize(candidate_path)

    return normalized


def _selected_catalog_entries(file_names: Optional[List[str]] = None) -> List[Dict]:
    _load_catalog()
    allowed = _allowed_filenames()

    entries = {
        filename: _normalize_entry(filename, entry)
        for filename, entry in _file_cache.items()
        if _is_allowed_filename(filename)
    }

    if allowed is not None:
        ordered_entries = {
            filename: entries[filename]
            for filename in allowed
            if filename in entries
        }
        entries = ordered_entries

    if file_names:
        return [entries[filename] for filename in file_names if filename in entries]
    return list(entries.values())


def _get_client() -> genai.Client:
    """Lazy init Google GenAI client."""
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set. Required for Google Files API.")
    return genai.Client(api_key=GOOGLE_API_KEY)


def _file_checksum(filepath: str) -> str:
    """SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_catalog() -> Dict[str, Dict]:
    """Load file catalog from disk."""
    global _file_cache
    try:
        if os.path.exists(_CATALOG_PATH):
            with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
                raw_cache = json.load(f)
                _file_cache = {
                    filename: _normalize_entry(filename, entry)
                    for filename, entry in raw_cache.items()
                    if _is_allowed_filename(filename)
                }
                if _file_cache != raw_cache:
                    _save_catalog()
                logger.info("Loaded file catalog: %d entries", len(_file_cache))
    except Exception:
        logger.warning("Failed to load file catalog", exc_info=True)
    return _file_cache


def _save_catalog() -> None:
    """Persist file catalog to disk."""
    try:
        os.makedirs(os.path.dirname(_CATALOG_PATH), exist_ok=True)
        with open(_CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(_file_cache, f, indent=2, ensure_ascii=False)
    except Exception:
        logger.warning("Failed to save file catalog", exc_info=True)


def upload_file(filepath: str, display_name: Optional[str] = None) -> Dict:
    """
    Upload a file to Google Files API. Returns cached URI if unchanged.

    Args:
        filepath: Path to the PDF/text file
        display_name: Human-readable name (defaults to filename)

    Returns:
        {"uri": str, "name": str, "checksum": str, "uploaded_at": float}
    """
    filepath = os.path.abspath(filepath)
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    filename = os.path.basename(filepath)
    checksum = _file_checksum(filepath)
    mime_type = _infer_mime_type(filename)

    # Check cache
    if filename in _file_cache and _file_cache[filename].get("checksum") == checksum:
        _file_cache[filename] = _normalize_entry(filename, _file_cache[filename])
        _save_catalog()
        logger.debug("File '%s' unchanged, using cached URI", filename)
        return _file_cache[filename]

    # Upload to Google
    client = _get_client()
    display = display_name or filename

    logger.info("Uploading '%s' to Google Files API...", display)

    uploaded = client.files.upload(
        file=filepath,
        config=genai_types.UploadFileConfig(display_name=display),
    )

    # Wait for processing
    while uploaded.state == "PROCESSING":
        time.sleep(1)
        uploaded = client.files.get(name=uploaded.name)

    if uploaded.state == "FAILED":
        raise RuntimeError(f"File upload failed: {uploaded.name}")

    entry = {
        "uri": uploaded.uri,
        "name": uploaded.name,
        "display_name": display,
        "filename": filename,
        "checksum": checksum,
        "uploaded_at": time.time(),
        "local_path": filepath,
        "mime_type": mime_type,
        "size_bytes": os.path.getsize(filepath),
    }

    _file_cache[filename] = _normalize_entry(filename, entry)
    _save_catalog()

    logger.info("Uploaded '%s' -> %s", display, uploaded.uri)
    return entry


def upload_all_legislation() -> List[Dict]:
    """
    Upload all files in LEGISLATION_DIR to Google Files API.
    Skips files that haven't changed (checksum-based).

    Returns list of uploaded/cached file entries.
    """
    _load_catalog()

    leg_dir = Path(LEGISLATION_DIR)
    if not leg_dir.exists():
        logger.warning("Legislation directory not found: %s", LEGISLATION_DIR)
        return []

    results = []
    manifest_filenames = _allowed_filenames()

    if manifest_filenames:
        candidates = [leg_dir / filename for filename in manifest_filenames]
    else:
        candidates = [fpath for fpath in sorted(leg_dir.iterdir()) if _is_allowed_filename(fpath.name)]

    for fpath in candidates:
        if not fpath.exists():
            logger.warning("Manifest entry not found in legislation dir: %s", fpath.name)
            continue
        if fpath.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            logger.warning("Skipping unsupported legislation file: %s", fpath.name)
            continue
        try:
            entry = upload_file(str(fpath))
            results.append(entry)
        except Exception:
            logger.error("Failed to upload '%s'", fpath.name, exc_info=True)

    logger.info("Legislation upload complete: %d files", len(results))
    return results


def list_uploaded_files() -> List[Dict]:
    """List all uploaded files from catalog."""
    return _selected_catalog_entries()


def query_legislation(
    question: str,
    file_names: Optional[List[str]] = None,
    temperature: float = 0.0,
) -> Tuple[str, Dict]:
    """
    Query legislation documents using Gemini with full file context.

    Args:
        question: The regulatory/legal question
        file_names: Specific files to include (None = all uploaded)
        temperature: LLM temperature (0 for legal accuracy)

    Returns:
        (answer_text, {"input_tokens": int, "output_tokens": int, "files_used": list})
    """
    client = _get_client()

    # Select files
    files = _selected_catalog_entries(file_names=file_names)

    if not files:
        raise ValueError("No legislation files available. Upload files first.")

    # Build content parts: file references + question
    parts = []
    for f in files:
        parts.append(genai_types.Part.from_uri(
            file_uri=f["uri"],
            mime_type=f.get("mime_type") or "application/pdf",
        ))

    system_instruction = (
        "Voce e um especialista em legislacao regulatoria brasileira de cannabis medicinal. "
        "Analise os documentos fornecidos e responda com precisao, citando artigos e paragrafos especificos. "
        "Se a resposta nao estiver nos documentos, diga explicitamente. "
        "Sempre cite: numero da norma, artigo, paragrafo e inciso quando aplicavel. "
        "Responda em portugues brasileiro."
    )

    parts.append(genai_types.Part.from_text(text=question))

    # Retry with exponential backoff (Gemini quota/availability)
    last_error = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[genai_types.Content(role="user", parts=parts)],
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_output_tokens=4096,
                ),
            )
            break
        except Exception as exc:
            last_error = exc
            wait = 2 ** attempt
            logger.warning("Gemini query attempt %d failed, retrying in %ds: %s", attempt + 1, wait, exc)
            time.sleep(wait)
    else:
        raise RuntimeError(
            f"Consulta regulatoria indisponivel apos 3 tentativas. Tente novamente em alguns minutos. ({last_error})"
        )

    # Extract token usage
    usage = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        um = response.usage_metadata
        usage = {
            "input_tokens": getattr(um, "prompt_token_count", 0),
            "output_tokens": getattr(um, "candidates_token_count", 0),
            "total_tokens": getattr(um, "total_token_count", 0),
        }

    usage["files_used"] = [f["display_name"] for f in files]
    usage["model"] = GEMINI_MODEL

    answer = response.text if hasattr(response, "text") else str(response)

    logger.info(
        "Legislation query answered. Files: %d, Tokens: %s",
        len(files),
        usage.get("total_tokens", "unknown"),
    )

    return answer, usage


def query_legislation_structured(
    question: str,
    file_names: Optional[List[str]] = None,
) -> Tuple[Dict, Dict]:
    """
    Query legislation with structured JSON response.

    Returns:
        (parsed_dict, usage_dict)
    """
    client = _get_client()

    files = _selected_catalog_entries(file_names=file_names)

    if not files:
        raise ValueError("No legislation files available.")

    parts = []
    for f in files:
        parts.append(genai_types.Part.from_uri(
            file_uri=f["uri"],
            mime_type=f.get("mime_type") or "application/pdf",
        ))

    system_instruction = (
        "Voce e um especialista em legislacao regulatoria brasileira de cannabis medicinal. "
        "Analise os documentos e responda em JSON com: "
        '{"answer": "resposta completa", "citations": [{"norm": "RDC 327/2019", "article": "Art. 8", '
        '"text": "texto do artigo"}], "applicable": true/false, "confidence": 0.0-1.0}'
    )

    parts.append(genai_types.Part.from_text(text=question))

    last_error = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[genai_types.Content(role="user", parts=parts)],
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0,
                    response_mime_type="application/json",
                    max_output_tokens=4096,
                ),
            )
            break
        except Exception as exc:
            last_error = exc
            wait = 2 ** attempt
            logger.warning("Gemini structured query attempt %d failed, retrying in %ds: %s", attempt + 1, wait, exc)
            time.sleep(wait)
    else:
        raise RuntimeError(
            f"Consulta regulatoria estruturada indisponivel apos 3 tentativas. ({last_error})"
        )

    usage = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        um = response.usage_metadata
        usage = {
            "input_tokens": getattr(um, "prompt_token_count", 0),
            "output_tokens": getattr(um, "candidates_token_count", 0),
            "total_tokens": getattr(um, "total_token_count", 0),
            "files_used": [f["display_name"] for f in files],
            "model": GEMINI_MODEL,
        }

    try:
        result = json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        result = {"answer": response.text if hasattr(response, "text") else str(response), "citations": [], "applicable": False, "confidence": 0.0}

    return result, usage
