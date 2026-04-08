"""
Setup local completo da CannabIA.

Uso:
    python scripts/setup_local.py

Executa em ordem:
  1. Roda todas as migrations (cria/atualiza tabelas)
  2. Seed de usuarios base
  3. Seed completo com dados demo
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("=" * 60)
    print("  CannabIA - Setup Local")
    print("=" * 60)

    # 1. Migrations
    print("\n[1/3] Rodando migrations...")
    try:
        from src.infra.run_migrations import run_all
        applied = run_all()
        if applied:
            print(f"  -> {len(applied)} migrations aplicadas")
        else:
            print("  -> Todas as migrations ja estao aplicadas")
    except Exception as e:
        print(f"  ERRO nas migrations: {e}")
        print("  Verifique se o PostgreSQL esta rodando e o DATABASE_URL esta correto no .env")
        sys.exit(1)

    # 2. Seed usuarios
    print("\n[2/3] Criando usuarios...")
    try:
        from scripts.seed_users import seed as seed_users
        seed_users()
    except Exception as e:
        print(f"  ERRO no seed de usuarios: {e}")
        sys.exit(1)

    # 3. Seed completo
    print("\n[3/3] Populando dados demo...")
    try:
        from scripts.seed_comprehensive import main as seed_comprehensive
        seed_comprehensive()
    except ImportError:
        print("  AVISO: seed_comprehensive.py ainda nao existe, pulando...")
    except Exception as e:
        print(f"  ERRO no seed completo: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  Setup concluido!")
    print("=" * 60)
    print("\n  Usuarios disponiveis:")
    print("    admin     / admin123      -> /admin")
    print("    medico    / medico123     -> /med/dashboard")
    print("    atendente / atendente123  -> /org/dashboard")
    print("    paciente  / paciente123   -> /p/dashboard")
    print("\n  Para iniciar:")
    print("    Backend:  python -m src.app")
    print("    Frontend: cd frontend && npm run dev")
    print("    Acesse:   http://127.0.0.1:3001")


if __name__ == "__main__":
    main()
