"""
Seed comprehensivo para popular TODAS as tabelas do CannabIA com dados demo realistas.

Uso:
    python scripts/seed_comprehensive.py

Idempotente: seguro para rodar multiplas vezes (usa SELECT antes de INSERT ou ON CONFLICT).
"""
import sys
import os
import json
import uuid
from datetime import datetime, timedelta, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infra.database import db_cursor
from src.repositories.user_repository import create_user, get_user_by_username

# Re-use existing seed for base users
import scripts.seed_users as seed_users


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CLINIC_ID = 1
TENANT_ID = None  # resolved at runtime


def _now():
    return datetime.utcnow()


def _days_ago(n):
    return _now() - timedelta(days=n)


def _days_ahead(n):
    return _now() + timedelta(days=n)


def _get_tenant_id():
    """Resolve the tenant_id for clinic 1."""
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT tenant_id FROM clinics WHERE id = %s", (CLINIC_ID,))
        row = cursor.fetchone()
        return row["tenant_id"] if row else 1


def _table_exists(cursor, table_name):
    cursor.execute(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
        (table_name,),
    )
    return cursor.fetchone()["exists"]


def _row_exists(cursor, table, condition, params):
    cursor.execute(f"SELECT 1 FROM {table} WHERE {condition} LIMIT 1", params)
    return cursor.fetchone() is not None


# ---------------------------------------------------------------------------
# 1. Users (extend seed_users)
# ---------------------------------------------------------------------------

EXTRA_USERS = [
    {"username": "medico2", "password": "medico123", "role": "Medico"},
    {"username": "medico3", "password": "medico123", "role": "Medico"},
]


def seed_extra_users():
    print("\n=== 1. Usuarios extras ===")
    # First run the base seed
    print("  Executando seed_users.seed()...")
    seed_users.seed()

    for u in EXTRA_USERS:
        existing = get_user_by_username(u["username"])
        if existing:
            user_id = existing["id"]
            print(f"  Usuario '{u['username']}' ja existe (id={user_id})")
        else:
            create_user(u["username"], u["password"], u["role"])
            created = get_user_by_username(u["username"])
            user_id = created["id"] if created else None
            print(f"  Criado: {u['username']} ({u['role']}) id={user_id}")

        if user_id:
            seed_users.link_user_to_clinic(user_id, CLINIC_ID, u["role"].lower())


# ---------------------------------------------------------------------------
# 2. Patients (15)
# ---------------------------------------------------------------------------

PATIENTS = [
    # user_id resolvido em runtime para o user 'paciente' (ver seed_patients)
    {"name": "Maria Oliveira Silva", "phone": "5562991001001", "email": "maria.oliveira@email.com", "user_id": "PACIENTE", "status": "ativo"},
    {"name": "João Santos Costa", "phone": "5562991002002", "email": "joao.santos@email.com", "user_id": None, "status": "ativo"},
    {"name": "Ana Clara Menezes", "phone": "5562991003003", "email": "ana.menezes@email.com", "user_id": None, "status": "em_tratamento"},
    {"name": "Pedro Henrique Lima", "phone": "5562991004004", "email": "pedro.lima@email.com", "user_id": None, "status": "ativo"},
    {"name": "Fernanda Alves Rocha", "phone": "5562991005005", "email": "fernanda.rocha@email.com", "user_id": None, "status": "aguardando_consulta"},
    {"name": "Carlos Eduardo Dias", "phone": "5562991006006", "email": "carlos.dias@email.com", "user_id": None, "status": "inativo"},
    {"name": "Beatriz Souza Martins", "phone": "5562991007007", "email": "beatriz.martins@email.com", "user_id": None, "status": "ativo"},
    {"name": "Lucas Gabriel Ferreira", "phone": "5562991008008", "email": "lucas.ferreira@email.com", "user_id": None, "status": "em_tratamento"},
    {"name": "Juliana Pereira Nunes", "phone": "5562991009009", "email": "juliana.nunes@email.com", "user_id": None, "status": "ativo"},
    {"name": "Roberto Carlos Araujo", "phone": "5562991010010", "email": "roberto.araujo@email.com", "user_id": None, "status": "em_tratamento"},
    {"name": "Camila Torres Santos", "phone": "5562991011011", "email": "camila.torres@email.com", "user_id": None, "status": "ativo"},
    {"name": "Rafael Oliveira Gomes", "phone": "5562991012012", "email": "rafael.gomes@email.com", "user_id": None, "status": "aguardando_consulta"},
    {"name": "Patricia Ribeiro Costa", "phone": "5562991013013", "email": "patricia.costa@email.com", "user_id": None, "status": "ativo"},
    {"name": "Thiago Mendes Vieira", "phone": "5562991014014", "email": "thiago.vieira@email.com", "user_id": None, "status": "em_tratamento"},
    {"name": "Isabela Nascimento Lima", "phone": "5562991015015", "email": "isabela.lima@email.com", "user_id": None, "status": "ativo"},
]

# Map name -> inserted id (populated at runtime)
patient_ids = {}


