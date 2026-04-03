"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useApiSession } from "@/lib/use-api-session";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui";
import { RiskIndicator } from "@/components/medical/risk-indicator";
import { BiometryCard } from "@/components/medical/biometry-card";
import { DifferentialDiagnosisCard } from "@/components/medical/differential-diagnosis-card";
import { TreatmentSummaryCard } from "@/components/medical/treatment-summary-card";
import { PrescriptionForm } from "@/components/medical/prescription-form";
import { ScientificEvidenceCard } from "@/components/medical/scientific-evidence-card";
import type {
  TriagemDashboardData,
  PrescriptionData,
} from "@/lib/types-medical";

// ── Mock data: simula o JSON que o Agent 3 devolve ────────────────────
const MOCK_DASHBOARD: TriagemDashboardData = {
  patient: {
    id: 1042,
    name: "Maria Silva Santos",
    age: 47,
    main_complaint: "Dor neuropatica cronica em membros inferiores ha 3 anos, refrataria a gabapentina",
    symptoms: [
      "Dor em queimacao bilateral",
      "Parestesias noturnas",
      "Insonia secundaria a dor",
      "Fadiga cronica",
      "Ansiedade moderada",
    ],
    current_medications: ["Gabapentina 300mg 3x/dia", "Amitriptilina 25mg a noite", "Clonazepam 0.5mg SOS"],
    allergies: ["AINEs", "Dipirona"],
    medical_history: "Diabetes tipo 2 ha 8 anos. Neuropatia diabetica diagnosticada em 2023. Historico de depressao tratada.",
  },
  vitals: {
    bp_systolic: 138,
    bp_diastolic: 88,
    heart_rate: 78,
    temperature: 36.4,
    spo2: 97,
    respiratory_rate: 16,
    weight_kg: 72,
    height_cm: 162,
    bmi: null,
    pain_level: 7,
  },
  pipeline: {
    clinical_analysis: {
      probable_conditions: [
        "Neuropatia diabetica periferica",
        "Sindrome de dor cronica",
        "Transtorno de ansiedade generalizada",
        "Insonia cronica secundaria",
      ],
      risk_level: "moderado",
      recommended_exams: [
        "Eletroneuromiografia (ENMG)",
        "HbA1c",
        "Hemograma completo",
        "Funcao hepatica (TGO/TGP)",
        "Funcao renal (Creatinina/Ureia)",
        "Vitamina B12",
      ],
      red_flags: [
        "Dor refrataria a tratamento convencional por >6 meses",
        "Uso concomitante de benzodiazepinicos (Clonazepam)",
      ],
    },
    treatment_plan: {
      cannabinoid_ratio: "CBD:THC 20:1",
      suggested_dosage: "CBD 50mg/dia (titulacao: iniciar com 10mg 2x/dia, aumentar 10mg/semana)",
      administration_route: "Oleo sublingual",
      monitoring_plan: "Reavaliacao em 30 dias. Escala EVA semanal. Diario de dor. Monitorar interacao com gabapentina e clonazepam. Glicemia de jejum mensal.",
      precautions: [
        "Interacao potencial CBD x Clonazepam — monitorar sedacao excessiva",
        "Paciente diabetica — CBD pode alterar metabolismo da glicose",
        "Ajustar gabapentina conforme resposta ao CBD",
        "Contraindicado aumento de THC sem reavaliacao presencial",
      ],
    },
    scientific_report: {
      summary: "Evidencias de nivel moderado-alto suportam o uso de canabidiol (CBD) no manejo de dor neuropatica diabetica. Meta-analise recente (Cochrane 2024) demonstrou reducao significativa na escala EVA (diferenca media: -2.1 pontos, IC 95%: -2.8 a -1.4). O ratio CBD:THC 20:1 e recomendado para pacientes com historico de ansiedade e uso de benzodiazepinicos.",
      supporting_evidence: [
        "Revisao sistematica Cochrane (2024): CBD isolado demonstrou eficacia superior ao placebo em neuropatia diabetica (NNT=4)",
        "Estudo randomizado duplo-cego (N=256, JAMA Neurology 2023): Oleo CBD sublingual 50mg/dia reduziu dor em 43% vs 18% placebo",
        "Metanalise de 8 ECRs (Pain Medicine 2024): Ratio CBD:THC alto (>10:1) associado a menor risco de efeitos adversos psiquiatricos",
        "Estudo observacional brasileiro (Rev Bras Neurologia 2023): 67% dos pacientes com neuropatia diabetica reportaram melhora clinicamente significativa com CBD apos 12 semanas",
      ],
      references: [
        "Fisher E, et al. Cannabinoids for neuropathic pain. Cochrane Database Syst Rev. 2024;3:CD012182",
        "Xu DH, et al. Sublingual CBD oil for diabetic neuropathy. JAMA Neurol. 2023;80(4):389-398",
        "Aviram J, Samuelly-Leichtag G. Efficacy of Cannabis-Based Medicines. Pain Med. 2024;25(1):87-101",
        "Santos RG, et al. Canabidiol na neuropatia diabetica. Rev Bras Neurol. 2023;59(2):15-23",
        "ANVISA. Resolucao RDC 660/2022 — Prescricao de produtos Cannabis",
      ],
    },
    rag_chunks_used: 14,
    report_model: "gemini-1.5-flash",
    token_usage: { input: 3420, output: 1890, total: 5310 },
  },
  extracted_conditions: [
    {
      condition_name: "Neuropatia diabetica periferica",
      icd10_hint: "G63.2",
      confidence: "alto",
      evidence_snippet: "dor em queimacao bilateral em membros inferiores, historico de diabetes ha 8 anos",
    },
    {
      condition_name: "Sindrome de dor cronica",
      icd10_hint: "G89.4",
      confidence: "alto",
      evidence_snippet: "dor refrataria ha 3 anos, nao responsiva a gabapentina",
    },
    {
      condition_name: "Transtorno de ansiedade generalizada",
      icd10_hint: "F41.1",
      confidence: "medio",
      evidence_snippet: "ansiedade moderada, uso de clonazepam SOS",
    },
    {
      condition_name: "Insonia cronica",
      icd10_hint: "G47.0",
      confidence: "medio",
      evidence_snippet: "parestesias noturnas causando insonia secundaria",
    },
  ],
  prescription_draft: null,
};

