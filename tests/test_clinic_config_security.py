from __future__ import annotations


def test_flatten_payload_masks_legacy_plaintext_secrets():
    from src.web.routes.clinic_config import _flatten_payload

    payload = _flatten_payload(
        {"name": "Clinica"},
        None,
        {
            "integracoes": {
                "apiKeyMeta": "plain-meta",
                "apiKeyOpenAI": "plain-openai",
                "smtpPassword": "plain-pass",
                "smtpHost": "smtp.example.com",
            }
        },
    )

    assert payload["smtpHost"] == "smtp.example.com"
    assert "apiKeyMeta" not in payload
    assert "apiKeyOpenAI" not in payload
    assert "smtpPassword" not in payload


def test_masked_secret_fields_uses_mask_for_legacy_and_encrypted(monkeypatch):
    from src.web.routes import clinic_config

    monkeypatch.setattr(
        clinic_config,
        "get_integrations",
        lambda tenant_id, decrypted=False: {
            "meta_whatsapp_key": "***",
            "openai_api_key": None,
            "ai_api_key": "***",
            "email_password": None,
        },
    )

    masked = clinic_config._masked_secret_fields(
        1,
        {"integracoes": {"smtpPassword": "legacy-plain"}},
    )

    assert masked["apiKeyMeta"] == clinic_config._MASKED_SECRET
    assert masked["apiKeyGemini"] == clinic_config._MASKED_SECRET
    assert masked["smtpPassword"] == clinic_config._MASKED_SECRET
    assert masked["apiKeyOpenAI"] == ""


def test_split_secret_payload_ignores_masks_and_maps_real_values():
    from src.web.routes.clinic_config import _MASKED_SECRET, _split_secret_payload

    updates = _split_secret_payload({
        "apiKeyMeta": _MASKED_SECRET,
        "apiKeyOpenAI": "sk-live",
        "apiKeyGemini": "",
        "smtpPassword": "smtp-secret",
    })

    assert updates == {
        "openai_api_key": "sk-live",
        "ai_api_key": "",
        "email_password": "smtp-secret",
    }


def test_split_secret_payload_ignores_admin_mask_variant():
    from src.web.routes.clinic_config import _split_secret_payload

    updates = _split_secret_payload({
        "apiKeyMeta": "***",
        "apiKeyOpenAI": "********",
        "apiKeyGemini": "AIza-real",
    })

    assert updates == {"ai_api_key": "AIza-real"}


def test_legacy_secret_updates_maps_plaintext_before_scrub():
    from src.web.routes.clinic_config import _legacy_secret_updates

    updates = _legacy_secret_updates({
        "integracoes": {
            "apiKeyMeta": "legacy-meta",
            "apiKeyOpenAI": "legacy-openai",
            "smtpPassword": "legacy-pass",
        }
    })

    assert updates == {
        "meta_whatsapp_key": "legacy-meta",
        "openai_api_key": "legacy-openai",
        "email_password": "legacy-pass",
    }


def test_tenant_admin_secret_update_ignores_masked_values():
    from src.web.routes.tenant_admin import _secret_update

    assert _secret_update({"ai_api_key": "***"}, "ai_api_key") is None
    assert _secret_update({"ai_api_key": "********"}, "ai_api_key") is None
    assert _secret_update({"ai_api_key": ""}, "ai_api_key") == ""
    assert _secret_update({"ai_api_key": "real-secret"}, "ai_api_key") == "real-secret"
