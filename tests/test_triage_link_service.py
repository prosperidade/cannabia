from __future__ import annotations

import pytest

from src.services import triage_link_service


def test_issue_and_resolve_triage_link(monkeypatch):
    monkeypatch.setattr(triage_link_service, "get_clinic_public_label", lambda clinic_id: "Clinica Segura")

    issued = triage_link_service.issue_triage_link(7)
    resolved = triage_link_service.resolve_triage_link_token(issued["token"])

    assert issued["clinic_id"] == 7
    assert issued["clinic_label"] == "Clinica Segura"
    assert "/triagem?token=" in issued["url"]
    assert resolved == {"clinic_id": 7, "clinic_label": "Clinica Segura"}


def test_resolve_triage_link_rejects_invalid_token():
    with pytest.raises(ValueError, match="Token de triagem invalido."):
        triage_link_service.resolve_triage_link_token("token-invalido")
