# src/infra/crypto.py
"""
Criptografia simétrica para colunas _encrypted usando Fernet.

A chave de criptografia é derivada da variável de ambiente ENCRYPTION_KEY.
Se ENCRYPTION_KEY não estiver definida, usa HKDF sobre SECRET_KEY como fallback
(menos seguro, mas garante que o sistema não quebre em ambientes de dev).

Uso:
    from src.infra.crypto import encrypt_value, decrypt_value

    ciphertext = encrypt_value("minha-api-key-secreta")
    plaintext  = decrypt_value(ciphertext)
"""

from __future__ import annotations

import base64
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger("cannabia.crypto")

# Variáveis de ambiente
_ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
_SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-fallback")


def _derive_key() -> bytes:
    """
    Deriva uma chave Fernet (32 bytes, base64-encoded) a partir de ENCRYPTION_KEY
    ou, como fallback, de SECRET_KEY via HKDF.

    Fernet exige exatamente 32 bytes URL-safe base64-encoded.
    """
    if _ENCRYPTION_KEY:
        # Se o operador forneceu uma chave Fernet direta, usa direto
        try:
            Fernet(_ENCRYPTION_KEY.encode())
            return _ENCRYPTION_KEY.encode()
        except (ValueError, Exception):
            pass

        # Senão, deriva via HKDF do valor fornecido
        raw = _ENCRYPTION_KEY.encode()
    else:
        logger.warning(
            "ENCRYPTION_KEY não definida. Derivando chave de SECRET_KEY via HKDF. "
            "Configure ENCRYPTION_KEY em produção para segurança adequada."
        )
        raw = _SECRET_KEY.encode()

    # HKDF para derivar 32 bytes determinísticos da chave de entrada
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"cannabia-fernet-v1",
        info=b"encryption-key-derivation",
    )
    derived = hkdf.derive(raw)
    return base64.urlsafe_b64encode(derived)


# Fernet singleton — inicializado uma vez na importação
_fernet_key = _derive_key()
_fernet = Fernet(_fernet_key)


def encrypt_value(plaintext: str) -> str:
    """
    Criptografa um valor de texto e retorna a string base64 do ciphertext.
    Retorna string vazia se o input for vazio/None.
    """
    if not plaintext:
        return ""
    token = _fernet.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    """
    Descriptografa um valor criptografado com encrypt_value().
    Retorna string vazia se o input for vazio/None.
    Levanta ValueError se o token for inválido ou a chave estiver errada.
    """
    if not ciphertext:
        return ""
    try:
        plaintext = _fernet.decrypt(ciphertext.encode("utf-8"))
        return plaintext.decode("utf-8")
    except InvalidToken:
        logger.error(
            "Falha ao descriptografar valor. Token inválido ou chave alterada."
        )
        raise ValueError(
            "Não foi possível descriptografar o valor. "
            "Verifique se ENCRYPTION_KEY não foi alterada."
        )


def generate_key() -> str:
    """
    Gera uma nova chave Fernet válida.
    Útil para operadores gerarem ENCRYPTION_KEY pela primeira vez:
        python -c "from src.infra.crypto import generate_key; print(generate_key())"
    """
    return Fernet.generate_key().decode("utf-8")
