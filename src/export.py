import csv
import mysql.connector
from mysql.connector import Error
from flask import Flask, Response, request

app = Flask(__name__)

@app.route('/export', methods=['GET'])
def export_csv():
    # Conecta ao banco de dados
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
    except Error as e:
        return f"Erro ao acessar o banco de dados: {e}", 500

    # Cria o CSV na memória
    def generate():
        header = ['ID', 'Remetente', 'Nome do Contato', 'Mensagem', 'Timestamp']
        yield ','.join(header) + '\n'
        for msg in messages:
            row = [
                str(msg.get('id', '')),
                msg.get('sender', ''),
                msg.get('contact_name', ''),
                msg.get('message_text', '').replace('\n', ' '),  # remove quebras de linha
                msg.get('timestamp', '')
            ]
            yield ','.join(row) + '\n'

    # Cria uma resposta com o CSV e define os cabeçalhos para download
    return Response(generate(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=mensagens.csv"})

if __name__ == '__main__':
    app.run(port=5003, debug=True)
