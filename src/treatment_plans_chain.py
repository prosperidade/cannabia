import os
from dotenv import load_dotenv, find_dotenv
import mysql.connector
from mysql.connector import Error
from langchain_openai import OpenAI  
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
api_key = os.getenv("OPENAI_API_KEY")

def insert_treatment_plan(patient_id, plan_description):
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
            query = "INSERT INTO treatment_plans (patient_id, plan_description) VALUES (%s, %s)"
            cursor.execute(query, (patient_id, plan_description))
            connection.commit()
            print("Plano de tratamento inserido com sucesso!")
    except Error as err:
        print("Erro ao inserir plano de tratamento:", err)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def run_treatment_plans_chain():
    prompt_template = PromptTemplate(
        input_variables=["patient_name"],
        template=(
            "Você é um super agente Cannab'IA. Por favor, crie um plano de tratamento personalizado para o paciente {patient_name}, "
            "baseado em seu histórico médico, sintomas e melhores práticas clínicas. Inclua sugestões de dosagens e proporções de canabinoides."
        )
    )
    
    llm = OpenAI(
        temperature=0.7,
        openai_api_key=api_key
    )
    
    chain = LLMChain(llm=llm, prompt=prompt_template)
    
    patient_name = "João Silva"  # Exemplo
    treatment_plan_details = chain.run(patient_name=patient_name)
    
    print("Detalhes do plano de tratamento coletados:")
    print(treatment_plan_details)
    
    # Supondo que o ID do paciente seja 1
    insert_treatment_plan(1, treatment_plan_details)

if __name__ == "__main__":
    run_treatment_plans_chain()
