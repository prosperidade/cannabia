from src.infra.database import db_cursor


# ==========================================
# WRITE OPERATIONS
# ==========================================

def save_incoming_message(clinic_id, sender, contact_name, message_text, timestamp):
    with db_cursor() as (connection, cursor):
        cursor.execute(
            """
            INSERT INTO incoming_messages 
                (clinic_id, sender, contact_name, message_text, timestamp)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (clinic_id, sender, contact_name, message_text, timestamp),
        )
        connection.commit()


def save_status_update(clinic_id, message_id, status, timestamp):
    with db_cursor() as (connection, cursor):
        cursor.execute(
            """
            INSERT INTO message_status_updates 
                (clinic_id, message_id, status, timestamp)
            VALUES (%s, %s, %s, %s)
            """,
            (clinic_id, message_id, status, timestamp),
        )
        connection.commit()


# ==========================================
# READ OPERATIONS
# ==========================================

def list_messages(clinic_id, sender=None):
    with db_cursor(dictionary=True) as (_, cursor):
        if sender:
            cursor.execute(
                """
                SELECT *
                FROM incoming_messages
                WHERE clinic_id = %s
                  AND sender = %s
                ORDER BY id DESC
                """,
                (clinic_id, sender),
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM incoming_messages
                WHERE clinic_id = %s
                ORDER BY id DESC
                """,
                (clinic_id,),
            )

        return cursor.fetchall()


def aggregate_messages_by_contact(clinic_id):
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT contact_name, COUNT(*) AS message_count
            FROM incoming_messages
            WHERE clinic_id = %s
            GROUP BY contact_name
            """,
            (clinic_id,),
        )
        return cursor.fetchall()


def aggregate_messages_by_day(clinic_id):
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                CASE
                    WHEN timestamp REGEXP '^[0-9]+$'
                        THEN DATE(FROM_UNIXTIME(CAST(timestamp AS UNSIGNED)))
                    ELSE DATE(LEFT(timestamp, 10))
                END AS message_date,
                COUNT(*) AS total_messages
            FROM incoming_messages
            WHERE clinic_id = %s
            GROUP BY message_date
            ORDER BY message_date ASC
            """,
            (clinic_id,),
        )
        return cursor.fetchall()