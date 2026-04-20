from __future__ import annotations

from pathlib import Path

from src.knowledge import google_files

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "google_files" / "manifest_seed"


def test_upload_all_legislation_respects_sources_manifest(monkeypatch):
    uploaded = []

    monkeypatch.setattr(google_files, "LEGISLATION_DIR", str(FIXTURES_DIR))
    monkeypatch.setattr(google_files, "_CATALOG_PATH", str(FIXTURES_DIR / "file_catalog.json"))
    monkeypatch.setattr(google_files, "_file_cache", {})
    monkeypatch.setattr(google_files, "_load_catalog", lambda: {})
    monkeypatch.setattr(
        google_files,
        "upload_file",
        lambda filepath, display_name=None: uploaded.append(Path(filepath).name) or {"display_name": Path(filepath).name},
    )

    google_files.upload_all_legislation()

    assert uploaded == ["RDC_327_2019_ANVISA.pdf", "Resolucao_CFM_2113_2014.md"]


def test_selected_catalog_entries_filters_out_helper_files(monkeypatch):
    monkeypatch.setattr(google_files, "LEGISLATION_DIR", str(FIXTURES_DIR))
    monkeypatch.setattr(google_files, "_CATALOG_PATH", str(FIXTURES_DIR / "file_catalog.json"))
    monkeypatch.setattr(
        google_files,
        "_file_cache",
        {
            "RDC_327_2019_ANVISA.pdf": {"uri": "u1", "display_name": "RDC", "checksum": "1"},
            "README.md": {"uri": "u2", "display_name": "README", "checksum": "2"},
        },
    )
    monkeypatch.setattr(google_files, "_load_catalog", lambda: google_files._file_cache)

    selected = google_files._selected_catalog_entries()

    assert [item["filename"] for item in selected] == ["RDC_327_2019_ANVISA.pdf"]
    assert selected[0]["mime_type"] == "application/pdf"
