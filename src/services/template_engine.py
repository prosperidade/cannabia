"""Template rendering engine — F4.4 do SCC.

Generaliza o renderer de ``governance_dossier.py`` usando o manifesto
central em ``data/templates/registry.yaml`` (F4.3) como fonte de verdade
para resolver ``template_id`` -> arquivo da versao ativa.

Interface publica:

- :func:`resolve` — devolve :class:`TemplateVersionRef` (introspeccao).
- :func:`render` — renderiza e retorna :class:`RenderedDocument` com
  ``content`` e ``content_hash`` SHA-256 (formato esperado por
  ``sops.content_hash`` e ``regulatory_reports.content_hash``).

Comportamento:

- ``StrictUndefined`` por padrao — campo ausente no contexto eleva
  :class:`TemplateRenderError`, evitando documento incompleto silencioso.
- Versao depreciada nao renderiza mais (doc 27 §9.3).
- Formato fora de ``output_formats`` da versao -> :class:`UnsupportedFormatError`.

F4.6 migrara ``governance_dossier.render_dossier_markdown`` para usar
este engine. Por enquanto ele continua standalone para nao expandir o
escopo de F4.4.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml
from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateError,
    UndefinedError,
    select_autoescape,
)

logger = logging.getLogger("cannabia.template_engine")


# ---------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------

TEMPLATES_ROOT = Path(__file__).resolve().parents[2] / "data" / "templates"
REGISTRY_FILE = TEMPLATES_ROOT / "registry.yaml"


# ---------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------

class TemplateEngineError(Exception):
    """Base para erros do template_engine."""


class TemplateNotFoundError(TemplateEngineError):
    """Template id desconhecido ou arquivo .md.j2 ausente no disco."""


class TemplateVersionError(TemplateEngineError):
    """Versao solicitada invalida, depreciada ou sem ``file`` no registry."""


class UnsupportedFormatError(TemplateEngineError):
    """Formato de saida fora de ``output_formats`` da versao."""


class TemplateRenderError(TemplateEngineError):
    """Falha durante renderizacao (ex.: StrictUndefined em campo ausente)."""


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class TemplateVersionRef:
    """Referencia resolvida de uma versao de template."""

    template_id: str
    version: str
    file: str                       # caminho relativo a TEMPLATES_ROOT
    absolute_path: Path
    status: str
    output_formats: tuple[str, ...]
    regulatory_refs: tuple[Any, ...]


@dataclass(frozen=True)
class RenderedDocument:
    """Resultado de uma renderizacao com hash para persistencia/ancoragem."""

    template_id: str
    version: str
    format: str
    content: str
    content_hash: str               # SHA-256 hex (64 chars), UTF-8
    rendered_at: datetime
    template_file: str              # relativo a TEMPLATES_ROOT, para auditoria


# ---------------------------------------------------------------------
# Carga e cache do registry
# ---------------------------------------------------------------------

_registry_cache_lock = threading.Lock()
_registry_cache: Optional[dict[str, Any]] = None

# Status de versao que impedem renderizacao (doc 27 §9.3).
_NON_RENDERABLE_STATUS = frozenset({"deprecated"})


def _load_registry() -> dict[str, Any]:
    """Le e faz cache do registry.yaml. Thread-safe."""
    global _registry_cache
    with _registry_cache_lock:
        if _registry_cache is None:
            if not REGISTRY_FILE.exists():
                raise TemplateEngineError(
                    f"Registry nao encontrado em {REGISTRY_FILE}"
                )
            _registry_cache = yaml.safe_load(
                REGISTRY_FILE.read_text(encoding="utf-8")
            ) or {}
            logger.debug(
                "registry_loaded templates=%d planned=%d",
                len(_registry_cache.get("templates") or []),
                len(_registry_cache.get("planned_templates") or []),
            )
        return _registry_cache


def _invalidate_registry_cache() -> None:
    """Forca recarregamento do registry — util em testes e em hot-reload."""
    global _registry_cache
    with _registry_cache_lock:
        _registry_cache = None


# ---------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------

def resolve(
    template_id: str,
    version: Optional[str] = None,
) -> TemplateVersionRef:
    """Resolve um ``template_id`` em uma referencia concreta.

    Se ``version`` for omitido, usa ``current_version`` do registry.
    Falha cedo (antes da renderizacao) para cada modo conhecido de
    invalidez: id desconhecido, versao desconhecida, versao depreciada,
    entrada sem ``file``, arquivo ausente no disco.
    """
    registry = _load_registry()
    for tpl in registry.get("templates") or []:
        if tpl.get("id") != template_id:
            continue
        versions = tpl.get("versions") or {}
        resolved_version = version or tpl.get("current_version")
        if resolved_version is None:
            raise TemplateVersionError(
                f"Template '{template_id}' sem current_version e "
                "versao nao informada."
            )
        meta = versions.get(resolved_version)
        if meta is None:
            raise TemplateVersionError(
                f"Versao '{resolved_version}' nao existe para '{template_id}'."
            )
        status = meta.get("status") or "active"
        if status in _NON_RENDERABLE_STATUS:
            raise TemplateVersionError(
                f"Versao '{resolved_version}' de '{template_id}' "
                f"esta '{status}' — nao pode ser renderizada."
            )
        file_rel = meta.get("file")
        if not file_rel:
            raise TemplateVersionError(
                f"Versao '{resolved_version}' de '{template_id}' nao "
                "declara 'file' no registry."
            )
        abs_path = TEMPLATES_ROOT / file_rel
        if not abs_path.is_file():
            raise TemplateNotFoundError(
                f"Arquivo do template nao encontrado: {abs_path}"
            )
        return TemplateVersionRef(
            template_id=template_id,
            version=resolved_version,
            file=file_rel,
            absolute_path=abs_path,
            status=status,
            output_formats=tuple(meta.get("output_formats") or ()),
            regulatory_refs=tuple(meta.get("regulatory_refs") or ()),
        )
    raise TemplateNotFoundError(
        f"Template id '{template_id}' nao esta no registry."
    )


# ---------------------------------------------------------------------
# Jinja environment
# ---------------------------------------------------------------------

def _build_environment() -> Environment:
    """Constroi Environment Jinja2 com os defaults declarados no registry."""
    registry = _load_registry()
    defaults = ((registry.get("engine") or {}).get("defaults")) or {}
    autoescape_ext = ("html", "xml") if defaults.get("autoescape") else ()
    undefined_cls = (
        StrictUndefined
        if defaults.get("undefined", "strict") == "strict"
        else None
    )
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_ROOT)),
        autoescape=select_autoescape(
            enabled_extensions=autoescape_ext,
            default_for_string=False,
        ),
        trim_blocks=defaults.get("trim_blocks", True),
        lstrip_blocks=defaults.get("lstrip_blocks", True),
        undefined=undefined_cls or StrictUndefined,
    )


# ---------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------

def _sha256_hex(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def render(
    template_id: str,
    context: dict[str, Any],
    *,
    format: str = "md",
    version: Optional[str] = None,
) -> RenderedDocument:
    """Renderiza um template do registry e devolve :class:`RenderedDocument`.

    Args:
        template_id: chave no registry (ex.: ``'eligibility/dossier'``).
        context: variaveis usadas pelo template. StrictUndefined forca
            que tudo que o template referenciar esteja presente.
        format: formato de saida. So ``'md'`` esta suportado ate F4.4.
            Conversao md -> PDF/A / DOCX fica para iteracoes futuras.
        version: versao especifica; se ``None``, usa ``current_version``.

    Returns:
        :class:`RenderedDocument` com ``content_hash`` SHA-256 pronto
        para ``regulatory_reports.content_hash``.
    """
    ref = resolve(template_id, version=version)

    if format not in ref.output_formats:
        raise UnsupportedFormatError(
            f"Formato '{format}' nao suportado por "
            f"{template_id}:{ref.version} "
            f"(suportados: {list(ref.output_formats) or ['(nenhum declarado)']})."
        )

    env = _build_environment()
    try:
        template = env.get_template(ref.file)
        content = template.render(**context)
    except UndefinedError as exc:
        raise TemplateRenderError(
            f"Campo obrigatorio ausente em {template_id}:{ref.version} — {exc}"
        ) from exc
    except TemplateError as exc:
        raise TemplateRenderError(
            f"Erro Jinja em {template_id}:{ref.version} — {exc}"
        ) from exc

    rendered_at = datetime.now(timezone.utc)
    content_hash = _sha256_hex(content)
    logger.info(
        "template_rendered id=%s version=%s format=%s length=%d hash=%s",
        template_id, ref.version, format, len(content), content_hash[:12],
    )
    return RenderedDocument(
        template_id=template_id,
        version=ref.version,
        format=format,
        content=content,
        content_hash=content_hash,
        rendered_at=rendered_at,
        template_file=ref.file,
    )