def seed_patients():
    print("\n=== 2. Pacientes (15) ===")
    with db_cursor(dictionary=True) as (conn, cursor):
        # Resolve user_id 'PACIENTE' em runtime para o id real do user 'paciente'
        cursor.execute("SELECT id FROM users WHERE username = 'paciente' LIMIT 1")
        paciente_row = cursor.fetchone()
        paciente_user_id = paciente_row["id"] if paciente_row else None

        for p in PATIENTS:
            cursor.execute(
                "SELECT id FROM patients WHERE clinic_id = %s AND phone = %s LIMIT 1",
                (CLINIC_ID, p["phone"]),
            )
            row = cursor.fetchone()
            if row:
                patient_ids[p["name"]] = row["id"]
                print(f"  Paciente '{p['name']}' ja existe (id={row['id']})")
                continue

            user_id = p["user_id"]
            if user_id == "PACIENTE":
                user_id = paciente_user_id

            cursor.execute(
                """
                INSERT INTO patients (clinic_id, name, email, phone, user_id, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (CLINIC_ID, p["name"], p["email"], p["phone"], user_id, p["status"]),
            )
            new_id = cursor.fetchone()["id"]
            patient_ids[p["name"]] = new_id
            print(f"  Criado paciente '{p['name']}' (id={new_id})")
        conn.commit()


def _pid(name):
    """Get patient id by name (must call after seed_patients)."""
    return patient_ids.get(name)


# ---------------------------------------------------------------------------
# 3. Anamnesis Reports (8)
# ---------------------------------------------------------------------------

ANAMNESIS_REPORTS = [
    {
        "patient_name": "Maria Oliveira Silva",
        "phone": "5562991001001",
        "status": "revisado",
        "anamnesis_data": {
            "chief_complaint": "Dor crônica lombar",
            "symptoms": "Dor lombar persistente há 3 anos, irradiando para membro inferior esquerdo. Piora ao ficar muito tempo sentada.",
            "duration": "3 anos",
            "severity": 7,
            "current_medications": ["Paracetamol 750mg", "Ibuprofeno 400mg (SOS)"],
            "allergies": [],
            "medical_history": "Hérnia discal L4-L5 diagnosticada em 2023. Fisioterapia sem melhora significativa.",
        },
        "clinical_analysis": {
            "probable_conditions": [{"name": "Dor lombar crônica", "icd10": "M54.5", "confidence": "alto"}],
            "risk_level": "moderado",
            "recommended_exams": ["Ressonância magnética lombar", "Hemograma completo"],
            "red_flags": [],
        },
        "treatment_plan": {
            "cannabinoid_ratio": "20:1 CBD:THC",
            "suggested_dosage": "25mg CBD 2x/dia",
            "administration_route": "sublingual",
            "monitoring_plan": "Retorno em 15 dias para avaliação de resposta",
            "precautions": ["Não dirigir nas primeiras 2 semanas", "Monitorar sonolência"],
        },
        "scientific_report": {
            "summary": "Evidências de nível moderado suportam o uso de CBD para dor crônica lombar, com redução média de 30% na escala VAS.",
            "supporting_evidence": [
                "CBD demonstrou eficácia em reduzir dor neuropática em ensaio clínico randomizado (n=128)",
                "Perfil de segurança favorável comparado a opioides em uso prolongado",
            ],
            "references": ["Häuser et al., 2018 - Systematic review of cannabis for pain", "Aviram & Samuelly-Leichtag, 2017 - Efficacy of Cannabis-Based Medicines"],
        },
        "rag_chunks_used": 5,
        "report_model": "gpt-4o-mini",
    },
    {
        "patient_name": "Ana Clara Menezes",
        "phone": "5562991003003",
        "status": "revisado",
        "anamnesis_data": {
            "chief_complaint": "Ansiedade generalizada severa",
            "symptoms": "Crises de ansiedade diárias, insônia, taquicardia, sudorese. Dificuldade de concentração no trabalho.",
            "duration": "2 anos",
            "severity": 8,
            "current_medications": ["Escitalopram 10mg", "Clonazepam 0.5mg (SOS)"],
            "allergies": ["Dipirona"],
            "medical_history": "TAG diagnosticado em 2024. Acompanhamento psiquiátrico regular. Tentativa prévia com sertralina sem sucesso.",
        },
        "clinical_analysis": {
            "probable_conditions": [
                {"name": "Transtorno de ansiedade generalizada", "icd10": "F41.1", "confidence": "alto"},
                {"name": "Insônia associada", "icd10": "G47.0", "confidence": "moderado"},
            ],
            "risk_level": "moderado",
            "recommended_exams": ["TSH", "Hemograma", "Perfil hepático"],
            "red_flags": ["Ideação suicida deve ser monitorada"],
        },
        "treatment_plan": {
            "cannabinoid_ratio": "10:1 CBD:THC",
            "suggested_dosage": "15mg CBD 3x/dia",
            "administration_route": "sublingual",
            "monitoring_plan": "Retorno em 10 dias. Escala HAM-A semanal.",
            "precautions": ["Manter acompanhamento psiquiátrico", "Não suspender medicação atual abruptamente"],
        },
        "scientific_report": {
            "summary": "CBD apresenta propriedades ansiolíticas em doses moderadas (15-50mg/dia), com mecanismo via receptores 5-HT1A.",
            "supporting_evidence": [
                "Estudo duplo-cego mostrou redução de 40% nos escores de ansiedade com CBD 300mg em simulação de fala pública",
                "Revisão sistemática de 2020 apoia uso de CBD como adjuvante para TAG",
            ],
            "references": ["Zuardi et al., 2017 - CBD for anxiety disorders", "Blessing et al., 2015 - CBD as potential treatment for anxiety"],
        },
        "rag_chunks_used": 7,
        "report_model": "gemini-pro",
    },
    {
        "patient_name": "Lucas Gabriel Ferreira",
        "phone": "5562991008008",
        "status": "pendente",
        "anamnesis_data": {
            "chief_complaint": "Epilepsia refratária",
            "symptoms": "Crises convulsivas tônico-clônicas, 3-4 vezes por semana, apesar de medicação antiepiléptica dupla.",
            "duration": "8 anos",
            "severity": 9,
            "current_medications": ["Valproato de sódio 500mg 2x/dia", "Levetiracetam 1000mg 2x/dia"],
            "allergies": [],
            "medical_history": "Epilepsia diagnosticada aos 14 anos. Refratária a 3 esquemas medicamentosos. Sem indicação cirúrgica.",
        },
        "clinical_analysis": {
            "probable_conditions": [{"name": "Epilepsia refratária", "icd10": "G40.3", "confidence": "alto"}],
            "risk_level": "alto",
            "recommended_exams": ["EEG", "Nível sérico de antiepilépticos", "Ressonância magnética encefálica"],
            "red_flags": ["Risco de status epilepticus", "Interação com valproato requer monitoramento hepático"],
        },
        "treatment_plan": {
            "cannabinoid_ratio": "25:1 CBD:THC",
            "suggested_dosage": "50mg CBD 2x/dia (titulação gradual)",
            "administration_route": "oral",
            "monitoring_plan": "Retorno semanal no primeiro mês. Dosagem de nível sérico antiepiléptico.",
            "precautions": ["Titulação lenta: iniciar com 10mg/dia", "Monitorar função hepática", "Nunca suspender antiepilépticos sem orientação"],
        },
        "scientific_report": {
            "summary": "Epidiolex (CBD purificado) é aprovado pela FDA para epilepsia refratária, com redução de 39% na frequência de crises.",
            "supporting_evidence": [
                "Ensaio clínico fase III com Epidiolex demonstrou redução significativa de crises em Dravet e Lennox-Gastaut",
                "Meta-análise de 2018 confirma eficácia do CBD como terapia adjuvante em epilepsia farmacorresistente",
            ],
            "references": ["Devinsky et al., 2017 - Trial of CBD for Drug-Resistant Seizures", "Lattanzi et al., 2018 - Efficacy and safety of CBD in epilepsy"],
        },
        "rag_chunks_used": 8,
        "report_model": "gpt-4o-mini",
    },
    {
        "patient_name": "Roberto Carlos Araujo",
        "phone": "5562991010010",
        "status": "revisado",
        "anamnesis_data": {
            "chief_complaint": "Fibromialgia com dor difusa",
            "symptoms": "Dor muscular generalizada, fadiga extrema, sono não reparador, pontos dolorosos em 14 de 18 tender points.",
            "duration": "5 anos",
            "severity": 8,
            "current_medications": ["Duloxetina 60mg", "Pregabalina 75mg 2x/dia", "Tramadol 50mg (SOS)"],
            "allergies": ["Codeína"],
            "medical_history": "Fibromialgia diagnosticada em 2021. Tentativas prévias com amitriptilina e ciclobenzaprina.",
        },
        "clinical_analysis": {
            "probable_conditions": [
                {"name": "Fibromialgia", "icd10": "M79.7", "confidence": "alto"},
                {"name": "Síndrome da fadiga crônica", "icd10": "G93.3", "confidence": "moderado"},
            ],
            "risk_level": "moderado",
            "recommended_exams": ["Vitamina D", "Ferritina", "PCR"],
            "red_flags": [],
        },
        "treatment_plan": {
            "cannabinoid_ratio": "15:1 CBD:THC",
            "suggested_dosage": "30mg CBD + 2mg THC 2x/dia",
            "administration_route": "sublingual",
            "monitoring_plan": "Retorno em 21 dias. Aplicar FIQ (Fibromyalgia Impact Questionnaire).",
            "precautions": ["Reduzir tramadol gradualmente", "Monitorar interação com pregabalina"],
        },
        "scientific_report": {
            "summary": "Canabinoides combinados CBD:THC mostram resultados promissores na fibromialgia, com melhora em dor, sono e qualidade de vida.",
            "supporting_evidence": [
                "Estudo observacional com 367 pacientes mostrou melhora de 50% na dor após 6 meses de tratamento canabinoide",
                "Nabilona (análogo THC) demonstrou superioridade ao placebo em melhora do sono na fibromialgia",
            ],
            "references": ["Sagy et al., 2019 - Safety and efficacy of medical cannabis in fibromyalgia", "Walitt et al., 2016 - Cannabinoids for fibromyalgia (Cochrane)"],
        },
        "rag_chunks_used": 6,
        "report_model": "gemini-pro",
    },
    {
        "patient_name": "Thiago Mendes Vieira",
        "phone": "5562991014014",
        "status": "pendente",
        "anamnesis_data": {
            "chief_complaint": "Insônia crônica grave",
            "symptoms": "Dificuldade para iniciar o sono, despertar frequente durante a noite, sono total de 3-4 horas por noite.",
            "duration": "4 anos",
            "severity": 7,
            "current_medications": ["Zolpidem 10mg"],
            "allergies": [],
            "medical_history": "Insônia crônica. Higiene do sono implementada sem melhora. Resistência a benzodiazepínicos.",
        },
        "clinical_analysis": {
            "probable_conditions": [{"name": "Insônia crônica", "icd10": "G47.0", "confidence": "alto"}],
            "risk_level": "baixo",
            "recommended_exams": ["Polissonografia", "TSH"],
            "red_flags": [],
        },
        "treatment_plan": {
            "cannabinoid_ratio": "5:1 CBD:THC",
            "suggested_dosage": "10mg CBD + 2mg THC 1x à noite",
            "administration_route": "sublingual",
            "monitoring_plan": "Retorno em 14 dias. Diário de sono.",
            "precautions": ["Não dirigir à noite", "Avaliar retirada gradual do zolpidem"],
        },
        "scientific_report": {
            "summary": "THC em baixas doses melhora a latência do sono, enquanto CBD reduz ansiedade pré-sono. Combinação sinérgica é recomendada.",
            "supporting_evidence": [
                "Revisão sistemática indica que THC reduz latência do sono em 15-30 minutos",
                "CBD em dose ansiolítica contribui para relaxamento pré-sono sem efeito rebote",
            ],
            "references": ["Suraev et al., 2020 - Cannabinoid therapies for insomnia", "Kesner & Lovinger, 2020 - Cannabinoids, sleep, and the endocannabinoid system"],
        },
        "rag_chunks_used": 4,
        "report_model": "gpt-4o-mini",
    },
    {
        "patient_name": "João Santos Costa",
        "phone": "5562991002002",
        "status": "revisado",
        "anamnesis_data": {
            "chief_complaint": "Dor neuropática pós-herpética",
            "symptoms": "Dor em queimação no tórax esquerdo após episódio de herpes zoster, alodinia ao toque leve.",
            "duration": "1 ano",
            "severity": 6,
            "current_medications": ["Gabapentina 300mg 3x/dia"],
            "allergies": [],
            "medical_history": "Herpes zoster em 2025. Neuralgia pós-herpética persistente. Imunossupressão por diabetes tipo 2.",
        },
        "clinical_analysis": {
            "probable_conditions": [{"name": "Neuralgia pós-herpética", "icd10": "B02.2", "confidence": "alto"}],
            "risk_level": "baixo",
            "recommended_exams": ["Glicemia de jejum", "HbA1c"],
            "red_flags": [],
        },
        "treatment_plan": {
            "cannabinoid_ratio": "20:1 CBD:THC",
            "suggested_dosage": "20mg CBD 2x/dia + creme tópico CBD na região afetada",
            "administration_route": "sublingual + tópico",
            "monitoring_plan": "Retorno em 21 dias. Escala de dor neuropática DN4.",
            "precautions": ["Monitorar glicemia", "Aplicar tópico com luvas"],
        },
        "scientific_report": {
            "summary": "CBD tópico e sistêmico apresenta potencial analgésico em dor neuropática, com ação anti-inflamatória via receptores TRPV1.",
            "supporting_evidence": [
                "Estudo piloto com CBD tópico em neuropatia periférica mostrou redução de 29% na dor",
                "Mecanismo TRPV1 de CBD é relevante para dessensibilização de fibras nociceptivas",
            ],
            "references": ["Xu et al., 2020 - Topical CBD for neuropathic pain", "Mlost et al., 2020 - CBD and pain modulation"],
        },
        "rag_chunks_used": 4,
        "report_model": "gpt-4o-mini",
    },
    {
        "patient_name": "Beatriz Souza Martins",
        "phone": "5562991007007",
        "status": "pendente",
        "anamnesis_data": {
            "chief_complaint": "Enxaqueca crônica",
            "symptoms": "Crises de enxaqueca 15+ dias/mês, fotofobia, náusea, aura visual em 40% das crises.",
            "duration": "6 anos",
            "severity": 8,
            "current_medications": ["Topiramato 50mg 2x/dia", "Sumatriptano 50mg (crise)"],
            "allergies": ["AAS"],
            "medical_history": "Enxaqueca crônica com aura. Falha terapêutica com propranolol e amitriptilina. Botox em avaliação.",
        },
        "clinical_analysis": {
            "probable_conditions": [{"name": "Enxaqueca crônica com aura", "icd10": "G43.1", "confidence": "alto"}],
            "risk_level": "moderado",
            "recommended_exams": ["Angiotomografia cerebral", "Fundo de olho"],
            "red_flags": ["Aura prolongada (>60min) requer investigação adicional"],
        },
        "treatment_plan": {
            "cannabinoid_ratio": "20:1 CBD:THC",
            "suggested_dosage": "25mg CBD 2x/dia (profilático)",
            "administration_route": "sublingual",
            "monitoring_plan": "Retorno em 30 dias. Diário de cefaleia.",
            "precautions": ["Manter topiramato", "CBD pode potencializar efeito sedativo do topiramato"],
        },
        "scientific_report": {
            "summary": "Canabinoides podem modular a via serotoninérgica envolvida na enxaqueca. Estudos preliminares sugerem redução na frequência de crises.",
            "supporting_evidence": [
                "Estudo retrospectivo com 121 pacientes mostrou redução de 50% na frequência de enxaqueca com cannabis",
                "Sistema endocanabinoide está envolvido na modulação de dor trigeminovascular",
            ],
            "references": ["Rhyne et al., 2016 - Effects of medical marijuana on migraine frequency", "Baron, 2018 - Medicinal properties of cannabinoids for headache disorders"],
        },
        "rag_chunks_used": 3,
        "report_model": "gemini-pro",
    },
    {
        "patient_name": "Pedro Henrique Lima",
        "phone": "5562991004004",
        "status": "revisado",
        "anamnesis_data": {
            "chief_complaint": "TEPT com insônia e pesadelos recorrentes",
            "symptoms": "Pesadelos frequentes, hipervigilância, flashbacks, evitação social, insônia de manutenção.",
            "duration": "3 anos",
            "severity": 8,
            "current_medications": ["Sertralina 100mg", "Prazosina 2mg à noite"],
            "allergies": [],
            "medical_history": "TEPT diagnosticado após evento traumático em 2023. Acompanhamento com psicóloga (EMDR). Melhora parcial.",
        },
        "clinical_analysis": {
            "probable_conditions": [
                {"name": "Transtorno de estresse pós-traumático", "icd10": "F43.1", "confidence": "alto"},
                {"name": "Insônia secundária", "icd10": "G47.0", "confidence": "moderado"},
            ],
            "risk_level": "moderado",
            "recommended_exams": ["Avaliação psicológica completa", "Cortisol salivar"],
            "red_flags": ["Monitorar ideação suicida", "Avaliar uso de substâncias"],
        },
        "treatment_plan": {
            "cannabinoid_ratio": "10:1 CBD:THC",
            "suggested_dosage": "20mg CBD 2x/dia + 5mg CBD à noite",
            "administration_route": "sublingual",
            "monitoring_plan": "Retorno em 14 dias. PCL-5 (escala TEPT) mensal.",
            "precautions": ["Manter psicoterapia EMDR", "Não suspender sertralina", "CBD pode reduzir metabolismo da sertralina - monitorar"],
        },
        "scientific_report": {
            "summary": "CBD demonstra potencial em atenuar memórias traumáticas via modulação do sistema endocanabinoide na amígdala e hipocampo.",
            "supporting_evidence": [
                "Estudo piloto com 11 pacientes TEPT mostrou redução de 50% nos pesadelos com CBD",
                "CBD facilitou a extinção de memórias aversivas em modelos pré-clínicos",
            ],
            "references": ["Elms et al., 2019 - CBD for PTSD", "Bitencourt & Takahashi, 2018 - Cannabidiol as a therapeutic alternative for PTSD"],
        },
        "rag_chunks_used": 6,
        "report_model": "gpt-4o-mini",
    },
]


def seed_anamnesis_reports():
    print("\n=== 3. Anamnesis Reports (8) ===")
    with db_cursor(dictionary=True) as (conn, cursor):
        if not _table_exists(cursor, "anamnesis_reports"):
            print("  SKIP: tabela anamnesis_reports nao existe")
            return

        for r in ANAMNESIS_REPORTS:
            pid = _pid(r["patient_name"])
            cursor.execute(
                "SELECT id FROM anamnesis_reports WHERE clinic_id = %s AND patient_name = %s AND phone = %s LIMIT 1",
                (CLINIC_ID, r["patient_name"], r["phone"]),
            )
            if cursor.fetchone():
                print(f"  Report para '{r['patient_name']}' ja existe")
                continue

            cursor.execute(
                """
                INSERT INTO anamnesis_reports
                    (clinic_id, patient_id, patient_name, phone, status,
                     anamnesis_data, clinical_analysis, treatment_plan, scientific_report,
                     rag_chunks_used, report_model)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    CLINIC_ID, pid, r["patient_name"], r["phone"], r["status"],
                    json.dumps(r["anamnesis_data"]),
                    json.dumps(r["clinical_analysis"]),
                    json.dumps(r["treatment_plan"]),
                    json.dumps(r["scientific_report"]),
                    r["rag_chunks_used"],
                    r["report_model"],
                ),
            )
            print(f"  Criado report para '{r['patient_name']}' (status={r['status']})")
        conn.commit()


