"""Seed script to create test users for development.

Cria os usuarios dev representativos do app unificado da clinica:
  - admin       (Admin global, super admin da plataforma)
  - dono        (Medico + is_clinic_admin=TRUE — medico-dono da clinica)
  - medico      (Medico assalariado, sem is_clinic_admin)
  - recepcao    (Recepcao — operacao do dia)
  - financeiro  (Financeiro — modulos financeiros)
  - admin_clinica (AdminClinica nao-medico — gestor sem perfil clinico)
  - paciente    (Paciente)

Idempotente: rodar 2x nao duplica usuarios. Atualiza is_clinic_admin
e renomeia o user 'atendente' (legado) para a senha nova se ja
existir como Recepcao.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infra.database import db_cursor
from src.repositories.user_repository import create_user, get_user_by_username


# Users dev. Cada um representa um perfil de uso real.
# A senha tambem serve como exemplo de credencial — em prod, password real.
USERS = [
    # username, password, role, is_clinic_admin, clinic_role (no user_clinics)
    {"username": "admin",         "password": "admin123",         "role": "Admin",        "is_clinic_admin": False, "clinic_role": "clinic_admin"},
    {"username": "dono",          "password": "dono123",          "role": "Medico",       "is_clinic_admin": True,  "clinic_role": "clinic_admin"},
    {"username": "medico",        "password": "medico123",        "role": "Medico",       "is_clinic_admin": False, "clinic_role": "medico"},
    {"username": "recepcao",      "password": "recepcao123",      "role": "Recepcao",     "is_clinic_admin": False, "clinic_role": "recepcao"},
    {"username": "financeiro",    "password": "financeiro123",    "role": "Financeiro",   "is_clinic_admin": False, "clinic_role": "financeiro"},
    {"username": "admin_clinica", "password": "adminclinica123",  "role": "AdminClinica", "is_clinic_admin": True,  "clinic_role": "clinic_admin"},
    {"username": "paciente",      "password": "paciente123",      "role": "Paciente",     "is_clinic_admin": False, "clinic_role": "paciente"},
]

# Nome legado mantido como alias no DB (apos renomear Atendente -> Recepcao
# em migration 038, o user 'atendente' ainda existe com role 'Recepcao').
LEGACY_USERNAME_ALIASES: dict[str, str] = {
    "atendente": "recepcao",  # so usado para detectar o legado e nao recriar
}


def ensure_default_clinic() -> int:
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


def link_user_to_clinic(user_id: int, clinic_id: int, role: str) -> None:
    """Link a user to a clinic via user_clinics (idempotent, atualiza role
    se ja existe com role diferente)."""
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            "SELECT role FROM user_clinics "
            "WHERE user_id = %s AND clinic_id = %s",
            (user_id, clinic_id),
        )
        existing = cursor.fetchone()
        if existing:
            if existing["role"] != role:
                cursor.execute(
                    "UPDATE user_clinics SET role = %s "
                    "WHERE user_id = %s AND clinic_id = %s",
                    (role, user_id, clinic_id),
                )
                conn.commit()
                print(
                    f"    -> Vinculo user_clinics atualizado "
                    f"({existing['role']} -> {role})"
                )
            else:
                print(
                    f"    -> Vinculo user_clinics ja existe "
                    f"(user_id={user_id}, clinic_id={clinic_id}, role={role})"
                )
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


def update_user_role_and_admin_flag(
    user_id: int, role: str, is_clinic_admin: bool
) -> None:
    """Garante que o user existente tem o role e a flag corretos.
    Util quando rerodamos o seed ou quando migration 038 renomeou
    Atendente sem ajustar a flag."""
    with db_cursor() as (conn, cursor):
        cursor.execute(
            "UPDATE users SET role = %s, is_clinic_admin = %s "
            "WHERE id = %s AND (role <> %s OR is_clinic_admin <> %s)",
            (role, is_clinic_admin, user_id, role, is_clinic_admin),
        )
        if cursor.rowcount > 0:
            print(
                f"    -> Ajustado users.role={role}, "
                f"is_clinic_admin={is_clinic_admin}"
            )
        conn.commit()


def seed() -> None:
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
            if user_id:
                print(f"  Criado: {u['username']} ({u['role']}) id={user_id}")

        if user_id:
            update_user_role_and_admin_flag(
                user_id, u["role"], u["is_clinic_admin"]
            )
            link_user_to_clinic(user_id, clinic_id, u["clinic_role"])


if __name__ == "__main__":
    print("Criando usuarios de teste...")
    seed()
    print("Concluido!")
