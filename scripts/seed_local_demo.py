from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.infra.database import db_cursor
from src.repositories.medical_record_repository import upsert_consultation_entry
from src.repositories.patient_timeline_repository import create_event

load_dotenv(".env")

CLINIC_ID = 1
TENANT_ID = 1
ADMIN_ID = 1
ADMIN_NAME = "admin"
BASE_TIME = datetime(2026, 4, 2, 9, 0, 0)

MESSAGE_SEED = [
    ("5511990001111", "Maria Oliveira", "Bom dia, senti melhora no sono.", BASE_TIME - timedelta(hours=2)),
    ("5511990001111", "Maria Oliveira", "Quero confirmar a consulta de sexta.", BASE_TIME - timedelta(hours=26)),
    ("5511990002222", "Joao Santos", "Ainda estou com dor neuropatica no fim do dia.", BASE_TIME - timedelta(hours=5)),
    ("5511990002222", "Joao Santos", "Enviei meus exames agora.", BASE_TIME - timedelta(hours=30)),
    ("5511990003333", "Clara Menezes", "Preciso remarcar meu retorno.", BASE_TIME - timedelta(hours=8)),
    ("5511990003333", "Clara Menezes", "A receita chegou por email?", BASE_TIME - timedelta(hours=54)),
    ("5511990001111", "Maria Oliveira", "Posso manter a dose atual por mais uma semana?", BASE_TIME - timedelta(hours=78)),
    ("5511990002222", "Joao Santos", "Obrigado pelo atendimento.", BASE_TIME - timedelta(hours=102)),
]

APPOINTMENT_SEED = [
    ("Maria Oliveira", datetime(2026, 4, 4, 14, 0, 0), "Agendada"),
    ("Joao Santos", datetime(2026, 4, 7, 10, 30, 0), "Confirmada"),
    ("Clara Menezes", datetime(2026, 4, 9, 16, 0, 0), "Agendada"),
]


def ensure_patient(name: str, email: str, phone: str) -> int:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            SELECT id
            FROM patients
            WHERE clinic_id = %s
              AND name = %s
            LIMIT 1
            """,
            (CLINIC_ID, name),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                """
                UPDATE patients
                SET email = COALESCE(NULLIF(email, ''), %s),
                    phone = COALESCE(NULLIF(phone, ''), %s)
                WHERE id = %s
                """,
                (email, phone, row["id"]),
            )
            conn.commit()
            return row["id"]

        cursor.execute(
            """
            INSERT INTO patients (clinic_id, name, email, phone)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (CLINIC_ID, name, email, phone),
        )
        patient_id = cursor.fetchone()["id"]
        conn.commit()
        return patient_id


def ensure_message(sender: str, contact_name: str, message_text: str, timestamp: str) -> None:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            SELECT id
            FROM incoming_messages
            WHERE clinic_id = %s
              AND sender = %s
              AND timestamp = %s
              AND COALESCE(message_text, '') = %s
            LIMIT 1
            """,
            (CLINIC_ID, sender, timestamp, message_text),
        )
        if cursor.fetchone():
            return

        cursor.execute(
            """
            INSERT INTO incoming_messages (clinic_id, sender, contact_name, message_text, timestamp)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (CLINIC_ID, sender, contact_name, message_text, timestamp),
        )
        conn.commit()


def cleanup_demo_messages() -> None:
    with db_cursor() as (conn, cursor):
        cursor.executemany(
            """
            DELETE FROM incoming_messages
            WHERE clinic_id = %s
              AND sender = %s
              AND message_text = %s
            """,
            [
                (CLINIC_ID, sender, message_text)
                for sender, _contact_name, message_text, _timestamp in MESSAGE_SEED
            ],
        )
        conn.commit()


