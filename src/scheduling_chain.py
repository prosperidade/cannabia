from flask import Blueprint, render_template, request, redirect, url_for
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

scheduling_bp = Blueprint('scheduling', __name__, template_folder='templates')

def get_db_connection():
    connection = mysql.connector.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='root',
        database='cannabia'
    )
    return connection

@scheduling_bp.route('/scheduling', methods=['GET', 'POST'])
def scheduling():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    if request.method == 'POST':
        patient_name = request.form.get('patient_name')
        appointment_date = request.form.get('appointment_date')  # formato: dd/mm/yyyy HH:MM
        try:
            dt = datetime.strptime(appointment_date, "%d/%m/%Y %H:%M")
            formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            return f"Erro ao processar a data: {e}", 400
        
        # Cria a tabela se não existir
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                patient_name VARCHAR(100),
                appointment_date DATETIME NOT NULL,
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        query = "INSERT INTO appointments (patient_name, appointment_date, status) VALUES (%s, %s, %s)"
        cursor.execute(query, (patient_name, formatted_date, "Agendada"))
        connection.commit()
        return redirect(url_for('scheduling.scheduling'))
    
    cursor.execute("SELECT * FROM appointments ORDER BY appointment_date DESC")
    appointments = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('scheduling_dashboard.html', appointments=appointments)

if __name__ == '__main__':
    # Para testes individuais, você pode rodar este módulo
    from flask import Flask
    app = Flask(__name__, template_folder='templates')
    app.register_blueprint(scheduling_bp)
    app.run(port=5007, debug=True)



