# tests/test_crypto.py
"""Testes do módulo de criptografia Fernet."""

import pytest


def test_encrypt_decrypt_roundtrip():
    """Criptografar e descriptografar deve retornar o valor original."""
    from src.infra.crypto import encrypt_value, decrypt_value

    original = "minha-api-key-super-secreta-123"
    encrypted = encrypt_value(original)

    assert encrypted != original
    assert len(encrypted) > 0

    decrypted = decrypt_value(encrypted)
    assert decrypted == original


def test_encrypt_empty_string():
    """String vazia deve retornar string vazia sem erro."""
    from src.infra.crypto import encrypt_value, decrypt_value

    assert encrypt_value("") == ""
    assert decrypt_value("") == ""


def test_encrypt_none_value():
    """None deve ser tratado como string vazia."""
    from src.infra.crypto import encrypt_value, decrypt_value

    assert encrypt_value(None) == ""
    assert decrypt_value(None) == ""


def test_different_inputs_produce_different_ciphertexts():
    """Inputs diferentes devem gerar ciphertexts diferentes."""
    from src.infra.crypto import encrypt_value

    a = encrypt_value("valor-a")
    b = encrypt_value("valor-b")
    assert a != b


def test_decrypt_invalid_token_raises():
    """Token inválido deve levantar ValueError."""
    from src.infra.crypto import decrypt_value

    with pytest.raises(ValueError, match="Não foi possível descriptografar"):
        decrypt_value("token-invalido-nao-fernet")


def test_generate_key_format():
    """Chave gerada deve ser uma string base64 URL-safe válida."""
    from src.infra.crypto import generate_key
    from cryptography.fernet import Fernet

    key = generate_key()
    assert isinstance(key, str)
    assert len(key) == 44  # Fernet key length in base64
    # Deve ser uma chave Fernet válida
    Fernet(key.encode())