# ---------------------------------------------------------------------------
# 4. Appointments (10)
# ---------------------------------------------------------------------------

def seed_appointments():
    print("\n=== 4. Agendamentos (10) ===")
    appointments = [
        {"patient": "Maria Oliveira Silva", "days": -25, "hour": 9, "status": "Realizada"},
        {"patient": "Ana Clara Menezes", "days": -18, "hour": 10, "status": "Realizada"},
        {"patient": "João Santos Costa", "days": -12, "hour": 14, "status": "Realizada"},
        {"patient": "Pedro Henrique Lima", "days": -5, "hour": 11, "status": "Cancelada"},
        {"patient": "Roberto Carlos Araujo", "days": -2, "hour": 15, "status": "Realizada"},
        {"patient": "Fernanda Alves Rocha", "days": 3, "hour": 9, "status": "Confirmada"},
        {"patient": "Beatriz Souza Martins", "days": 7, "hour": 10, "status": "Agendada"},
        {"patient": "Lucas Gabriel Ferreira", "days": 14, "hour": 14, "status": "Agendada"},
        {"patient": "Thiago Mendes Vieira", "days": 21, "hour": 11, "status": "Agendada"},
        {"patient": "Camila Torres Santos", "days": 28, "hour": 16, "status": "Confirmada"},
    ]

    with db_cursor(dictionary=True) as (conn, cursor):
        for a in appointments:
            pid = _pid(a["patient"])
            if not pid:
                print(f"  SKIP: paciente '{a['patient']}' nao encontrado")
                continue

            appt_date = (_now() + timedelta(days=a["days"])).replace(
                hour=a["hour"], minute=0, second=0, microsecond=0
            )

            cursor.execute(
                "SELECT id FROM appointments WHERE clinic_id = %s AND patient_id = %s AND appointment_date = %s LIMIT 1",
                (CLINIC_ID, pid, appt_date),
            )
            if cursor.fetchone():
                print(f"  Agendamento para '{a['patient']}' ja existe")
                continue

            cursor.execute(
                """
                INSERT INTO appointments (clinic_id, patient_id, appointment_date, status)
                VALUES (%s, %s, %s, %s)
                """,
                (CLINIC_ID, pid, appt_date, a["status"]),
            )
            print(f"  Agendamento: {a['patient']} em {appt_date.strftime('%d/%m/%Y %H:%M')} ({a['status']})")
        conn.commit()


# ---------------------------------------------------------------------------
# 5. Incoming Messages (30)
# ---------------------------------------------------------------------------

