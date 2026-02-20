import sys
from getpass import getpass

from src.repositories.user_repository import create_user

def main():
    print("=== Criar Usuário Admin ===")

    username = input("Username: ").strip()
    password = getpass("Password: ")
    role = "Admin"

    if not username or not password:
        print("Username e senha são obrigatórios.")
        sys.exit(1)

    create_user(username, password, role)
    print("Usuário criado com sucesso!")

if __name__ == "__main__":
    main()