export default function TriagemDashboardPage() {
  const { data: session, loading } = useApiSession();
  const router = useRouter();
  const [dashData] = useState<TriagemDashboardData>(MOCK_DASHBOARD);

  useEffect(() => {
    if (!loading && !session) router.replace("/login");
  }, [loading, session, router]);

  if (loading || !session) return null;

  const { patient, vitals, pipeline, extracted_conditions } = dashData;
  const { clinical_analysis, treatment_plan, scientific_report } = pipeline;

  function handlePrescriptionSubmit(rx: PrescriptionData) {
    // TODO: POST /api/v1/prescriptions
    console.info("[Prescricao]", rx);
  }

  return (
    <AppShell session={session} title="Triagem & Diagnostico" subtitle={`Paciente #${patient.id} — ${patient.name}`}>

      {/* ── Patient Header ─────────────────────────────── */}
      <div className="ds-medico-header">
        <div className="ds-medico-header__patient">
          <div className="ds-medico-header__avatar">
            {patient.name.charAt(0)}
          </div>
          <div className="ds-medico-header__info">
            <h2>{patient.name}</h2>
            <p>{patient.age} anos — {patient.main_complaint}</p>
          </div>
        </div>
        <div className="ds-medico-header__badges">
          <RiskIndicator level={clinical_analysis.risk_level as "baixo" | "moderado" | "alto" | "critico"} />
          <Badge tone="info" pulse>Pipeline concluido</Badge>
        </div>
      </div>

      {/* ── Patient Context Chips ──────────────────────── */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 20 }}>
        {patient.symptoms.map((s) => (
          <Badge key={s} tone="warning">{s}</Badge>
        ))}
        {patient.allergies.map((a) => (
          <Badge key={a} tone="danger">Alergia: {a}</Badge>
        ))}
        {patient.current_medications.map((m) => (
          <Badge key={m} tone="neutral">{m}</Badge>
        ))}
      </div>

      {/* ── Section: Monitoramento ─────────────────────── */}
      <div className="ds-medico-section-label">Monitoramento Clinico</div>
      <BiometryCard vitals={vitals} />

      {/* ── Section: Inteligencia Clinica ───────────────── */}
      <div className="ds-medico-section-label" style={{ marginTop: 28 }}>Inteligencia Clinica IA</div>
      <div className="ds-medico-grid">
        <DifferentialDiagnosisCard
          conditions={extracted_conditions}
          analysis={clinical_analysis}
        />
        <TreatmentSummaryCard
          plan={treatment_plan}
          report={scientific_report}
        />
      </div>

      {/* ── Section: Evidencia ─────────────────────────── */}
      <div className="ds-medico-section-label" style={{ marginTop: 28 }}>Base Cientifica</div>
      <ScientificEvidenceCard
        report={scientific_report}
        ragChunksUsed={pipeline.rag_chunks_used}
        reportModel={pipeline.report_model}
      />

      {/* ── Section: Prescricao ────────────────────────── */}
      <div className="ds-medico-section-label" style={{ marginTop: 28 }}>Prescricao Eletronica</div>
      <PrescriptionForm
        patient={patient}
        plan={treatment_plan}
        onSubmit={handlePrescriptionSubmit}
      />
    </AppShell>
  );
}
