"""COM-2 — parser completo: todas as mensagens/entries do payload Meta são
processadas (fim da perda silenciosa em batch — 29.3 P3/RM2)."""
from __future__ import annotations

import src.services.message_service as ms


def _patch_sideeffects(monkeypatch):
    """Neutraliza I/O (DB, e-mail, fluxo) e captura o que foi processado."""
    saved = []
    processed = []
    monkeypatch.setattr(
        ms.message_repository,
        "save_incoming_message",
        lambda clinic_id, sender, name, text, ts, wamid=None: (
            saved.append((clinic_id, sender, text)) or len(saved)
        ),
    )
    monkeypatch.setattr(ms, "send_email_notification", lambda *a, **k: True)
    monkeypatch.setattr(ms, "process_message", lambda *a, **k: processed.append(a))
    # threading import é resolvido dentro da função; substitui no módulo de origem
    import src.services.conversation_service as cs
    monkeypatch.setattr(cs, "receive_inbound_message", lambda *a, **k: {"message_id": 1})
    return saved, processed


def test_iter_message_changes_varre_todos_os_entries_e_changes():
    data = {
        "entry": [
            {"changes": [
                {"field": "messages", "value": {"messages": [{"id": "w1"}]}},
                {"field": "message_template_status_update", "value": {"id": "t1"}},
            ]},
            {"changes": [
                {"field": "messages", "value": {"messages": [{"id": "w2"}]}},
            ]},
        ]
    }
    out = list(ms.iter_message_changes(data))
    assert len(out) == 3
    assert out[0][0] == "messages"
    assert out[1][0] == "message_template_status_update"
    assert out[2][1]["messages"][0]["id"] == "w2"


def test_handle_message_event_processa_todas_mensagens_do_batch(monkeypatch):
    saved, processed = _patch_sideeffects(monkeypatch)
    value = {
        "contacts": [
            {"wa_id": "5511111111111", "profile": {"name": "Ana"}},
            {"wa_id": "5522222222222", "profile": {"name": "Bruno"}},
        ],
        "messages": [
            {"id": "w1", "from": "5511111111111", "text": {"body": "oi"}, "timestamp": "1"},
            {"id": "w2", "from": "5522222222222", "text": {"body": "ola"}, "timestamp": "2"},
            {"id": "w3", "from": "5511111111111", "text": {"body": "tudo bem"}, "timestamp": "3"},
        ],
    }

    ms.handle_message_event(value, clinic_id=1)

    # As 3 mensagens do batch foram salvas e encaminhadas (nenhuma perdida).
    assert len(saved) == 3
    assert len(processed) == 3
    assert [s[1] for s in saved] == ["5511111111111", "5522222222222", "5511111111111"]


def test_contact_name_casa_por_wa_id(monkeypatch):
    saved, processed = _patch_sideeffects(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        ms, "process_message",
        lambda clinic_id, sender, name, text, tenant_id=None: captured.update({sender: name}),
    )
    value = {
        "contacts": [
            {"wa_id": "5511111111111", "profile": {"name": "Ana"}},
            {"wa_id": "5522222222222", "profile": {"name": "Bruno"}},
        ],
        "messages": [
            {"id": "w2", "from": "5522222222222", "text": {"body": "ola"}, "timestamp": "2"},
        ],
    }
    ms.handle_message_event(value, clinic_id=1)
    assert captured["5522222222222"] == "Bruno"


def test_uma_mensagem_com_erro_nao_interrompe_as_demais(monkeypatch):
    saved, processed = _patch_sideeffects(monkeypatch)

    def boom(clinic_id, sender, name, text, tenant_id=None):
        if sender == "bad":
            raise RuntimeError("falha isolada")
        processed.append(sender)

    monkeypatch.setattr(ms, "process_message", boom)
    value = {
        "messages": [
            {"id": "w1", "from": "ok1", "text": {"body": "a"}, "timestamp": "1"},
            {"id": "w2", "from": "bad", "text": {"body": "b"}, "timestamp": "2"},
            {"id": "w3", "from": "ok2", "text": {"body": "c"}, "timestamp": "3"},
        ],
    }
    ms.handle_message_event(value, clinic_id=1)
    # A falha de "bad" não impede ok1 e ok2.
    assert processed == ["ok1", "ok2"]
    assert len(saved) == 3
