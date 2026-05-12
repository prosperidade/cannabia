"""Sanitize HTML boilerplate from legislation markdowns.

Captura HTML bruta produzida por `download_legislation_sources.ps1` (Imprensa
Nacional / Planalto / CFM) carrega muito boilerplate: <head>, scripts de
analytics, navegacao, footer, accessibility widgets, etc. Esses bytes inflam
o consumo de tokens no Gemini Files API sem agregar informacao normativa.

Este script gera arquivos paralelos `*_sanitized.md` em
`data/legislation/` mantendo apenas o conteudo normativo (texto da norma,
ementa, articulado, capitulos, secoes, paragrafos, incisos, assinatura
final).

Decisao operacional:
- NAO substituimos o arquivo original (`*.md`) — mantemos como base auditavel
  do scrape bruto.
- Geramos `*_sanitized.md` ao lado.
- O manifesto `sources.json` e o uploader continuam apontando para o original
  por padrao, mas o uploader pode ser ajustado para preferir a versao
  sanitizada via campo opcional `sanitized_filename` em sources.json (nao
  obrigatorio na Sprint 3).

Uso:
    env/Scripts/python.exe scripts/sanitize_legislation_markdowns.py
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
LEG_DIR = ROOT / "data" / "legislation"

# -----------------------------------------------------------------------------
# Utilitarios genericos
# -----------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_BLANK_RE = re.compile(r"\n{3,}")
_NBSP_RE = re.compile(r" |&nbsp;")


def _strip_html(text: str) -> str:
    # Remove blocos <script>, <style>, comentarios HTML antes do strip generico.
    text = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<!--[\s\S]*?-->", " ", text)
    text = _TAG_RE.sub(" ", text)
    return text


def _normalize_whitespace(text: str) -> str:
    text = _NBSP_RE.sub(" ", text)
    text = html.unescape(text)
    # Normaliza espacos por linha
    lines = []
    for line in text.splitlines():
        line = _WS_RE.sub(" ", line).strip()
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = _BLANK_RE.sub("\n\n", cleaned)
    return cleaned.strip() + "\n"


# -----------------------------------------------------------------------------
# Sanitizadores por norma
# -----------------------------------------------------------------------------

def sanitize_rdc_660(raw: str) -> str:
    """RDC 660/2022 - DOU/Imprensa Nacional.

    O articulado vive dentro de `<div class="texto-dou">` mais um par
    <html><body>...</body></html> aninhado. Capturamos esse bloco.
    """
    # Pega tudo entre <div class="texto-dou"> e o proximo </div> de fechamento
    # (o conteudo tem html aninhado, entao usamos pareamento ate </div>).
    match = re.search(
        r'<div class="texto-dou">([\s\S]*?)</div>\s*<div class="informacao-conteudo-dou">',
        raw,
    )
    if not match:
        raise RuntimeError("RDC 660: bloco texto-dou nao encontrado")

    body = match.group(1)
    text = _strip_html(body)
    text = _normalize_whitespace(text)

    header = (
        "# RDC nº 660/2022 — texto normativo sanitizado\n\n"
        "- Fonte oficial: https://www.in.gov.br/en/web/dou/-/resolucao-rdc-n-660-de-30-de-marco-de-2022-389908959\n"
        "- Sanitizado automaticamente a partir do scrape DOU/Imprensa Nacional.\n"
        "- Boilerplate (nav, scripts, header, footer, analytics) removido.\n"
        "\n---\n\n"
    )
    return header + text


def sanitize_lei_11343(raw: str) -> str:
    """Lei 11.343/2006 - Planalto/CCIVIL.

    O articulado esta dentro do <body id="view"> da pagina Planalto. Cortamos
    fora header/nav/scripts/footer (header `<header>`, `<nav>`, `<script>`,
    e tudo apos a assinatura `Brasília, 23 de agosto de 2006`).
    """
    # Encontra inicio do conteudo normativo: a epigrafe "LEI Nº 11.343"
    start = raw.find("LEI Nº 11.343")
    if start == -1:
        # fallback: busca por <body id="view">
        body_match = re.search(r'<body[^>]*id="view"[^>]*>([\s\S]*?)</body>', raw)
        if not body_match:
            raise RuntimeError("Lei 11.343: corpo nao encontrado")
        body = body_match.group(1)
    else:
        body = raw[start:]

    # Remove tags <header>, <nav>, e tudo a partir do primeiro <script id="f5_cspm">
    body = re.sub(r"<script[\s\S]*", " ", body)
    body = re.sub(r"<nav[\s\S]*?</nav>", " ", body, flags=re.IGNORECASE)
    body = re.sub(r"<header[\s\S]*?</header>", " ", body, flags=re.IGNORECASE)
    body = re.sub(r"includeHTML\(\)", " ", body)
    body = re.sub(r"Não\s*remover!?", " ", body, flags=re.IGNORECASE)

    text = _strip_html(body)
    text = _normalize_whitespace(text)

    # Remove cabecalho de "Presidência da República / Secretaria-Geral" se sobrar
    text = re.sub(r"^\s*Presidência da República\s*\n.*?\n", "", text, count=1, flags=re.IGNORECASE | re.MULTILINE)

    # Trunca apos a linha "Este texto não substitui o publicado no DOU"
    end_marker = re.search(r"Este texto não substitui o publicado no DOU[^\n]*", text)
    if end_marker:
        text = text[: end_marker.end()].rstrip() + "\n"

    header = (
        "# Lei nº 11.343/2006 — texto normativo sanitizado\n\n"
        "- Fonte oficial: https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11343.htm\n"
        "- Sanitizado automaticamente a partir do HTML do Planalto.\n"
        "- Boilerplate (header, nav, scripts F5/analytics, includeHTML) removido.\n"
        "\n---\n\n"
    )
    return header + text


def sanitize_cfm_2113(raw: str) -> str:
    """Resolucao CFM 2.113/2014 - portal CFM canabidiol.

    A pagina official do CFM e' uma landing com nav lateral + texto curto
    informativo + footer + analytics. O texto normativo util esta no
    `<div class="content internas"> ... <section> ... <h3>PÁGINA INICIAL</h3>
    <h4>CFM regulamenta o uso compassivo do canabidiol...</h4> ... </section>`.
    """
    # Captura titulo (h3 CFM regulamenta) ate a linha "Clique aqui e faça o
    # download da Resolução CFM 2113/14" inclusive.
    match = re.search(
        r"(CFM regulamenta o uso compassivo do canabidiol[\s\S]*?Resolução CFM\s*2113/14)",
        raw,
    )
    if not match:
        raise RuntimeError("CFM 2113: bloco normativo nao encontrado")

    body = match.group(1)
    text = _strip_html(body)
    text = _normalize_whitespace(text)

    # Subtitulo/preambulo expostos pelo CFM ficam no <h2><h3> no header — vamos
    # remontar um cabecalho normativo curto para o Gemini.
    header = (
        "# Resolução CFM nº 2.113/2014 — texto normativo sanitizado\n\n"
        "- Fonte oficial: https://portal.cfm.org.br/canabidiol/index.php\n"
        "- PDF oficial: http://www.portalmedico.org.br/resolucoes/CFM/2014/2113_2014.pdf\n"
        "- Ementa: Aprova o uso compassivo do canabidiol para o tratamento de\n"
        "  epilepsias da criança e do adolescente refratárias aos tratamentos\n"
        "  convencionais.\n"
        "- Sanitizado automaticamente a partir do portal CFM.\n"
        "- Boilerplate (nav, scripts, footer, accessibility widget) removido.\n"
        "\n---\n\n"
    )
    return header + text


SANITIZERS: dict[str, Callable[[str], str]] = {
    "RDC_660_2022_ANVISA.md": sanitize_rdc_660,
    "Lei_11_343_2006_Planalto.md": sanitize_lei_11343,
    "Resolucao_CFM_2113_2014.md": sanitize_cfm_2113,
}


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _sanitized_path(original: Path) -> Path:
    return original.with_name(original.stem + "_sanitized.md")


def run(dry_run: bool = False) -> dict:
    summary = {"files": [], "total_input_bytes": 0, "total_output_bytes": 0}
    for filename, sanitizer in SANITIZERS.items():
        src = LEG_DIR / filename
        if not src.exists():
            summary["files"].append({"file": filename, "status": "missing"})
            continue

        raw = src.read_text(encoding="utf-8")
        try:
            cleaned = sanitizer(raw)
        except Exception as exc:  # noqa: BLE001
            summary["files"].append(
                {"file": filename, "status": "error", "error": str(exc)}
            )
            continue

        dest = _sanitized_path(src)
        input_size = len(raw.encode("utf-8"))
        output_size = len(cleaned.encode("utf-8"))
        reduction = 0.0 if input_size == 0 else (1 - output_size / input_size) * 100

        if not dry_run:
            dest.write_text(cleaned, encoding="utf-8")

        summary["files"].append(
            {
                "file": filename,
                "sanitized": dest.name,
                "input_bytes": input_size,
                "output_bytes": output_size,
                "reduction_pct": round(reduction, 1),
                "status": "ok" if not dry_run else "dry-run",
            }
        )
        summary["total_input_bytes"] += input_size
        summary["total_output_bytes"] += output_size

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Nao escreve arquivos.")
    args = parser.parse_args()

    summary = run(dry_run=args.dry_run)
    print("=" * 72)
    print("Sanitizacao de markdowns regulatorios")
    print("=" * 72)
    for item in summary["files"]:
        print(item)
    if summary["total_input_bytes"]:
        total_reduction = (
            1 - summary["total_output_bytes"] / summary["total_input_bytes"]
        ) * 100
        print("-" * 72)
        print(
            f"Total: {summary['total_input_bytes']:,} bytes -> "
            f"{summary['total_output_bytes']:,} bytes "
            f"({total_reduction:.1f}% reducao)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
