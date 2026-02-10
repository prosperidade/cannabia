import os
import mysql.connector
from mysql.connector import Error
from fpdf import FPDF

def fetch_patient_data(patient_id):
    """
    Busca os dados do paciente a partir do ID.
    """
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='root',
            database='cannabia'
        )
        cursor = connection.cursor()
        query = "SELECT name, email, phone, created_at FROM patients WHERE id = %s"
        cursor.execute(query, (patient_id,))
        patient = cursor.fetchone()
        return patient
    except Error as err:
        print("Erro ao buscar dados do paciente:", err)
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def fetch_appointments(patient_id):
    """
    Busca todos os agendamentos associados ao paciente.
    """
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='root',
            database='cannabia'
        )
        cursor = connection.cursor()
        query = "SELECT appointment_date, status, created_at FROM appointments WHERE patient_id = %s"
        cursor.execute(query, (patient_id,))
        appointments = cursor.fetchall()
        return appointments
    except Error as err:
        print("Erro ao buscar agendamentos:", err)
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def generate_pdf_report(patient_id):
    """
    Gera um relatório em PDF para o paciente especificado.
    """
    patient = fetch_patient_data(patient_id)
    appointments = fetch_appointments(patient_id)
    
    if not patient:
        print("Nenhum dado encontrado para o paciente.")
        return

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Cabeçalho do relatório
    pdf.cell(200, 10, txt="Relatório do Paciente", ln=1, align="C")
    
    # Dados do paciente
    pdf.cell(200, 10, txt=f"Nome: {patient[0]}", ln=2)
    pdf.cell(200, 10, txt=f"E-mail: {patient[1]}", ln=3)
    pdf.cell(200, 10, txt=f"Telefone: {patient[2]}", ln=4)
    pdf.cell(200, 10, txt=f"Criado em: {patient[3]}", ln=5)
    
    pdf.ln(10)  # Espaço entre seções
    pdf.cell(200, 10, txt="Agendamentos:", ln=6)
    
    if appointments:
        for app in appointments:
            pdf.cell(200, 10, txt=f"Data: {app[0]} - Status: {app[1]} - Criado em: {app[2]}", ln=1)
    else:
        pdf.cell(200, 10, txt="Nenhum agendamento encontrado.", ln=1)
    
    output_filename = f"report_patient_{patient_id}.pdf"
    pdf.output(output_filename)
    print(f"Relatório gerado com sucesso: {output_filename}")

if __name__ == "__main__":
    # Altere o ID para o paciente que você deseja gerar o relatório.
    generate_pdf_report(1)
