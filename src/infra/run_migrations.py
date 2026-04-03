from pathlib import Path

from src.infra.database import db_cursor


MIGRATIONS_DIR = Path("migrations")


def run_sql_file(path):
    sql_content = Path(path).read_text(encoding='utf-8')
    if not sql_content.strip():
        return

    with db_cursor() as (connection, cursor):
        cursor.execute(sql_content)
        connection.commit()


def list_migration_files():
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def run_all():
    applied = []
    for migration_file in list_migration_files():
        run_sql_file(migration_file)
        applied.append(str(migration_file))
    return applied


if __name__ == '__main__':
    applied = run_all()
    print(f'{len(applied)} migrations aplicadas com sucesso.')
