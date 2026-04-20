"""Testes de resolucao de segredos por tenant com fallback para env."""

from unittest.mock import patch


def test_whatsapp_config_fallback_to_env():
    """Quando nao ha integrations, deve cair para config global."""
    from src.services import tenant_secrets

    with patch.object(tenant_secrets, "_tenant_integrations", return_value=None), \
         patch.object(tenant_secrets, "_load_env_fallback", return_value={
             "whatsapp_phone_number_id": "env-phone",
             "meta_whatsapp_key": "env-key",
             "whatsapp_app_secret": "env-secret",
             "verify_token": "env-verify",
             "email_from": None,
             "smtp_server": None,
             "smtp_port": None,
             "email_password": None,
             "doctor_email": None,
             "google_api_key": None,
         }):
        cfg = tenant_secrets.get_whatsapp_config(tenant_id=42)
        assert cfg["phone_number_id"] == "env-phone"
        assert cfg["access_token"] == "env-key"
        assert cfg["app_secret"] == "env-secret"
        assert cfg["verify_token"] == "env-verify"


def test_whatsapp_config_prefers_tenant_value():
    """Valor do tenant sobrescreve env quando nao-nulo."""
    from src.services import tenant_secrets

    tenant_integ = {
        "whatsapp_phone_number_id": "tenant-phone",
        "meta_whatsapp_key": "tenant-key",
        "whatsapp_app_secret": None,  # deve cair para env
        "verify_token": "",  # vazio tambem cai para env
        "whatsapp_business_account_id": "waba-123",
    }

    with patch.object(tenant_secrets, "_tenant_integrations", return_value=tenant_integ), \
         patch.object(tenant_secrets, "_load_env_fallback", return_value={
             "whatsapp_phone_number_id": "env-phone",
             "meta_whatsapp_key": "env-key",
             "whatsapp_app_secret": "env-secret",
             "verify_token": "env-verify",
             "email_from": None,
             "smtp_server": None,
             "smtp_port": None,
             "email_password": None,
             "doctor_email": None,
             "google_api_key": None,
         }):
        cfg = tenant_secrets.get_whatsapp_config(tenant_id=42)
        assert cfg["phone_number_id"] == "tenant-phone"
        assert cfg["access_token"] == "tenant-key"
        # Valores None/vazios no tenant devem cair para env
        assert cfg["app_secret"] == "env-secret"
        assert cfg["verify_token"] == "env-verify"
        assert cfg["business_account_id"] == "waba-123"


def test_ai_config_default_provider_is_gemini():
    from src.services import tenant_secrets

    with patch.object(tenant_secrets, "_tenant_integrations", return_value=None), \
         patch.object(tenant_secrets, "_load_env_fallback", return_value={
             "whatsapp_phone_number_id": None,
             "meta_whatsapp_key": None,
             "whatsapp_app_secret": None,
             "verify_token": None,
             "email_from": None,
             "smtp_server": None,
             "smtp_port": None,
             "email_password": None,
             "doctor_email": None,
             "google_api_key": "global-google-key",
         }):
        cfg = tenant_secrets.get_ai_config(tenant_id=None)
        assert cfg["provider"] == "gemini"
        assert cfg["google_api_key"] == "global-google-key"


def test_email_config_merges_tenant_and_env():
    from src.services import tenant_secrets

    tenant_integ = {
        "email_from": "clinica@tenant.com.br",
        "smtp_server": None,
        "smtp_port": 2525,
        "email_password": "tenant-pw",
        "doctor_email": None,
    }

    with patch.object(tenant_secrets, "_tenant_integrations", return_value=tenant_integ), \
         patch.object(tenant_secrets, "_load_env_fallback", return_value={
             "whatsapp_phone_number_id": None,
             "meta_whatsapp_key": None,
             "whatsapp_app_secret": None,
             "verify_token": None,
             "email_from": "default@env.com",
             "smtp_server": "smtp.gmail.com",
             "smtp_port": 587,
             "email_password": "env-pw",
             "doctor_email": "doctor@env.com",
             "google_api_key": None,
         }):
        cfg = tenant_secrets.get_email_config(tenant_id=1)
        assert cfg["email_from"] == "clinica@tenant.com.br"
        assert cfg["smtp_server"] == "smtp.gmail.com"  # fallback
        assert cfg["smtp_port"] == 2525
        assert cfg["email_password"] == "tenant-pw"
        assert cfg["doctor_email"] == "doctor@env.com"  # fallback
