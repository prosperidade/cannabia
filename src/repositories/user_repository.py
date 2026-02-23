# src/repositories/user_repository.py
import bcrypt
from src.infra.database import db_cursor


def create_user(username: str, password: str, role: str = "Admin"):
    password_bytes = password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

    with db_cursor() as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (%s, %s, %s)
            """,
            (username, hashed.decode("utf-8"), role),
        )
        conn.commit()


def get_user_by_username(username: str):
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT * FROM users WHERE username = %s AND is_active = TRUE",
            (username,),
        )
        return cursor.fetchone()


def get_user_by_id(user_id: int):
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT * FROM users WHERE id = %s AND is_active = TRUE",
            (user_id,),
        )
        return cursor.fetchone()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )
