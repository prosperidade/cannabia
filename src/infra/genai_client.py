"""Factory única do client google-genai (Gemini).

Suporta DOIS backends, selecionados por env — porque eles têm BILLING SEPARADO:

- **AI Studio** (default): `genai.Client(api_key=GOOGLE_API_KEY)`. Endpoint
  `generativelanguage.googleapis.com`. Billing/prepay PRÓPRIO do AI Studio
  (NÃO consome os créditos do Google Cloud).
- **Vertex AI**: `genai.Client(vertexai=True, project=..., location=...)`. Billing
  no **projeto GCP** — é aqui que ficam os créditos do Google Cloud. Ative com:
    GOOGLE_GENAI_USE_VERTEXAI=true
    GOOGLE_CLOUD_PROJECT=<seu-projeto-gcp>
    GOOGLE_CLOUD_LOCATION=us-central1            # opcional (default)
  + Application Default Credentials (ADC): `GOOGLE_APPLICATION_CREDENTIALS`
  apontando para o JSON de service account, OU `gcloud auth application-default login`.

Contexto (2026-06-11): o erro "prepayment credits depleted / ai.studio" ocorre
porque o sistema falava com o AI Studio (api_key), cujo saldo é separado dos
créditos do Google Cloud (Vertex). Esta factory permite apontar o Gemini para o
Vertex e consumir os créditos GCP, sem mudar o resto do código.
"""

from __future__ import annotations

import os

from google import genai


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def use_vertex() -> bool:
    """True quando o backend Vertex AI está habilitado por env."""
    return _truthy(os.getenv("GOOGLE_GENAI_USE_VERTEXAI"))


def make_genai_client() -> genai.Client:
    """Cria o client genai no backend configurado (Vertex AI ou AI Studio)."""
    if use_vertex():
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        if not project:
            raise RuntimeError(
                "GOOGLE_GENAI_USE_VERTEXAI=true exige GOOGLE_CLOUD_PROJECT definido "
                "(e ADC: GOOGLE_APPLICATION_CREDENTIALS ou `gcloud auth application-default login`)."
            )
        return genai.Client(vertexai=True, project=project, location=location)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY ausente. Defina-a (AI Studio) ou habilite Vertex via "
            "GOOGLE_GENAI_USE_VERTEXAI=true + GOOGLE_CLOUD_PROJECT."
        )
    return genai.Client(api_key=api_key)
