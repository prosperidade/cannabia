# src/services/appointment_service.py
from datetime import datetime, timezone

from flask import g

from src.repositories import appointment_repository
from src.repositories.patient_repository import get_or_create_patient_by_name
from src.repositories.patient_timeline_repository import create_event


def create_appointment_from_form(patient_name: str, appointment_date: str) -> int:
    """
    Cria um agendamento a partir dos dados do formulário.
    Valida o formato de data. clinic_id vem automaticamente de g via repositório.
    """
    if not patient_name or not appointment_date:
        raise ValueError('Nome do paciente e data são obrigatórios.')

    try:
        dt = datetime.strptime(appointment_date, '%d/%m/%Y %H:%M')
    except ValueError as exc:
        raise ValueError('Formato de data inválido. Use dd/mm/yyyy HH:MM.') from exc

    return _create_appointment(patient_name, dt)


def create_appointment_from_api(patient_name: str, appointment_date: str) -> int:
    if not patient_name or not appointment_date:
        raise ValueError('Nome do paciente e data são obrigatórios.')

    try:
        normalized = appointment_date.strip().replace('Z', '+00:00')
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError('Formato de data inválido. Use ISO 8601.') from exc

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

    return _create_appointment(patient_name, dt)


def _create_appointment(patient_name: str, dt: datetime) -> int:
    clinic_id = getattr(g, 'clinic_id', None)
    if clinic_id is None:
        raise RuntimeError('clinic_id não encontrado no contexto da request')

    patient_id = get_or_create_patient_by_name(clinic_id, patient_name)
    appointment_id = appointment_repository.create_appointment(
        patient_id,
        dt.strftime('%Y-%m-%d %H:%M:%S'),
    )

    create_event(
        clinic_id=clinic_id,
        tenant_id=getattr(g, "tenant_id", None),
        patient_id=patient_id,
        event_type="appointment_created",
        journey_stage="agendamento_realizado",
        title="Agendamento criado",
        description=f"Consulta agendada para {dt.strftime('%d/%m/%Y às %H:%M')}.",
        source_type="appointment",
        source_id=appointment_id,
        metadata={
            "status": "Agendada",
            "appointment_date": dt.strftime('%d/%m/%Y %H:%M'),
        },
    )
    return appointment_id


def list_appointments(*, limit=None, offset: int = 0, include_total: bool = False):
    """Lista os agendamentos da clínica atual (clinic_id vem de g via repositório).

    Sem args -> retorna lista nua (compat).
    Com `limit` -> retorna dict paginado (Sprint 2 Track Page).
    """
    return appointment_repository.list_appointments(
        limit=limit, offset=offset, include_total=include_total
    )
