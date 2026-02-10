import os
from dotenv import load_dotenv, find_dotenv
import mysql.connector
from mysql.connector import Error
from langchain_openai import OpenAI  
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

# Carrega o .env da raiz do projeto
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
api_key = os.getenv("OPENAI_API_KEY")

def insert_medical_history(patient_id, history):
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
            query = "INSERT INTO medical_history (patient_id, history) VALUES (%s, %s)"
            cursor.execute(query, (patient_id, history))
            connection.commit()
            print("Histórico médico inserido com sucesso!")
    except Error as err:
        print("Erro ao inserir histórico médico:", err)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def run_medical_history_chain():
    prompt_template = PromptTemplate(
        input_variables=["patient_name"],
        template=(
            "Você é um super agente Cannab'IA. Por favor, colete o histórico médico completo do paciente {patient_name}. "
            "Inclua informações sobre doenças prévias, medicações, alergias e outros detalhes relevantes."
        )
    )
    
    llm = OpenAI(
        temperature=0.7,
        openai_api_key=api_key
    )
    
    chain = LLMChain(llm=llm, prompt=prompt_template)
    
    patient_name = "João Silva"  # Exemplo
    medical_history_details = chain.run(patient_name=patient_name)
    
    print("Detalhes do histórico médico coletados:")
    print(medical_history_details)
    
    # Supondo que o ID do paciente seja 1 (ajuste conforme necessário)
    insert_medical_history(1, medical_history_details)

if __name__ == "__main__":
    run_medical_history_chain()
