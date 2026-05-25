"""Testes do template_engine (F4.4 do SCC).

Usa o registry real (``data/templates/registry.yaml``) para o happy path,
pois ele catalogara versoes reais no ciclo de vida do produto. Casos
negativos usam monkeypatch sobre ``_registry_cache`` para injetar
manifestos artificiais sem tocar no arquivo de disco.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.services import template_engine as te
from src.services.template_engine import (
    RenderedDocument,
    TemplateNotFoundError,
    TemplateRenderError,
    TemplateVersionError,
    TemplateVersionRef,
    UnsupportedFormatError,
    render,
    resolve,
)


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def dossier_context() -> dict:
    """Contexto minimamente completo para ``eligibility/dossier`` v1.

    Espelha o contexto usado em ``test_governance_dossier.py`` para o
    caminho 'pendencias' — assim nao precisamos tocar no banco nem
    depender das funcoes de build_dossier_data aqui.
    """
    return {
        "tenant": {
            "legal_name": "X", "trade_name": None, "cnpj": None,
            "incorporation_date": None, "tenant_type": "association",
        },
        "association": None,
        "documents": [],
        "documents_by_type": {},
        "rts": [],
        "primary_rt": None,
        "presidente": None,
        "capacity": None,
        "eligibility": {
            "is_eligible": False,
            "has_warnings": True,
            "checked_at": "2026-04-20T00:00:00+00:00",
        },
        "findings": [
            {"code": "legal_nature", "status": "pass",
             "message": "ok", "details": {}},
            {"code": "incorporation_time", "status": "fail",
             "message": "sem data", "details": {}},
            {"code": "active_technical_responsible", "status": "fail",
             "message": "sem RT", "details": {}},
            {"code": "technical_operational_capacity", "status": "fail",
             "message": "sem capacity", "details": {}},
            {"code": "statute_document", "status": "warn",
             "message": "sem estatuto", "details": {}},
        ],
        "findings_by_code": {},
        "fail_count": 3,
        "warn_count": 1,
        "template_version": "v1",
        "generated_at": "2026-04-20T00:00:00+00:00",
    }


@pytest.fixture
def fake_registry(monkeypatch):
    """Instala um registry artificial em ``_registry_cache``.

    Usa o arquivo do dossier real para cenarios que precisam renderizar;
    usa caminhos fake quando o teste espera erro antes do I/O.
    """
    def _install(registry: dict) -> None:
        monkeypatch.setattr(te, "_registry_cache", registry)

    yield _install

    # monkeypatch restaura _registry_cache ao valor original; forcamos
    # re-load para que testes posteriores peguem o registry real.
    te._invalidate_registry_cache()


# ---------------------------------------------------------------------
# resolve()
# ---------------------------------------------------------------------

class TestResolve:
    def test_happy_path_usa_current_version(self):
        ref = resolve("eligibility/dossier")
        assert isinstance(ref, TemplateVersionRef)
        assert ref.template_id == "eligibility/dossier"
        assert ref.version == "v1"
        assert ref.file == "eligibility/dossier_v1.md.j2"
        assert ref.absolute_path.is_file()
        assert ref.status == "active"
        assert "md" in ref.output_formats

    def test_version_explicita(self):
        ref = resolve("eligibility/dossier", version="v1")
        assert ref.version == "v1"

    def test_id_desconhecido(self):
        with pytest.raises(TemplateNotFoundError, match="nao esta no registry"):
            resolve("eligibility/inexistente")

    def test_versao_desconhecida(self):
        with pytest.raises(TemplateVersionError, match="nao existe"):
            resolve("eligibility/dossier", version="v99")

    def test_versao_depreciada_bloqueada(self, fake_registry):
        fake_registry({
            "engine": {"defaults": {"undefined": "strict"}},
            "templates": [{
                "id": "test/dep",
                "current_version": "v1",
                "versions": {"v1": {
                    "file": "eligibility/dossier_v1.md.j2",
                    "status": "deprecated",
                    "output_formats": ["md"],
                }},
            }],
        })
        with pytest.raises(TemplateVersionError, match="deprecated"):
            resolve("test/dep")

    def test_sem_current_version_e_sem_override(self, fake_registry):
        fake_registry({
            "engine": {"defaults": {"undefined": "strict"}},
            "templates": [{
                "id": "test/orf",
                "versions": {"v1": {
                    "file": "eligibility/dossier_v1.md.j2",
                    "status": "active",
                    "output_formats": ["md"],
                }},
            }],
        })
        with pytest.raises(TemplateVersionError, match="current_version"):
            resolve("test/orf")

    def test_versao_sem_file(self, fake_registry):
        fake_registry({
            "engine": {"defaults": {"undefined": "strict"}},
            "templates": [{
                "id": "test/no_file",
                "current_version": "v1",
                "versions": {"v1": {
                    "status": "active",
                    "output_formats": ["md"],
                }},
            }],
        })
        with pytest.raises(TemplateVersionError, match="nao declara 'file'"):
            resolve("test/no_file")

    def test_arquivo_inexistente_no_disco(self, fake_registry):
        fake_registry({
            "engine": {"defaults": {"undefined": "strict"}},
            "templates": [{
                "id": "test/ghost",
                "current_version": "v1",
                "versions": {"v1": {
                    "file": "eligibility/arquivo_que_nao_existe_v1.md.j2",
                    "status": "active",
                    "output_formats": ["md"],
                }},
            }],
        })
        with pytest.raises(TemplateNotFoundError, match="nao encontrado"):
            resolve("test/ghost")


# ---------------------------------------------------------------------
# render()
# ---------------------------------------------------------------------

class TestRender:
    def test_renderiza_dossier_via_engine(self, dossier_context):
        doc = render("eligibility/dossier", dossier_context, format="md")
        assert isinstance(doc, RenderedDocument)
        assert doc.template_id == "eligibility/dossier"
        assert doc.version == "v1"
        assert doc.format == "md"
        assert doc.template_file == "eligibility/dossier_v1.md.j2"
        assert "# Dossie de Elegibilidade" in doc.content
        assert "Apto a submissao:** NAO" in doc.content
        # SHA-256 hex: 64 chars, so digits hex minusculos
        assert len(doc.content_hash) == 64
        assert all(c in "0123456789abcdef" for c in doc.content_hash)

    def test_hash_estavel_para_mesmo_contexto(self, dossier_context):
        d1 = render("eligibility/dossier", dossier_context, format="md")
        d2 = render("eligibility/dossier", copy.deepcopy(dossier_context),
                    format="md")
        assert d1.content == d2.content
        assert d1.content_hash == d2.content_hash

    def test_hash_muda_com_contexto_diferente(self, dossier_context):
        ctx2 = copy.deepcopy(dossier_context)
        ctx2["tenant"]["legal_name"] = "Outro Nome"
        d1 = render("eligibility/dossier", dossier_context, format="md")
        d2 = render("eligibility/dossier", ctx2, format="md")
        assert d1.content_hash != d2.content_hash

    def test_formato_nao_suportado(self, dossier_context):
        with pytest.raises(UnsupportedFormatError, match="nao suportado"):
            render("eligibility/dossier", dossier_context, format="pdf")

    def test_campo_obrigatorio_ausente_levanta_render_error(self, dossier_context):
        ctx = copy.deepcopy(dossier_context)
        del ctx["tenant"]
        with pytest.raises(TemplateRenderError, match="ausente"):
            render("eligibility/dossier", ctx, format="md")

    def test_rendered_at_e_utc_e_recente(self, dossier_context):
        doc = render("eligibility/dossier", dossier_context, format="md")
        assert doc.rendered_at.tzinfo is timezone.utc
        delta = (datetime.now(timezone.utc) - doc.rendered_at).total_seconds()
        assert 0 <= delta < 60

    def test_content_hash_bate_com_sha256_manual(self, dossier_context):
        import hashlib
        doc = render("eligibility/dossier", dossier_context, format="md")
        expected = hashlib.sha256(doc.content.encode("utf-8")).hexdigest()
        assert doc.content_hash == expected

    def test_render_nao_polui_contexto_original(self, dossier_context):
        snapshot = copy.deepcopy(dossier_context)
        render("eligibility/dossier", dossier_context, format="md")
        assert dossier_context == snapshot


# ---------------------------------------------------------------------
# Registry loader / cache
# ---------------------------------------------------------------------

class TestRegistryLoader:
    def test_load_registry_retorna_dict_com_templates(self):
        te._invalidate_registry_cache()
        reg = te._load_registry()
        assert reg["registry_version"] == "1.0"
        ids = [t["id"] for t in reg["templates"]]
        assert "eligibility/dossier" in ids

    def test_invalidate_forca_reload(self, monkeypatch):
        reg1 = te._load_registry()
        te._invalidate_registry_cache()
        reg2 = te._load_registry()
        # Mesmo conteudo, mas objetos diferentes apos invalidacao
        assert reg1 == reg2
        assert reg1 is not reg2

    def test_registry_ausente_levanta_template_engine_error(self, monkeypatch):
        te._invalidate_registry_cache()
        ghost = Path(__file__).resolve().parent / "fixtures" / "nao_existe.yaml"
        monkeypatch.setattr(te, "REGISTRY_FILE", ghost)
        with pytest.raises(te.TemplateEngineError, match="nao encontrado"):
            te._load_registry()
        te._invalidate_registry_cache()


# ---------------------------------------------------------------------
# Smoke: tipos do dataclass
# ---------------------------------------------------------------------

class TestRenderedDocumentShape:
    def test_rendered_document_e_imutavel(self, dossier_context):
        doc = render("eligibility/dossier", dossier_context, format="md")
        with pytest.raises((AttributeError, TypeError)):
            doc.content = "modificado"  # frozen dataclass

    def test_template_version_ref_e_imutavel(self):
        ref = resolve("eligibility/dossier")
        with pytest.raises((AttributeError, TypeError)):
            ref.version = "v2"
