"""CLI-1 — religar o loop de follow-up no webhook (29.2 R1 / C1).

Respostas a follow-ups 'sent' são registradas e geram evento de timeline, em vez
de descartadas; sessão 'completed' não é deletada.
"""
from __future__ import annotations

import src.services.message_service as ms
import src.services.anamnesis_flow as af
import src.repositories.session_repository as sr
import src.repositories.patient_timeline_repository as ptr
import src.services.telemetry_crm_service as tcrm


def test_resposta_de_followup_e_consumida_e_gera_evento(monkeypatch):
    monkeypatch.setattr(sr, "get_session", lambda clinic_id, phone: None)
    monkeypatch.setattr(
        tcrm.TelemetryCRMService, "handle_patient_response",
        lambda self, c, p, t: {"id": 9, "patient_id": 3, "followup_type": "d3"},
    )
    events = []
    monkeypatch.setattr(ptr, "create_event", lambda **k: events.append(k))

    assert ms._maybe_handle_followup_response(1, "5511", "1") is True
    assert events and events[0]["event_type"] == "followup_respondido"
    assert events[0]["patient_id"] == 3
    assert events[0]["metadata"]["followup_type"] == "d3"


def test_gatilho_nao_e_tratado_como_followup(monkeypatch):
    chamadas = {"n": 0}
    monkeypatch.setattr(
        tcrm.TelemetryCRMService, "handle_patient_response",
        lambda self, c, p, t: chamadas.__setitem__("n", chamadas["n"] + 1) or {"id": 1},
    )
    # "Oi" deve (re)iniciar a anamnese, não virar resposta de follow-up.
    assert ms._maybe_handle_followup_response(1, "5511", "Oi") is False
    assert chamadas["n"] == 0


def test_anamnese_ativa_nao_e_sequestrada(monkeypatch):
    monkeypatch.setattr(sr, "get_session", lambda c, p: {"step": "awaiting_age", "data": {}})
    chamadas = {"n": 0}
    monkeypatch.setattr(
        tcrm.TelemetryCRMService, "handle_patient_response",
        lambda self, c, p, t: chamadas.__setitem__("n", chamadas["n"] + 1) or {"id": 1},
    )
    assert ms._maybe_handle_followup_response(1, "5511", "35") is False
    assert chamadas["n"] == 0


def test_sem_followup_pendente_retorna_false(monkeypatch):
    monkeypatch.setattr(sr, "get_session", lambda c, p: None)
    monkeypatch.setattr(
        tcrm.TelemetryCRMService, "handle_patient_response", lambda self, c, p, t: None
    )
    assert ms._maybe_handle_followup_response(1, "5511", "estou melhor") is False


def test_handle_message_event_roteia_followup_antes_da_anamnese(monkeypatch):
    monkeypatch.setattr(ms.message_repository, "save_incoming_message", lambda *a, **k: 1)
    import src.services.conversation_service as cs
    monkeypatch.setattr(cs, "receive_inbound_message", lambda *a, **k: {"message_id": 1})
    monkeypatch.setattr(sr, "get_session", lambda c, p: None)
    monkeypatch.setattr(
        tcrm.TelemetryCRMService, "handle_patient_response",
        lambda self, c, p, t: {"id": 9, "patient_id": 3, "followup_type": "d3"},
    )
    monkeypatch.setattr(ptr, "create_event", lambda **k: None)
    processed = []
    monkeypatch.setattr(ms, "process_message", lambda *a, **k: processed.append(a))

    value = {"messages": [{"id": "w1", "from": "5511", "text": {"body": "1"}, "timestamp": "1"}]}
    ms.handle_message_event(value, clinic_id=1)
    assert processed == []  # follow-up consumiu a mensagem; anamnese não chamada


def test_sessao_completed_nao_e_deletada(monkeypatch):
    monkeypatch.setattr(
        af, "get_session", lambda c, p: {"step": "completed", "data": {"patient_name": "Ana"}}
    )
    deleted = []
    monkeypatch.setattr(af, "delete_session", lambda c, p: deleted.append((c, p)))
    replies = []
    monkeypatch.setattr(af, "send_whatsapp_text", lambda phone, msg, tenant_id=None: replies.append(msg))

    af.process_message(1, "5511", "Ana", "estou melhor")
    assert deleted == []                       # sessão completed preservada
    assert replies and "concluída" in replies[0]
