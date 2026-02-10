from flask import Blueprint, render_template
import mysql.connector
from mysql.connector import Error

historico_bp = Blueprint('historico', __name__, template_folder='templates')

@historico_bp.route('/historico', methods=['GET'])
def historico():
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='root',
            database='cannabia'
        )
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM incoming_messages ORDER BY id DESC"
        cursor.execute(query)
        messages = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('historico_atendimento.html', messages=messages)
    except Exception as e:
        return f"Erro ao acessar o histórico: {e}", 500

if __name__ == '__main__':
    from flask import Flask
    app = Flask(__name__, template_folder='templates')
    app.register_blueprint(historico_bp)
    app.run(port=5008, debug=True)