def ensure_appointment(patient_id: int, appointment_date: str, status: str) -> None:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            SELECT id
            FROM appointments
            WHERE clinic_id = %s
              AND patient_id = %s
              AND appointment_date = %s
            LIMIT 1
            """,
            (CLINIC_ID, patient_id, appointment_date),
        )
        if cursor.fetchone():
            return

        cursor.execute(
            """
            INSERT INTO appointments (clinic_id, patient_id, appointment_date, status)
            VALUES (%s, %s, %s, %s)
            """,
            (CLINIC_ID, patient_id, appointment_date, status),
        )
        conn.commit()


def cleanup_demo_appointments(patient_ids: list[int]) -> None:
    with db_cursor() as (conn, cursor):
        cursor.execute(
            """
            DELETE FROM appointments
            WHERE clinic_id = %s
              AND patient_id = ANY(%s)
            """,
            (CLINIC_ID, patient_ids),
        )
        conn.commit()


def ensure_report(
    patient_id: int,
    patient_name: str,
    phone: str,
    status: str,
    created_at: str,
    anamnesis_data: dict,
    clinical_analysis: dict,
    treatment_plan: dict,
    scientific_report: dict,
    rag_chunks_used: int,
    report_model: str,
) -> int:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            SELECT id
            FROM anamnesis_reports
            WHERE clinic_id = %s
              AND patient_id = %s
              AND status = %s
              AND phone = %s
            LIMIT 1
            """,
            (CLINIC_ID, patient_id, status, phone),
        )
        row = cursor.fetchone()
        if row:
            return row["id"]

        cursor.execute(
            """
            INSERT INTO anamnesis_reports (
                clinic_id,
                patient_id,
                patient_name,
                phone,
                anamnesis_data,
                clinical_analysis,
                treatment_plan,
                scientific_report,
                rag_chunks_used,
                report_model,
                status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                CLINIC_ID,
                patient_id,
                patient_name,
                phone,
                json.dumps(anamnesis_data, ensure_ascii=False),
                json.dumps(clinical_analysis, ensure_ascii=False),
                json.dumps(treatment_plan, ensure_ascii=False),
                json.dumps(scientific_report, ensure_ascii=False),
                rag_chunks_used,
                report_model,
                status,
                created_at,
                created_at,
            ),
        )
        report_id = cursor.fetchone()["id"]
        conn.commit()
        return report_id


def ensure_ai_log(
    patient_id: int,
    request_id: str,
    endpoint: str,
    status: str,
    model: str,
    total_tokens: int,
    total_time_ms: int,
    estimated_cost_usd: float,
    created_at: str,
    error_message: str | None = None,
) -> None:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            SELECT id
            FROM ai_audit_logs
            WHERE clinic_id = %s
              AND request_id = %s
            LIMIT 1
            """,
            (CLINIC_ID, request_id),
        )
        if cursor.fetchone():
            return

        input_tokens = max(total_tokens // 2, 1)
        output_tokens = max(total_tokens - input_tokens, 1)

        cursor.execute(
            """
            INSERT INTO ai_audit_logs (
                patient_id,
                clinic_id,
                request_id,
                user_id,
                endpoint,
                input_payload,
                output_payload,
                status,
                error_message,
                model,
                prompt_version,
                prompt_hash,
                input_tokens,
                output_tokens,
                total_tokens,
                clinical_time_ms,
                treatment_time_ms,
                report_time_ms,
                total_time_ms,
                created_at,
                estimated_cost_usd
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                patient_id,
                CLINIC_ID,
                request_id,
                str(ADMIN_ID),
                endpoint,
                json.dumps({"seed": True}, ensure_ascii=False),
                json.dumps({"status": status}, ensure_ascii=False),
                status,
                error_message,
                model,
                "v1-demo",
                "seed-demo-hash",
                input_tokens,
                output_tokens,
                total_tokens,
                max(total_time_ms // 3, 1),
                max(total_time_ms // 3, 1),
                max(total_time_ms // 3, 1),
                total_time_ms,
                created_at,
                estimated_cost_usd,
            ),
        )
        conn.commit()


def ensure_timeline_event(
    patient_id: int,
    event_type: str,
    title: str,
    description: str,
    source_type: str,
    source_id: int,
    journey_stage: str,
    event_time: datetime,
    metadata: dict,
) -> None:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id
            FROM patient_timeline_events
            WHERE clinic_id = %s
              AND patient_id = %s
              AND event_type = %s
              AND source_type = %s
              AND source_id = %s
            LIMIT 1
            """,
            (CLINIC_ID, patient_id, event_type, source_type, source_id),
        )
        if cursor.fetchone():
            return

    create_event(
        clinic_id=CLINIC_ID,
        tenant_id=TENANT_ID,
        patient_id=patient_id,
        event_type=event_type,
        journey_stage=journey_stage,
        title=title,
        description=description,
        source_type=source_type,
        source_id=source_id,
        event_time=event_time,
        metadata=metadata,
    )


def build_demo_data() -> None:
    now = BASE_TIME

    maria_id = ensure_patient("Maria Oliveira", "maria@demo.local", "5511990001111")
    joao_id = ensure_patient("Joao Santos", "joao@demo.local", "5511990002222")
    clara_id = ensure_patient("Clara Menezes", "clara@demo.local", "5511990003333")

    cleanup_demo_messages()
    for sender, name, text, timestamp in MESSAGE_SEED:
        ensure_message(
            sender=sender,
            contact_name=name,
            message_text=text,
            timestamp=timestamp.isoformat(),
        )

    cleanup_demo_appointments([maria_id, joao_id, clara_id])
    appointment_patient_ids = {
        "Maria Oliveira": maria_id,
        "Joao Santos": joao_id,
        "Clara Menezes": clara_id,
    }
    for patient_name, appointment_date, status in APPOINTMENT_SEED:
        ensure_appointment(
            appointment_patient_ids[patient_name],
            appointment_date.strftime("%Y-%m-%d %H:%M:%S"),
            status,
        )

    maria_report_id = ensure_report(
        patient_id=maria_id,
        patient_name="Maria Oliveira",
        phone="5511990001111",
        status="revisado",
        created_at=(now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
        anamnesis_data={
            "chief_complaint": "Insônia de manutenção",
            "medical_history": "Ansiedade crônica e dor miofascial",
            "current_medication": "Escitalopram 10mg",
        },
        clinical_analysis={
            "risk_level": "baixo",
            "probable_conditions": ["insonia", "ansiedade"],
            "recommended_exams": ["hemograma", "vitamina d"],
        },
        treatment_plan={
            "suggested_dosage": "CBD 20mg à noite por 14 dias",
            "monitoring_plan": "Reavaliar qualidade do sono e sedação em 30 dias",
        },
        scientific_report={
            "summary": "Evidência moderada para melhora subjetiva do sono em uso supervisionado.",
        },
        rag_chunks_used=6,
        report_model="gpt-4o-mini",
    )

    joao_report_id = ensure_report(
        patient_id=joao_id,
        patient_name="Joao Santos",
        phone="5511990002222",
        status="pendente",
        created_at=(now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        anamnesis_data={
            "chief_complaint": "Dor neuropática",
            "medical_history": "Hérnia de disco lombar",
            "current_medication": "Pregabalina 75mg",
        },
        clinical_analysis={
            "risk_level": "moderado",
            "probable_conditions": ["dor neuropatica", "inflamacao cronica"],
            "recommended_exams": ["ressonancia lombar"],
        },
        treatment_plan={
            "suggested_dosage": "CBD/THC 1:1 à noite, iniciar dose baixa",
            "monitoring_plan": "Acompanhar sedação, apetite e intensidade de dor",
        },
        scientific_report={
            "summary": "Literatura sugere benefício potencial em casos refratários de dor neuropática.",
        },
        rag_chunks_used=4,
        report_model="gpt-4o-mini",
    )

    ensure_timeline_event(
        patient_id=maria_id,
        event_type="anamnesis_completed",
        journey_stage="anamnese_concluida",
        title="Anamnese assistida concluida",
        description="Fluxo inicial finalizado com geração de relatório clínico.",
        source_type="anamnesis_report",
        source_id=maria_report_id,
        event_time=now - timedelta(days=3),
        metadata={"report_model": "gpt-4o-mini"},
    )
    ensure_timeline_event(
        patient_id=maria_id,
        event_type="anamnesis_reviewed",
        journey_stage="caso_revisado",
        title="Atendimento revisado pelo medico",
        description="Relatório revisado e encaminhado ao prontuário longitudinal.",
        source_type="anamnesis_report",
        source_id=maria_report_id,
        event_time=now - timedelta(days=2),
        metadata={"status": "revisado"},
    )
    ensure_timeline_event(
        patient_id=joao_id,
        event_type="anamnesis_completed",
        journey_stage="anamnese_concluida",
        title="Anamnese assistida concluida",
        description="Caso aguardando validação clínica.",
        source_type="anamnesis_report",
        source_id=joao_report_id,
        event_time=now - timedelta(days=1),
        metadata={"status": "pendente"},
    )

    upsert_consultation_entry(
        clinic_id=CLINIC_ID,
        tenant_id=TENANT_ID,
        patient_id=maria_id,
        author_user_id=ADMIN_ID,
        author_name=ADMIN_NAME,
        source_report_id=maria_report_id,
        consultation_status="consulta_realizada",
        medical_observations="Paciente refere melhora parcial do sono e redução da ansiedade noturna.",
        clinical_assessment="Quadro estável, sem sinais de piora clínica.",
        conduct="Manter CBD noturno e revisar ajuste em 30 dias.",
        requested_exams=["hemograma", "vitamina d"],
        follow_up_plan="Revisão ambulatorial em 30 dias com diário do sono.",
    )

    ensure_ai_log(
        patient_id=maria_id,
        request_id="seed-ai-001",
        endpoint="/ai/test",
        status="success",
        model="gpt-4o-mini",
        total_tokens=1820,
        total_time_ms=920,
        estimated_cost_usd=0.0312,
        created_at=(now - timedelta(days=2, hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    ensure_ai_log(
        patient_id=joao_id,
        request_id="seed-ai-002",
        endpoint="/ai/test",
        status="error",
        model="gpt-4o-mini",
        total_tokens=1320,
        total_time_ms=1105,
        estimated_cost_usd=0.0258,
        created_at=(now - timedelta(days=1, hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
        error_message="Timeout controlado no estágio de relatório científico.",
    )
    ensure_ai_log(
        patient_id=clara_id,
        request_id="seed-ai-003",
        endpoint="/ai/test",
        status="security_blocked",
        model="gpt-4o-mini",
        total_tokens=240,
        total_time_ms=210,
        estimated_cost_usd=0.0021,
        created_at=(now - timedelta(hours=18)).strftime("%Y-%m-%d %H:%M:%S"),
        error_message="Payload bloqueado por validação de segurança.",
    )
    ensure_ai_log(
        patient_id=maria_id,
        request_id="seed-ai-004",
        endpoint="/ai/test",
        status="success",
        model="gpt-4o-mini",
        total_tokens=2050,
        total_time_ms=840,
        estimated_cost_usd=0.0349,
        created_at=(now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
    )


def summary() -> dict:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM patients WHERE clinic_id = %s) AS patients,
                (SELECT COUNT(*) FROM incoming_messages WHERE clinic_id = %s) AS messages,
                (SELECT COUNT(*) FROM appointments WHERE clinic_id = %s) AS appointments,
                (SELECT COUNT(*) FROM anamnesis_reports WHERE clinic_id = %s) AS reports,
                (SELECT COUNT(*) FROM ai_audit_logs WHERE clinic_id = %s) AS ai_logs
            """,
            (CLINIC_ID, CLINIC_ID, CLINIC_ID, CLINIC_ID, CLINIC_ID),
        )
        return cursor.fetchone()


if __name__ == "__main__":
    build_demo_data()
    stats = summary()
    print(
        "Seed local concluído:",
        json.dumps(stats, ensure_ascii=False),
    )
