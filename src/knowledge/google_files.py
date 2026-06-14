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

# gemini-2.0-flash foi DESCONTINUADO (404 "no longer available") — doc 30 C3.
# Default migrado para gemini-2.5-flash (29.4 R2). Override via GEMINI_FILES_MODEL.
GEMINI_MODEL = os.getenv("GEMINI_FILES_MODEL", "gemini-2.5-flash")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Fallback OpenAI para consultas de legislacao quando o Gemini falha (quota/erro).
# IMPORTANTE: o Gemini le PDFs escaneados (multimodal); o OpenAI so enxerga TEXTO,
# entao o fallback cobre as normas com arquivo textual (.md/.txt). Normas so-imagem
# (PDFs escaneados, ex.: RDCs de 2026) ficam indisponiveis no modo fallback — isso
# e sinalizado explicitamente na resposta e no usage (image_only_skipped).
LEGISLATION_FALLBACK_MODEL = os.getenv("LEGISLATION_FALLBACK_MODEL", "gpt-4.1-mini")
_TEXT_EXTENSIONS = {".md", ".txt"}
_openai_client = None

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
    except (OSError, json.JSONDecodeError):
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
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to load file catalog", exc_info=True)
    return _file_cache


def _save_catalog() -> None:
    """Persist file catalog to disk."""
    try:
        os.makedirs(os.path.dirname(_CATALOG_PATH), exist_ok=True)
        with open(_CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(_file_cache, f, indent=2, ensure_ascii=False)
    except (OSError, TypeError):
        # OSError: disco cheio/permissao; TypeError: entry com tipo nao-serializavel
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
        except Exception:  # noqa: BLE001 — boundary do loop de upload
            # Google Files API pode levantar qualquer tipo (genai.errors, httpx, OSError,
            # RuntimeError). Capturamos amplo para nao quebrar o batch inteiro por um
            # arquivo bichado; cada falha vai com exc_info=True para diagnostico.
            logger.error("Failed to upload '%s'", fpath.name, exc_info=True)

    logger.info("Legislation upload complete: %d files", len(results))
    return results


def list_uploaded_files() -> List[Dict]:
    """List all uploaded files from catalog."""
    return _selected_catalog_entries()


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client


def _load_legislation_texts() -> Tuple[List[Tuple[str, str]], List[str]]:
    """Carrega o texto das normas com arquivo textual (.md/.txt) do manifesto.

    Retorna (textos, so_imagem):
      - textos     = [(titulo, conteudo)] das normas com texto disponivel.
      - so_imagem  = titulos das normas sem texto (PDFs escaneados) — fora do fallback.
    """
    texts: List[Tuple[str, str]] = []
    image_only: List[str] = []
    for entry in _load_manifest_entries():
        title = entry.get("title") or entry.get("norm_number") or entry.get("filename")
        # Prefere a versao sanitizada (texto limpo) quando declarada no manifesto.
        candidates = []
        if entry.get("sanitized_filename"):
            candidates.append(entry["sanitized_filename"])
        candidates.append(entry.get("filename"))
        text_path = None
        for name in candidates:
            if name and Path(name).suffix.lower() in _TEXT_EXTENSIONS:
                candidate = Path(LEGISLATION_DIR) / name
                if candidate.exists():
                    text_path = candidate
                    break
        if text_path is None:
            image_only.append(title)
            continue
        try:
            texts.append((title, text_path.read_text(encoding="utf-8")))
        except OSError:
            image_only.append(title)
    return texts, image_only


def _query_legislation_openai_fallback(question: str, temperature: float) -> Tuple[str, Dict]:
    """Fallback de query_legislation: responde via OpenAI sobre o TEXTO das normas.

    Acionado quando o Gemini esgota as tentativas. Cobre normas textuais; normas
    so-imagem ficam de fora (sinalizado). Levanta RuntimeError se nao houver
    OPENAI_API_KEY ou corpus textual.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Fallback OpenAI indisponivel: OPENAI_API_KEY ausente.")
    texts, image_only = _load_legislation_texts()
    if not texts:
        raise RuntimeError("Fallback OpenAI sem corpus textual de legislacao disponivel.")

    corpus = "\n\n".join(f"===== {title} =====\n{content}" for title, content in texts)
    disclaimer = ""
    if image_only:
        disclaimer = (
            " ATENCAO: modo de contingencia (Gemini indisponivel) — cobre apenas "
            "normas com texto. NAO consultadas neste modo (PDF escaneado): "
            + ", ".join(image_only) + "."
        )
    system_instruction = (
        "Voce e um especialista em legislacao regulatoria brasileira de cannabis medicinal. "
        "Responda com precisao usando SOMENTE os documentos fornecidos, citando numero da norma, "
        "artigo, paragrafo e inciso quando aplicavel. Se a resposta nao estiver nos documentos, "
        "diga explicitamente. Responda em portugues brasileiro." + disclaimer
    )
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=LEGISLATION_FALLBACK_MODEL,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"DOCUMENTOS:\n{corpus}\n\nPERGUNTA: {question}"},
        ],
        temperature=temperature,
        max_tokens=4096,
    )
    answer = (response.choices[0].message.content or "") if response.choices else ""
    u = getattr(response, "usage", None)
    usage = {
        "input_tokens": getattr(u, "prompt_tokens", 0) if u else 0,
        "output_tokens": getattr(u, "completion_tokens", 0) if u else 0,
        "total_tokens": getattr(u, "total_tokens", 0) if u else 0,
        "files_used": [t for t, _ in texts],
        "model": LEGISLATION_FALLBACK_MODEL,
        "fallback": True,
        "fallback_reason": "gemini_unavailable",
        "image_only_skipped": image_only,
    }
    logger.warning(
        "Legislation query via FALLBACK OpenAI (%s). Normas so-imagem puladas: %s",
        LEGISLATION_FALLBACK_MODEL, image_only,
    )
    return answer, usage


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
    # FULL-TEXT DURÁVEL (A5/A11 follow-up): a fonte é o TEXTO das normas (.md em
    # data/legislation, via manifesto), NÃO mais a Gemini Files API (que expirava
    # em 48h). Passa o corpus INTEIRO ao LLM — full-document preserva referências
    # cruzadas da lei (95% vs 70% com chunks). `file_names` mantido por compat; o
    # corpus de legislação é pequeno e vai inteiro.
    texts, image_only = _load_legislation_texts()
    if not texts:
        raise ValueError(
            "Sem texto de legislacao disponivel. Gere os .md com "
            "scripts/ocr_legislation_pdfs.py e declare sanitized_filename no sources.json."
        )
    corpus = "\n\n".join(f"===== {title} =====\n{content}" for title, content in texts)
    files_used = [t for t, _ in texts]

    system_instruction = (
        "Voce e um especialista em legislacao regulatoria brasileira de cannabis medicinal. "
        "Analise os documentos fornecidos e responda com precisao, citando numero da norma, "
        "artigo, paragrafo e inciso quando aplicavel. Se a resposta nao estiver nos documentos, "
        "diga explicitamente. Responda em portugues brasileiro."
    )
    user_text = f"DOCUMENTOS:\n{corpus}\n\nPERGUNTA: {question}"

    client = _get_client()  # manter referencia (evita GC fechar o client mid-call)
    last_error = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[genai_types.Content(
                    role="user", parts=[genai_types.Part.from_text(text=user_text)]
                )],
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_output_tokens=4096,
                ),
            )
            break
        except Exception as exc:  # noqa: BLE001 — boundary do retry de Gemini
            last_error = exc
            wait = 2 ** attempt
            logger.warning("Gemini legislation attempt %d failed, retrying in %ds: %s", attempt + 1, wait, exc)
            time.sleep(wait)
    else:
        # Gemini esgotou as tentativas: fallback OpenAI sobre o MESMO texto.
        logger.error("Gemini indisponivel apos 3 tentativas; acionando fallback OpenAI. (%s)", last_error)
        try:
            return _query_legislation_openai_fallback(question, temperature)
        except Exception as fb_exc:  # noqa: BLE001 — agrega os dois erros
            raise RuntimeError(
                f"Consulta regulatoria indisponivel: Gemini falhou ({last_error}) "
                f"e fallback OpenAI falhou ({fb_exc})."
            )

    usage = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        um = response.usage_metadata
        usage = {
            "input_tokens": getattr(um, "prompt_token_count", 0),
            "output_tokens": getattr(um, "candidates_token_count", 0),
            "total_tokens": getattr(um, "total_token_count", 0),
        }
    usage["files_used"] = files_used
    usage["model"] = GEMINI_MODEL
    usage["fallback"] = False

    answer = response.text if hasattr(response, "text") else str(response)
    logger.info(
        "Legislation query answered (full-text durável, %d normas, %s tokens).",
        len(texts), usage.get("total_tokens", "unknown"),
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
    # FULL-TEXT DURÁVEL (igual a query_legislation): corpus textual, sem Files API.
    texts, image_only = _load_legislation_texts()
    if not texts:
        raise ValueError(
            "Sem texto de legislacao disponivel. Gere os .md com "
            "scripts/ocr_legislation_pdfs.py e declare sanitized_filename no sources.json."
        )
    corpus = "\n\n".join(f"===== {title} =====\n{content}" for title, content in texts)
    files_used = [t for t, _ in texts]

    system_instruction = (
        "Voce e um especialista em legislacao regulatoria brasileira de cannabis medicinal. "
        "Analise os documentos e responda em JSON com: "
        '{"answer": "resposta completa", "citations": [{"norm": "RDC 327/2019", "article": "Art. 8", '
        '"text": "texto do artigo"}], "applicable": true/false, "confidence": 0.0-1.0}'
    )
    user_text = f"DOCUMENTOS:\n{corpus}\n\nPERGUNTA: {question}"

    client = _get_client()  # manter referencia (evita GC fechar o client mid-call)
    last_error = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[genai_types.Content(
                    role="user", parts=[genai_types.Part.from_text(text=user_text)]
                )],
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0,
                    response_mime_type="application/json",
                    max_output_tokens=4096,
                ),
            )
            break
        except Exception as exc:  # noqa: BLE001 — boundary do retry de Gemini structured
            last_error = exc
            wait = 2 ** attempt
            logger.warning("Gemini structured attempt %d failed, retrying in %ds: %s", attempt + 1, wait, exc)
            time.sleep(wait)
    else:
        # Fallback OpenAI: resposta textual embrulhada no formato estruturado.
        logger.error("Gemini structured indisponivel; fallback OpenAI. (%s)", last_error)
        try:
            answer, fb_usage = _query_legislation_openai_fallback(question, 0.0)
            return (
                {"answer": answer, "citations": [], "applicable": True,
                 "confidence": 0.5, "fallback": True},
                fb_usage,
            )
        except Exception as fb_exc:  # noqa: BLE001
            raise RuntimeError(
                f"Consulta regulatoria estruturada indisponivel: Gemini ({last_error}) "
                f"e fallback OpenAI ({fb_exc})."
            )

    usage = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        um = response.usage_metadata
        usage = {
            "input_tokens": getattr(um, "prompt_token_count", 0),
            "output_tokens": getattr(um, "candidates_token_count", 0),
            "total_tokens": getattr(um, "total_token_count", 0),
        }
    usage["files_used"] = files_used
    usage["model"] = GEMINI_MODEL
    usage["fallback"] = False

    try:
        result = json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        result = {"answer": response.text if hasattr(response, "text") else str(response),
                  "citations": [], "applicable": False, "confidence": 0.0}

    return result, usage