def seed_incoming_messages():
    print("\n=== 5. Mensagens recebidas (30) ===")

    messages = [
        ("5562991001001", "Maria Oliveira Silva", "Bom dia doutor, gostaria de agendar minha consulta de retorno.", -7, "08:30"),
        ("5562991001001", "Maria Oliveira Silva", "Estou sentindo melhora na dor lombar com o óleo de CBD.", -6, "14:20"),
        ("5562991001001", "Maria Oliveira Silva", "A dose de 25mg está sendo suficiente. Obrigada!", -5, "09:15"),
        ("5562991003003", "Ana Clara Menezes", "Doutor, tive uma crise de ansiedade ontem à noite.", -7, "07:45"),
        ("5562991003003", "Ana Clara Menezes", "O CBD está ajudando durante o dia, mas à noite ainda é difícil.", -6, "20:30"),
        ("5562991003003", "Ana Clara Menezes", "Posso aumentar a dose noturna?", -5, "21:00"),
        ("5562991003003", "Ana Clara Menezes", "Entendi, vou manter a dose e anotar no diário. Obrigada.", -4, "10:15"),
        ("5562991002002", "João Santos Costa", "Boa tarde, a dor no tórax melhorou com o creme tópico.", -6, "15:30"),
        ("5562991002002", "João Santos Costa", "Estou aplicando 2x ao dia como orientado.", -5, "16:00"),
        ("5562991002002", "João Santos Costa", "Minha glicemia está controlada, fiz exame ontem.", -3, "11:20"),
        ("5562991004004", "Pedro Henrique Lima", "Doutor, os pesadelos diminuíram bastante essa semana.", -5, "08:00"),
        ("5562991004004", "Pedro Henrique Lima", "Estou dormindo melhor e a terapeuta notou melhora.", -3, "09:30"),
        ("5562991005005", "Fernanda Alves Rocha", "Olá, gostaria de informações sobre tratamento com cannabis.", -7, "10:00"),
        ("5562991005005", "Fernanda Alves Rocha", "Sofro de artrite reumatóide há 8 anos.", -7, "10:02"),
        ("5562991005005", "Fernanda Alves Rocha", "Já tentei vários medicamentos sem sucesso.", -7, "10:05"),
        ("5562991005005", "Fernanda Alves Rocha", "Obrigada pelas informações, vou agendar.", -6, "14:30"),
        ("5562991008008", "Lucas Gabriel Ferreira", "Doutor, tive 2 crises essa semana, menos que antes.", -4, "07:00"),
        ("5562991008008", "Lucas Gabriel Ferreira", "A titulação está em 30mg agora. Quando aumento?", -3, "08:15"),
        ("5562991008008", "Lucas Gabriel Ferreira", "Ok, manterei 30mg mais uma semana. Obrigado.", -2, "09:00"),
        ("5562991010010", "Roberto Carlos Araujo", "A dor muscular melhorou 40% desde que comecei o tratamento.", -5, "16:45"),
        ("5562991010010", "Roberto Carlos Araujo", "Consegui reduzir o tramadol para 1x/dia.", -3, "17:00"),
        ("5562991010010", "Roberto Carlos Araujo", "Estou mais disposto e dormindo melhor.", -1, "14:30"),
        ("5562991007007", "Beatriz Souza Martins", "Boa noite, tive 8 crises de enxaqueca esse mês.", -4, "19:30"),
        ("5562991007007", "Beatriz Souza Martins", "É menos que o mês passado que foram 12.", -4, "19:32"),
        ("5562991007007", "Beatriz Souza Martins", "Quando posso aumentar a dose do CBD?", -3, "10:00"),
        ("5562991014014", "Thiago Mendes Vieira", "Doutor, estou dormindo 5 horas agora! Antes eram só 3.", -3, "22:00"),
        ("5562991014014", "Thiago Mendes Vieira", "A combinação CBD+THC à noite está fazendo diferença.", -2, "21:30"),
        ("5562991011011", "Camila Torres Santos", "Olá, gostaria de iniciar tratamento para dor crônica.", -2, "13:00"),
        ("5562991012012", "Rafael Oliveira Gomes", "Boa tarde, tenho esclerose múltipla e me indicaram cannabis.", -1, "15:00"),
        ("5562991012012", "Rafael Oliveira Gomes", "Posso enviar meus exames por aqui?", -1, "15:05"),
    ]

    with db_cursor(dictionary=True) as (conn, cursor):
        for phone, name, text, days_offset, time_str in messages:
            ts_dt = _days_ago(-days_offset).replace(
                hour=int(time_str.split(":")[0]),
                minute=int(time_str.split(":")[1]),
                second=0, microsecond=0,
            )
            ts = str(int(ts_dt.timestamp()))

            # Check by sender + timestamp to avoid duplicates
            cursor.execute(
                "SELECT id FROM incoming_messages WHERE clinic_id = %s AND sender = %s AND timestamp = %s LIMIT 1",
                (CLINIC_ID, phone, ts),
            )
            if cursor.fetchone():
                continue

            cursor.execute(
                """
                INSERT INTO incoming_messages (clinic_id, sender, contact_name, message_text, timestamp)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (CLINIC_ID, phone, name, text, ts),
            )
        conn.commit()
    print(f"  Inseridas ate 30 mensagens de WhatsApp")


# ---------------------------------------------------------------------------
# 6. Treatment Plans (5)
# ---------------------------------------------------------------------------

def seed_treatment_plans():
    print("\n=== 6. Planos de Tratamento (5) ===")

    plans = [
        {
            "patient": "Maria Oliveira Silva",
            "plan_name": "Protocolo Dor Crônica",
            "plan_description": "Protocolo para manejo de dor lombar crônica com CBD em dose moderada.",
            "cbd_thc_ratio": "20:1",
            "dosage": "25mg CBD 2x/dia",
            "frequency": "2x ao dia",
            "route": "sublingual",
            "schedule": [
                {"period": "manhã", "dose": "25mg CBD", "taken": True},
                {"period": "noite", "dose": "25mg CBD", "taken": True},
            ],
            "precautions": ["Não dirigir nas primeiras 2 semanas", "Monitorar sonolência"],
            "adjustment_history": [
                {"date": "2026-03-01", "change": "Iniciou com 15mg CBD 2x/dia", "reason": "Dose inicial conservadora"},
                {"date": "2026-03-15", "change": "Aumentou para 25mg CBD 2x/dia", "reason": "Resposta parcial após 14 dias"},
            ],
            "next_return_date": _days_ahead(10),
        },
        {
            "patient": "Ana Clara Menezes",
            "plan_name": "Protocolo Ansiedade",
            "plan_description": "Protocolo para TAG com CBD como adjuvante ansiolítico.",
            "cbd_thc_ratio": "10:1",
            "dosage": "15mg CBD 3x/dia",
            "frequency": "3x ao dia",
            "route": "sublingual",
            "schedule": [
                {"period": "manhã", "dose": "15mg CBD", "taken": True},
                {"period": "tarde", "dose": "15mg CBD", "taken": False},
                {"period": "noite", "dose": "15mg CBD", "taken": True},
            ],
            "precautions": ["Manter acompanhamento psiquiátrico", "Não suspender escitalopram"],
            "adjustment_history": [
                {"date": "2026-03-10", "change": "Iniciou com 10mg CBD 2x/dia", "reason": "Início gradual"},
                {"date": "2026-03-24", "change": "Aumentou para 15mg CBD 3x/dia", "reason": "Boa tolerância, necessidade de cobertura diurna"},
            ],
            "next_return_date": _days_ahead(5),
        },
        {
            "patient": "Thiago Mendes Vieira",
            "plan_name": "Protocolo Insônia",
            "plan_description": "Protocolo para insônia crônica com combinação CBD:THC noturna.",
            "cbd_thc_ratio": "5:1",
            "dosage": "10mg CBD + 2mg THC 1x à noite",
            "frequency": "1x à noite",
            "route": "sublingual",
            "schedule": [
                {"period": "noite (30min antes de dormir)", "dose": "10mg CBD + 2mg THC", "taken": True},
            ],
            "precautions": ["Não dirigir à noite", "Avaliar retirada gradual do zolpidem"],
            "adjustment_history": [
                {"date": "2026-03-05", "change": "Iniciou com 5mg CBD + 1mg THC", "reason": "Dose inicial baixa por ser primeira vez com THC"},
                {"date": "2026-03-19", "change": "Aumentou para 10mg CBD + 2mg THC", "reason": "Tolerância boa, sono melhorou mas ainda insuficiente"},
            ],
            "next_return_date": _days_ahead(14),
        },
        {
            "patient": "Lucas Gabriel Ferreira",
            "plan_name": "Protocolo Epilepsia",
            "plan_description": "Protocolo de CBD em alta dose como adjuvante para epilepsia refratária.",
            "cbd_thc_ratio": "25:1",
            "dosage": "50mg CBD 2x/dia (titulação gradual)",
            "frequency": "2x ao dia",
            "route": "oral",
            "schedule": [
                {"period": "manhã", "dose": "50mg CBD", "taken": True},
                {"period": "noite", "dose": "50mg CBD", "taken": True},
            ],
            "precautions": ["Titulação lenta", "Monitorar função hepática", "Nunca suspender antiepilépticos"],
            "adjustment_history": [
                {"date": "2026-02-15", "change": "Iniciou com 10mg CBD 2x/dia", "reason": "Protocolo de titulação Epidiolex-like"},
                {"date": "2026-03-01", "change": "Aumentou para 25mg CBD 2x/dia", "reason": "Sem efeitos adversos, redução parcial de crises"},
                {"date": "2026-03-20", "change": "Aumentou para 50mg CBD 2x/dia", "reason": "Dose-alvo atingida, crises reduzidas em 50%"},
            ],
            "next_return_date": _days_ahead(7),
        },
        {
            "patient": "Roberto Carlos Araujo",
            "plan_name": "Protocolo Fibromialgia",
            "plan_description": "Protocolo multimodal para fibromialgia com CBD:THC combinado.",
            "cbd_thc_ratio": "15:1",
            "dosage": "30mg CBD + 2mg THC 2x/dia",
            "frequency": "2x ao dia",
            "route": "sublingual",
            "schedule": [
                {"period": "manhã", "dose": "30mg CBD + 2mg THC", "taken": True},
                {"period": "noite", "dose": "30mg CBD + 2mg THC", "taken": False},
            ],
            "precautions": ["Reduzir tramadol gradualmente", "Monitorar interação com pregabalina"],
            "adjustment_history": [
                {"date": "2026-03-01", "change": "Iniciou com 15mg CBD 2x/dia", "reason": "CBD isolado para avaliar tolerância"},
                {"date": "2026-03-15", "change": "Adicionou 2mg THC por dose", "reason": "Necessidade de componente analgésico adicional"},
                {"date": "2026-03-28", "change": "Aumentou CBD para 30mg por dose", "reason": "Boa tolerância, dor ainda presente"},
            ],
            "next_return_date": _days_ahead(21),
        },
    ]

    with db_cursor(dictionary=True) as (conn, cursor):
        for plan in plans:
            pid = _pid(plan["patient"])
            if not pid:
                print(f"  SKIP: paciente '{plan['patient']}' nao encontrado")
                continue

            cursor.execute(
                "SELECT id FROM treatment_plans WHERE clinic_id = %s AND patient_id = %s AND plan_name = %s LIMIT 1",
                (CLINIC_ID, pid, plan["plan_name"]),
            )
            if cursor.fetchone():
                print(f"  Plano '{plan['plan_name']}' ja existe")
                continue

            cursor.execute(
                """
                INSERT INTO treatment_plans
                    (clinic_id, patient_id, plan_description, plan_name, status,
                     cbd_thc_ratio, dosage, frequency, route,
                     schedule, precautions, adjustment_history, next_return_date)
                VALUES (%s, %s, %s, %s, 'ativo', %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    CLINIC_ID, pid, plan["plan_description"], plan["plan_name"],
                    plan["cbd_thc_ratio"], plan["dosage"], plan["frequency"], plan["route"],
                    json.dumps(plan["schedule"]),
                    json.dumps(plan["precautions"]),
                    json.dumps(plan["adjustment_history"]),
                    plan["next_return_date"],
                ),
            )
            print(f"  Criado plano '{plan['plan_name']}' para {plan['patient']}")
        conn.commit()


# ---------------------------------------------------------------------------
# 7. Prescriptions (4)
# ---------------------------------------------------------------------------

