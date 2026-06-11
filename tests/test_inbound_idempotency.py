"""COM-1 — idempotencia inbound por wamid (29.3 RM1).

Valida os indices unicos parciais da migration 050 (ON CONFLICT) e o
curto-circuito de reentrega no handler de mensagens.
"""
from __future__ import annotations

import src.services.message_service as ms

_INCOMING_SQL = (
    "INSERT INTO incoming_messages "
    "(clinic_id, sender, contact_name, message_text, timestamp, wamid) "
    "VALUES (%s,%s,%s,%s,%s,%s) "
    "ON CONFLICT (clinic_id, wamid) WHERE wamid IS NOT NULL DO NOTHING RETURNING id"
)


def _existing_clinic(cur) -> int:
    cur.execute("SELECT id FROM clinics ORDER BY id LIMIT 1")
    row = cur.fetchone()
    return row["id"] if row else 1


def test_wamid_duplicado_nao_insere_de_novo(db_cursor):
    cid = _existing_clinic(db_cursor)
    db_cursor.execute(_INCOMING_SQL, (cid, "5511", "Ana", "oi", "1", "wamid-DUP"))
    first = db_cursor.fetchone()
    db_cursor.execute(_INCOMING_SQL, (cid, "5511", "Ana", "oi", "1", "wamid-DUP"))
    second = db_cursor.fetchone()
    assert first is not None          # 1a gravacao insere
    assert second is None             # reentrega com mesmo wamid: DO NOTHING


def test_wamids_distintos_inserem(db_cursor):
    cid = _existing_clinic(db_cursor)
    db_cursor.execute(_INCOMING_SQL, (cid, "5511", "Ana", "a", "1", "wamid-A"))
    a = db_cursor.fetchone()
    db_cursor.execute(_INCOMING_SQL, (cid, "5511", "Ana", "b", "2", "wamid-B"))
    b = db_cursor.fetchone()
    assert a is not None and b is not None


def test_wamid_nulo_nunca_conflita(db_cursor):
    """Mensagens legadas sem wamid sempre inserem (NULL nao participa do indice)."""
    cid = _existing_clinic(db_cursor)
    db_cursor.execute(_INCOMING_SQL, (cid, "5511", "Ana", "x", "1", None))
    a = db_cursor.fetchone()
    db_cursor.execute(_INCOMING_SQL, (cid, "5511", "Ana", "x", "1", None))
    b = db_cursor.fetchone()
    assert a is not None and b is not None


def test_conversation_messages_external_id_unico(db_cursor):
    cid = _existing_clinic(db_cursor)
    db_cursor.execute(
        "INSERT INTO conversations (clinic_id, contact_phone, channel, status) "
        "VALUES (%s,%s,'whatsapp','open') RETURNING id",
        (cid, "5511999000"),
    )
    conv = db_cursor.fetchone()["id"]
    sql = (
        "INSERT INTO conversation_messages "
        "(conversation_id, clinic_id, direction, sender_type, message_text, message_type, external_id) "
        "VALUES (%s,%s,'inbound','patient',%s,'text',%s) "
        "ON CONFLICT (external_id) WHERE external_id IS NOT NULL DO NOTHING RETURNING id"
    )
    db_cursor.execute(sql, (conv, cid, "oi", "ext-unique-1"))
    a = db_cursor.fetchone()
    db_cursor.execute(sql, (conv, cid, "oi", "ext-unique-1"))
    b = db_cursor.fetchone()
    assert a is not None and b is None


def test_handle_message_event_curto_circuita_wamid_duplicado(monkeypatch):
    """Reentrega Meta (mesmo wamid no batch) processa anamnese uma unica vez."""
    state = {"save": 0, "process": 0}

    def fake_save(clinic_id, sender, name, text, ts, wamid=None):
        state["save"] += 1
        return 123 if state["save"] == 1 else None  # 2a tentativa: duplicada

    monkeypatch.setattr(ms.message_repository, "save_incoming_message", fake_save)
    monkeypatch.setattr(ms, "send_email_notification", lambda *a, **k: True)
    monkeypatch.setattr(
        ms, "process_message",
        lambda *a, **k: state.__setitem__("process", state["process"] + 1),
    )
    import src.services.conversation_service as cs
    monkeypatch.setattr(cs, "receive_inbound_message", lambda *a, **k: {"message_id": 1})

    value = {"messages": [
        {"id": "wamid-X", "from": "5511", "text": {"body": "oi"}, "timestamp": "1"},
        {"id": "wamid-X", "from": "5511", "text": {"body": "oi"}, "timestamp": "1"},
    ]}
    ms.handle_message_event(value, clinic_id=1)

    assert state["save"] == 2     # ambas tentaram gravar
    assert state["process"] == 1  # a 2a (duplicada) curto-circuitou
