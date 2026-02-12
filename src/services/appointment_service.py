from datetime import datetime

from src.repositories import appointment_repository


def create_appointment_from_form(patient_name, appointment_date):
    if not patient_name or not appointment_date:
        raise ValueError('Nome do paciente e data são obrigatórios.')

    try:
        dt = datetime.strptime(appointment_date, '%d/%m/%Y %H:%M')
    except ValueError as exc:
        raise ValueError('Formato de data inválido. Use dd/mm/yyyy HH:MM.') from exc

    appointment_repository.ensure_appointments_table()
    appointment_repository.create_appointment(patient_name, dt.strftime('%Y-%m-%d %H:%M:%S'))


def list_appointments():
    appointment_repository.ensure_appointments_table()
    return appointment_repository.list_appointments()
