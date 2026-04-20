from __future__ import annotations

from contextlib import contextmanager

from src.knowledge.legislation_catalog import (
    _build_catalog_record,
    infer_legislation_metadata,
    sync_legislation_catalog,
)


def test_infer_legislation_metadata_detects_rdc_and_source():
    metadata = infer_legislation_metadata({"display_name": "RDC_327_2019_ANVISA.pdf"})

    assert metadata["title"] == "RDC 327 2019 ANVISA"
    assert metadata["source"] == "anvisa"
    assert metadata["norm_number"] == "RDC 327/2019"
    assert metadata["norm_body"] == "ANVISA"


def test_build_catalog_record_prefers_manifest_metadata():
    record = _build_catalog_record(
        {
            "filename": "Lei_11_343_2006_Planalto.md",
            "display_name": "Lei_11_343_2006_Planalto.md",
            "uri": "gs://lei",
            "name": "files/lei",
            "checksum": "abc",
            "size_bytes": 10,
        },
        clinic_id=1,
        ingested_by="manual_upload",
    )

    assert record["title"] == "Lei nº 11.343/2006"
    assert record["norm_number"] == "Lei 11.343/2006"
    assert record["source"] == "planalto"
    assert record["source_url"] == "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11343.htm"


def test_sync_legislation_catalog_creates_and_updates_entries(monkeypatch):
    class FakeConn:
        def __init__(self):
            self.committed = False

        def commit(self):
            self.committed = True

    class FakeCursor:
        def __init__(self):
            self.select_results = [None, None, None, None, {"id": 9}]
            self._fetchone = None

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())

            if normalized.startswith("SELECT id FROM knowledge_catalog"):
                self._fetchone = self.select_results.pop(0)
            elif normalized.startswith("INSERT INTO knowledge_catalog"):
                self._fetchone = {"id": 7}
            elif normalized.startswith("UPDATE knowledge_catalog"):
                self._fetchone = {"id": 9}
            else:
                raise AssertionError(f"Unexpected SQL: {normalized}")

        def fetchone(self):
            return self._fetchone

    fake_conn = FakeConn()
    fake_cursor = FakeCursor()

    @contextmanager
    def fake_db_cursor(dictionary=False):
        assert dictionary is True
        yield fake_conn, fake_cursor

    monkeypatch.setattr("src.knowledge.legislation_catalog.db_cursor", fake_db_cursor)

    summary = sync_legislation_catalog(
        [
            {
                "display_name": "RDC 327 2019.pdf",
                "name": "files/rdc-327",
                "uri": "gs://rdc327",
                "checksum": "abc",
                "size_bytes": 1234,
                "local_path": "data/legislation/RDC 327 2019.pdf",
            },
            {
                "display_name": "Lei 11.343 2006.pdf",
                "name": "files/lei-11343",
                "uri": "gs://lei11343",
                "checksum": "def",
                "size_bytes": 4567,
                "local_path": "data/legislation/Lei 11.343 2006.pdf",
            },
        ],
        clinic_id=3,
    )

    assert fake_conn.committed is True
    assert summary["created"] == 1
    assert summary["updated"] == 1
    assert summary["total"] == 2
    assert summary["items"][0]["catalog_id"] == 7
    assert summary["items"][1]["catalog_id"] == 9
    assert summary["items"][1]["action"] == "updated"
