from src.infra.database import db_cursor


def ensure_appointments_table():
    with db_cursor() as (connection, cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                patient_name VARCHAR(100),
                appointment_date DATETIME NOT NULL,
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()


def create_appointment(patient_name, appointment_date, status="Agendada"):
    with db_cursor() as (connection, cursor):
        cursor.execute(
            "INSERT INTO appointments (patient_name, appointment_date, status) VALUES (%s, %s, %s)",
            (patient_name, appointment_date, status),
        )
        connection.commit()


def list_appointments():
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute("SELECT * FROM appointments ORDER BY appointment_date DESC")
        return cursor.fetchall()
