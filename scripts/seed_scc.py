"""Seed complementar do Sandbox Compliance Core (SCC).

Popula as tabelas que `seed_comprehensive.py` nao cobre — governance
(F1), members (F2), sandbox/regulatory (F3.2/F4) e pharmacovigilance
(F3.1/F3.3+).

Idempotente: usa SELECT antes de INSERT ou ON CONFLICT. Pode rodar
multiplas vezes seguidas.

Pre-requisitos:
  - tenant_id=1 (Cannabia) e clinic_id=1 (Clinica Cannabia) ja existem
  - users dev (admin/medico/atendente/paciente) ja existem
  - patients ja existem (rodar `seed_comprehensive.py` antes para gerar)

Uso:
    env/Scripts/python.exe scripts/seed_scc.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.infra.database import db_cursor


# Estado conhecido (vide CLAUDE.md, docs/25, project_dev_credentials)
TENANT_ID = 1
CLINIC_ID = 1


# ============================================================================
# Helpers
# ============================================================================


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(n: int) -> datetime:
    return _now() - timedelta(days=n)


def _resolve_user(username: str) -> int | None:
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        return row["id"] if row else None


def _section(title: str) -> None:
    print(f"\n=== {title} ===")


def _ok(msg: str) -> None:
    print(f"  {msg}")


# ============================================================================
# 1. associations + institutional_documents + technical_responsibles
# ============================================================================


def seed_governance(admin_id: int) -> dict:
    """Popula governance hub (F1.x): associations, documents, RTs."""
    _section("1. Governance Hub (F1)")

    out: dict = {}

    with db_cursor(dictionary=True) as (conn, cur):
        # 1.1 associations (1 linha por tenant_id) — UPSERT
        cur.execute(
            """
            INSERT INTO associations (
              tenant_id, members_count, is_judicial_operation,
              directive_board, sandbox_application_status
            )
            VALUES (%s, 0, FALSE, %s::jsonb, 'preparing')
            ON CONFLICT (tenant_id) DO UPDATE SET
              members_count = EXCLUDED.members_count,
              sandbox_application_status = COALESCE(
                associations.sandbox_application_status,
                EXCLUDED.sandbox_application_status
              ),
              updated_at = NOW()
            RETURNING tenant_id
            """,
            (TENANT_ID, json.dumps([
                {"role": "presidente", "name": "Dr. Roberto Souza", "cpf": "***.***.***-**"},
                {"role": "vice", "name": "Dra. Carolina Lima", "cpf": "***.***.***-**"},
                {"role": "tesoureiro", "name": "Joao Mendes", "cpf": "***.***.***-**"},
            ])),
        )
        _ok(f"associations: tenant={TENANT_ID} (preparando sandbox)")

        # 1.2 institutional_documents — 3 docs (estatuto + ata + comprovante)
        docs_to_seed = [
            {
                "doc_type": "statute",
                "title": "Estatuto Social — Cannabia Associacao",
                "version": "v1.0",
                "valid_from": "2024-01-15",
                "file_uri": "/storage/seed/estatuto_v1.pdf",
            },
            {
                "doc_type": "board_minutes",
                "title": "Ata de Assembleia 2026/03",
                "version": "v1.0",
                "valid_from": "2026-03-10",
                "file_uri": "/storage/seed/ata_2026_03.pdf",
            },
            {
                "doc_type": "incorporation_proof",
                "title": "Comprovante CNPJ + Inscricao Estadual",
                "version": "v1.0",
                "valid_from": "2024-01-20",
                "file_uri": "/storage/seed/cnpj_proof.pdf",
            },
        ]
        doc_ids: list[int] = []
        for d in docs_to_seed:
            cur.execute(
                """
                SELECT id FROM institutional_documents
                WHERE tenant_id = %s AND document_type = %s AND version = %s
                LIMIT 1
                """,
                (TENANT_ID, d["doc_type"], d["version"]),
            )
            existing = cur.fetchone()
            if existing:
                doc_ids.append(existing["id"])
                _ok(f"institutional_documents: '{d['title']}' ja existe (id={existing['id']})")
                continue
            cur.execute(
                """
                INSERT INTO institutional_documents (
                  tenant_id, document_type, title, version, file_uri,
                  file_hash, valid_from, is_active, uploaded_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s)
                RETURNING id
                """,
                (
                    TENANT_ID, d["doc_type"], d["title"], d["version"],
                    d["file_uri"],
                    "0" * 64,  # placeholder de SHA-256 (64 chars hex)
                    d["valid_from"], admin_id,
                ),
            )
            new_id = cur.fetchone()["id"]
            doc_ids.append(new_id)
            _ok(f"institutional_documents: '{d['title']}' criado (id={new_id})")

        out["doc_ids"] = doc_ids

        # 1.3 statute_document_id na associations (aponta para o estatuto)
        if doc_ids:
            cur.execute(
                "UPDATE associations SET statute_document_id = %s WHERE tenant_id = %s",
                (doc_ids[0], TENANT_ID),
            )

        # 1.4 technical_responsibles — 1 medico responsavel + 1 farmaceutico
        rts_to_seed = [
            {
                "full_name": "Dr. Felipe Andrade",
                "council": "CRM",
                "council_number": "12345",
                "council_state": "SP",
                "habilitation_valid_until": "2027-12-31",
                "user_id": _resolve_user("medico"),
            },
            {
                "full_name": "Dra. Marina Ferreira",
                "council": "CRF",
                "council_number": "8721",
                "council_state": "SP",
                "habilitation_valid_until": "2027-06-30",
                "user_id": None,
            },
        ]
        for rt in rts_to_seed:
            cur.execute(
                """
                SELECT id FROM technical_responsibles
                WHERE professional_council = %s
                  AND council_number = %s
                  AND council_state = %s
                """,
                (rt["council"], rt["council_number"], rt["council_state"]),
            )
            existing = cur.fetchone()
            if existing:
                _ok(f"technical_responsibles: {rt['council']}/{rt['council_state']} {rt['council_number']} ja existe (id={existing['id']})")
                continue
            cur.execute(
                """
                INSERT INTO technical_responsibles (
                  tenant_id, user_id, full_name,
                  professional_council, council_number, council_state,
                  habilitation_valid_until, document_ids, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
                """,
                (
                    TENANT_ID, rt["user_id"], rt["full_name"],
                    rt["council"], rt["council_number"], rt["council_state"],
                    rt["habilitation_valid_until"], [],
                ),
            )
            new_id = cur.fetchone()["id"]
            _ok(f"technical_responsibles: {rt['full_name']} ({rt['council']}) criado (id={new_id})")

        conn.commit()
    return out


# ============================================================================
# 2. association_members (F2 — vincula patients ao tenant)
# ============================================================================


def seed_members() -> list[int]:
    """Cria 5 members vinculando os primeiros 5 patients do clinic 1."""
    _section("2. Association Members (F2)")
    member_ids: list[int] = []
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            "SELECT id, name FROM patients WHERE clinic_id = %s "
            "ORDER BY id LIMIT 5",
            (CLINIC_ID,),
        )
        patients = cur.fetchall()
        if not patients:
            _ok("Sem patients no clinic 1 — rode seed_comprehensive primeiro.")
            return []

        for idx, p in enumerate(patients, start=1):
            mb_number = f"MB-2026-{idx:04d}"
            cur.execute(
                "SELECT id FROM association_members "
                "WHERE tenant_id = %s AND membership_number = %s",
                (TENANT_ID, mb_number),
            )
            existing = cur.fetchone()
            if existing:
                member_ids.append(existing["id"])
                _ok(f"member {mb_number} ja existe (id={existing['id']}, patient='{p['name']}')")
                continue

            joined = (_now() - timedelta(days=180 - idx * 10)).date()
            cur.execute(
                """
                INSERT INTO association_members (
                  tenant_id, patient_id, membership_number,
                  membership_status, joined_at
                )
                VALUES (%s, %s, %s, 'active', %s)
                RETURNING id
                """,
                (TENANT_ID, p["id"], mb_number, joined),
            )
            new_id = cur.fetchone()["id"]
            member_ids.append(new_id)
            _ok(f"member {mb_number} criado (id={new_id}, patient='{p['name']}')")

        # Atualiza members_count em associations
        cur.execute(
            "UPDATE associations SET members_count = "
            "(SELECT COUNT(*) FROM association_members "
            " WHERE tenant_id = %s AND membership_status = 'active') "
            "WHERE tenant_id = %s",
            (TENANT_ID, TENANT_ID),
        )

        conn.commit()
    return member_ids


# ============================================================================
# 3. seed_sandbox_defaults (F6.3 — chama a funcao opt-in para riscos+SOPs)
# ============================================================================


def seed_sandbox_defaults_invoke() -> None:
    """Chama a funcao SQL `seed_sandbox_defaults(tenant_id)` da migration 037."""
    _section("3. Sandbox Defaults (F6.3) — riscos sanitarios + SOPs")
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            "SELECT object_type, inserted FROM seed_sandbox_defaults(%s)",
            (TENANT_ID,),
        )
        rows = cur.fetchall()
        for r in rows:
            _ok(f"{r['object_type']}: {r['inserted']} novos registros")
        conn.commit()


# ============================================================================
# 4. sandbox_projects + protocols + indicators + values (F3.2)
# ============================================================================


def seed_sandbox_project() -> dict:
    """Cria 1 projeto sandbox 'active' com protocolo vigente, 3 indicadores
    mandatorios e 90 dias de telemetria."""
    _section("4. Sandbox Project + Protocol + Indicators + Values (F3.2)")
    out: dict = {}
    with db_cursor(dictionary=True) as (conn, cur):
        # 4.1 sandbox_project — projeto principal de teste
        cur.execute(
            "SELECT id FROM sandbox_projects "
            "WHERE tenant_id = %s AND project_code = %s",
            (TENANT_ID, "PROJ-SEED-001"),
        )
        existing = cur.fetchone()
        if existing:
            project_id = existing["id"]
            _ok(f"sandbox_project PROJ-SEED-001 ja existe (id={project_id})")
        else:
            cur.execute(
                """
                INSERT INTO sandbox_projects (
                  tenant_id, project_code, title, status,
                  submitted_at, approved_at, started_at,
                  anvisa_reference
                )
                VALUES (%s, 'PROJ-SEED-001',
                        'Estudo Observacional de Cannabis Medicinal — SEED',
                        'active',
                        %s, %s, %s, 'ANVISA-SANDBOX-2026-001')
                RETURNING id
                """,
                (TENANT_ID, _days_ago(120), _days_ago(100), _days_ago(90)),
            )
            project_id = cur.fetchone()["id"]
            _ok(f"sandbox_project PROJ-SEED-001 criado (id={project_id}, status=active)")
        out["project_id"] = project_id

        # 4.2 sandbox_protocols — 1 protocolo vigente (effective_until=NULL)
        cur.execute(
            "SELECT id FROM sandbox_protocols "
            "WHERE project_id = %s AND protocol_version = 'v1.0'",
            (project_id,),
        )
        proto_existing = cur.fetchone()
        if not proto_existing:
            empty = json.dumps({})
            scope = json.dumps({
                "indication": "Dor cronica nao oncologica",
                "population": "Adultos 18-75 anos",
                "interventions": ["CBD 200mg/dia oral", "CBD:THC 20:1"],
            })
            norms = json.dumps([
                "RDC 327/2019",
                "RDC 660/2022",
                "RDC 1014/2026 — Sandbox Regulatorio",
            ])
            monitoring = json.dumps({
                "endpoints": ["pain_level (0-10)", "sleep_quality"],
                "schedule": "D+3, D+7, D+15, mensal",
                "alerts": ["severity >= severe → notify ANVISA"],
            })
            discontinuity = json.dumps({
                "criteria": ["evento adverso grave", "perda de eficacia"],
                "wash_out": "30 dias",
            })
            cur.execute(
                """
                INSERT INTO sandbox_protocols (
                  project_id, protocol_version,
                  scope, applicable_norms, modulated_norms,
                  monitoring_parameters, discontinuity_plan,
                  quality_requirements, data_sharing_obligations,
                  effective_from, effective_until
                )
                VALUES (%s, 'v1.0', %s::jsonb, %s::jsonb, %s::jsonb,
                        %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                        %s, NULL)
                RETURNING id
                """,
                (project_id, scope, norms, empty,
                 monitoring, discontinuity, empty, empty,
                 _days_ago(90)),
            )
            proto_id = cur.fetchone()["id"]
            _ok(f"sandbox_protocol v1.0 criado (id={proto_id}, vigente)")
        else:
            _ok(f"sandbox_protocol v1.0 ja existe (id={proto_existing['id']})")

        # 4.3 sandbox_indicators — 3 mandatorios (alvos diferentes para
        # exercitar on_target=True/False na view).
        indicators_seed = [
            {
                "code": "IDX-PAIN-REDUCTION",
                "name": "Reducao media de dor (D+30 vs baseline)",
                "formula": "AVG(D30 - baseline)",
                "unit": "pontos (0-10)",
                "target": 3.0,
                "freq": "monthly",
            },
            {
                "code": "IDX-RESPONSE-RATE",
                "name": "Taxa de resposta a follow-ups",
                "formula": "responded / sent",
                "unit": "fracao (0-1)",
                "target": 0.7,
                "freq": "monthly",
            },
            {
                "code": "IDX-AE-INCIDENCE",
                "name": "Incidencia de eventos adversos graves",
                "formula": "severe+life_threat+fatal / total_pacientes",
                "unit": "fracao (0-1)",
                "target": 0.05,
                "freq": "monthly",
            },
        ]
        indicator_ids: dict[str, int] = {}
        for ind in indicators_seed:
            cur.execute(
                "SELECT id FROM sandbox_indicators "
                "WHERE project_id = %s AND indicator_code = %s",
                (project_id, ind["code"]),
            )
            ex = cur.fetchone()
            if ex:
                indicator_ids[ind["code"]] = ex["id"]
                _ok(f"indicator {ind['code']} ja existe (id={ex['id']})")
                continue
            cur.execute(
                """
                INSERT INTO sandbox_indicators (
                  project_id, indicator_code, indicator_name,
                  calculation_formula, unit, target_value,
                  reporting_frequency, is_mandatory
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
                """,
                (project_id, ind["code"], ind["name"],
                 ind["formula"], ind["unit"], ind["target"], ind["freq"]),
            )
            new_id = cur.fetchone()["id"]
            indicator_ids[ind["code"]] = new_id
            _ok(f"indicator {ind['code']} criado (id={new_id}, target={ind['target']})")

        out["indicator_ids"] = indicator_ids

        # 4.4 sandbox_indicator_values — 3 meses de telemetria por indicador.
        # Valores escolhidos para mix de on_target=True/False na view (5%
        # de tolerancia).
        values_plan = {
            "IDX-PAIN-REDUCTION": [
                # target=3.0 → on_target = abs(latest-3)/3 <= 0.05 → 2.85..3.15
                ("M-3", 1.5),  # off-target
                ("M-2", 2.4),  # off-target
                ("M-1", 3.05),  # ON-TARGET (1.6% off)
            ],
            "IDX-RESPONSE-RATE": [
                # target=0.7 → on_target = 0.665..0.735
                ("M-3", 0.55),
                ("M-2", 0.62),
                ("M-1", 0.71),  # ON-TARGET (1.4% off)
            ],
            "IDX-AE-INCIDENCE": [
                # target=0.05 → on_target = 0.0475..0.0525
                ("M-3", 0.08),  # off-target (alta)
                ("M-2", 0.06),
                ("M-1", 0.07),  # off-target (40% off)
            ],
        }
        for code, points in values_plan.items():
            ind_id = indicator_ids.get(code)
            if not ind_id:
                continue
            for label, value in points:
                # period: M-3 = 90-60 dias atras; M-2 = 60-30; M-1 = 30-0
                month_offset = int(label.split("-")[1])
                period_start = _days_ago(month_offset * 30)
                period_end = _days_ago((month_offset - 1) * 30)
                # Idempotencia por label dentro de calculation_details
                # (period_start muda em segundos a cada run via _days_ago).
                cur.execute(
                    "SELECT id FROM sandbox_indicator_values "
                    "WHERE indicator_id = %s "
                    "  AND calculation_details->>'label' = %s",
                    (ind_id, label),
                )
                if cur.fetchone():
                    continue
                cur.execute(
                    """
                    INSERT INTO sandbox_indicator_values (
                      indicator_id, period_start, period_end,
                      calculated_value, calculation_details
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (ind_id, period_start, period_end, value,
                     json.dumps({"label": label, "method": "seed_synthetic"})),
                )
            _ok(f"  values para {code}: 3 periodos inseridos")

        conn.commit()
    return out


# ============================================================================
# 5. adverse_events + pharmacovigilance_notifications (F3.1/F3.3+)
# ============================================================================


def seed_pharmacovigilance(member_ids: list[int]) -> dict:
    """Cria 6 eventos adversos (severidades mistas), 2 com triagem IA
    persistida, 2 com notificacao registrada."""
    _section("5. Pharmacovigilance — adverse_events + notifications (F3)")
    out: dict = {"event_ids": []}
    if not member_ids:
        _ok("Sem members — pulando pharmacovigilance.")
        return out

    events_seed = [
        # (description, severity, reported_via, days_ago, member_idx, notes)
        (
            "[SEED] Paciente relatou sonolencia diurna leve apos primeira dose.",
            "mild", "whatsapp", 25, 0, None,
        ),
        (
            "[SEED] Tontura ao levantar nos primeiros 3 dias de uso.",
            "mild", "phone", 18, 1, None,
        ),
        (
            "[SEED] Nausea moderada apos titulacao para 200mg/dia.",
            "moderate", "consultation", 12, 2, None,
        ),
        (
            "[SEED] Paciente foi internado apos crise convulsiva — 1 dia hospitalizado.",
            "severe", "consultation", 8, 3, "ESCALADO",
        ),
        (
            "[SEED] Paciente perdeu consciencia momentaneamente. Investigacao em andamento.",
            "severe", "phone", 5, 0, "ESCALADO",
        ),
        (
            "[SEED] Reacao alergica leve (rash cutaneo) — auto-limitada em 48h.",
            "mild", "web", 2, 4, None,
        ),
    ]

    with db_cursor(dictionary=True) as (conn, cur):
        for desc, sev, via, ago, m_idx, note in events_seed:
            # Idempotencia: descricao [SEED] e unica por evento
            cur.execute(
                "SELECT id FROM adverse_events "
                "WHERE tenant_id = %s AND description = %s",
                (TENANT_ID, desc),
            )
            ex = cur.fetchone()
            if ex:
                out["event_ids"].append(ex["id"])
                _ok(f"event '{desc[:50]}...' ja existe (id={ex['id']})")
                continue

            reported_at = _days_ago(ago)
            onset_at = reported_at - timedelta(hours=12)
            cur.execute(
                """
                INSERT INTO adverse_events (
                  tenant_id, member_id, reported_at, event_onset_at,
                  severity, description, reported_via
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (TENANT_ID, member_ids[m_idx], reported_at, onset_at,
                 sev, desc, via),
            )
            event_id = cur.fetchone()["id"]
            out["event_ids"].append(event_id)
            tag = f" [{note}]" if note else ""
            _ok(f"event criado (id={event_id}, sev={sev}{tag})")
        conn.commit()

    # 5.1 Triagem IA em 2 dos eventos severos (sem chamar a skill —
    # gravamos diretamente um payload realista para nao depender do
    # AgenteRegulatorio aqui).
    triage_targets = []
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(
            "SELECT id, severity FROM adverse_events "
            "WHERE tenant_id = %s AND description LIKE %s "
            "ORDER BY id",
            (TENANT_ID, "[SEED]%"),
        )
        for r in cur.fetchall():
            if r["severity"] in ("severe", "life_threatening", "fatal"):
                triage_targets.append(r["id"])

    medico_id = _resolve_user("medico")
    with db_cursor(dictionary=True) as (conn, cur):
        for ev_id in triage_targets[:2]:  # so os 2 primeiros severos
            payload = {
                "ok": True,
                "severity_reported": "severe",
                "severity_suggested": "life_threatening",
                "escalated": True,
                "notify_required": True,
                "red_flags": ["internado", "convulsao"],
                "model_version": "regulatorio-triage-v1-heuristic",
                "reasoning": "Escalado por hospitalizacao + crise convulsiva.",
            }
            cur.execute(
                """
                UPDATE adverse_events
                SET ai_triage_result = %s::jsonb,
                    triaged_by = %s,
                    updated_at = NOW()
                WHERE id = %s AND ai_triage_result IS NULL
                RETURNING id
                """,
                (json.dumps(payload), medico_id, ev_id),
            )
            if cur.fetchone():
                _ok(f"triage_result registrada no evento {ev_id}")
        conn.commit()

    # 5.2 pharmacovigilance_notifications em 2 eventos
    out["notification_ids"] = []
    with db_cursor(dictionary=True) as (conn, cur):
        for ev_id in triage_targets[:2]:
            cur.execute(
                "SELECT id FROM pharmacovigilance_notifications "
                "WHERE adverse_event_id = %s LIMIT 1",
                (ev_id,),
            )
            if cur.fetchone():
                _ok(f"notification para evento {ev_id} ja existe")
                continue
            cur.execute(
                """
                INSERT INTO pharmacovigilance_notifications (
                  adverse_event_id, notification_target, notified_at,
                  notification_reference, response_payload
                )
                VALUES (%s, 'internal_only', %s, %s, %s::jsonb)
                RETURNING id
                """,
                (ev_id, _now(), f"MOCK-SEED-{ev_id:08X}",
                 json.dumps({
                     "provider": "mock", "accepted": True,
                     "note": "Notificacao seed via mock client.",
                 })),
            )
            new_id = cur.fetchone()["id"]
            out["notification_ids"].append(new_id)
            _ok(f"notification criada (id={new_id}, evento={ev_id}, target=internal_only)")
        conn.commit()

    return out


# ============================================================================
# 6. Validacao final — counts por tabela
# ============================================================================


def print_summary() -> None:
    _section("Resumo final")
    queries = [
        ("tenants", "SELECT COUNT(*) AS n FROM tenants WHERE id = %s", (TENANT_ID,)),
        ("clinics", "SELECT COUNT(*) AS n FROM clinics WHERE id = %s", (CLINIC_ID,)),
        ("patients", "SELECT COUNT(*) AS n FROM patients WHERE clinic_id = %s", (CLINIC_ID,)),
        ("association_members", "SELECT COUNT(*) AS n FROM association_members WHERE tenant_id = %s", (TENANT_ID,)),
        ("institutional_documents", "SELECT COUNT(*) AS n FROM institutional_documents WHERE tenant_id = %s", (TENANT_ID,)),
        ("technical_responsibles", "SELECT COUNT(*) AS n FROM technical_responsibles WHERE tenant_id = %s", (TENANT_ID,)),
        ("sanitary_risks", "SELECT COUNT(*) AS n FROM sanitary_risks WHERE tenant_id = %s", (TENANT_ID,)),
        ("sops", "SELECT COUNT(*) AS n FROM sops WHERE tenant_id = %s", (TENANT_ID,)),
        ("sandbox_projects", "SELECT COUNT(*) AS n FROM sandbox_projects WHERE tenant_id = %s", (TENANT_ID,)),
        ("sandbox_indicators", "SELECT COUNT(*) AS n FROM sandbox_indicators si JOIN sandbox_projects sp ON sp.id = si.project_id WHERE sp.tenant_id = %s", (TENANT_ID,)),
        ("sandbox_indicator_values", "SELECT COUNT(*) AS n FROM sandbox_indicator_values siv JOIN sandbox_indicators si ON si.id = siv.indicator_id JOIN sandbox_projects sp ON sp.id = si.project_id WHERE sp.tenant_id = %s", (TENANT_ID,)),
        ("adverse_events", "SELECT COUNT(*) AS n FROM adverse_events WHERE tenant_id = %s", (TENANT_ID,)),
        ("pv_notifications", "SELECT COUNT(*) AS n FROM pharmacovigilance_notifications n JOIN adverse_events ae ON ae.id = n.adverse_event_id WHERE ae.tenant_id = %s", (TENANT_ID,)),
    ]
    with db_cursor(dictionary=True) as (_, cur):
        for label, sql, params in queries:
            cur.execute(sql, params)
            n = cur.fetchone()["n"]
            print(f"  {label:30s} {n:>5d}")


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    print("=" * 60)
    print(f"  SEED SCC — tenant_id={TENANT_ID}, clinic_id={CLINIC_ID}")
    print("=" * 60)

    admin_id = _resolve_user("admin")
    if admin_id is None:
        print("ERRO: usuario 'admin' nao encontrado. Rode seed_users.py primeiro.")
        sys.exit(1)

    seed_governance(admin_id)
    member_ids = seed_members()
    seed_sandbox_defaults_invoke()
    seed_sandbox_project()
    seed_pharmacovigilance(member_ids)
    print_summary()

    print("\n" + "=" * 60)
    print("  SEED SCC CONCLUIDO COM SUCESSO!")
    print("=" * 60)


if __name__ == "__main__":
    main()
