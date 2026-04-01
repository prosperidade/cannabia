import mysql.connector
from mysql.connector import Error

def inspeçao_geral_cannabia():
    try:
        # Configuração da conexão (ajuste a senha conforme seu MAMP)
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root", # No MAMP a senha padrão geralmente é 'root'
            database="cannabia"
        )

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            
            # Lista de tabelas para inspecionar
            tabelas = [
                "patients", 
                "medical_history", 
                "treatment_plans", 
                "monitoring", 
                "scientific_references", 
                "alerts"
            ]

            print("="*60)
            print("📊 RELATÓRIO DE DADOS ATUAIS - CANNAB'IA")
            print("="*60)

            for tabela in tabelas:
                cursor.execute(f"SELECT * FROM {tabela}")
                rows = cursor.fetchall()
                
                print(f"\n# TABELA: {tabela.upper()} ({len(rows)} registros)")
                print("-" * 30)
                
                if not rows:
                    print("   [Vazia]")
                else:
                    for row in rows:
                        print(f" > Registro ID {list(row.values())[0]}:")
                        for coluna, valor in row.items():
                            print(f"   - {coluna}: {valor}")
                        print("   " + "."*20)
            
            print("\n" + "="*60)
            print("Inspeção finalizada com sucesso.")

    except Error as e:
        print(f"Erro ao acessar o MySQL: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    inspeçao_geral_cannabia()