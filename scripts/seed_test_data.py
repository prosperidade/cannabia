"""
scripts/seed_test_data.py
Insere 2 atendimentos fictícios completos na tabela anamnesis_reports
para validar o layout do Dashboard do Médico.

Uso:
    env\\Scripts\\python scripts/seed_test_data.py
"""
import sys
import os

# Garante que src/ esteja no PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from src.infra.database import db_cursor

# ── Dados fictícios ────────────────────────────────────────────────────────────

RECORDS = [
    {
        "clinic_id":    1,
        "patient_name": "Maria Oliveira",
        "phone":        "5562991110001",
        "anamnesis_data": {
            "patient_name":       "Maria Oliveira",
            "age":                45,
            "main_complaint":     "Dor crônica nas articulações (joelhos e quadril) há 3 anos",
            "symptoms":           ["Dor articular", "Inflamação", "Dificuldade de locomoção", "Insônia"],
            "current_medications":["Ibuprofeno 400mg", "Omeprazol 20mg"],
            "allergies":          ["Dipirona"],
            "medical_history":    "Artrite reumatoide diagnosticada em 2021. Sem cirurgias."
        },
        "clinical_analysis": {
            "probable_conditions": ["Artrite Reumatoide", "Dor Nociceptiva Crônica"],
            "risk_level":          "Médio",
            "recommended_exams":   ["PCR", "VHS", "Fator Reumatoide"],
            "red_flags":           ["Uso prolongado de AINEs - risco gástrico"],
            "clinical_notes":      "Paciente apresenta quadro clássico de artrite reumatoide com componente inflamatório ativo."
        },
        "treatment_plan": {
            "cannabinoid_ratio":    "CBD:THC 20:1",
            "suggested_dosage":     "10mg CBD / 0,5mg THC — 2x ao dia",
            "administration_route": "Óleo sublingual",
            "monitoring_plan":      "Reavaliação em 30 dias com escala de dor VAS",
            "precautions":          ["Monitorar pressão arterial", "Evitar uso em jejum"]
        },
        "scientific_report": {
            "summary":    "Evidências crescentes suportam o uso de canabidiol (CBD) no controle da dor inflamatória crônica associada à artrite reumatoide, com perfil de segurança favorável em relação aos AINEs tradicionais.",
            "supporting_evidence": [
                "Blake et al. (2006): CBD reduziu pontuação de dor e inflamação em pacientes com AR.",
                "Hammell et al. (2016): Administração transdérmica de CBD reduziu inflamação articular em modelo animal.",
                "Fitzcharles et al. (2020): Revisão sistemática confirma eficácia do cannabis medicinal em dor reumática."
            ],
            "references": [
                "Blake DR et al. Rheumatology (2006). DOI: 10.1093/rheumatology/kel407",
                "Hammell DC et al. Eur J Pain (2016). DOI: 10.1002/ejp.818",
                "Fitzcharles MA et al. Semin Arthritis Rheum (2020). DOI: 10.1016/j.semarthrit.2020.01.010"
            ]
        },
        "rag_chunks_used": 3,
        "report_model":    "gemini-1.5-flash",
    },
    {
        "clinic_id":    1,
        "patient_name": "Carlos Mendes",
        "phone":        "5562991110002",
        "anamnesis_data": {
            "patient_name":        "Carlos Mendes",
            "age":                 32,
            "main_complaint":      "Ansiedade generalizada e episódios de pânico frequentes",
            "symptoms":            ["Ansiedade", "Taquicardia", "Insônia", "Tensão muscular"],
            "current_medications": ["Nenhuma"],
            "allergies":           ["Nenhuma"],
            "medical_history":     "Diagnóstico de TAG (Transtorno de Ansiedade Generalizada) em 2023. Sem tratamento farmacológico prévio."
        },
        "clinical_analysis": {
            "probable_conditions": ["Transtorno de Ansiedade Generalizada", "Insônia Secundária"],
            "risk_level":          "Baixo",
            "recommended_exams":   ["TSH", "Hemograma completo"],
            "red_flags":           [],
            "clinical_notes":      "Candidato favorável ao tratamento com CBD dado perfil anxiolítico documentado e ausência de contraindicações."
        },
        "treatment_plan": {
            "cannabinoid_ratio":    "CBD puro isolado",
            "suggested_dosage":     "25mg CBD — 1x ao dia (noturno)",
            "administration_route": "Cápsula gelatinosa",
            "monitoring_plan":      "Escala GAD-7 no retorno de 45 dias",
            "precautions":          ["Não combinar com benzodiazepínicos sem supervisão médica"]
        },
        "scientific_report": {
            "summary":    "O CBD demonstra efeito ansiolítico dose-dependente em estudos clínicos, com mecanismo de ação via receptores serotonérgicos 5-HT1A e modulação do sistema endocanabinoide, sem risco de dependência física.",
            "supporting_evidence": [
                "Bergamaschi et al. (2011): CBD 600mg reduziu ansiedade em pacientes com fobia social em simulação de fala pública.",
                "Shannon et al. (2019): CBD melhorou escores de ansiedade e qualidade do sono em 79,2% dos pacientes.",
                "Blessing et al. (2015): Revisão pré-clínica e clínica confirma eficácia do CBD em múltiplos transtornos de ansiedade."
            ],
            "references": [
                "Bergamaschi MM et al. Neuropsychopharmacology (2011). DOI: 10.1038/npp.2011.6",
                "Shannon S et al. Perm J (2019). DOI: 10.7812/TPP/18-041",
                "Blessing EM et al. Neurotherapeutics (2015). DOI: 10.1007/s13311-015-0387-1"
            ]
        },
        "rag_chunks_used": 3,
        "report_model":    "gemini-1.5-flash",
    },
]

# ── Ingestão ───────────────────────────────────────────────────────────────────

import json

def main():
    inserted = 0
    with db_cursor() as (conn, cursor):
        for rec in RECORDS:
            cursor.execute(
                """
                INSERT INTO anamnesis_reports
                  (clinic_id, patient_name, phone, anamnesis_data,
                   clinical_analysis, treatment_plan, scientific_report,
                   rag_chunks_used, report_model, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    rec["clinic_id"],
                    rec["patient_name"],
                    rec["phone"],
                    json.dumps(rec["anamnesis_data"],    ensure_ascii=False),
                    json.dumps(rec["clinical_analysis"], ensure_ascii=False),
                    json.dumps(rec["treatment_plan"],    ensure_ascii=False),
                    json.dumps(rec["scientific_report"], ensure_ascii=False),
                    rec["rag_chunks_used"],
                    rec["report_model"],
                    "pendente",
                ),
            )
            inserted += 1
            print(f"  ✅ Inserido: #{cursor.lastrowid} — {rec['patient_name']}")
        conn.commit()

    print(f"\n✅ {inserted} atendimentos de teste inseridos com sucesso!")
    print("   Acesse /atendimentos para visualizar o dashboard.")


if __name__ == "__main__":
    main()