def seed_prescriptions():
    print("\n=== 7. Prescrições (4) ===")

    prescriptions = [
        {
            "patient": "Maria Oliveira Silva",
            "doctor_name": "Dr. Carlos Alberto Mendes",
            "doctor_crm": "CRM/GO 12345",
            "cannabinoid_ratio": "20:1 CBD:THC",
            "spectrum": "full_spectrum",
            "administration_route": "sublingual",
            "concentration_mg_ml": 50.0,
            "max_daily_mg": 50.0,
            "titration_protocol": [
                {"week": 1, "dose_mg": 15, "frequency": "2x/dia"},
                {"week": 2, "dose_mg": 20, "frequency": "2x/dia"},
                {"week": 3, "dose_mg": 25, "frequency": "2x/dia"},
            ],
            "clinical_rationale": "Dor lombar crônica refratária a analgésicos convencionais. CBD full spectrum para efeito entourage.",
            "contraindications": ["Gestação", "Hepatopatia grave"],
            "drug_interactions": ["Paracetamol: interação mínima"],
            "monitoring_checkpoints": [
                {"day": 7, "action": "Avaliar tolerância e efeitos adversos"},
                {"day": 14, "action": "Escala VAS + ajuste de dose"},
                {"day": 30, "action": "Reavaliação completa"},
            ],
            "confidence_score": 0.85,
            "evidence_sources": ["Häuser et al., 2018", "Aviram & Samuelly-Leichtag, 2017"],
            "safety_limits": {"max_single_dose_mg": 30, "max_daily_mg": 60},
            "custom_notes": "Paciente responsiva ao tratamento. Manter protocolo.",
            "validity_days": 180,
        },
        {
            "patient": "Ana Clara Menezes",
            "doctor_name": "Dr. Carlos Alberto Mendes",
            "doctor_crm": "CRM/GO 12345",
            "cannabinoid_ratio": "10:1 CBD:THC",
            "spectrum": "broad_spectrum",
            "administration_route": "sublingual",
            "concentration_mg_ml": 30.0,
            "max_daily_mg": 45.0,
            "titration_protocol": [
                {"week": 1, "dose_mg": 10, "frequency": "2x/dia"},
                {"week": 2, "dose_mg": 10, "frequency": "3x/dia"},
                {"week": 3, "dose_mg": 15, "frequency": "3x/dia"},
            ],
            "clinical_rationale": "TAG severo com insônia associada. CBD como adjuvante ansiolítico ao escitalopram.",
            "contraindications": ["Insuficiência hepática"],
            "drug_interactions": ["Escitalopram: CBD pode aumentar nível sérico - monitorar", "Clonazepam: potencialização sedativa"],
            "monitoring_checkpoints": [
                {"day": 7, "action": "Avaliar ansiedade e sono"},
                {"day": 14, "action": "HAM-A + ajuste"},
                {"day": 30, "action": "Reavaliar necessidade de clonazepam"},
            ],
            "confidence_score": 0.78,
            "evidence_sources": ["Zuardi et al., 2017", "Blessing et al., 2015"],
            "safety_limits": {"max_single_dose_mg": 20, "max_daily_mg": 50},
            "custom_notes": "Manter psicoterapia concomitante. Avaliar retirada gradual de benzo.",
            "validity_days": 180,
        },
        {
            "patient": "Lucas Gabriel Ferreira",
            "doctor_name": "Dr. Carlos Alberto Mendes",
            "doctor_crm": "CRM/GO 12345",
            "cannabinoid_ratio": "25:1 CBD:THC",
            "spectrum": "isolate",
            "administration_route": "oral",
            "concentration_mg_ml": 100.0,
            "max_daily_mg": 100.0,
            "titration_protocol": [
                {"week": 1, "dose_mg": 10, "frequency": "2x/dia"},
                {"week": 2, "dose_mg": 20, "frequency": "2x/dia"},
                {"week": 3, "dose_mg": 30, "frequency": "2x/dia"},
                {"week": 4, "dose_mg": 50, "frequency": "2x/dia"},
            ],
            "clinical_rationale": "Epilepsia refratária a 3 esquemas. CBD baseado em protocolo Epidiolex.",
            "contraindications": ["Hepatopatia", "Uso concomitante de clobazam em altas doses"],
            "drug_interactions": ["Valproato: risco hepatotóxico aumentado - monitorar ALT/AST", "Levetiracetam: interação mínima"],
            "monitoring_checkpoints": [
                {"day": 7, "action": "TGO/TGP + tolerância"},
                {"day": 14, "action": "Nível sérico antiepiléptico"},
                {"day": 30, "action": "EEG + reavaliação de crises"},
            ],
            "confidence_score": 0.92,
            "evidence_sources": ["Devinsky et al., 2017", "Lattanzi et al., 2018"],
            "safety_limits": {"max_single_dose_mg": 60, "max_daily_mg": 120},
            "custom_notes": "Protocolo de epilepsia refratária - requer acompanhamento semanal no primeiro mês.",
            "validity_days": 90,
        },
        {
            "patient": "Roberto Carlos Araujo",
            "doctor_name": "Dr. Carlos Alberto Mendes",
            "doctor_crm": "CRM/GO 12345",
            "cannabinoid_ratio": "15:1 CBD:THC",
            "spectrum": "full_spectrum",
            "administration_route": "sublingual",
            "concentration_mg_ml": 40.0,
            "max_daily_mg": 64.0,
            "titration_protocol": [
                {"week": 1, "dose_mg": 15, "frequency": "2x/dia"},
                {"week": 2, "dose_mg": 20, "frequency": "2x/dia"},
                {"week": 3, "dose_mg": 30, "frequency": "2x/dia", "note": "Adicionar 2mg THC por dose"},
            ],
            "clinical_rationale": "Fibromialgia refratária. CBD:THC combinado para dor e sono. Objetivo: reduzir tramadol.",
            "contraindications": ["Alergia a codeína (precaução com THC)"],
            "drug_interactions": ["Pregabalina: potencialização de tontura - iniciar dose baixa", "Duloxetina: monitorar síndrome serotoninérgica"],
            "monitoring_checkpoints": [
                {"day": 14, "action": "FIQ + avaliar redução de tramadol"},
                {"day": 30, "action": "Reavaliação completa + exames laboratoriais"},
            ],
            "confidence_score": 0.75,
            "evidence_sources": ["Sagy et al., 2019", "Walitt et al., 2016"],
            "safety_limits": {"max_single_dose_mg": 35, "max_daily_mg": 70, "max_thc_daily_mg": 10},
            "custom_notes": "Paciente relatou alergia a codeína. THC em baixa dose parece ser bem tolerado.",
            "validity_days": 180,
        },
    ]

    with db_cursor(dictionary=True) as (conn, cursor):
        if not _table_exists(cursor, "prescriptions"):
            print("  SKIP: tabela prescriptions nao existe")
            return

        for rx in prescriptions:
            pid = _pid(rx["patient"])
            if not pid:
                print(f"  SKIP: paciente '{rx['patient']}' nao encontrado")
                continue

            cursor.execute(
                "SELECT id FROM prescriptions WHERE clinic_id = %s AND patient_id = %s AND cannabinoid_ratio = %s LIMIT 1",
                (CLINIC_ID, pid, rx["cannabinoid_ratio"]),
            )
            if cursor.fetchone():
                print(f"  Prescricao para '{rx['patient']}' ja existe")
                continue

            cursor.execute(
                """
                INSERT INTO prescriptions
                    (clinic_id, patient_id, doctor_user_id, doctor_name, doctor_crm,
                     cannabinoid_ratio, spectrum, administration_route,
                     concentration_mg_ml, max_daily_mg,
                     titration_protocol, clinical_rationale,
                     contraindications, drug_interactions, monitoring_checkpoints,
                     confidence_score, evidence_sources, safety_limits,
                     custom_notes, validity_days, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active')
                """,
                (
                    CLINIC_ID, pid, 6, rx["doctor_name"], rx["doctor_crm"],  # medico user_id=6
                    rx["cannabinoid_ratio"], rx["spectrum"], rx["administration_route"],
                    rx["concentration_mg_ml"], rx["max_daily_mg"],
                    json.dumps(rx["titration_protocol"]), rx["clinical_rationale"],
                    json.dumps(rx["contraindications"]), json.dumps(rx["drug_interactions"]),
                    json.dumps(rx["monitoring_checkpoints"]),
                    rx["confidence_score"], json.dumps(rx["evidence_sources"]),
                    json.dumps(rx["safety_limits"]),
                    rx["custom_notes"], rx["validity_days"],
                ),
            )
            print(f"  Prescricao para '{rx['patient']}' criada")
        conn.commit()


# ---------------------------------------------------------------------------
# 8. Campaign Templates (3)
# ---------------------------------------------------------------------------

def seed_campaign_templates():
    print("\n=== 8. Campaign Templates (3) ===")

    templates = [
        {
            "name": "Lembrete de Retorno",
            "description": "Lembra o paciente sobre a data da próxima consulta de retorno.",
            "channel": "whatsapp",
            "template_body": "Olá {{patient_name}}! 🌿 Lembrete: sua consulta de retorno está agendada para {{appointment_date}}. Confirme respondendo SIM. Clínica Cannab'IA.",
            "variables": ["patient_name", "appointment_date"],
            "status": "active",
        },
        {
            "name": "Pesquisa de Satisfação",
            "description": "Envia pesquisa NPS após consulta realizada.",
            "channel": "whatsapp",
            "template_body": "Olá {{patient_name}}! Como foi sua experiência na última consulta? De 0 a 10, quanto você recomendaria a Clínica Cannab'IA? Responda com o número. Obrigado!",
            "variables": ["patient_name"],
            "status": "active",
        },
        {
            "name": "Novidades do Tratamento",
            "description": "Newsletter mensal com novidades sobre cannabis medicinal.",
            "channel": "email",
            "template_body": "Prezado(a) {{patient_name}},\n\nConfira as novidades deste mês sobre cannabis medicinal:\n\n{{newsletter_content}}\n\nAtenciosamente,\nEquipe Clínica Cannab'IA",
            "variables": ["patient_name", "newsletter_content"],
            "status": "draft",
        },
    ]

    with db_cursor(dictionary=True) as (conn, cursor):
        if not _table_exists(cursor, "campaign_templates"):
            print("  SKIP: tabela campaign_templates nao existe")
            return

        # Ensure tenant exists
        global TENANT_ID
        if TENANT_ID is None:
            TENANT_ID = _get_tenant_id()
        if not TENANT_ID:
            print("  SKIP: tenant_id nao encontrado para clinic_id=1")
            return

        for t in templates:
            cursor.execute(
                "SELECT id FROM campaign_templates WHERE clinic_id = %s AND name = %s LIMIT 1",
                (CLINIC_ID, t["name"]),
            )
            if cursor.fetchone():
                print(f"  Template '{t['name']}' ja existe")
                continue

            cursor.execute(
                """
                INSERT INTO campaign_templates
                    (tenant_id, clinic_id, name, description, channel, template_body, variables, status, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    TENANT_ID, CLINIC_ID, t["name"], t["description"],
                    t["channel"], t["template_body"],
                    json.dumps(t["variables"]),
                    t["status"], 1,  # admin user
                ),
            )
            print(f"  Template '{t['name']}' criado ({t['channel']}, {t['status']})")
        conn.commit()


# ---------------------------------------------------------------------------
# 9. Stock Inventory (6)
# ---------------------------------------------------------------------------

def seed_stock_inventory():
    print("\n=== 9. Estoque (6 itens) ===")

    items = [
        {"product_name": "Óleo CBD Full Spectrum 3000mg", "batch_number": "FS3000-2026A", "quantity": 50, "unit": "frascos", "expiry_date": "2026-12-31", "status": "disponivel", "supplier": "Associação Brasileira de Cannabis Medicinal"},
        {"product_name": "Óleo CBD:THC 20:1 1500mg", "batch_number": "CT201-2026B", "quantity": 30, "unit": "frascos", "expiry_date": "2026-10-15", "status": "disponivel", "supplier": "HempMeds Brasil"},
        {"product_name": "Cápsula CBD 25mg", "batch_number": "CAP25-2026C", "quantity": 200, "unit": "unidades", "expiry_date": "2027-01-20", "status": "disponivel", "supplier": "Prati-Donaduzzi"},
        {"product_name": "Creme Tópico CBD 500mg", "batch_number": "TOP500-2026D", "quantity": 25, "unit": "tubos", "expiry_date": "2026-08-10", "status": "disponivel", "supplier": "Green Care Farmacêutica"},
        {"product_name": "Tintura CBD Isolado 1000mg", "batch_number": "ISO1000-2026E", "quantity": 15, "unit": "frascos", "expiry_date": "2026-06-15", "status": "proximo_vencimento", "supplier": "Ease Labs"},
        {"product_name": "Óleo THC:CBD 1:1 600mg", "batch_number": "TC11-2026F", "quantity": 8, "unit": "frascos", "expiry_date": "2026-11-30", "status": "estoque_baixo", "supplier": "Associação Brasileira de Cannabis Medicinal"},
    ]

    with db_cursor(dictionary=True) as (conn, cursor):
        if not _table_exists(cursor, "stock_inventory"):
            print("  SKIP: tabela stock_inventory nao existe")
            return

        for item in items:
            cursor.execute(
                "SELECT id FROM stock_inventory WHERE clinic_id = %s AND product_name = %s LIMIT 1",
                (CLINIC_ID, item["product_name"]),
            )
            if cursor.fetchone():
                print(f"  Item '{item['product_name']}' ja existe")
                continue

            cursor.execute(
                """
                INSERT INTO stock_inventory
                    (clinic_id, product_name, batch_number, quantity, unit, expiry_date, status, supplier)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    CLINIC_ID, item["product_name"], item["batch_number"],
                    item["quantity"], item["unit"], item["expiry_date"],
                    item["status"], item["supplier"],
                ),
            )
            print(f"  Estoque: {item['product_name']} ({item['quantity']} {item['unit']})")
        conn.commit()


# ---------------------------------------------------------------------------
# 9b. Stock Dispensations (5)
# ---------------------------------------------------------------------------

