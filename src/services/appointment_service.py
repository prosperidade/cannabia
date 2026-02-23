# src/services/appointment_service.py
from datetime import datetime

from src.repositories import appointment_repository
from src.repositories.patient_repository import get_or_create_patient_by_name


def create_appointment_from_form(patient_name: str, appointment_date: str) -> None:
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

    # Garante que o paciente existe (get_or_create) — clinic_id vem de g
    from flask import g
    clinic_id = getattr(g, 'clinic_id', None)
    if clinic_id is None:
        raise RuntimeError('clinic_id não encontrado no contexto da request')

    patient_id = get_or_create_patient_by_name(clinic_id, patient_name)
    appointment_repository.create_appointment(patient_id, dt.strftime('%Y-%m-%d %H:%M:%S'))


def list_appointments() -> list:
    """Lista os agendamentos da clínica atual (clinic_id vem de g via repositório)."""
    return appointment_repository.list_appointments()
