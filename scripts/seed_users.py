"""Seed script to create test users for development."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infra.database import db_cursor
from src.repositories.user_repository import create_user, get_user_by_username

USERS = [
    {"username": "admin", "password": "admin123", "role": "Admin"},
    {"username": "medico", "password": "medico123", "role": "Medico"},
    {"username": "atendente", "password": "atendente123", "role": "Atendente"},
    {"username": "paciente", "password": "paciente123", "role": "Paciente"},
]


def ensure_default_clinic():
    """Create the default clinic if it does not exist. Returns the clinic id."""
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT id FROM clinics WHERE slug = 'cannabia' LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f"  Clinica padrao ja existe (id={row['id']})")
            return row["id"]

        cursor.execute(
            """
            INSERT INTO clinics (name, slug, is_active)
            VALUES ('Clinica Cannabia', 'cannabia', TRUE)
            RETURNING id
            """,
        )
        clinic_id = cursor.fetchone()["id"]
        conn.commit()
        print(f"  Clinica padrao criada (id={clinic_id})")
        return clinic_id


def link_user_to_clinic(user_id: int, clinic_id: int, role: str):
    """Link a user to a clinic via user_clinics (idempotent)."""
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            "SELECT 1 FROM user_clinics WHERE user_id = %s AND clinic_id = %s",
            (user_id, clinic_id),
        )
        if cursor.fetchone():
            print(f"    -> Vinculo user_clinics ja existe (user_id={user_id}, clinic_id={clinic_id})")
            return

        cursor.execute(
            """
            INSERT INTO user_clinics (user_id, clinic_id, role, is_default)
            VALUES (%s, %s, %s, TRUE)
            ON CONFLICT (user_id, clinic_id) DO NOTHING
            """,
            (user_id, clinic_id, role),
        )
        conn.commit()
        print(f"    -> Vinculado a clinica {clinic_id} com role '{role}'")


def seed():
    clinic_id = ensure_default_clinic()

    for u in USERS:
        existing = get_user_by_username(u["username"])
        if existing:
            user_id = existing["id"]
            print(f"  Usuario '{u['username']}' ja existe (id={user_id})")
        else:
            create_user(u["username"], u["password"], u["role"])
            created = get_user_by_username(u["username"])
            user_id = created["id"] if created else None
            print(f"  Criado: {u['username']} ({u['role']}) id={user_id}")

        if user_id:
            # Map user role to clinic role
            clinic_role = "clinic_admin" if u["role"] == "Admin" else u["role"].lower()
            link_user_to_clinic(user_id, clinic_id, clinic_role)


if __name__ == "__main__":
    print("Criando usuarios de teste...")
    seed()
    print("Concluido!")
