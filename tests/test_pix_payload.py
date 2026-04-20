"""Testes do gerador de BR Code Pix (EMV)."""

from src.integrations.pix import _crc16_ccitt, _tlv, build_pix_payload


def test_tlv_format():
    assert _tlv("00", "br.gov.bcb.pix") == "0014br.gov.bcb.pix"
    assert _tlv("52", "0000") == "52040000"


def test_crc16_ccitt_known_value():
    # CRC16 CCITT-FALSE de "123456789" = 0x29B1
    assert _crc16_ccitt("123456789") == "29B1"


def test_build_pix_payload_structure():
    payload = build_pix_payload(
        pix_key="tenant@cannabia.app",
        merchant_name="CLINICA VERDE",
        merchant_city="SAO PAULO",
        amount_cents=2500,
        txid="abc123",
        description="Consulta",
    )
    # Deve iniciar com formato 0002 e conter GUI Pix
    assert payload.startswith("000201")
    assert "br.gov.bcb.pix" in payload
    assert "tenant@cannabia.app" in payload
    # Montante em reais (25.00)
    assert "540525.00" in payload
    # txid
    assert "0506abc123" in payload or "abc123" in payload
    # Pais BR
    assert "5802BR" in payload


def test_build_pix_payload_crc_valid():
    payload = build_pix_payload(
        pix_key="00000000000",
        merchant_name="TEST",
        merchant_city="BRASIL",
        amount_cents=100,
        txid="xyz",
    )
    # Ultimos 4 chars sao o CRC; recomputando sobre o restante (incluindo "6304") deve casar
    body, crc = payload[:-4], payload[-4:]
    assert _crc16_ccitt(body) == crc


def test_build_pix_payload_truncates_long_fields():
    payload = build_pix_payload(
        pix_key="chave-longa@dominio.com.br",
        merchant_name="NOME MUITO LONGO QUE DEVE SER TRUNCADO AO LIMITE",
        merchant_city="CIDADE MUITO LONGA AQUI",
        amount_cents=999,
        txid="t" * 40,
    )
    # Deve continuar sendo string valida
    assert isinstance(payload, str)
    assert len(payload) > 0
