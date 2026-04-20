# src/integrations/pix.py
"""
Gerador do EMV (BR Code) para Pix.

Formato padrao do Banco Central (DICT / Pix manual / "copia e cola").
Nao depende de integracao com banco; pode ser gerado localmente.
Cada campo segue TLV: ID(2 chars) + LEN(2 chars) + VALUE.

Referencia: Manual do BR Code versao 2 — BACEN 2020.
"""

from __future__ import annotations

from typing import Optional


def _tlv(field_id: str, value: str) -> str:
    length = f"{len(value):02d}"
    return f"{field_id}{length}{value}"


def _crc16_ccitt(data: str) -> str:
    """CRC16-CCITT (FALSE) — polinomio 0x1021, seed 0xFFFF."""
    crc = 0xFFFF
    for ch in data.encode("utf-8"):
        crc ^= ch << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def build_pix_payload(
    *,
    pix_key: str,
    merchant_name: str,
    merchant_city: str,
    amount_cents: int,
    txid: str,
    description: Optional[str] = None,
) -> str:
    """
    Constroi o BR Code Pix (copia e cola).

    Args:
        pix_key: chave Pix do recebedor (CPF, CNPJ, email, telefone ou aleatoria)
        merchant_name: nome do recebedor (maximo 25 chars, sem acento)
        merchant_city: cidade (maximo 15 chars)
        amount_cents: valor em centavos
        txid: identificador unico da cobranca (alfanumerico, 1-25 chars)
        description: texto adicional (opcional)

    Returns:
        string do BR Code pronta para copia e cola / geracao de QR.
    """
    gui = _tlv("00", "br.gov.bcb.pix")
    key_block = _tlv("01", pix_key)
    merchant_info_value = gui + key_block
    if description:
        merchant_info_value += _tlv("02", description[:72])
    merchant_info = _tlv("26", merchant_info_value)

    payload_format = _tlv("00", "01")
    merchant_category = _tlv("52", "0000")
    currency = _tlv("53", "986")  # BRL
    amount_str = f"{amount_cents / 100:.2f}"
    amount_field = _tlv("54", amount_str)
    country = _tlv("58", "BR")

    name = (merchant_name or "RECIPIENT")[:25]
    city = (merchant_city or "BRASIL")[:15]

    # Additional data — txid em 05
    add_data = _tlv("05", (txid or "***")[:25])
    additional = _tlv("62", add_data)

    partial = (
        payload_format
        + merchant_info
        + merchant_category
        + currency
        + amount_field
        + country
        + _tlv("59", name)
        + _tlv("60", city)
        + additional
        + "6304"
    )
    crc = _crc16_ccitt(partial)
    return partial + crc
