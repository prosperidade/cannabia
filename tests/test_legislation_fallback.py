"""
A5 follow-up — fallback OpenAI para query_legislation quando o Gemini falha.

Cobre: separacao texto vs so-imagem, acionamento do fallback apos Gemini esgotar
tentativas, e a sinalizacao de modo de contingencia no usage.
"""

from __future__ import annotations

import types

import pytest

import src.knowledge.google_files as gf


def test_load_legislation_texts_separates_text_and_image():
    texts, image_only = gf._load_legislation_texts()
    text_titles = " | ".join(t for t, _ in texts)
    img_titles = " | ".join(image_only)
    # Normas com .md sao lidas como texto (RDC 660, Lei 11.343, CFM).
    assert "660" in text_titles
    # PDFs escaneados (extensao .pdf) ficam fora do fallback, por extensao.
    assert "327" in img_titles
    assert ("1.011" in img_titles) or ("1.015" in img_titles)


class _FakeMsg:
    def __init__(self, content):
        self.message = types.SimpleNamespace(content=content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeMsg(content)]
        self.usage = types.SimpleNamespace(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        )


class _FakeOpenAI:
    def __init__(self, content="RESPOSTA FALLBACK"):
        self._content = content
        self.calls = []

        outer = self

        class _Chat:
            class completions:  # noqa: N801
                @staticmethod
                def create(**kwargs):
                    outer.calls.append(kwargs)
                    return _FakeCompletion(outer._content)

        self.chat = _Chat()


def test_fallback_uses_openai_and_flags_contingency(monkeypatch):
    fake = _FakeOpenAI("RESPOSTA FALLBACK")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(gf, "_get_openai_client", lambda: fake)

    answer, usage = gf._query_legislation_openai_fallback("Qual a base legal?", 0.0)

    assert answer == "RESPOSTA FALLBACK"
    assert usage["fallback"] is True
    assert usage["model"] == gf.LEGISLATION_FALLBACK_MODEL
    assert usage["fallback_reason"] == "gemini_unavailable"
    # normas so-imagem registradas como puladas
    assert any("327" in t for t in usage["image_only_skipped"])
    # o modelo configurado foi o usado na chamada
    assert fake.calls and fake.calls[0]["model"] == gf.LEGISLATION_FALLBACK_MODEL


def test_fallback_requires_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        gf._query_legislation_openai_fallback("x", 0.0)


def test_query_legislation_falls_back_when_gemini_fails(monkeypatch):
    # Gemini sempre falha; fallback responde.
    monkeypatch.setattr(gf.time, "sleep", lambda *_: None)  # nao dorme nos retries
    monkeypatch.setattr(
        gf, "_selected_catalog_entries",
        lambda file_names=None: [
            {"uri": "files/x", "display_name": "RDC", "mime_type": "application/pdf"}
        ],
    )

    class _BadGemini:
        class models:  # noqa: N801
            @staticmethod
            def generate_content(**kwargs):
                raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(gf, "_get_client", lambda: _BadGemini())
    monkeypatch.setattr(
        gf, "_query_legislation_openai_fallback",
        lambda question, temperature: ("FALLBACK_OK", {"fallback": True, "model": "gpt-4.1-mini"}),
    )

    answer, usage = gf.query_legislation("pergunta qualquer")
    assert answer == "FALLBACK_OK"
    assert usage["fallback"] is True
