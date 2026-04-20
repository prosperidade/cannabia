from __future__ import annotations

from pathlib import Path

import pytest

from src.infra import run_migrations


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "migrations"

def test_list_migration_files_ignores_tracking_file(monkeypatch):
    monkeypatch.setattr(run_migrations, "MIGRATIONS_DIR", FIXTURES_DIR / "canonical")

    files = run_migrations.list_migration_files()

    assert [file.name for file in files] == [
        "001_first.sql",
        "002_second.sql",
    ]


def test_list_migration_files_rejects_duplicate_versions(monkeypatch):
    monkeypatch.setattr(
        run_migrations,
        "MIGRATIONS_DIR",
        FIXTURES_DIR / "duplicate_versions",
    )

    with pytest.raises(run_migrations.MigrationVersionConflictError):
        run_migrations.list_migration_files()


def test_run_all_normalizes_legacy_blank_checksum(monkeypatch):
    migration = FIXTURES_DIR / "canonical" / "001_first.sql"
    checksum = run_migrations._sha256(migration.read_text(encoding="utf-8"))
    recorded: list[tuple[str, str, str]] = []
    executed: list[Path] = []

    monkeypatch.setattr(run_migrations, "_ensure_tracking_table", lambda: None)
    monkeypatch.setattr(
        run_migrations,
        "_get_applied",
        lambda: {
            "001": run_migrations.AppliedMigration(
                filename="001_first.sql",
                checksum="",
            )
        },
    )
    monkeypatch.setattr(run_migrations, "list_migration_files", lambda: [migration])
    monkeypatch.setattr(run_migrations, "run_sql_file", lambda path: executed.append(path))
    monkeypatch.setattr(
        run_migrations,
        "_record_migration",
        lambda version, filename, checksum: recorded.append((version, filename, checksum)),
    )

    assert run_migrations.run_all() == []
    assert executed == []
    assert recorded == [
        (
            "001",
            "001_first.sql",
            checksum,
        )
    ]


def test_run_all_normalizes_legacy_filename_when_checksum_matches(monkeypatch):
    migration = FIXTURES_DIR / "canonical" / "001_first.sql"
    checksum = run_migrations._sha256(migration.read_text(encoding="utf-8"))
    recorded: list[tuple[str, str, str]] = []

    monkeypatch.setattr(run_migrations, "_ensure_tracking_table", lambda: None)
    monkeypatch.setattr(
        run_migrations,
        "_get_applied",
        lambda: {
            "001": run_migrations.AppliedMigration(
                filename="001_legacy_name.sql",
                checksum=checksum,
            )
        },
    )
    monkeypatch.setattr(run_migrations, "list_migration_files", lambda: [migration])
    monkeypatch.setattr(
        run_migrations,
        "_record_migration",
        lambda version, filename, persisted_checksum: recorded.append(
            (version, filename, persisted_checksum)
        ),
    )

    assert run_migrations.run_all() == []
    assert recorded == [
        (
            "001",
            "001_first.sql",
            checksum,
        )
    ]
