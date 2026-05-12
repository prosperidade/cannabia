"""CLI Python para upload da base regulatoria para o Google Files API.

Alternativa operacional ao endpoint `POST /api/v1/regulatory/upload`
(admin-only, requer login Flask). Util para:
  - CI/CD e jobs agendados (ops)
  - smoke local sem subir o servidor
  - reupload after manifest expansion (Sprint 4)

Comportamento:
  - Le `data/legislation/sources.json` por padrao.
  - Faz upload de cada arquivo do manifesto via
    `src.knowledge.google_files.upload_all_legislation()` (idempotente —
    SHA-256 cache do uploader pula arquivos inalterados).
  - Sincroniza com `knowledge_catalog` via
    `src.knowledge.legislation_catalog.sync_legislation_catalog()`.
  - Output tabular: filename, size, uri, catalog_id, status.

Flags:
  --dry-run         Lista arquivos do manifesto sem fazer upload.
  --commit          Sincronizacao real (default).
  --file <path>     Faz upload de um unico arquivo (path absoluto ou
                    relativo ao cwd). Caso o arquivo nao esteja no
                    manifesto, o uploader continua valido mas nao sera
                    persistido no `knowledge_catalog` (filename fora do
                    sources.json).

Exemplos:
  env\\Scripts\\python.exe scripts/upload_legislation.py --dry-run
  env\\Scripts\\python.exe scripts/upload_legislation.py --commit
  env\\Scripts\\python.exe scripts/upload_legislation.py --file data/legislation/RDC_327_2019_ANVISA.pdf
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _format_size(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0.00 MB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def _print_table(rows: List[dict]) -> None:
    if not rows:
        print("(nenhum arquivo)")
        return

    headers = ["filename", "size", "uri", "catalog_id", "status"]
    widths = {h: len(h) for h in headers}
    for r in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(r.get(h, ""))))

    line = " | ".join(h.ljust(widths[h]) for h in headers)
    sep = "-+-".join("-" * widths[h] for h in headers)
    print(line)
    print(sep)
    for r in rows:
        print(" | ".join(str(r.get(h, "")).ljust(widths[h]) for h in headers))


def _load_manifest() -> list[dict]:
    import json

    manifest = ROOT / "data" / "legislation" / "sources.json"
    if not manifest.exists():
        return []
    try:
        return json.loads(manifest.read_text(encoding="utf-8")) or []
    except Exception as exc:  # noqa: BLE001
        print(f"[erro] manifesto ilegivel: {exc}", file=sys.stderr)
        return []


def _dry_run() -> int:
    entries = _load_manifest()
    leg_dir = ROOT / "data" / "legislation"
    rows: list[dict] = []
    for item in entries:
        filename = item.get("filename") or "?"
        path = leg_dir / filename
        rows.append({
            "filename": filename,
            "size": _format_size(path.stat().st_size if path.exists() else 0),
            "uri": "(dry-run)",
            "catalog_id": "-",
            "status": "ok" if path.exists() else "MISSING",
        })
    _print_table(rows)
    return 0 if all(r["status"] == "ok" for r in rows) else 1


def _resolve_single_file(arg_path: str) -> Path:
    candidate = Path(arg_path)
    if not candidate.is_absolute():
        candidate = (Path.cwd() / arg_path).resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"arquivo nao encontrado: {arg_path}")
    return candidate


def _commit(single_file: str | None = None) -> int:
    # Importa tardio para que --dry-run nao exija GOOGLE_API_KEY.
    from src.knowledge.google_files import (  # noqa: PLC0415
        upload_all_legislation,
        upload_file,
    )
    from src.knowledge.legislation_catalog import (  # noqa: PLC0415
        sync_legislation_catalog,
    )

    if single_file:
        path = _resolve_single_file(single_file)
        print(f"Upload single file: {path}")
        entry = upload_file(str(path))
        results = [entry]
    else:
        print("Upload completo (todas as normas do manifesto)...")
        results = upload_all_legislation()

    if not results:
        print("[aviso] nenhum arquivo retornado pelo uploader.")
        return 1

    try:
        catalog_summary = sync_legislation_catalog(
            results, ingested_by="cli_upload"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[erro] sync_legislation_catalog falhou: {exc}", file=sys.stderr)
        catalog_summary = {"items": []}

    catalog_by_filename = {
        item.get("filename"): item.get("catalog_id")
        for item in catalog_summary.get("items", [])
    }

    rows = []
    for entry in results:
        filename = entry.get("filename") or os.path.basename(
            entry.get("local_path") or ""
        )
        rows.append(
            {
                "filename": filename,
                "size": _format_size(entry.get("size_bytes", 0)),
                "uri": entry.get("uri") or "-",
                "catalog_id": catalog_by_filename.get(filename, "-"),
                "status": "ok",
            }
        )

    _print_table(rows)

    created = catalog_summary.get("created", 0) if isinstance(catalog_summary, dict) else 0
    updated = catalog_summary.get("updated", 0) if isinstance(catalog_summary, dict) else 0
    print()
    print(f"Catalogo: {created} criados, {updated} atualizados, {len(results)} arquivos.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Lista arquivos sem upload.")
    mode.add_argument("--commit", action="store_true", help="Realiza upload (default).")
    parser.add_argument("--file", help="Upload de um unico arquivo (path).")
    args = parser.parse_args()

    if args.dry_run:
        return _dry_run()

    if not os.getenv("GOOGLE_API_KEY"):
        print(
            "[erro] GOOGLE_API_KEY nao configurada. Defina no .env ou exporte no ambiente.",
            file=sys.stderr,
        )
        return 2

    return _commit(single_file=args.file)


if __name__ == "__main__":
    raise SystemExit(main())
