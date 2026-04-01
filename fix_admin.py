"""
fix_admin.py — Upsert seguro do usuário 'admin' no banco PostgreSQL do Render.

Uso:
    python fix_admin.py

Requer: DATABASE_URL no ambiente (ou .env na raiz do projeto).
"""

import os
import sys

import bcrypt
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ ERRO: DATABASE_URL não encontrada no ambiente.")
    sys.exit(1)

USERNAME = "admin"
PASSWORD = "admin123"
ROLE     = "Medico"
CLINIC_ID = 1

# ── 1. Gera o hash bcrypt ────────────────────────────────────────────────────
password_hash = bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
print(f"✅ Hash bcrypt gerado para '{USERNAME}'.")

# ── 2. Conecta ao PostgreSQL ─────────────────────────────────────────────────
try:
    conn = psycopg2.connect(DATABASE_URL)
    cur  = conn.cursor()
    print("✅ Conexão com o banco estabelecida.")
except Exception as e:
    print(f"❌ Falha ao conectar ao banco: {e}")
    sys.exit(1)

try:
    # ── 3. Upsert do usuário admin ───────────────────────────────────────────
    cur.execute(
        """
        INSERT INTO users (username, password_hash, role, is_active)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (username)
        DO UPDATE SET
            password_hash = EXCLUDED.password_hash,
            role          = EXCLUDED.role,
            is_active     = TRUE
        RETURNING id
        """,
        (USERNAME, password_hash, ROLE),
    )
    user_id = cur.fetchone()[0]
    print(f"✅ Usuário '{USERNAME}' upserted com ID={user_id}.")

    # ── 4. Garante o vínculo na user_clinics ─────────────────────────────────
    cur.execute(
        """
        INSERT INTO user_clinics (user_id, clinic_id, role, is_default)
        VALUES (%s, %s, 'clinic_admin', TRUE)
        ON CONFLICT (user_id, clinic_id)
        DO UPDATE SET
            role       = EXCLUDED.role,
            is_default = TRUE
        """,
        (user_id, CLINIC_ID),
    )
    print(f"✅ Vínculo user_clinics garantido: user_id={user_id} → clinic_id={CLINIC_ID}.")

    conn.commit()
    print("\n🎉 Script finalizado com sucesso!")
    print(f"   Login:  {USERNAME}")
    print(f"   Senha:  {PASSWORD}")

except Exception as e:
    conn.rollback()
    print(f"❌ Erro durante a operação: {e}")
    sys.exit(1)

finally:
    cur.close()
    conn.close()