def seed_stock_dispensations():
    print("\n=== 9b. Dispensações de Estoque (5) ===")

    dispensations = [
        {"product_name": "Óleo CBD Full Spectrum 3000mg", "patient": "Maria Oliveira Silva", "quantity": 2, "notes": "Dispensação inicial - protocolo dor crônica lombar."},
        {"product_name": "Óleo CBD:THC 20:1 1500mg", "patient": "João Santos Costa", "quantity": 1, "notes": "Dispensação para dor neuropática pós-herpética."},
        {"product_name": "Cápsula CBD 25mg", "patient": "Ana Clara Menezes", "quantity": 60, "notes": "Cápsulas para 20 dias de tratamento ansiolítico (3x/dia)."},
        {"product_name": "Creme Tópico CBD 500mg", "patient": "João Santos Costa", "quantity": 1, "notes": "Creme tópico para aplicação na região torácica."},
        {"product_name": "Óleo CBD Full Spectrum 3000mg", "patient": "Roberto Carlos Araujo", "quantity": 1, "notes": "Dispensação para protocolo fibromialgia."},
    ]

    with db_cursor(dictionary=True) as (conn, cursor):
        if not _table_exists(cursor, "stock_dispensations"):
            print("  SKIP: tabela stock_dispensations nao existe")
            return

        if not _table_exists(cursor, "stock_inventory"):
            print("  SKIP: tabela stock_inventory nao existe (dependencia)")
            return

        for d in dispensations:
            pid = _pid(d["patient"])
            if not pid:
                print(f"  SKIP: paciente '{d['patient']}' nao encontrado")
                continue

            # Resolve stock_item_id
            cursor.execute(
                "SELECT id FROM stock_inventory WHERE clinic_id = %s AND product_name = %s LIMIT 1",
                (CLINIC_ID, d["product_name"]),
            )
            item_row = cursor.fetchone()
            if not item_row:
                print(f"  SKIP: produto '{d['product_name']}' nao encontrado no estoque")
                continue

            stock_item_id = item_row["id"]

            # Check for existing dispensation (idempotent)
            cursor.execute(
                "SELECT id FROM stock_dispensations WHERE clinic_id = %s AND stock_item_id = %s AND patient_id = %s AND notes = %s LIMIT 1",
                (CLINIC_ID, stock_item_id, pid, d["notes"]),
            )
            if cursor.fetchone():
                print(f"  Dispensacao '{d['product_name']}' -> '{d['patient']}' ja existe")
                continue

            cursor.execute(
                """
                INSERT INTO stock_dispensations
                    (clinic_id, stock_item_id, patient_id, quantity, dispensed_by, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (CLINIC_ID, stock_item_id, pid, d["quantity"], 7, d["notes"]),  # atendente user_id=7
            )
            print(f"  Dispensacao: {d['product_name']} -> {d['patient']} (qty={d['quantity']})")
        conn.commit()


# ---------------------------------------------------------------------------
# 10. Billing Records (7)
# ---------------------------------------------------------------------------

def seed_billing():
    print("\n=== 10. Faturamento (7 registros) ===")

    records = [
        {"patient": "Maria Oliveira Silva", "description": "Consulta inicial - Anamnese completa", "amount": 450.00, "status": "pago", "due_days": -45, "paid": True},
        {"patient": "Ana Clara Menezes", "description": "Consulta de retorno", "amount": 350.00, "status": "pago", "due_days": -30, "paid": True},
        {"patient": "João Santos Costa", "description": "Consulta inicial - Avaliação clínica", "amount": 450.00, "status": "pago", "due_days": -20, "paid": True},
        {"patient": "Pedro Henrique Lima", "description": "Consulta de retorno + ajuste de dosagem", "amount": 380.00, "status": "pendente", "due_days": -5, "paid": False},
        {"patient": "Lucas Gabriel Ferreira", "description": "Consulta especializada - Epilepsia", "amount": 550.00, "status": "pendente", "due_days": 10, "paid": False},
        {"patient": "Roberto Carlos Araujo", "description": "Consulta de retorno", "amount": 350.00, "status": "vencido", "due_days": -55, "paid": False},
        {"patient": "Beatriz Souza Martins", "description": "Primeira consulta - Enxaqueca crônica", "amount": 450.00, "status": "pendente", "due_days": 15, "paid": False},
    ]

    with db_cursor(dictionary=True) as (conn, cursor):
        if not _table_exists(cursor, "billing"):
            print("  SKIP: tabela billing nao existe")
            return

        for b in records:
            pid = _pid(b["patient"])
            if not pid:
                continue

            due = (_now() + timedelta(days=b["due_days"])).date()

            cursor.execute(
                "SELECT id FROM billing WHERE clinic_id = %s AND patient_id = %s AND description = %s LIMIT 1",
                (CLINIC_ID, pid, b["description"]),
            )
            if cursor.fetchone():
                print(f"  Faturamento para '{b['patient']}' ja existe")
                continue

            paid_at = (_now() + timedelta(days=b["due_days"] + 2)) if b["paid"] else None

            cursor.execute(
                """
                INSERT INTO billing (clinic_id, patient_id, description, amount, status, due_date, paid_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (CLINIC_ID, pid, b["description"], b["amount"], b["status"], due, paid_at),
            )
            print(f"  Faturamento: {b['patient']} - R${b['amount']:.2f} ({b['status']})")
        conn.commit()


# ---------------------------------------------------------------------------
# 11. Symptom Diary (30 entries over 30 days)
# ---------------------------------------------------------------------------

def seed_symptom_diary():
    print("\n=== 11. Diário de Sintomas (30 entradas, 30 dias) ===")

    with db_cursor(dictionary=True) as (conn, cursor):
        if not _table_exists(cursor, "symptom_diary"):
            print("  SKIP: tabela symptom_diary nao existe")
            return

        # Maria Oliveira - 14+ entries spread over 30 days (showing improvement)
        maria_id = _pid("Maria Oliveira Silva")
        ana_id = _pid("Ana Clara Menezes")

        entries = []

        if maria_id:
            # Maria: dor crônica lombar - 16 entries over 30 days (scores: overall 5-9, pain 2-6, sleep 5-8, mood bom/regular/otimo)
            # Days ago: spread across 30 days (not every day — realistic journaling)
            maria_days_ago =  [30, 28, 26, 24, 22, 20, 18, 16, 14, 12, 10,  8,  6,  4,  2,  1]
            maria_moods =     ["regular", "regular", "regular", "bom", "bom", "regular", "bom", "bom", "bom", "otimo", "bom", "otimo", "otimo", "otimo", "otimo", "otimo"]
            maria_pain =      [6, 6, 5, 5, 5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 3, 2]
            maria_sleep =     [5, 5, 5, 6, 6, 5, 6, 7, 7, 7, 7, 8, 7, 8, 7, 8]
            maria_overall =   [5, 5, 6, 6, 6, 5, 7, 7, 7, 8, 8, 8, 8, 9, 8, 9]

            maria_notes_map = {
                0: ("sonolencia", "Primeiro dia com óleo CBD. Senti sonolência leve."),
                2: ("boca_seca", "Boca seca leve durante a tarde."),
                4: ("sonolencia", "Sonolência após a dose da manhã, mas passou rápido."),
                5: ("", "Dia difícil, dor aumentou após esforço físico."),
                7: ("", "Adaptando bem ao tratamento. Menos dor ao sentar."),
                9: ("", "Melhor dia desde o início do tratamento!"),
                11: ("", "Dormindo muito melhor. Acordo descansada."),
                13: ("", "Consegui fazer caminhada de 30 min sem dor."),
                15: ("", "Manutenção excelente. Me sinto muito bem."),
            }

            for i in range(len(maria_days_ago)):
                se = []
                notes = ""
                if i in maria_notes_map:
                    se_name, notes = maria_notes_map[i]
                    if se_name:
                        se = [se_name]

                entries.append({
                    "patient_id": maria_id,
                    "user_id": 8,  # Maria has user_id=8 (paciente)
                    "overall_score": maria_overall[i],
                    "pain_level": maria_pain[i],
                    "sleep_quality": maria_sleep[i],
                    "mood": maria_moods[i],
                    "side_effects": se,
                    "notes": notes,
                    "days_ago": maria_days_ago[i],
                })

        if ana_id:
            # Ana: ansiedade - 14 entries over 30 days
            ana_days_ago =  [29, 27, 25, 22, 20, 17, 15, 12, 10,  8,  6,  4,  2,  1]
            ana_moods =     ["ruim", "ruim", "ruim", "regular", "regular", "regular", "bom", "regular", "bom", "bom", "regular", "bom", "bom", "otimo"]
            ana_pain =      [3, 3, 2, 2, 2, 2, 1, 2, 1, 1, 2, 1, 1, 1]
            ana_sleep =     [3, 4, 4, 4, 5, 5, 5, 4, 6, 6, 5, 6, 7, 7]
            ana_overall =   [3, 4, 4, 5, 5, 5, 6, 5, 6, 7, 6, 7, 7, 8]

            ana_notes_map = {
                0: (["sonolencia"], "Sonolência após dose noturna. Ansiedade forte durante o dia."),
                2: (["sonolencia"], "Ainda com sonolência noturna. Ansiedade diminuiu um pouco."),
                4: (["boca_seca", "tontura_leve"], "Tontura leve pela manhã, passou após 30 minutos."),
                6: ([], "Primeiro dia sem crise de ansiedade!"),
                9: ([], "Dormindo melhor, acordei apenas 1 vez durante a noite."),
                13: ([], "Semana incrível! Ansiedade muito mais controlada."),
            }

            for i in range(len(ana_days_ago)):
                se = []
                notes = ""
                if i in ana_notes_map:
                    se, notes = ana_notes_map[i]

                entries.append({
                    "patient_id": ana_id,
                    "user_id": None,
                    "overall_score": ana_overall[i],
                    "pain_level": ana_pain[i],
                    "sleep_quality": ana_sleep[i],
                    "mood": ana_moods[i],
                    "side_effects": se,
                    "notes": notes,
                    "days_ago": ana_days_ago[i],
                })

        count = 0
        for e in entries:
            entry_date = _days_ago(e["days_ago"]).replace(hour=21, minute=0, second=0, microsecond=0)

            cursor.execute(
                "SELECT id FROM symptom_diary WHERE patient_id = %s AND created_at::date = %s::date LIMIT 1",
                (e["patient_id"], entry_date),
            )
            if cursor.fetchone():
                continue

            cursor.execute(
                """
                INSERT INTO symptom_diary
                    (clinic_id, patient_id, user_id, overall_score, pain_level, sleep_quality,
                     mood, side_effects, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    CLINIC_ID, e["patient_id"], e["user_id"],
                    e["overall_score"], e["pain_level"], e["sleep_quality"],
                    e["mood"], json.dumps(e["side_effects"]), e["notes"],
                    entry_date,
                ),
            )
            count += 1
        conn.commit()
    print(f"  Inseridas {count} entradas no diário de sintomas")


# ---------------------------------------------------------------------------
# 12. AI Audit Logs (8)
# ---------------------------------------------------------------------------

def seed_ai_audit_logs():
    print("\n=== 12. AI Audit Logs (8) ===")

    logs = [
        {
            "patient": "Maria Oliveira Silva", "endpoint": "/api/ai/anamnesis-analysis",
            "model": "gpt-4o-mini", "status": "success",
            "input_tokens": 2450, "output_tokens": 1820, "total_tokens": 4270,
            "clinical_time_ms": 3200, "treatment_time_ms": 2100, "report_time_ms": 1500, "total_time_ms": 6800,
            "cost": 0.002135, "days_ago": 25,
        },
        {
            "patient": "Ana Clara Menezes", "endpoint": "/api/ai/anamnesis-analysis",
            "model": "gemini-pro", "status": "success",
            "input_tokens": 2800, "output_tokens": 2100, "total_tokens": 4900,
            "clinical_time_ms": 2800, "treatment_time_ms": 1900, "report_time_ms": 1200, "total_time_ms": 5900,
            "cost": 0.001470, "days_ago": 18,
        },
        {
            "patient": "Lucas Gabriel Ferreira", "endpoint": "/api/ai/anamnesis-analysis",
            "model": "gpt-4o-mini", "status": "success",
            "input_tokens": 3100, "output_tokens": 2500, "total_tokens": 5600,
            "clinical_time_ms": 4100, "treatment_time_ms": 2800, "report_time_ms": 1800, "total_time_ms": 8700,
            "cost": 0.002800, "days_ago": 14,
        },
        {
            "patient": "Roberto Carlos Araujo", "endpoint": "/api/ai/anamnesis-analysis",
            "model": "gemini-pro", "status": "success",
            "input_tokens": 2600, "output_tokens": 1950, "total_tokens": 4550,
            "clinical_time_ms": 2500, "treatment_time_ms": 1700, "report_time_ms": 1100, "total_time_ms": 5300,
            "cost": 0.001365, "days_ago": 10,
        },
        {
            "patient": "Thiago Mendes Vieira", "endpoint": "/api/ai/anamnesis-analysis",
            "model": "gpt-4o-mini", "status": "success",
            "input_tokens": 2200, "output_tokens": 1600, "total_tokens": 3800,
            "clinical_time_ms": 2900, "treatment_time_ms": 1800, "report_time_ms": 1300, "total_time_ms": 6000,
            "cost": 0.001900, "days_ago": 7,
        },
        {
            "patient": "Beatriz Souza Martins", "endpoint": "/api/ai/anamnesis-analysis",
            "model": "gemini-pro", "status": "error", "error_message": "Rate limit exceeded. Retry after 30s.",
            "input_tokens": 2700, "output_tokens": 0, "total_tokens": 2700,
            "clinical_time_ms": 0, "treatment_time_ms": 0, "report_time_ms": 0, "total_time_ms": 1200,
            "cost": 0.000810, "days_ago": 5,
        },
        {
            "patient": "Beatriz Souza Martins", "endpoint": "/api/ai/anamnesis-analysis",
            "model": "gemini-pro", "status": "success",
            "input_tokens": 2700, "output_tokens": 2000, "total_tokens": 4700,
            "clinical_time_ms": 3000, "treatment_time_ms": 2000, "report_time_ms": 1400, "total_time_ms": 6400,
            "cost": 0.001410, "days_ago": 5,
        },
        {
            "patient": "Pedro Henrique Lima", "endpoint": "/api/ai/treatment-plan",
            "model": "gpt-4o-mini", "status": "success",
            "input_tokens": 1800, "output_tokens": 1200, "total_tokens": 3000,
            "clinical_time_ms": 0, "treatment_time_ms": 3500, "report_time_ms": 0, "total_time_ms": 3500,
            "cost": 0.001500, "days_ago": 3,
        },
    ]

    with db_cursor(dictionary=True) as (conn, cursor):
        for log in logs:
            pid = _pid(log["patient"])
            if not pid:
                continue

            request_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"seed-{log['patient']}-{log['endpoint']}-{log['days_ago']}"))

            cursor.execute(
                "SELECT id FROM ai_audit_logs WHERE request_id = %s LIMIT 1",
                (request_id,),
            )
            if cursor.fetchone():
                continue

            created = _days_ago(log["days_ago"])

            cursor.execute(
                """
                INSERT INTO ai_audit_logs
                    (patient_id, clinic_id, request_id, user_id, endpoint,
                     input_payload, output_payload, status, error_message,
                     model, prompt_version, prompt_hash,
                     input_tokens, output_tokens, total_tokens,
                     clinical_time_ms, treatment_time_ms, report_time_ms, total_time_ms,
                     estimated_cost_usd, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    pid, CLINIC_ID, request_id, "2", log["endpoint"],
                    json.dumps({"patient_id": pid, "source": "seed"}),
                    json.dumps({"status": log["status"]}) if log["status"] == "success" else None,
                    log["status"],
                    log.get("error_message"),
                    log["model"], "v1.2.0", "abc123def456",
                    log["input_tokens"], log["output_tokens"], log["total_tokens"],
                    log["clinical_time_ms"], log["treatment_time_ms"],
                    log["report_time_ms"], log["total_time_ms"],
                    log["cost"], created,
                ),
            )
        conn.commit()
    print(f"  Inseridos ate 8 registros de auditoria IA")


# ---------------------------------------------------------------------------
# 13. Timeline Events (18)
# ---------------------------------------------------------------------------

def seed_timeline_events():
    print("\n=== 13. Timeline Events (18) ===")

    events = [
        {"patient": "Maria Oliveira Silva", "type": "anamnesis_received", "stage": "triagem", "title": "Anamnese recebida via WhatsApp", "desc": "Paciente completou fluxo de anamnese assistida pelo bot.", "days_ago": 26},
        {"patient": "Maria Oliveira Silva", "type": "ai_analysis_completed", "stage": "anamnese_concluida", "title": "Análise IA concluída", "desc": "Relatório clínico gerado com modelo gpt-4o-mini (5 chunks RAG).", "days_ago": 25},
        {"patient": "Maria Oliveira Silva", "type": "consultation_scheduled", "stage": "agendamento_realizado", "title": "Consulta agendada", "desc": "Primeira consulta presencial agendada.", "days_ago": 24},
        {"patient": "Maria Oliveira Silva", "type": "prescription_issued", "stage": "tratamento_iniciado", "title": "Prescrição emitida", "desc": "Prescrição de CBD 20:1 Full Spectrum emitida pelo Dr. Carlos.", "days_ago": 20},
        {"patient": "Maria Oliveira Silva", "type": "medical_record_updated", "stage": "acompanhamento", "title": "Prontuário atualizado", "desc": "Registros de melhora parcial após 14 dias de tratamento.", "days_ago": 10},
        {"patient": "Ana Clara Menezes", "type": "anamnesis_received", "stage": "triagem", "title": "Anamnese recebida via WhatsApp", "desc": "Paciente descreveu quadro de ansiedade severa.", "days_ago": 19},
        {"patient": "Ana Clara Menezes", "type": "ai_analysis_completed", "stage": "anamnese_concluida", "title": "Análise IA concluída", "desc": "Relatório gerado via Gemini Pro (7 chunks RAG).", "days_ago": 18},
        {"patient": "Ana Clara Menezes", "type": "consultation_scheduled", "stage": "agendamento_realizado", "title": "Consulta agendada", "desc": "Consulta inicial marcada.", "days_ago": 17},
        {"patient": "Ana Clara Menezes", "type": "prescription_issued", "stage": "tratamento_iniciado", "title": "Prescrição emitida", "desc": "CBD 10:1 Broad Spectrum prescrito como adjuvante.", "days_ago": 15},
        {"patient": "Lucas Gabriel Ferreira", "type": "anamnesis_received", "stage": "triagem", "title": "Anamnese recebida via WhatsApp", "desc": "Caso complexo de epilepsia refratária recebido.", "days_ago": 15},
        {"patient": "Lucas Gabriel Ferreira", "type": "ai_analysis_completed", "stage": "anamnese_concluida", "title": "Análise IA concluída - Alta prioridade", "desc": "Risco alto identificado. Encaminhamento prioritário recomendado.", "days_ago": 14},
        {"patient": "Lucas Gabriel Ferreira", "type": "consultation_scheduled", "stage": "agendamento_realizado", "title": "Consulta prioritária agendada", "desc": "Agendamento prioritário por classificação de risco alto.", "days_ago": 13},
        {"patient": "Roberto Carlos Araujo", "type": "anamnesis_received", "stage": "triagem", "title": "Anamnese recebida via WhatsApp", "desc": "Fibromialgia com múltiplas comorbidades relatadas.", "days_ago": 11},
        {"patient": "Roberto Carlos Araujo", "type": "ai_analysis_completed", "stage": "anamnese_concluida", "title": "Análise IA concluída", "desc": "Análise via Gemini Pro com recomendação de CBD:THC combinado.", "days_ago": 10},
        {"patient": "Roberto Carlos Araujo", "type": "prescription_issued", "stage": "tratamento_iniciado", "title": "Prescrição emitida", "desc": "CBD:THC 15:1 Full Spectrum para manejo de fibromialgia.", "days_ago": 8},
        {"patient": "Thiago Mendes Vieira", "type": "anamnesis_received", "stage": "triagem", "title": "Anamnese recebida via WhatsApp", "desc": "Insônia crônica grave com dependência de zolpidem.", "days_ago": 8},
        {"patient": "Thiago Mendes Vieira", "type": "ai_analysis_completed", "stage": "anamnese_concluida", "title": "Análise IA concluída", "desc": "Protocolo CBD:THC noturno sugerido pelo modelo.", "days_ago": 7},
        {"patient": "Fernanda Alves Rocha", "type": "anamnesis_received", "stage": "triagem", "title": "Primeiro contato via WhatsApp", "desc": "Paciente buscando informações sobre tratamento para artrite.", "days_ago": 4},
    ]

    with db_cursor(dictionary=True) as (conn, cursor):
        if not _table_exists(cursor, "patient_timeline_events"):
            print("  SKIP: tabela patient_timeline_events nao existe")
            return

        count = 0
        for ev in events:
            pid = _pid(ev["patient"])
            if not pid:
                continue

            event_time = _days_ago(ev["days_ago"])

            cursor.execute(
                """SELECT id FROM patient_timeline_events
                   WHERE clinic_id = %s AND patient_id = %s AND event_type = %s AND title = %s LIMIT 1""",
                (CLINIC_ID, pid, ev["type"], ev["title"]),
            )
            if cursor.fetchone():
                continue

            cursor.execute(
                """
                INSERT INTO patient_timeline_events
                    (clinic_id, tenant_id, patient_id, event_type, journey_stage,
                     title, description, event_time, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    CLINIC_ID, TENANT_ID, pid, ev["type"], ev["stage"],
                    ev["title"], ev["desc"], event_time,
                    json.dumps({"source": "seed", "seed_version": "1.0"}),
                ),
            )
            count += 1
        conn.commit()
    print(f"  Inseridos {count} eventos na timeline")


# ---------------------------------------------------------------------------
# 14. Medical Records (5) + Entries
# ---------------------------------------------------------------------------

def seed_medical_records():
    print("\n=== 14. Prontuários Médicos (5) ===")

    patients_for_records = [
        "Maria Oliveira Silva",
        "Ana Clara Menezes",
        "Lucas Gabriel Ferreira",
        "Roberto Carlos Araujo",
        "Pedro Henrique Lima",
    ]

    entries_data = {
        "Maria Oliveira Silva": [
            {
                "entry_type": "consultation_note",
                "title": "Consulta inicial - Dor lombar crônica",
                "status": "finalizado",
                "medical_observations": "Paciente refere dor lombar crônica há 3 anos com irradiação para MIE. Já realizou fisioterapia sem melhora significativa. Exames de imagem evidenciam hérnia discal L4-L5.",
                "clinical_assessment": "Dor lombar crônica (M54.5) com componente neuropático. Risco moderado. Indicação de terapia canabinoide.",
                "conduct": "Prescrito CBD 20:1 Full Spectrum, 25mg 2x/dia sublingual. Retorno em 15 dias.",
                "requested_exams": ["Hemograma completo", "PCR", "VHS"],
                "follow_up_plan": "Retorno em 15 dias para avaliação de resposta ao tratamento. Aplicar escala VAS.",
            },
            {
                "entry_type": "follow_up",
                "title": "Retorno 15 dias - Melhora parcial",
                "status": "finalizado",
                "medical_observations": "Paciente relata melhora de 40% na dor lombar. Sono melhorou. Efeitos adversos: sonolência leve nos primeiros 5 dias, já resolvida.",
                "clinical_assessment": "Resposta parcial positiva ao CBD. Manter protocolo atual.",
                "conduct": "Manter dose de 25mg CBD 2x/dia. Próximo retorno em 30 dias.",
                "requested_exams": [],
                "follow_up_plan": "Retorno em 30 dias. Manter diário de sintomas.",
            },
        ],
        "Ana Clara Menezes": [
            {
                "entry_type": "consultation_note",
                "title": "Consulta inicial - Ansiedade generalizada",
                "status": "finalizado",
                "medical_observations": "TAG severo com insônia associada. Em uso de escitalopram 10mg e clonazepam SOS. Psicoterapia em andamento (TCC). Paciente relata crises diárias de ansiedade.",
                "clinical_assessment": "TAG (F41.1) severo refratário parcial a ISRS. Indicação de CBD como adjuvante ansiolítico.",
                "conduct": "CBD 10:1 Broad Spectrum, 15mg 3x/dia sublingual. Manter escitalopram. Reduzir clonazepam gradualmente.",
                "requested_exams": ["TSH", "T4 livre", "Hemograma"],
                "follow_up_plan": "Retorno em 10 dias. Escala HAM-A semanal.",
            },
        ],
        "Lucas Gabriel Ferreira": [
            {
                "entry_type": "consultation_note",
                "title": "Consulta especializada - Epilepsia refratária",
                "status": "finalizado",
                "medical_observations": "Epilepsia refratária diagnosticada há 8 anos. Crises tônico-clônicas 3-4x/semana. Refratário a 3 esquemas antiepilépticos. Atualmente: valproato + levetiracetam.",
                "clinical_assessment": "Epilepsia farmacorresistente (G40.3). Risco alto. Candidato a protocolo CBD baseado em Epidiolex.",
                "conduct": "Iniciar CBD isolado com titulação lenta: 10mg 2x/dia, aumentando 10mg/semana até 50mg 2x/dia. Monitorar TGO/TGP semanalmente.",
                "requested_exams": ["EEG", "TGO/TGP", "Nível sérico valproato", "Hemograma completo"],
                "follow_up_plan": "Retorno semanal no primeiro mês. Diário de crises obrigatório.",
            },
            {
                "entry_type": "follow_up",
                "title": "Retorno semana 2 - Titulação em andamento",
                "status": "rascunho",
                "medical_observations": "Paciente em dose de 25mg 2x/dia. Crises reduziram para 2x/semana. TGO/TGP dentro da normalidade. Sem efeitos adversos significativos.",
                "clinical_assessment": "Resposta positiva à titulação. Prosseguir aumento de dose conforme protocolo.",
                "conduct": "Aumentar para 30mg 2x/dia na próxima semana. Manter monitoramento hepático.",
                "requested_exams": ["TGO/TGP"],
                "follow_up_plan": "Retorno em 7 dias. Manter diário de crises.",
            },
        ],
        "Roberto Carlos Araujo": [
            {
                "entry_type": "consultation_note",
                "title": "Consulta inicial - Fibromialgia",
                "status": "finalizado",
                "medical_observations": "Fibromialgia há 5 anos com dor generalizada, fadiga e sono não reparador. 14/18 tender points positivos. Em uso de duloxetina, pregabalina e tramadol SOS.",
                "clinical_assessment": "Fibromialgia (M79.7) severa com componente de fadiga crônica. Indicação de CBD:THC combinado.",
                "conduct": "CBD:THC 15:1, iniciar com 15mg CBD 2x/dia, adicionar 2mg THC após 2 semanas se bem tolerado.",
                "requested_exams": ["Vitamina D", "Ferritina", "PCR", "VHS"],
                "follow_up_plan": "Retorno em 21 dias. Aplicar FIQ.",
            },
        ],
        "Pedro Henrique Lima": [
            {
                "entry_type": "consultation_note",
                "title": "Consulta inicial - TEPT",
                "status": "finalizado",
                "medical_observations": "TEPT após evento traumático em 2023. Pesadelos frequentes, hipervigilância, flashbacks. Em uso de sertralina 100mg e prazosina 2mg. Acompanhamento com EMDR.",
                "clinical_assessment": "TEPT (F43.1) com insônia secundária. Indicação de CBD como adjuvante para redução de pesadelos e ansiedade.",
                "conduct": "CBD 10:1, 20mg 2x/dia + 5mg à noite sublingual. Manter sertralina e prazosina. Manter EMDR.",
                "requested_exams": ["Cortisol salivar", "Avaliação psicológica PCL-5"],
                "follow_up_plan": "Retorno em 14 dias. PCL-5 mensal.",
            },
        ],
    }

    with db_cursor(dictionary=True) as (conn, cursor):
        if not _table_exists(cursor, "medical_records"):
            print("  SKIP: tabela medical_records nao existe")
            return

        for patient_name in patients_for_records:
            pid = _pid(patient_name)
            if not pid:
                print(f"  SKIP: paciente '{patient_name}' nao encontrado")
                continue

            # Check/create medical_record
            cursor.execute(
                "SELECT id FROM medical_records WHERE clinic_id = %s AND patient_id = %s LIMIT 1",
                (CLINIC_ID, pid),
            )
            row = cursor.fetchone()
            if row:
                mr_id = row["id"]
                print(f"  Prontuario para '{patient_name}' ja existe (id={mr_id})")
            else:
                cursor.execute(
                    """
                    INSERT INTO medical_records (clinic_id, tenant_id, patient_id, primary_doctor_id, status)
                    VALUES (%s, %s, %s, %s, 'ativo')
                    RETURNING id
                    """,
                    (CLINIC_ID, TENANT_ID, pid, 2),
                )
                mr_id = cursor.fetchone()["id"]
                print(f"  Prontuario criado para '{patient_name}' (id={mr_id})")

            # Create entries
            for entry in entries_data.get(patient_name, []):
                cursor.execute(
                    """SELECT id FROM medical_record_entries
                       WHERE clinic_id = %s AND patient_id = %s AND title = %s AND entry_type = %s LIMIT 1""",
                    (CLINIC_ID, pid, entry["title"], entry["entry_type"]),
                )
                if cursor.fetchone():
                    continue

                cursor.execute(
                    """
                    INSERT INTO medical_record_entries
                        (clinic_id, tenant_id, medical_record_id, patient_id,
                         author_user_id, author_name, entry_type, title, status,
                         medical_observations, clinical_assessment, conduct,
                         requested_exams, follow_up_plan)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        CLINIC_ID, TENANT_ID, mr_id, pid,
                        2, "Dr. Carlos Alberto Mendes", entry["entry_type"],
                        entry["title"], entry["status"],
                        entry["medical_observations"], entry["clinical_assessment"],
                        entry["conduct"],
                        json.dumps(entry["requested_exams"]),
                        entry["follow_up_plan"],
                    ),
                )
                print(f"    + Entrada: {entry['title']}")

        conn.commit()


