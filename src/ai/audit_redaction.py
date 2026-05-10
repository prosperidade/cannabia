"""
PII redaction estrutural para ai_audit_logs.input_payload/output_payload.

Track A.3 — Sprint 1 CannabIA. Estratégia (c) híbrido aprovada na Phase 0:

1. Walk recursivo em dict/list, redact value inteiro quando key matcha
   uma SENSITIVE_KEY (case-insensitive).
2. Em string-leaves de keys NÃO sensíveis, aplica regex pra pegar
   CPF/email/phone/RG/CRM/SUS embutidos em texto livre clínico.

Aplica-se em src/repositories/ai_audit_repository.py:67-68 ANTES do
json.dumps. Single point of intervention — toda call site de
save_ai_audit_log (5+ em service.py, 1 em prescription_service, futuras)
herda proteção automática.

FAIL-SAFE OBRIGATÓRIO: nunca raise. Em caso de erro interno, devolve
um dict com _redaction_failed=True + lista de top-level keys, garantindo
que audit log NÃO desaparece mesmo se sanitizer quebrar.

Substitui o antigo _sanitize_pii regex-based de src/ai/memory.py (escrito
pra MemPalace, removido em Track C.2 da Sprint 1). Esta versao trabalha
em JSONB estruturado (dict/list), nao em string livre serializada.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("cannabia.audit_redaction")


# =====================================================
# SENSITIVE KEYS — value redact integral
# =====================================================
# Match case-insensitive contra os keys do dict. Cobre:
#  - Identificadores civis: nome, CPF, RG, CNH, passaporte, SUS.
#  - Contato: email, phone, whatsapp, address.
#  - Datas pessoais: dob, birth_date.
#  - Identificacao profissional: CRM, COREN, CRO.
#  - Auth secrets defensivos (caso payload contamine): password, token.
# Nao inclui campos clinicos free-text (medical_history, allergies,
# medications, symptoms) — sao DADOS clinicos auditaveis, mas PII
# embutido neles eh tratado pelo regex em string-leaves.
SENSITIVE_KEYS: frozenset[str] = frozenset({
    # Identificadores
    "name", "patient_name", "full_name", "nome", "nome_completo",
    "cpf", "rg", "cnh", "passport", "passaporte",
    "cartao_sus", "sus_card", "cns", "numero_sus",
    # Contato
    "email", "e_mail", "mail",
    "phone", "telefone", "celular", "whatsapp", "tel",
    # Endereco
    "address", "endereco", "rua", "logradouro", "cep",
    # Data de nascimento
    "dob", "birth_date", "birthdate", "data_nascimento", "nascimento",
    # Profissional (medico responsavel)
    "doctor_name", "physician_name", "author_name",
    "crm", "coren", "cro", "rqe",
    # Auth secrets (defensivo)
    "password", "senha", "passwd",
    "auth_token", "api_key", "secret_key", "encryption_key",
})

# Replacement marker pra value de key sensivel. Mantem schema do JSONB
# previsivel (string), permitindo queries posteriores filtrarem registros
# sanitizados.
_KEY_REDACT_MARKER = "[REDACTED:key]"


# =====================================================
# REGEX patterns — string-leaves de keys NAO sensiveis
# =====================================================
# Reusa logica de src/ai/memory.py:39-46 (estavel) + adicoes pra A.3.
_STRING_LEAF_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # CPF (formato BR canonico)
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[CPF_REDACTED]"),
    # CPF sem mascara (raro, mas defensivo) — exige contexto pra reduzir falso positivo
    (re.compile(r"\bCPF\s*[:=]?\s*\d{11}\b", re.IGNORECASE), "[CPF_REDACTED]"),
    # CNPJ
    (re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"), "[CNPJ_REDACTED]"),
    # RG (formatos BR variados — 1 ou 2 digitos iniciais + grupo de 3 + grupo de 3 + 1 dig/X)
    (re.compile(r"\b\d{1,2}\.\d{3}\.\d{3}-?[0-9Xx]\b"), "[RG_REDACTED]"),
    (re.compile(r"\bRG\s*[:=]?\s*\d{1,2}\.?\d{3}\.?\d{3}-?[0-9Xx]\b", re.IGNORECASE), "[RG_REDACTED]"),
    # Phone (BR — sufixo 4 ou 5 digitos + 4 digitos)
    (re.compile(r"\b\d{4,5}-\d{4}\b"), "[PHONE_REDACTED]"),
    (re.compile(r"\b55\d{10,11}\b"), "[PHONE_REDACTED]"),
    (re.compile(r"\(\d{2}\)\s*\d{4,5}-?\d{4}"), "[PHONE_REDACTED]"),
    # Email
    (re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"), "[EMAIL_REDACTED]"),
    # Endereco com prefixo de logradouro
    (
        re.compile(
            r"\b(?:Rua|Av\.?|Avenida|Alameda|Travessa|Pra(?:c|ç)a|Estrada|Rodovia)"
            r"\s+[A-ZÁÉÍÓÚÃÕÂÊÎÔÛÇ][\w\sáéíóúãõâêîôûç,]*?\d+",
            re.IGNORECASE,
        ),
        "[ADDRESS_REDACTED]",
    ),
    # CEP
    (re.compile(r"\b\d{5}-\d{3}\b"), "[CEP_REDACTED]"),
    # CRM/COREN/CRO/RQE — id profissional
    (
        re.compile(r"\b(?:CRM|COREN|CRO|RQE)[/-]?[A-Z]{2}\s*\d{4,7}\b", re.IGNORECASE),
        "[PROFESSIONAL_ID_REDACTED]",
    ),
    # Cartao SUS / CNS — REQUER contexto explicito (decisao do coordenador
    # 2026-05-10: \b\d{15}\b solto da muito falso positivo).
    (
        re.compile(
            r"(?i)\b(?:cart[aã]o\s+(?:nacional\s+de\s+sa[uú]de|sus)|CNS|n(?:ú|u)mero\s+SUS)"
            r"[\s:.=-]*\d{15}\b"
        ),
        "[SUS_CARD_REDACTED]",
    ),
    # Nome de paciente em prefixo "paciente: Joao Silva"
    (
        re.compile(
            r"(?:paciente|patient|nome)\s*[:=]\s*[A-Z][a-záéíóúãõâêîôûç]+"
            r"(?:\s+[A-Z][a-záéíóúãõâêîôûç]+)+",
            re.IGNORECASE,
        ),
        "[PATIENT_NAME_REDACTED]",
    ),
]


def _is_sensitive_key(key: Any) -> bool:
    """True se key (string) bate com SENSITIVE_KEYS case-insensitive."""
    if not isinstance(key, str):
        return False
    return key.lower() in SENSITIVE_KEYS


def _sanitize_string(value: str) -> str:
    """Aplica regex em string-leaf pra pegar PII embutido em texto livre."""
    if not value:
        return value
    for pattern, replacement in _STRING_LEAF_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def _walk(value: Any) -> Any:
    """Walk recursivo: dict -> redact-by-key, list -> recurse, str -> regex."""
    if isinstance(value, dict):
        return {
            k: (_KEY_REDACT_MARKER if _is_sensitive_key(k) else _walk(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_walk(item) for item in value]
    if isinstance(value, str):
        return _sanitize_string(value)
    # int, float, bool, None — passam intactos
    return value


def sanitize_clinical_payload(payload: Any) -> Any:
    """Sanitiza payload clinico antes de gravar em ai_audit_logs.

    Estrategia hibrida (Q-A1 c):
    - Keys do dict que matcham SENSITIVE_KEYS (case-insensitive) tem
      o valor inteiro substituido por [REDACTED:key].
    - String-leaves dentro de keys nao-sensiveis passam por regex
      pra capturar PII embutido em texto livre clinico (CPF, phone,
      email, RG, CRM, address, CEP, SUS, nome com prefixo).

    FAIL-SAFE: NUNCA raise. Se algo dar errado durante o walk, devolve
    um dict mínimo com _redaction_failed=True. O audit log NAO pode
    desaparecer porque o sanitizer quebrou — eh melhor gravar um payload
    incompleto do que perder o registro inteiro.

    None passa intacto (caller usa pra output_payload em early-exit
    branches; ja eh None mesmo).
    """
    if payload is None:
        return None
    try:
        return _walk(payload)
    except BaseException as exc:  # noqa: BLE001 — fail-safe: capturar tudo
        logger.error(
            "Falha em sanitize_clinical_payload — gravando audit log com flag de erro. "
            "Tipo do payload: %s; erro: %r",
            type(payload).__name__,
            exc,
        )
        keys: list[str] | None = None
        if isinstance(payload, dict):
            try:
                keys = sorted(str(k) for k in payload.keys())
            except BaseException:  # noqa: BLE001
                keys = None
        return {
            "_redaction_failed": True,
            "_payload_type": type(payload).__name__,
            "_payload_keys": keys,
            "_error": str(exc)[:200],
        }
