"""Sprint D Q3: garante que toda env var referenciada em codigo de produto
esteja documentada em `.env.example`, para o novato nao descobrir variavel
critica so depois de quebrar em runtime.

Estrategia:
- Le `.env.example` na raiz e extrai chaves `KEY=...`.
- Percorre `src/` capturando padroes `os.environ.get("KEY")` e `os.getenv("KEY")`.
- Falha se houver chave usada em codigo de produto que nao aparece no
  `.env.example` (excluindo whitelist de envs do SO e de teste).

Quando essa regressao quebrar:
1. Se a env nova faz parte do produto -> adicionar em `.env.example`.
2. Se e uma env opcional de teste/dev -> juntar ao set `IGNORED_ENVS` aqui.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"


# Envs do SO ou herdadas do ambiente que nao precisam ser documentadas.
IGNORED_ENVS = {
    # Sistema operacional
    "PATH", "HOME", "TEMP", "TMP", "TMPDIR", "USERPROFILE", "LOCALAPPDATA",
    "APPDATA", "SystemRoot", "COMSPEC", "OS", "PROCESSOR_ARCHITECTURE",
    "PROCESSOR_IDENTIFIER", "PYTHONPATH", "VIRTUAL_ENV",
    # Ambiente runtime (Flask/Werkzeug/Pytest internos)
    "FLASK_ENV", "FLASK_DEBUG", "PYTEST_CURRENT_TEST",
    "WERKZEUG_RUN_MAIN", "WERKZEUG_SERVER_FD",
    # Gates de teste opcionais (ja documentados em outro lugar)
    "RUN_REAL_GEMINI_SMOKE", "RUN_REAL_INTEGRATION_TESTS",
}


ENV_USAGE_PATTERN = re.compile(
    r"""os\.(?:environ\.get|getenv)\(\s*["']([A-Z_][A-Z0-9_]*)["']""",
    re.VERBOSE,
)
ENV_INDEX_PATTERN = re.compile(
    r"""os\.environ\[\s*["']([A-Z_][A-Z0-9_]*)["']\s*\]""",
)


def _read_documented_envs() -> set[str]:
    if not ENV_EXAMPLE.is_file():
        pytest.fail(f".env.example nao encontrado em {ENV_EXAMPLE}")
    keys: set[str] = set()
    for raw_line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key.isidentifier():
            keys.add(key)
    return keys


def _scan_code_for_env_usage() -> dict[str, set[str]]:
    """Retorna {ENV_KEY: {paths onde aparece}}."""
    found: dict[str, set[str]] = {}
    for path in SRC_DIR.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for key in ENV_USAGE_PATTERN.findall(text):
            found.setdefault(key, set()).add(str(path.relative_to(PROJECT_ROOT)))
        for key in ENV_INDEX_PATTERN.findall(text):
            found.setdefault(key, set()).add(str(path.relative_to(PROJECT_ROOT)))
    return found


def test_env_example_exists_and_has_keys():
    documented = _read_documented_envs()
    assert documented, f".env.example deveria documentar variaveis (lido em {ENV_EXAMPLE})"


def test_every_env_used_in_src_is_documented():
    documented = _read_documented_envs()
    used = _scan_code_for_env_usage()

    missing: dict[str, set[str]] = {}
    for key, files in used.items():
        if key in IGNORED_ENVS:
            continue
        if key in documented:
            continue
        missing[key] = files

    if missing:
        details = "\n".join(
            f"  - {key} (usado em: {', '.join(sorted(files))})"
            for key, files in sorted(missing.items())
        )
        pytest.fail(
            "Envs referenciadas em src/ mas ausentes do .env.example:\n"
            f"{details}\n"
            "Adicione cada uma em .env.example (com comentario explicando o "
            "default) ou inclua em IGNORED_ENVS aqui se for runtime/teste."
        )
