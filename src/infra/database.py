from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor

from src.config import DATABASE_URL


def get_connection():
    return psycopg2.connect(DATABASE_URL)


@contextmanager
def db_cursor(dictionary=False):
    connection = get_connection()
    if dictionary:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
    else:
        cursor = connection.cursor()
    try:
        yield connection, cursor
    finally:
        cursor.close()
        connection.close()
