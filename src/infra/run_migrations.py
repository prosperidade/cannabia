from pathlib import Path

from src.infra.database import db_cursor


def run_sql_file(path):
    sql_content = Path(path).read_text(encoding='utf-8')
    statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

    with db_cursor() as (connection, cursor):
        for stmt in statements:
            cursor.execute(stmt)
        connection.commit()


if __name__ == '__main__':
    run_sql_file('migrations/001_initial_schema.sql')
    print('Migração aplicada com sucesso.')
