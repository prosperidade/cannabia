from flask import Flask, render_template
import mysql.connector
from mysql.connector import Error

app = Flask(__name__, template_folder='templates')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='root',
            database='cannabia'
        )
        # Utilize dictionary=True para obter os resultados como dicionários
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM incoming_messages ORDER BY id DESC"
        cursor.execute(query)
        messages = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('dashboard.html', messages=messages)
    except Exception as e:
        return f"Erro ao acessar o dashboard: {e}", 500

if __name__ == '__main__':
    app.run(port=5002, debug=True)

