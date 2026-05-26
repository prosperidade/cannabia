"""Sprint D M1: testes dos providers de storage (src/infra/storage.py).

NoopStorage e o default e tem que falhar explicitamente. LocalStorage
escreve em filesystem (uso dev). R2Storage e testado com boto3 mockado
para nao depender de credenciais externas.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infra import storage

_LOCAL_STORAGE_TEST_ROOT = Path("pytest-cache-files-storage/storage_backends").resolve()


def test_noop_is_default(monkeypatch):
    monkeypatch.delenv("STORAGE_PROVIDER", raising=False)
    backend = storage.get_backend()
    with pytest.raises(storage.StorageNotConfigured) as exc:
        backend.upload(key="x", content=b"a", content_type="application/pdf")
    assert "STORAGE_PROVIDER" in str(exc.value)


def test_unknown_provider_falls_back_to_noop(monkeypatch):
    monkeypatch.setenv("STORAGE_PROVIDER", "minio")
    backend = storage.get_backend()
    with pytest.raises(storage.StorageNotConfigured):
        backend.upload(key="x", content=b"a", content_type="application/pdf")


def test_local_writes_file_and_returns_public_url(monkeypatch):
    local_root = _LOCAL_STORAGE_TEST_ROOT / "public_url"
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(local_root))
    monkeypatch.setenv("STORAGE_LOCAL_PUBLIC_BASE", "/uploads")

    backend = storage.get_backend()
    url = backend.upload(
        key="onboarding/42/crm_doc.pdf",
        content=b"hello",
        content_type="application/pdf",
    )

    assert url == "/uploads/onboarding/42/crm_doc.pdf"
    written = local_root / "onboarding" / "42" / "crm_doc.pdf"
    assert written.read_bytes() == b"hello"


def test_local_creates_nested_directories(monkeypatch):
    local_root = _LOCAL_STORAGE_TEST_ROOT / "nested_dirs"
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(local_root))
    backend = storage.get_backend()
    backend.upload(key="a/b/c/d/file.png", content=b"x", content_type="image/png")
    assert (local_root / "a" / "b" / "c" / "d" / "file.png").exists()


def test_r2_requires_all_credentials(monkeypatch):
    monkeypatch.setenv("STORAGE_PROVIDER", "r2")
    for var in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(storage.StorageNotConfigured) as exc:
        storage.get_backend()
    message = str(exc.value)
    assert "R2_ACCOUNT_ID" in message
    assert "R2_ACCESS_KEY_ID" in message
    assert "R2_SECRET_ACCESS_KEY" in message
    assert "R2_BUCKET" in message


def test_r2_calls_put_object_with_expected_args(monkeypatch):
    monkeypatch.setenv("STORAGE_PROVIDER", "r2")
    monkeypatch.setenv("R2_ACCOUNT_ID", "acc-1")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key-1")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret-1")
    monkeypatch.setenv("R2_BUCKET", "cannabia-docs")
    monkeypatch.delenv("R2_PUBLIC_BASE_URL", raising=False)

    fake_client = MagicMock()
    with patch("boto3.client", return_value=fake_client) as boto_client:
        backend = storage.get_backend()
        url = backend.upload(
            key="onboarding/7/diploma.pdf",
            content=b"binary",
            content_type="application/pdf",
        )

    boto_client.assert_called_once()
    kwargs = boto_client.call_args.kwargs
    assert kwargs["endpoint_url"] == "https://acc-1.r2.cloudflarestorage.com"
    assert kwargs["aws_access_key_id"] == "key-1"
    assert kwargs["aws_secret_access_key"] == "secret-1"
    assert kwargs["region_name"] == "auto"

    fake_client.put_object.assert_called_once_with(
        Bucket="cannabia-docs",
        Key="onboarding/7/diploma.pdf",
        Body=b"binary",
        ContentType="application/pdf",
    )
    assert url == "s3://cannabia-docs/onboarding/7/diploma.pdf"


def test_r2_uses_public_base_url_when_set(monkeypatch):
    monkeypatch.setenv("STORAGE_PROVIDER", "r2")
    monkeypatch.setenv("R2_ACCOUNT_ID", "acc-1")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key-1")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret-1")
    monkeypatch.setenv("R2_BUCKET", "cannabia-docs")
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://cdn.cannabia.app")

    with patch("boto3.client", return_value=MagicMock()):
        backend = storage.get_backend()
        url = backend.upload(
            key="onboarding/7/diploma.pdf",
            content=b"x",
            content_type="application/pdf",
        )

    assert url == "https://cdn.cannabia.app/onboarding/7/diploma.pdf"
