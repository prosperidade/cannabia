from database import db_cursor


def ensure_message_tables():
    with db_cursor() as (connection, cursor):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS incoming_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender VARCHAR(50),
                contact_name VARCHAR(100),
                message_text TEXT,
                timestamp VARCHAR(50)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS message_status_updates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message_id VARCHAR(100),
                status VARCHAR(50),
                timestamp VARCHAR(50)
            )
            """
        )
        connection.commit()


def save_incoming_message(sender, contact_name, message_text, timestamp):
    with db_cursor() as (connection, cursor):
        cursor.execute(
            """
            INSERT INTO incoming_messages (sender, contact_name, message_text, timestamp)
            VALUES (%s, %s, %s, %s)
            """,
            (sender, contact_name, message_text, timestamp),
        )
        connection.commit()


def save_status_update(message_id, status, timestamp):
    with db_cursor() as (connection, cursor):
        cursor.execute(
            """
            INSERT INTO message_status_updates (message_id, status, timestamp)
            VALUES (%s, %s, %s)
            """,
            (message_id, status, timestamp),
        )
        connection.commit()


def list_messages(sender=None):
    with db_cursor(dictionary=True) as (_, cursor):
        if sender:
            cursor.execute("SELECT * FROM incoming_messages WHERE sender = %s ORDER BY id DESC", (sender,))
        else:
            cursor.execute("SELECT * FROM incoming_messages ORDER BY id DESC")
        return cursor.fetchall()


def aggregate_messages_by_contact():
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            "SELECT contact_name, COUNT(*) AS message_count FROM incoming_messages GROUP BY contact_name"
        )
        return cursor.fetchall()


def aggregate_messages_by_day():
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT
                DATE(
                    CASE
                        WHEN timestamp REGEXP '^[0-9]+$' THEN FROM_UNIXTIME(CAST(timestamp AS UNSIGNED))
                        ELSE STR_TO_DATE(timestamp, '%Y-%m-%d %H:%i:%s')
                    END
                ) AS message_date,
                COUNT(*) AS total_messages
            FROM incoming_messages
            GROUP BY message_date
            ORDER BY message_date ASC
            """
        )
        return cursor.fetchall()
