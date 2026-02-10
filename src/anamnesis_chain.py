import os
from dotenv import load_dotenv
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import mysql.connector
from mysql.connector import Error

# Carrega as variáveis do arquivo .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

def insert_patient(name, email=None, phone=None):
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
            query = "INSERT INTO patients (name, email, phone) VALUES (%s, %s, %s)"
            cursor.execute(query, (name, email, phone))
            connection.commit()
            print("Paciente inserido com sucesso!")
    except Error as err:
        print("Erro ao inserir paciente:", err)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def run_anamnesis_chain():
    prompt_template = PromptTemplate(
        input_variables=["patient_name"],
        template=(
            "Você é um super agente Cannab'IA. Por favor, colete os dados de anamnese do paciente {patient_name}. "
            "Pergunte sobre histórico médico, sintomas, medicações em uso, alergias e outros detalhes relevantes."
        )
    )
    
    # Inicializa o LLM com a chave carregada do .env
    llm = OpenAI(
        temperature=0.7,
        openai_api_key=api_key
    )
    
    chain = LLMChain(llm=llm, prompt=prompt_template)
    
    patient_name = "João Silva"
    anamnesis_details = chain.run(patient_name=patient_name)
    
    print("Detalhes da anamnese coletados:")
    print(anamnesis_details)
    
    insert_patient(name=patient_name)

if __name__ == "__main__":
    run_anamnesis_chain()
