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
            RETURNING id
            """,
            (clinic_id, sender, contact_name, message_text, timestamp),
        )
        connection.commit()
        msg_id = cursor.fetchone()[0]
        return msg_id


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

def list_messages(clinic_id, sender=None, search=None):
    with db_cursor(dictionary=True) as (_, cursor):
        clauses = ["clinic_id = %s"]
        params = [clinic_id]

        if sender:
            clauses.append("sender = %s")
            params.append(sender)

        if search:
            term = f"%{search.strip()}%"
            clauses.append(
                """
                (
                    sender ILIKE %s
                    OR COALESCE(contact_name, '') ILIKE %s
                    OR COALESCE(message_text, '') ILIKE %s
                )
                """
            )
            params.extend([term, term, term])

        cursor.execute(
            f"""
            SELECT *
            FROM incoming_messages
            WHERE {' AND '.join(clauses)}
            ORDER BY id DESC
            """,
            params,
        )

        return cursor.fetchall()


def list_message_contacts(clinic_id, limit=25, search=None):
    with db_cursor(dictionary=True) as (_, cursor):
        clauses = ["clinic_id = %s"]
        params = [clinic_id]

        if search:
            term = f"%{search.strip()}%"
            clauses.append(
                """
                (
                    sender ILIKE %s
                    OR COALESCE(contact_name, '') ILIKE %s
                )
                """
            )
            params.extend([term, term])

        params.append(limit)
        cursor.execute(
            f"""
            SELECT
                sender,
                COALESCE(NULLIF(MAX(contact_name), ''), sender) AS label,
                COUNT(*) AS count
            FROM incoming_messages
            WHERE {' AND '.join(clauses)}
            GROUP BY sender
            ORDER BY count DESC, sender ASC
            LIMIT %s
            """,
            params,
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
                    WHEN timestamp ~ '^[0-9]+$'
                        THEN TO_TIMESTAMP(CAST(timestamp AS NUMERIC))::DATE
                    ELSE LEFT(timestamp, 10)::DATE
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
