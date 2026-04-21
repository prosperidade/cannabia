"""Testes unit do document_review_service (F4.7 do SCC).

Cobre a maquina de estados, signature_hash verificavel e as chamadas
SQL esperadas — tudo com db_cursor mockado para nao depender de DB.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from src.services import document_review_service as drs
from src.services.document_review_service import (
    ALL_ACTIONS,
    ALLOWED_TRANSITIONS,
    InvalidActionError,
    InvalidTransitionError,
    ReportNotFoundError,
    ReviewStep,
    _compute_signature,
    transition,
    verify_signature,
)


# ---------------------------------------------------------------------
# Maquina de estados (puro)
# ---------------------------------------------------------------------

class TestStateMachine:
    def test_todas_as_acoes_tem_origem_e_destino(self):
        for action, (allowed_from, to_status) in ALLOWED_TRANSITIONS.items():
            assert isinstance(allowed_from, frozenset)
            assert allowed_from, action
            assert to_status in {"rt_review", "legal_review", "approved", "rejected"}

    def test_draft_submit_to_rt_vai_para_rt_review(self):
        allowed_from, to = ALLOWED_TRANSITIONS["submit_to_rt"]
        assert "draft" in allowed_from
        assert to == "rt_review"

    def test_rejected_pode_ser_reabrido_via_submit_to_rt(self):
        allowed_from, _ = ALLOWED_TRANSITIONS["submit_to_rt"]
        assert "rejected" in allowed_from

    def test_rt_approve_final_pula_legal(self):
        allowed_from, to = ALLOWED_TRANSITIONS["rt_approve_final"]
        assert allowed_from == frozenset({"rt_review"})
        assert to == "approved"

    def test_legal_review_nao_aceita_rt_actions(self):
        for action in ("rt_approve", "rt_approve_final", "rt_reject"):
            allowed_from, _ = ALLOWED_TRANSITIONS[action]
            assert "legal_review" not in allowed_from


# ---------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------

class TestSignature:
    def _make_step(self, **overrides) -> ReviewStep:
        defaults = {
            "id": 1, "report_id": 7,
            "from_status": "draft", "to_status": "rt_review",
            "action": "submit_to_rt", "actor_user_id": 42,
            "actor_role": "medico", "notes": None,
            "content_hash_at_review": "a" * 64,
            "signature_hash": "x" * 64,
            "reviewed_at": datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
        }
        defaults.update(overrides)
        # recomputa signature valida para o teste feliz
        if "signature_hash" not in overrides:
            defaults["signature_hash"] = _compute_signature(
                report_id=defaults["report_id"],
                from_status=defaults["from_status"],
                to_status=defaults["to_status"],
                action=defaults["action"],
                actor_user_id=defaults["actor_user_id"],
                content_hash=defaults["content_hash_at_review"],
                reviewed_at_iso=defaults["reviewed_at"].isoformat(),
            )
        return ReviewStep(**defaults)

    def test_assinatura_valida_retorna_true(self):
        step = self._make_step()
        assert verify_signature(step) is True

    def test_alteracao_do_to_status_invalida_assinatura(self):
        step = self._make_step()
        tampered = ReviewStep(
            **{**step.__dict__, "to_status": "approved"}
        )
        assert verify_signature(tampered) is False

    def test_alteracao_do_content_hash_invalida_assinatura(self):
        step = self._make_step()
        tampered = ReviewStep(
            **{**step.__dict__, "content_hash_at_review": "b" * 64}
        )
        assert verify_signature(tampered) is False

    def test_signature_bate_com_sha256_manual(self):
        step = self._make_step()
        payload = (
            f"{step.report_id}:{step.from_status}:{step.to_status}:"
            f"{step.action}:{step.actor_user_id}:"
            f"{step.content_hash_at_review}:{step.reviewed_at.isoformat()}"
        )
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        assert step.signature_hash == expected


# ---------------------------------------------------------------------
# Transition com db mockado
# ---------------------------------------------------------------------

class _FakeCursor:
    def __init__(self, responses: list):
        self._responses = list(responses)
        self._last = None
        self.executes: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.executes.append((sql, tuple(params)))
        self._last = self._responses.pop(0) if self._responses else None

    def fetchone(self):
        return self._last


class _FakeConn:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class _FakeCtx:
    def __init__(self, cursor, conn):
        self._cursor = cursor
        self._conn = conn

    def __enter__(self):
        return (self._conn, self._cursor)

    def __exit__(self, *exc):
        return False


def _install_fake(monkeypatch, responses):
    cursor = _FakeCursor(responses)
    conn = _FakeConn()
    ctx = _FakeCtx(cursor, conn)
    monkeypatch.setattr(
        "src.services.document_review_service.db_cursor",
        lambda dictionary=True: ctx,
    )
    return cursor, conn


def _report_row(report_id: int = 7, status: str = "draft",
                content_hash: str = "a" * 64) -> dict:
    return {"id": report_id, "status": status, "content_hash": content_hash}


def _step_row(**overrides) -> dict:
    now = datetime(2026, 4, 21, 12, tzinfo=timezone.utc)
    defaults = {
        "id": 1, "report_id": 7,
        "from_status": "draft", "to_status": "rt_review",
        "action": "submit_to_rt",
        "actor_user_id": 42, "actor_role": "medico", "notes": None,
        "content_hash_at_review": "a" * 64,
        "signature_hash": "x" * 64,
        "reviewed_at": now,
    }
    defaults.update(overrides)
    return defaults


class TestTransition:
    def test_happy_path_submit_to_rt(self, monkeypatch):
        report = _report_row(status="draft")
        step = _step_row(from_status="draft", to_status="rt_review")
        # responses na ordem: SELECT report, INSERT step (RETURNING), UPDATE report
        cursor, conn = _install_fake(monkeypatch, [report, step, None])

        result = transition(7, "submit_to_rt", actor_user_id=42,
                            actor_role="medico", notes="ok")
        assert result.to_status == "rt_review"
        assert result.action == "submit_to_rt"
        # SELECT + INSERT + UPDATE
        assert len(cursor.executes) == 3
        assert "SELECT" in cursor.executes[0][0]
        assert "INSERT INTO document_review_workflows" in cursor.executes[1][0]
        assert "UPDATE regulatory_reports" in cursor.executes[2][0]
        assert conn.commits == 1

    def test_happy_path_legal_approve_registra_approver(self, monkeypatch):
        report = _report_row(status="legal_review")
        step = _step_row(
            from_status="legal_review", to_status="approved",
            action="legal_approve",
        )
        cursor, _ = _install_fake(monkeypatch, [report, step, None])
        result = transition(7, "legal_approve", actor_user_id=9,
                            actor_role="admin")
        assert result.to_status == "approved"
        # UPDATE ao aprovar deve setar approved_by e approved_at
        update_sql = cursor.executes[2][0]
        assert "approved_by" in update_sql
        assert "approved_at" in update_sql

    def test_transicao_invalida_levanta(self, monkeypatch):
        report = _report_row(status="draft")
        _install_fake(monkeypatch, [report])
        with pytest.raises(InvalidTransitionError, match="rt_approve"):
            transition(7, "rt_approve", actor_user_id=1, actor_role="admin")

    def test_acao_desconhecida(self, monkeypatch):
        report = _report_row(status="draft")
        _install_fake(monkeypatch, [report])
        with pytest.raises(InvalidActionError, match="desconhecida"):
            transition(7, "teleport", actor_user_id=1, actor_role="admin")

    def test_report_inexistente(self, monkeypatch):
        _install_fake(monkeypatch, [None])
        with pytest.raises(ReportNotFoundError, match="nao encontrado"):
            transition(999, "submit_to_rt", actor_user_id=1, actor_role="medico")

    def test_signature_do_step_persistido_e_valida(self, monkeypatch):
        """Quando INSERT retorna a linha inserida, a signature do step
        retornado tem que bater com a recomputacao."""
        now = datetime(2026, 4, 21, 12, tzinfo=timezone.utc)
        report = _report_row(status="rt_review", content_hash="a" * 64)
        # Como o service calcula signature_hash e passa no INSERT, o
        # step_row "devolvido" pelo DB reflete esse mesmo valor. Aqui
        # construimos o row da mesma forma para simular fielmente.
        expected_sig = _compute_signature(
            report_id=7, from_status="rt_review", to_status="legal_review",
            action="rt_approve", actor_user_id=42,
            content_hash="a" * 64, reviewed_at_iso=now.isoformat(),
        )
        step = _step_row(
            from_status="rt_review", to_status="legal_review",
            action="rt_approve", actor_user_id=42, reviewed_at=now,
            signature_hash=expected_sig,
        )
        _install_fake(monkeypatch, [report, step, None])
        # Monkeypatch datetime.now para bater com o reviewed_at do step
        class _FakeDT:
            @staticmethod
            def now(tz=None):
                return now
        monkeypatch.setattr("src.services.document_review_service.datetime", _FakeDT)

        result = transition(7, "rt_approve", actor_user_id=42,
                            actor_role="medico")
        assert verify_signature(result) is True

    def test_estado_terminal_approved_nao_aceita_acoes(self, monkeypatch):
        report = _report_row(status="approved")
        _install_fake(monkeypatch, [report])
        with pytest.raises(InvalidTransitionError):
            transition(7, "rt_approve", actor_user_id=1, actor_role="admin")
        # Tambem nao aceita submit_to_rt (reabertura so a partir de rejected)
        _install_fake(monkeypatch, [report])
        with pytest.raises(InvalidTransitionError):
            transition(7, "submit_to_rt", actor_user_id=1, actor_role="medico")


# ---------------------------------------------------------------------
# All actions constant
# ---------------------------------------------------------------------

class TestActionsExported:
    def test_all_actions_cobre_os_6(self):
        assert set(ALL_ACTIONS) == {
            "submit_to_rt", "rt_approve", "rt_approve_final",
            "rt_reject", "legal_approve", "legal_reject",
        }
