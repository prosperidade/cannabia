from flask import Flask, render_template, request
import mysql.connector
from mysql.connector import Error

app = Flask(__name__, template_folder='templates')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    sender_filter = request.args.get('sender', None)
    
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='root',
            database='cannabia'
        )
        cursor = connection.cursor(dictionary=True)
        
        if sender_filter:
            query = "SELECT * FROM incoming_messages WHERE sender = %s ORDER BY id DESC"
            cursor.execute(query, (sender_filter,))
        else:
            query = "SELECT * FROM incoming_messages ORDER BY id DESC"
            cursor.execute(query)
        messages = cursor.fetchall()
        
        # Dados para gráfico de barras: mensagens por contato
        agg_query = "SELECT contact_name, COUNT(*) AS message_count FROM incoming_messages GROUP BY contact_name"
        cursor.execute(agg_query)
        agg_data = cursor.fetchall()
        labels = [row['contact_name'] for row in agg_data]
        counts = [row['message_count'] for row in agg_data]
        
        # Dados para gráfico de linha: evolução das mensagens por dia
        agg_query_time = """
        SELECT DATE(FROM_UNIXTIME(timestamp)) AS message_date, COUNT(*) AS total_messages
        FROM incoming_messages
        GROUP BY message_date
        ORDER BY message_date ASC
        """
        cursor.execute(agg_query_time)
        agg_time_data = cursor.fetchall()
        line_labels = [row['message_date'] for row in agg_time_data]
        line_data = [row['total_messages'] for row in agg_time_data]
        
        cursor.close()
        connection.close()
        
        return render_template('dashboard.html', 
                               messages=messages, 
                               sender_filter=sender_filter,
                               labels=labels, 
                               counts=counts,
                               line_labels=line_labels,
                               line_data=line_data)
    except Exception as e:
        return f"Erro ao acessar o dashboard: {e}", 500

if __name__ == '__main__':
    app.run(port=5001, debug=True)

