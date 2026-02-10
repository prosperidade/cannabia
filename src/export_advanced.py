import csv
import io
import mysql.connector
from mysql.connector import Error
from flask import Flask, Response, request
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

@app.route('/export', methods=['GET'])
def export_csv():
    # Obtém os filtros da query string
    sender = request.args.get('sender', None)
    start_date = request.args.get('start_date', None)
    end_date = request.args.get('end_date', None)
    
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='root',
            database='cannabia'
        )
        cursor = connection.cursor(dictionary=True)
        
        # Construção dinâmica da query
        query = "SELECT * FROM incoming_messages WHERE 1=1"
        params = []
        
        if sender:
            query += " AND sender = %s"
            params.append(sender)
        
        # Converter datas do formato dd/mm/yyyy para YYYY-MM-DD HH:MM:SS
        if start_date:
            try:
                dt_start = datetime.strptime(start_date, "%d/%m/%Y")
                start_date_formatted = dt_start.strftime("%Y-%m-%d 00:00:00")
                query += " AND FROM_UNIXTIME(timestamp) >= %s"
                params.append(start_date_formatted)
            except Exception as e:
                return f"Erro ao processar data de início: {e}", 400
        
        if end_date:
            try:
                dt_end = datetime.strptime(end_date, "%d/%m/%Y")
                end_date_formatted = dt_end.strftime("%Y-%m-%d 23:59:59")
                query += " AND FROM_UNIXTIME(timestamp) <= %s"
                params.append(end_date_formatted)
            except Exception as e:
                return f"Erro ao processar data de fim: {e}", 400
        
        query += " ORDER BY id DESC"
        
        cursor.execute(query, tuple(params))
        messages = cursor.fetchall()
        cursor.close()
        connection.close()
        
        # Gera o CSV em memória
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Sender', 'Contact Name', 'Message Text', 'Timestamp'])
        for msg in messages:
            writer.writerow([
                msg.get('id', ''),
                msg.get('sender', ''),
                msg.get('contact_name', ''),
                msg.get('message_text', '').replace('\n', ' '),
                msg.get('timestamp', '')
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=export.csv"}
        )
    except Exception as e:
        return f"Erro ao exportar CSV: {e}", 500

if __name__ == '__main__':
    app.run(port=5006, debug=True)

