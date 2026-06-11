"""OCR/extracao de texto durável das normas em PDF -> Markdown.

A11/A5 follow-up (quitacao da divida do RAG efemero): a fonte durável da
legislacao passa a ser o TEXTO (.md), nao a Gemini Files API (que expira em 48h).
Este script gera `<stem>_sanitized.md` para cada PDF do manifesto:

  - PDF com camada de texto  -> extracao direta via PyMuPDF (fitz).
  - PDF escaneado (0 texto)   -> OCR via Gemini (multimodal), com continuacao
                                 automatica quando a saida trunca (MAX_TOKENS).

Idempotente: pula se o `_sanitized.md` ja existe (use --force para regenerar).
Requer GOOGLE_API_KEY (billing) para o caminho de OCR.

Uso:
  env\\Scripts\\python.exe scripts/ocr_legislation_pdfs.py            # todos os PDFs do manifesto
  env\\Scripts\\python.exe scripts/ocr_legislation_pdfs.py --file data/legislation/RDC_1012_2026_ANVISA.pdf
  env\\Scripts\\python.exe scripts/ocr_legislation_pdfs.py --force
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEG_DIR = ROOT / "data" / "legislation"
OCR_MODEL = os.getenv("GEMINI_FILES_MODEL", "gemini-2.5-flash")
PAGE_DPI = 150

PAGE_PROMPT = (
    "Transcreva FIELMENTE todo o texto desta pagina de um documento oficial "
    "(Resolucao Anvisa publicada no DOU), em texto puro. Preserve numeracao de "
    "artigos, paragrafos, incisos e alineas. NAO resuma, NAO comente, NAO repita. "
    "Em linhas de preenchimento pontilhado (ex.: 'Art. 4o ......'), escreva apenas "
    "'[...]' no lugar dos pontos. Se a pagina nao tiver texto, responda exatamente '[sem texto]'."
)

# Runs longos de caracteres de preenchimento (pontos/underscores/etc.) viram marcador.
_FILL_RUN = re.compile(r"([.·_\-…•])\1{5,}")
_BLANKS = re.compile(r"\n{3,}")


def _clean(text: str) -> str:
    text = _FILL_RUN.sub(" [...] ", text)
    text = _BLANKS.sub("\n\n", text)
    return text.strip()


def _has_text_layer(pdf_path: Path) -> int:
    import fitz
    doc = fitz.open(str(pdf_path))
    try:
        return sum(len(doc[i].get_text().strip()) for i in range(len(doc)))
    finally:
        doc.close()


def _extract_pymupdf(pdf_path: Path) -> str:
    import fitz
    doc = fitz.open(str(pdf_path))
    try:
        return "\n\n".join(doc[i].get_text() for i in range(len(doc))).strip()
    finally:
        doc.close()


def _gemini_page_text(client, gt, png: bytes) -> str:
    """OCR de UMA pagina (imagem). Retry com backoff em erros transientes (503/429)."""
    parts = [
        gt.Part.from_bytes(data=png, mime_type="image/png"),
        gt.Part.from_text(text=PAGE_PROMPT),
    ]
    last = None
    for attempt in range(4):
        try:
            resp = client.models.generate_content(
                model=OCR_MODEL,
                contents=[gt.Content(role="user", parts=parts)],
                config=gt.GenerateContentConfig(temperature=0.0, max_output_tokens=8192),
            )
            return resp.text or ""
        except Exception as exc:  # noqa: BLE001 — boundary de retry (503/429/network)
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OCR de pagina falhou apos retries: {last}")


def _ocr_via_gemini(pdf_path: Path) -> str:
    """OCR pagina-a-pagina (renderiza cada pagina como imagem e transcreve).

    Mais confiavel que mandar o PDF inteiro: saida bounded por pagina, sem
    continuacao cross-pagina (que corrompia linhas pontilhadas)."""
    import fitz
    from google import genai
    from google.genai import types as gt

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    doc = fitz.open(str(pdf_path))
    pages_text = []
    try:
        for i in range(len(doc)):
            pix = doc[i].get_pixmap(dpi=PAGE_DPI)
            png = pix.tobytes("png")
            text = _gemini_page_text(client, gt, png).strip()
            if text and text != "[sem texto]":
                pages_text.append(text)
            print(f"    pagina {i+1}/{len(doc)} ok ({len(text)} chars)", flush=True)
    finally:
        doc.close()
    return "\n\n".join(pages_text)


def _process(pdf_path: Path, force: bool) -> str:
    out = LEG_DIR / f"{pdf_path.stem}_sanitized.md"
    if out.exists() and not force:
        return f"skip (existe): {out.name}"
    chars = _has_text_layer(pdf_path)
    if chars > 500:
        text = _extract_pymupdf(pdf_path)
        method = "pymupdf"
    else:
        if not os.getenv("GOOGLE_API_KEY"):
            return f"ERRO {pdf_path.name}: escaneado mas GOOGLE_API_KEY ausente"
        text = _ocr_via_gemini(pdf_path)
        method = "gemini-ocr"
    text = _clean(text)
    if not text or len(text) < 200:
        return f"ERRO {pdf_path.name}: texto vazio/curto ({len(text)} chars)"
    header = f"<!-- Texto durável gerado de {pdf_path.name} via {method}. Fonte: PDF oficial Anvisa/DOU. -->\n\n"
    out.write_text(header + text + "\n", encoding="utf-8")
    return f"OK {pdf_path.name} -> {out.name} ({method}, {len(text)} chars)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", help="PDF unico (path).")
    ap.add_argument("--force", action="store_true", help="Regenera mesmo se o .md existir.")
    args = ap.parse_args()

    if args.file:
        pdfs = [Path(args.file)]
    else:
        pdfs = sorted(LEG_DIR.glob("*.pdf"))
    if not pdfs:
        print("(nenhum PDF encontrado)")
        return 1
    rc = 0
    for p in pdfs:
        msg = _process(p, args.force)
        print(msg)
        if msg.startswith("ERRO"):
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
