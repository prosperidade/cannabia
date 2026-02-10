import os
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error

def insert_alert(patient_id, message, alert_time):
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='root',
            database='cannabia'
        )
        if connection.is_connected():
            cursor = connection.cursor()
            query = "INSERT INTO alerts (patient_id, message, alert_time) VALUES (%s, %s, %s)"
            cursor.execute(query, (patient_id, message, alert_time))
            connection.commit()
            print("Alerta inserido com sucesso!")
    except Error as err:
        print("Erro ao inserir alerta:", err)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def run_alerts_monitoring():
    # Exemplo: simula um alerta para o paciente com id 1
    patient_id = 1
    message = "Lembrete: Sua consulta está agendada para amanhã. Por favor, confirme sua presença."
    # Define o horário do alerta para 24 horas a partir de agora
    alert_time = datetime.now() + timedelta(hours=24)
    alert_time_str = alert_time.strftime("%Y-%m-%d %H:%M:%S")
    
    insert_alert(patient_id, message, alert_time_str)

if __name__ == "__main__":
    run_alerts_monitoring()
