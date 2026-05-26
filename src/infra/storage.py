"""Sprint D M1: storage de arquivos com providers plugaveis.

Tres backends:

- `noop`  (default): toda operacao levanta StorageNotConfigured com mensagem
  explicita. Garante que app sobe sem storage configurado, mas qualquer
  endpoint que tente upload retorna 503 com instrucao clara.

- `local`: filesystem (`STORAGE_LOCAL_ROOT`, default `uploads_local/`). Bom
  para dev. URLs retornadas sao paths relativos prefixados por
  `STORAGE_LOCAL_PUBLIC_BASE` (default `/uploads`). Nao serve em prod (Render
  e ephemeral; arquivo nao sobrevive deploy).

- `r2`: Cloudflare R2 via boto3 com endpoint S3-compat. Exige R2_ACCOUNT_ID,
  R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY e R2_BUCKET. boto3 e import
  lazy: nao precisa estar instalado em dev/CI quando STORAGE_PROVIDER != r2.

Contrato:
    backend = get_backend()
    url = backend.upload(key="onboarding/42/crm_doc.pdf",
                         content=b"...", content_type="application/pdf")

Convencao de keys: `<area>/<user_id>/<field>.<ext>`. Override pelo caller.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Protocol

logger = logging.getLogger("cannabia.infra.storage")


class StorageError(Exception):
    """Erro generico do storage."""


class StorageNotConfigured(StorageError):
    """Provider invalido ou credenciais ausentes."""


class StorageBackend(Protocol):
    def upload(self, *, key: str, content: bytes, content_type: str) -> str:
        """Sobe `content` em `key`. Retorna URL acessivel."""
        ...


_DEFAULT_LOCAL_ROOT = "uploads_local"


def _make_noop() -> StorageBackend:
    class _NoopStorage:
        def upload(self, *, key: str, content: bytes, content_type: str) -> str:
            raise StorageNotConfigured(
                "STORAGE_PROVIDER nao configurado. Defina STORAGE_PROVIDER=r2 "
                "ou STORAGE_PROVIDER=local em .env para habilitar uploads."
            )

    return _NoopStorage()


def _make_local() -> StorageBackend:
    root = Path(os.getenv("STORAGE_LOCAL_ROOT", _DEFAULT_LOCAL_ROOT)).resolve()
    public_base = os.getenv("STORAGE_LOCAL_PUBLIC_BASE", "/uploads").rstrip("/")

    class _LocalStorage:
        def upload(self, *, key: str, content: bytes, content_type: str) -> str:
            full = root / key
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes(content)
            logger.info("storage.local.upload key=%s bytes=%s", key, len(content))
            return f"{public_base}/{key}"

    return _LocalStorage()


def _make_r2() -> StorageBackend:
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise StorageNotConfigured(
            "STORAGE_PROVIDER=r2 mas boto3 nao esta instalado. "
            "Adicione 'boto3' ao requirements.txt e reinstale."
        ) from exc

    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    bucket = os.environ.get("R2_BUCKET")
    public_base = os.environ.get("R2_PUBLIC_BASE_URL", "").strip().rstrip("/")

    missing = [
        name
        for name, value in [
            ("R2_ACCOUNT_ID", account_id),
            ("R2_ACCESS_KEY_ID", access_key),
            ("R2_SECRET_ACCESS_KEY", secret_key),
            ("R2_BUCKET", bucket),
        ]
        if not value
    ]
    if missing:
        raise StorageNotConfigured(
            f"STORAGE_PROVIDER=r2 exige variaveis ausentes: {', '.join(missing)}"
        )

    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )

    class _R2Storage:
        def upload(self, *, key: str, content: bytes, content_type: str) -> str:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
            logger.info("storage.r2.upload key=%s bytes=%s", key, len(content))
            if public_base:
                return f"{public_base}/{key}"
            return f"s3://{bucket}/{key}"

    return _R2Storage()


_FACTORIES = {
    "noop": _make_noop,
    "local": _make_local,
    "r2": _make_r2,
}


def get_backend() -> StorageBackend:
    """Resolve o backend conforme STORAGE_PROVIDER (default noop)."""
    provider = (os.getenv("STORAGE_PROVIDER") or "noop").lower().strip()
    factory = _FACTORIES.get(provider)
    if factory is None:
        logger.warning(
            "storage.unknown_provider provider=%s fallback=noop", provider
        )
        return _make_noop()
    return factory()