# ---------------------------------------------------------------------------
# 15. Billing Subscription (clinic -> professional plan)
# ---------------------------------------------------------------------------

def seed_billing_subscription():
    print("\n=== 15. Billing Subscription ===")

    with db_cursor(dictionary=True) as (conn, cursor):
        if not _table_exists(cursor, "billing_subscriptions"):
            print("  SKIP: tabela billing_subscriptions nao existe")
            return

        # Check if subscription already exists
        cursor.execute(
            "SELECT id FROM billing_subscriptions WHERE clinic_id = %s AND status IN ('active', 'trial') LIMIT 1",
            (CLINIC_ID,),
        )
        if cursor.fetchone():
            print("  Subscription para clinic_id=1 ja existe")
            return

        # Get professional plan id
        cursor.execute("SELECT id FROM billing_plans WHERE slug = 'professional' LIMIT 1")
        plan_row = cursor.fetchone()
        if not plan_row:
            print("  SKIP: plano 'professional' nao encontrado")
            return

        cursor.execute(
            """
            INSERT INTO billing_subscriptions (clinic_id, plan_id, status, billing_cycle)
            VALUES (%s, %s, 'active', 'monthly')
            """,
            (CLINIC_ID, plan_row["id"]),
        )
        conn.commit()
        print(f"  Clinic 1 vinculada ao plano Professional (plan_id={plan_row['id']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  SEED COMPREHENSIVO - Cannab'IA")
    print("  Populando todas as tabelas com dados demo")
    print("=" * 60)

    global TENANT_ID

    try:
        # Phase 1: Users & clinic
        seed_extra_users()

        # Resolve tenant_id
        TENANT_ID = _get_tenant_id()
        print(f"\n  [info] tenant_id resolvido: {TENANT_ID}")

        # Phase 2: Patients
        seed_patients()

        # Phase 3: Clinical data (depends on patients)
        seed_anamnesis_reports()
        seed_appointments()
        seed_incoming_messages()
        seed_treatment_plans()
        seed_prescriptions()

        # Phase 4: Operational data
        seed_campaign_templates()
        seed_stock_inventory()
        seed_stock_dispensations()
        seed_billing()
        seed_symptom_diary()

        # Phase 5: Audit & timeline
        seed_ai_audit_logs()
        seed_timeline_events()
        seed_medical_records()
        seed_billing_subscription()

        print("\n" + "=" * 60)
        print("  SEED CONCLUIDO COM SUCESSO!")
        print("  ~200 registros inseridos em todas as tabelas")
        print("=" * 60)

    except Exception as e:
        print(f"\n  ERRO durante seed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
