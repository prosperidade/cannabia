"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

import { cn } from "@/lib/cn";
import { getAttendance, saveMedicalRecord, reviewAttendance, ApiError } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import type {
  AttendanceDetail,
  AttendanceReport,
  TimelineEvent,
  MedicalRecordEntry,
  MedicalRecordPayload,
} from "@/lib/types";
import type {
  ClinicalAnalysis,
  TreatmentPlan,
  ScientificReport,
  ExtractedCondition,
  VitalSigns,
  PatientContext,
  RiskLevel,
  ConfidenceLevel,
} from "@/lib/types-medical";
import { MaterialIcon, Badge, Button, Card, ProgressBar, Avatar } from "@/components/ui-tw";

/* ---------------------------------------------------------------------------
 * Constants & Helpers
 * --------------------------------------------------------------------------- */

const RISK_CONFIG: Record<
  RiskLevel,
  { label: string; tone: "danger" | "warning" | "success" | "primary"; dotColor: string }
> = {
  critico: { label: "Critico", tone: "danger", dotColor: "bg-red-500" },
  alto: { label: "Alto", tone: "warning", dotColor: "bg-orange-500" },
  moderado: { label: "Moderado", tone: "warning", dotColor: "bg-yellow-500" },
  baixo: { label: "Baixo", tone: "success", dotColor: "bg-emerald-500" },
};

const CONFIDENCE_MAP: Record<
  ConfidenceLevel,
  { label: string; percent: number; variant: "primary" | "warning" | "danger" }
> = {
  alto: { label: "Alto", percent: 88, variant: "primary" },
  medio: { label: "Medio", percent: 62, variant: "warning" },
  baixo: { label: "Baixo", percent: 35, variant: "danger" },
};

const AI_TABS = [
  { key: "analise", label: "Analise", icon: "psychology" },
  { key: "tratamento", label: "Tratamento", icon: "medication_liquid" },
  { key: "evidencias", label: "Evidencias", icon: "menu_book" },
  { key: "prontuario", label: "Prontuario", icon: "edit_note" },
] as const;

type AiTab = (typeof AI_TABS)[number]["key"];

const MOBILE_PANELS = [
  { key: "chat", label: "Chat", icon: "chat" },
  { key: "ia", label: "IA", icon: "auto_awesome" },
] as const;

type MobilePanel = (typeof MOBILE_PANELS)[number]["key"];

const CONSULTATION_STATUS_OPTIONS = [
  { value: "em_andamento", label: "Em andamento" },
  { value: "concluida", label: "Concluida" },
  { value: "cancelada", label: "Cancelada" },
  { value: "aguardando_retorno", label: "Aguardando retorno" },
];

/** Format elapsed seconds into mm:ss. */
function formatTimer(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/** Parse risk level from report data. */
function parseRiskLevel(report: AttendanceReport): RiskLevel {
  const ca = report.clinical_analysis as Partial<ClinicalAnalysis> | null;
  const raw = (ca?.risk_level ?? "").toLowerCase().trim();
  if (raw === "critical" || raw === "critico") return "critico";
  if (raw === "high" || raw === "alto") return "alto";
  if (raw === "moderate" || raw === "moderado") return "moderado";
  return "baixo";
}

/** Parse clinical_analysis from the report's Record<string,unknown>. */
function parseClinicalAnalysis(raw: Record<string, unknown>): ClinicalAnalysis {
  return {
    probable_conditions: (raw.probable_conditions as string[] | undefined) ?? [],
    risk_level: (raw.risk_level as RiskLevel | undefined) ?? "baixo",
    recommended_exams: (raw.recommended_exams as string[] | undefined) ?? [],
    red_flags: (raw.red_flags as string[] | undefined) ?? [],
  };
}

function parseTreatmentPlan(raw: Record<string, unknown>): TreatmentPlan {
  return {
    cannabinoid_ratio: (raw.cannabinoid_ratio as string | undefined) ?? "",
    suggested_dosage: (raw.suggested_dosage as string | undefined) ?? "",
    administration_route: (raw.administration_route as string | undefined) ?? "",
    monitoring_plan: (raw.monitoring_plan as string | undefined) ?? "",
    precautions: (raw.precautions as string[] | undefined) ?? [],
  };
}

function parseScientificReport(raw: Record<string, unknown>): ScientificReport {
  return {
    summary: (raw.summary as string | undefined) ?? "",
    supporting_evidence: (raw.supporting_evidence as string[] | undefined) ?? [],
    references: (raw.references as string[] | undefined) ?? [],
  };
}

/** Build patient context from anamnesis_data. */
function parsePatientContext(report: AttendanceReport): PatientContext {
  const an = report.anamnesis_data ?? {};
  return {
    id: report.patient_id ?? 0,
    name: report.patient_name,
    age: (an.age as number | undefined) ?? (an.idade as number | undefined) ?? 0,
    main_complaint:
      (an.main_complaint as string | undefined) ??
      (an.queixa_principal as string | undefined) ??
      "",
    symptoms: (an.symptoms as string[] | undefined) ?? (an.sintomas as string[] | undefined) ?? [],
    current_medications:
      (an.current_medications as string[] | undefined) ??
      (an.medicamentos_atuais as string[] | undefined) ??
      [],
    allergies:
      (an.allergies as string[] | undefined) ?? (an.alergias as string[] | undefined) ?? [],
    medical_history:
      (an.medical_history as string | undefined) ??
      (an.historico_medico as string | undefined) ??
      null,
  };
}

/** Parse extracted conditions from clinical_analysis. */
function parseExtractedConditions(ca: ClinicalAnalysis): ExtractedCondition[] {
  return ca.probable_conditions.map((cond, i) => ({
    condition_name: cond,
    icd10_hint: null,
    confidence:
      i === 0
        ? ("alto" as ConfidenceLevel)
        : i === 1
          ? ("medio" as ConfidenceLevel)
          : ("baixo" as ConfidenceLevel),
    evidence_snippet: null,
  }));
}

/** Parse vital signs from anamnesis_data. */
function parseVitalSigns(an: Record<string, unknown>): VitalSigns | null {
  const vitals = (an.vital_signs ?? an.sinais_vitais ?? an.vitals) as
    | Partial<VitalSigns>
    | undefined;
  if (!vitals) return null;
  return {
    bp_systolic: vitals.bp_systolic ?? null,
    bp_diastolic: vitals.bp_diastolic ?? null,
    heart_rate: vitals.heart_rate ?? null,
    temperature: vitals.temperature ?? null,
    spo2: vitals.spo2 ?? null,
    respiratory_rate: vitals.respiratory_rate ?? null,
    weight_kg: vitals.weight_kg ?? null,
    height_cm: vitals.height_cm ?? null,
    bmi: vitals.bmi ?? null,
    pain_level: vitals.pain_level ?? null,
  };
}

/** Map timeline event to a chat-like message. */
function timelineToChat(event: TimelineEvent): {
  id: number;
  side: "left" | "right" | "center";
  text: string;
  time: string;
  label: string;
} {
  const time = new Date(event.event_time).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });

  if (event.source_type === "patient" || event.event_type === "message_received") {
    return {
      id: event.id,
      side: "right",
      text: event.description ?? event.title,
      time,
      label: "Paciente",
    };
  }
  if (event.source_type === "ai" || event.event_type === "ai_response") {
    return {
      id: event.id,
      side: "left",
      text: event.description ?? event.title,
      time,
      label: "IA",
    };
  }
  if (event.event_type === "system" || event.event_type === "status_change") {
    return { id: event.id, side: "center", text: event.title, time, label: "Sistema" };
  }
  // Default: show as AI/system message on the left
  return {
    id: event.id,
    side: "left",
    text: event.description ?? event.title,
    time,
    label: event.event_type,
  };
}

/* ---------------------------------------------------------------------------
 * Toast Component (inline, lightweight)
 * --------------------------------------------------------------------------- */

type ToastType = "success" | "error";

function Toast({
  message,
  type,
  onClose,
}: {
  message: string;
  type: ToastType;
  onClose: () => void;
}) {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div
      className={cn(
        "fixed top-4 right-4 z-[100] flex items-center gap-3 px-5 py-3 rounded-xl shadow-2xl border backdrop-blur-md animate-slide-in-right",
        type === "success"
          ? "bg-emerald-950/90 border-emerald-500/30 text-emerald-300"
          : "bg-red-950/90 border-red-500/30 text-red-300",
      )}
    >
      <MaterialIcon icon={type === "success" ? "check_circle" : "error"} size="sm" />
      <span className="text-sm font-medium">{message}</span>
      <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100 transition-opacity">
        <MaterialIcon icon="close" size="sm" />
      </button>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Main Page Component
 * --------------------------------------------------------------------------- */

export default function ConsultaAoVivoPage() {
  const params = useParams();
  const router = useRouter();
  const session = useApiSession();

  const attendanceId = params.id as string;

  // Data state
  const [detail, setDetail] = useState<AttendanceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [aiTab, setAiTab] = useState<AiTab>("analise");
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>("chat");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [highlightedCondition, setHighlightedCondition] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Medical record form
  const [mrStatus, setMrStatus] = useState("em_andamento");
  const [mrObservations, setMrObservations] = useState("");
  const [mrAssessment, setMrAssessment] = useState("");
  const [mrConduct, setMrConduct] = useState("");
  const [mrExams, setMrExams] = useState("");
  const [mrFollowUp, setMrFollowUp] = useState("");
  const [saving, setSaving] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  // Toast
  const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null);

  // Auth redirect
  useEffect(() => {
    if (!session.loading && !session.data?.authenticated) {
      router.replace("/login");
    }
  }, [session.loading, session.data, router]);

  // Fetch attendance detail
  const fetchDetail = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAttendance(attendanceId);
      setDetail(data);
      // Pre-fill medical record form from consultation_entry if available
      if (data.consultation_entry) {
        const entry = data.consultation_entry;
        setMrStatus(entry.status ?? "em_andamento");
        setMrObservations(entry.medical_observations ?? "");
        setMrAssessment(entry.clinical_assessment ?? "");
        setMrConduct(entry.conduct ?? "");
        setMrExams((entry.requested_exams ?? []).join(", "));
        setMrFollowUp(entry.follow_up_plan ?? "");
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Falha ao carregar o atendimento.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [attendanceId]);

  useEffect(() => {
    if (session.data?.authenticated) {
      void fetchDetail();
    }
  }, [session.data?.authenticated, fetchDetail]);

  // Consultation timer
  useEffect(() => {
    const interval = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [detail]);

  // Derived data
  const report = detail?.report ?? null;
  const timeline = detail?.timeline ?? [];
  const medicalRecordEntries = detail?.medical_record_entries ?? [];

  const riskLevel = report ? parseRiskLevel(report) : "baixo";
  const riskCfg = RISK_CONFIG[riskLevel];

  const clinicalAnalysis = useMemo(
    () => (report ? parseClinicalAnalysis(report.clinical_analysis) : null),
    [report],
  );
  const treatmentPlan = useMemo(
    () => (report ? parseTreatmentPlan(report.treatment_plan) : null),
    [report],
  );
  const scientificReport = useMemo(
    () => (report ? parseScientificReport(report.scientific_report) : null),
    [report],
  );
  const patientContext = useMemo(() => (report ? parsePatientContext(report) : null), [report]);
  const extractedConditions = useMemo(
    () => (clinicalAnalysis ? parseExtractedConditions(clinicalAnalysis) : []),
    [clinicalAnalysis],
  );
  const vitalSigns = useMemo(
    () => (report ? parseVitalSigns(report.anamnesis_data) : null),
    [report],
  );

  const chatMessages = useMemo(() => timeline.map(timelineToChat), [timeline]);

  // Toggle expandable section
  const toggleSection = (key: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Copy to clipboard
  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setToast({ message: "Copiado!", type: "success" });
    } catch {
      setToast({ message: "Erro ao copiar.", type: "error" });
    }
  };

  // Save medical record
  const handleSaveMedicalRecord = async () => {
    if (!session.data?.csrf_token) return;
    setSaving(true);
    try {
      const payload: MedicalRecordPayload = {
        consultation_status: mrStatus,
        medical_observations: mrObservations,
        clinical_assessment: mrAssessment,
        conduct: mrConduct,
        requested_exams: mrExams
          .split(",")
          .map((e) => e.trim())
          .filter(Boolean),
        follow_up_plan: mrFollowUp,
      };
      await saveMedicalRecord(attendanceId, session.data.csrf_token, payload);
      setToast({ message: "Prontuario salvo com sucesso!", type: "success" });
      void fetchDetail(); // refresh
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Erro ao salvar prontuario.";
      setToast({ message: msg, type: "error" });
    } finally {
      setSaving(false);
    }
  };

  // Review attendance
  const handleReview = async () => {
    if (!session.data?.csrf_token) return;
    setReviewing(true);
    try {
      await reviewAttendance(attendanceId, session.data.csrf_token);
      setToast({ message: "Atendimento marcado como revisado!", type: "success" });
      void fetchDetail();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Erro ao revisar atendimento.";
      setToast({ message: msg, type: "error" });
    } finally {
      setReviewing(false);
    }
  };

  /* -----------------------------------------------------------------------
   * Loading / Error / Auth states
   * ----------------------------------------------------------------------- */

  if (session.loading || loading) {
    return (
      <div className="flex items-center justify-center min-h-[80vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando consulta...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[80vh]">
        <div className="glass-panel rounded-2xl p-8 text-center space-y-4 max-w-md">
          <MaterialIcon icon="error_outline" size="xl" className="text-error" />
          <p className="text-stone-400">{error}</p>
          <div className="flex items-center gap-3 justify-center">
            <Button variant="secondary" size="sm" icon="refresh" onClick={fetchDetail}>
              Tentar novamente
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon="arrow_back"
              onClick={() => router.push("/med/fila")}
            >
              Voltar
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!detail || !report) {
    return (
      <div className="flex items-center justify-center min-h-[80vh]">
        <div className="glass-panel rounded-2xl p-12 text-center space-y-4">
          <MaterialIcon icon="search_off" size="xl" className="text-stone-600" />
          <p className="text-stone-400 text-lg font-headline font-bold">
            Atendimento nao encontrado
          </p>
          <Button
            variant="secondary"
            size="sm"
            icon="arrow_back"
            onClick={() => router.push("/med/fila")}
          >
            Voltar a fila
          </Button>
        </div>
      </div>
    );
  }

  /* -----------------------------------------------------------------------
   * Render helpers
   * ----------------------------------------------------------------------- */

  /** LEFT PANEL: Chat area */
  const renderChatPanel = () => (
    <div className="flex flex-col h-full">
      {/* Chat Header */}
      <div className="glass-panel rounded-t-2xl px-4 lg:px-6 py-3 border-b border-white/5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Avatar name={report.patient_name} size="md" />
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-headline font-bold text-on-surface text-sm lg:text-base">
                {report.patient_name}
              </h2>
              <Badge tone={riskCfg.tone} pulse={riskLevel === "critico"}>
                <span className={cn("w-1.5 h-1.5 rounded-full mr-1", riskCfg.dotColor)} />
                {riskCfg.label}
              </Badge>
            </div>
            <p className="text-[11px] text-stone-500 font-mono">{report.phone}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-primary/10 px-3 py-1.5 rounded-full">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="text-xs font-mono font-bold text-primary">
              {formatTimer(elapsedSeconds)}
            </span>
          </div>
          <button
            onClick={() => router.push("/med/fila")}
            className="p-2 rounded-lg hover:bg-white/5 transition-colors text-stone-400 hover:text-on-surface"
            title="Voltar a fila"
          >
            <MaterialIcon icon="close" size="sm" />
          </button>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-3 custom-scrollbar">
        {chatMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <MaterialIcon icon="chat_bubble_outline" size="xl" className="text-stone-700 mb-3" />
            <p className="text-stone-500 text-sm">Nenhuma mensagem neste atendimento.</p>
          </div>
        ) : (
          chatMessages.map((msg) => {
            if (msg.side === "center") {
              return (
                <div key={msg.id} className="flex justify-center">
                  <span className="text-[10px] text-stone-500 bg-white/5 px-3 py-1 rounded-full border border-white/5">
                    {msg.text} &middot; {msg.time}
                  </span>
                </div>
              );
            }
            if (msg.side === "right") {
              return (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[80%] lg:max-w-[70%]">
                    <div className="bg-primary/10 border border-primary/20 rounded-2xl rounded-br-md px-4 py-3">
                      <p className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap">
                        {msg.text}
                      </p>
                    </div>
                    <p className="text-[10px] text-stone-600 text-right mt-1">
                      {msg.label} &middot; {msg.time}
                    </p>
                  </div>
                </div>
              );
            }
            // left (AI / system)
            return (
              <div key={msg.id} className="flex justify-start">
                <div className="max-w-[80%] lg:max-w-[70%]">
                  <div className="glass-panel rounded-2xl rounded-bl-md px-4 py-3 border border-white/5">
                    <p className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap">
                      {msg.text}
                    </p>
                  </div>
                  <p className="text-[10px] text-stone-600 mt-1">
                    <MaterialIcon
                      icon="auto_awesome"
                      size="sm"
                      className="text-primary text-[10px] mr-1 align-middle"
                    />
                    {msg.label} &middot; {msg.time}
                  </p>
                </div>
              </div>
            );
          })
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Async-only notice (real-time chat virá em sprint futura) */}
      <div className="shrink-0 p-3 lg:p-4 border-t border-white/5">
        <div className="flex items-start gap-3 rounded-xl bg-surface-container-low/60 px-4 py-3 border border-outline-variant/20">
          <MaterialIcon icon="info" size="sm" className="text-stone-400 shrink-0 mt-0.5" />
          <p className="text-[11px] text-stone-400 leading-relaxed">
            Comunicação com o paciente é assíncrona via WhatsApp. Acima você vê o histórico real da
            anamnese e dos eventos do atendimento. Chat em tempo real virá em sprint futura.
          </p>
        </div>
      </div>
    </div>
  );

  /** RIGHT PANEL: AI Assistant */
  const renderAiPanel = () => (
    <div className="flex flex-col h-full">
      {/* AI Panel Header */}
      <div className="glass-panel rounded-t-2xl px-4 py-3 border-b border-white/5 shrink-0">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-headline font-bold text-sm uppercase tracking-widest flex items-center gap-2 text-primary">
            <MaterialIcon icon="auto_awesome" size="sm" />
            Assistente IA
          </h3>
          <Badge tone="primary" pulse>
            AO VIVO
          </Badge>
        </div>
        {/* AI Tabs */}
        <div className="flex gap-1 overflow-x-auto no-scrollbar">
          {AI_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setAiTab(tab.key)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all whitespace-nowrap",
                aiTab === tab.key
                  ? "bg-primary/15 text-primary"
                  : "text-stone-500 hover:text-stone-300 hover:bg-white/5",
              )}
            >
              <MaterialIcon icon={tab.icon} size="sm" className="text-[14px]" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* AI Tab Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {aiTab === "analise" && renderAnaliseTab()}
        {aiTab === "tratamento" && renderTratamentoTab()}
        {aiTab === "evidencias" && renderEvidenciasTab()}
        {aiTab === "prontuario" && renderProntuarioTab()}
      </div>
    </div>
  );

  /** Tab: Analise Clinica */
  const renderAnaliseTab = () => (
    <>
      {/* Patient Context Card */}
      {patientContext && (
        <Card variant="glass" padding="sm" className="border-l-4 border-l-primary">
          <div className="flex items-center gap-2 mb-3">
            <MaterialIcon icon="person" size="sm" className="text-primary" />
            <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
              Contexto do Paciente
            </span>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-stone-400">Nome</span>
              <span className="text-sm font-semibold text-on-surface">{patientContext.name}</span>
            </div>
            {patientContext.age > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-stone-400">Idade</span>
                <span className="text-sm font-semibold text-on-surface">
                  {patientContext.age} anos
                </span>
              </div>
            )}
            {patientContext.main_complaint && (
              <div>
                <span className="text-xs text-stone-400">Queixa principal</span>
                <p className="text-sm text-on-surface mt-0.5">{patientContext.main_complaint}</p>
              </div>
            )}
            {patientContext.symptoms.length > 0 && (
              <div>
                <span className="text-xs text-stone-400">Sintomas</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {patientContext.symptoms.map((s, i) => (
                    <span
                      key={i}
                      className="text-[10px] bg-white/5 border border-white/10 px-2 py-0.5 rounded-full text-stone-300"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {patientContext.current_medications.length > 0 && (
              <div>
                <span className="text-xs text-stone-400">Medicamentos atuais</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {patientContext.current_medications.map((m, i) => (
                    <span
                      key={i}
                      className="text-[10px] bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded-full text-blue-300"
                    >
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {patientContext.allergies.length > 0 && (
              <div>
                <span className="text-xs text-stone-400">Alergias</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {patientContext.allergies.map((a, i) => (
                    <span
                      key={i}
                      className="text-[10px] bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded-full text-red-300"
                    >
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Vital Signs */}
      {vitalSigns && (
        <Card variant="glass" padding="sm">
          <button
            onClick={() => toggleSection("vitals")}
            className="w-full flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <MaterialIcon icon="monitor_heart" size="sm" className="text-primary" />
              <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                Sinais Vitais
              </span>
            </div>
            <MaterialIcon
              icon={expandedSections.has("vitals") ? "expand_less" : "expand_more"}
              size="sm"
              className="text-stone-500"
            />
          </button>
          {expandedSections.has("vitals") && (
            <div className="grid grid-cols-2 gap-2 mt-3">
              {vitalSigns.bp_systolic != null && vitalSigns.bp_diastolic != null && (
                <VitalItem
                  label="PA"
                  value={`${vitalSigns.bp_systolic}/${vitalSigns.bp_diastolic}`}
                  unit="mmHg"
                  icon="bloodtype"
                />
              )}
              {vitalSigns.heart_rate != null && (
                <VitalItem
                  label="FC"
                  value={String(vitalSigns.heart_rate)}
                  unit="bpm"
                  icon="favorite"
                />
              )}
              {vitalSigns.temperature != null && (
                <VitalItem
                  label="Temp"
                  value={String(vitalSigns.temperature)}
                  unit="C"
                  icon="thermostat"
                />
              )}
              {vitalSigns.spo2 != null && (
                <VitalItem label="SpO2" value={String(vitalSigns.spo2)} unit="%" icon="air" />
              )}
              {vitalSigns.respiratory_rate != null && (
                <VitalItem
                  label="FR"
                  value={String(vitalSigns.respiratory_rate)}
                  unit="irpm"
                  icon="pulmonology"
                />
              )}
              {vitalSigns.pain_level != null && (
                <VitalItem
                  label="Dor"
                  value={String(vitalSigns.pain_level)}
                  unit="/10"
                  icon="sentiment_very_dissatisfied"
                />
              )}
            </div>
          )}
        </Card>
      )}

      {/* Differential Diagnosis */}
      <Card variant="glass" padding="sm">
        <div className="flex items-center gap-2 mb-3">
          <MaterialIcon icon="diagnosis" size="sm" className="text-primary" />
          <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
            Diagnostico Diferencial
          </span>
        </div>
        {extractedConditions.length === 0 ? (
          <p className="text-xs text-stone-500 italic">Nenhuma condicao identificada ainda.</p>
        ) : (
          <div className="space-y-3">
            {extractedConditions.map((cond, i) => {
              const conf = CONFIDENCE_MAP[cond.confidence];
              const isHighlighted = highlightedCondition === cond.condition_name;
              return (
                <div
                  key={i}
                  onClick={() =>
                    setHighlightedCondition(isHighlighted ? null : cond.condition_name)
                  }
                  className={cn(
                    "bg-white/5 rounded-xl p-3 border transition-all cursor-pointer",
                    isHighlighted
                      ? "border-primary/40 bg-primary/5"
                      : "border-white/5 hover:border-white/10",
                  )}
                >
                  <div className="flex justify-between items-start mb-1.5">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-on-surface">{cond.condition_name}</p>
                      {cond.icd10_hint && (
                        <span className="text-[10px] text-stone-500 font-mono">
                          {cond.icd10_hint}
                        </span>
                      )}
                    </div>
                    <span
                      className={cn(
                        "text-xs font-bold font-mono ml-2",
                        `text-${conf.variant === "primary" ? "primary" : conf.variant === "warning" ? "amber-400" : "red-400"}`,
                      )}
                    >
                      {conf.percent}%
                    </span>
                  </div>
                  <ProgressBar value={conf.percent} variant={conf.variant} size="sm" glow />
                  {cond.evidence_snippet && (
                    <p className="text-[10px] text-stone-500 mt-2 italic leading-relaxed">
                      {cond.evidence_snippet}
                    </p>
                  )}
                  {isHighlighted && (
                    <div className="mt-2 flex items-center gap-2">
                      <Badge tone="neutral">Confianca: {conf.label}</Badge>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          void copyToClipboard(`${cond.condition_name} (${cond.icd10_hint ?? ""})`);
                        }}
                        className="text-[10px] text-primary hover:underline"
                      >
                        Copiar
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Red Flags */}
      {clinicalAnalysis && clinicalAnalysis.red_flags.length > 0 && (
        <Card variant="glass" padding="sm" className="border-l-4 border-l-error">
          <div className="flex items-center gap-2 mb-3">
            <MaterialIcon icon="warning" size="sm" className="text-error" />
            <span className="text-xs font-bold uppercase tracking-widest text-error">
              Sinais de Alerta
            </span>
          </div>
          <div className="space-y-2">
            {clinicalAnalysis.red_flags.map((flag, i) => (
              <div
                key={i}
                className="flex items-start gap-2 bg-error/5 border border-error/10 rounded-lg px-3 py-2"
              >
                <MaterialIcon icon="emergency" size="sm" className="text-error mt-0.5 shrink-0" />
                <span className="text-xs text-red-200 leading-relaxed">{flag}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Recommended Exams */}
      {clinicalAnalysis && clinicalAnalysis.recommended_exams.length > 0 && (
        <Card variant="glass" padding="sm">
          <div className="flex items-center gap-2 mb-3">
            <MaterialIcon icon="labs" size="sm" className="text-primary" />
            <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
              Exames Recomendados
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {clinicalAnalysis.recommended_exams.map((exam, i) => (
              <span
                key={i}
                className="text-xs bg-primary/10 border border-primary/20 text-primary px-3 py-1.5 rounded-full font-medium"
              >
                {exam}
              </span>
            ))}
          </div>
        </Card>
      )}
    </>
  );

  /** Tab: Plano Terapeutico */
  const renderTratamentoTab = () => (
    <>
      {treatmentPlan && (
        <>
          {/* Cannabinoid Ratio */}
          <Card variant="glass" padding="sm" className="border-l-4 border-l-primary">
            <div className="flex items-center gap-2 mb-3">
              <MaterialIcon icon="medication_liquid" size="sm" className="text-primary" />
              <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                Protocolo Canabinoides
              </span>
            </div>
            <div className="bg-primary/10 border border-primary/20 rounded-xl p-4 space-y-3">
              {treatmentPlan.cannabinoid_ratio && (
                <div>
                  <span className="text-[10px] uppercase text-primary font-bold tracking-widest">
                    Proporcao CBD:THC
                  </span>
                  <p className="text-lg font-headline font-bold text-on-surface mt-0.5">
                    {treatmentPlan.cannabinoid_ratio}
                  </p>
                </div>
              )}
              {treatmentPlan.suggested_dosage && (
                <div>
                  <span className="text-[10px] uppercase text-stone-400 font-bold tracking-widest">
                    Dosagem Sugerida
                  </span>
                  <p className="text-sm text-on-surface mt-0.5">{treatmentPlan.suggested_dosage}</p>
                </div>
              )}
              {treatmentPlan.administration_route && (
                <div>
                  <span className="text-[10px] uppercase text-stone-400 font-bold tracking-widest">
                    Via de Administracao
                  </span>
                  <p className="text-sm text-on-surface mt-0.5">
                    {treatmentPlan.administration_route}
                  </p>
                </div>
              )}
              <button
                onClick={() =>
                  void copyToClipboard(
                    `Proporcao: ${treatmentPlan.cannabinoid_ratio}\nDosagem: ${treatmentPlan.suggested_dosage}\nVia: ${treatmentPlan.administration_route}`,
                  )
                }
                className="text-[10px] text-primary hover:underline flex items-center gap-1"
              >
                <MaterialIcon icon="content_copy" size="sm" className="text-[12px]" />
                Copiar recomendacao
              </button>
            </div>
          </Card>

          {/* Monitoring Plan */}
          {treatmentPlan.monitoring_plan && (
            <Card variant="glass" padding="sm">
              <button
                onClick={() => toggleSection("monitoring")}
                className="w-full flex items-center justify-between"
              >
                <div className="flex items-center gap-2">
                  <MaterialIcon icon="monitoring" size="sm" className="text-primary" />
                  <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                    Plano de Monitoramento
                  </span>
                </div>
                <MaterialIcon
                  icon={expandedSections.has("monitoring") ? "expand_less" : "expand_more"}
                  size="sm"
                  className="text-stone-500"
                />
              </button>
              {expandedSections.has("monitoring") && (
                <p className="text-sm text-stone-300 mt-3 leading-relaxed whitespace-pre-wrap">
                  {treatmentPlan.monitoring_plan}
                </p>
              )}
            </Card>
          )}

          {/* Precautions */}
          {treatmentPlan.precautions.length > 0 && (
            <Card variant="glass" padding="sm">
              <div className="flex items-center gap-2 mb-3">
                <MaterialIcon icon="health_and_safety" size="sm" className="text-amber-400" />
                <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                  Precaucoes
                </span>
              </div>
              <ul className="space-y-2">
                {treatmentPlan.precautions.map((p, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <MaterialIcon
                      icon="chevron_right"
                      size="sm"
                      className="text-amber-400 mt-0.5 shrink-0"
                    />
                    <span className="text-xs text-stone-300 leading-relaxed">{p}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Generate Prescription Button */}
          <Link href={`/med/prescricao/${attendanceId}`}>
            <Button icon="contract" className="w-full">
              Gerar Prescricao
            </Button>
          </Link>
        </>
      )}

      {!treatmentPlan?.cannabinoid_ratio && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <MaterialIcon icon="medication_liquid" size="xl" className="text-stone-700 mb-3" />
          <p className="text-stone-500 text-sm">Nenhum plano terapeutico disponivel.</p>
          <p className="text-stone-600 text-xs mt-1">
            O plano sera gerado apos a analise completa.
          </p>
        </div>
      )}
    </>
  );

  /** Tab: Evidencias Cientificas */
  const renderEvidenciasTab = () => (
    <>
      {scientificReport && (
        <>
          {/* Summary */}
          {scientificReport.summary && (
            <Card variant="glass" padding="sm" className="border-l-4 border-l-primary">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <MaterialIcon icon="summarize" size="sm" className="text-primary" />
                  <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                    Resumo Cientifico
                  </span>
                </div>
                <button
                  onClick={() => void copyToClipboard(scientificReport.summary)}
                  className="text-[10px] text-primary hover:underline"
                >
                  Copiar
                </button>
              </div>
              <p className="text-sm text-stone-300 leading-relaxed whitespace-pre-wrap">
                {scientificReport.summary}
              </p>
            </Card>
          )}

          {/* Supporting Evidence */}
          {scientificReport.supporting_evidence.length > 0 && (
            <Card variant="glass" padding="sm">
              <div className="flex items-center gap-2 mb-3">
                <MaterialIcon icon="science" size="sm" className="text-primary" />
                <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                  Evidencias de Suporte
                </span>
              </div>
              <ul className="space-y-3">
                {scientificReport.supporting_evidence.map((ev, i) => (
                  <li key={i} className="bg-white/5 border border-white/5 rounded-lg p-3">
                    <p className="text-xs text-stone-300 leading-relaxed">{ev}</p>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* References */}
          {scientificReport.references.length > 0 && (
            <Card variant="glass" padding="sm">
              <div className="flex items-center gap-2 mb-3">
                <MaterialIcon icon="menu_book" size="sm" className="text-primary" />
                <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                  Referencias
                </span>
              </div>
              <ul className="space-y-2">
                {scientificReport.references.map((ref, i) => (
                  <li key={i}>
                    <p className="text-[11px] text-primary leading-tight hover:underline cursor-pointer">
                      {ref}
                    </p>
                    <span className="text-[9px] text-stone-500 uppercase mt-0.5 block">
                      Referencia {i + 1}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* RAG Info */}
          <Card variant="glass" padding="sm">
            <div className="flex items-center gap-2 mb-3">
              <MaterialIcon icon="data_usage" size="sm" className="text-stone-400" />
              <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                Detalhes da Analise
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/5 rounded-lg p-2.5 text-center">
                <p className="text-lg font-bold font-mono text-primary">{report.rag_chunks_used}</p>
                <p className="text-[10px] text-stone-500 uppercase">Fontes Consultadas</p>
              </div>
              <div className="bg-white/5 rounded-lg p-2.5 text-center">
                <p className="text-[11px] font-bold font-mono text-on-surface truncate">
                  {report.report_model}
                </p>
                <p className="text-[10px] text-stone-500 uppercase">Modelo de Analise</p>
              </div>
            </div>
          </Card>
        </>
      )}

      {!scientificReport?.summary && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <MaterialIcon icon="menu_book" size="xl" className="text-stone-700 mb-3" />
          <p className="text-stone-500 text-sm">Nenhuma evidencia cientifica disponivel.</p>
        </div>
      )}
    </>
  );

  /** Tab: Prontuario */
  const renderProntuarioTab = () => (
    <>
      {/* Medical Record Form */}
      <Card variant="glass" padding="sm" className="border-l-4 border-l-primary">
        <div className="flex items-center gap-2 mb-4">
          <MaterialIcon icon="edit_note" size="sm" className="text-primary" />
          <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
            Prontuario da Consulta
          </span>
        </div>
        <div className="space-y-4">
          {/* Status */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Status da Consulta
            </label>
            <select
              value={mrStatus}
              onChange={(e) => setMrStatus(e.target.value)}
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface text-sm focus:border-primary-container focus:outline-none transition-colors"
            >
              {CONSULTATION_STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Observations */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Observacoes Medicas
            </label>
            <textarea
              value={mrObservations}
              onChange={(e) => setMrObservations(e.target.value)}
              rows={3}
              placeholder="Observacoes clinicas relevantes..."
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface text-sm placeholder:text-stone-600 focus:border-primary-container focus:outline-none transition-colors resize-none"
            />
          </div>

          {/* Clinical Assessment */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Avaliacao Clinica
            </label>
            <textarea
              value={mrAssessment}
              onChange={(e) => setMrAssessment(e.target.value)}
              rows={3}
              placeholder="Avaliacao clinica do paciente..."
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface text-sm placeholder:text-stone-600 focus:border-primary-container focus:outline-none transition-colors resize-none"
            />
          </div>

          {/* Conduct */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Conduta
            </label>
            <textarea
              value={mrConduct}
              onChange={(e) => setMrConduct(e.target.value)}
              rows={3}
              placeholder="Conduta terapeutica adotada..."
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface text-sm placeholder:text-stone-600 focus:border-primary-container focus:outline-none transition-colors resize-none"
            />
          </div>

          {/* Requested Exams */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Exames Solicitados
            </label>
            <textarea
              value={mrExams}
              onChange={(e) => setMrExams(e.target.value)}
              rows={2}
              placeholder="Separar por virgula: Hemograma, PCR, Vitamina D..."
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface text-sm placeholder:text-stone-600 focus:border-primary-container focus:outline-none transition-colors resize-none"
            />
          </div>

          {/* Follow-up Plan */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Plano de Retorno
            </label>
            <textarea
              value={mrFollowUp}
              onChange={(e) => setMrFollowUp(e.target.value)}
              rows={2}
              placeholder="Retorno em 30 dias para reavaliacao..."
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface text-sm placeholder:text-stone-600 focus:border-primary-container focus:outline-none transition-colors resize-none"
            />
          </div>

          {/* Save Button */}
          <Button icon="save" loading={saving} onClick={handleSaveMedicalRecord} className="w-full">
            Salvar Prontuario
          </Button>
        </div>
      </Card>

      {/* Previous Entries */}
      {medicalRecordEntries.length > 0 && (
        <Card variant="glass" padding="sm">
          <button
            onClick={() => toggleSection("prev-entries")}
            className="w-full flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <MaterialIcon icon="history" size="sm" className="text-stone-400" />
              <span className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                Entradas Anteriores ({medicalRecordEntries.length})
              </span>
            </div>
            <MaterialIcon
              icon={expandedSections.has("prev-entries") ? "expand_less" : "expand_more"}
              size="sm"
              className="text-stone-500"
            />
          </button>
          {expandedSections.has("prev-entries") && (
            <div className="mt-3 space-y-3">
              {medicalRecordEntries.map((entry) => (
                <MedicalRecordEntryCard key={entry.id} entry={entry} />
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Review Button */}
      <Button
        variant="secondary"
        icon="verified"
        loading={reviewing}
        onClick={handleReview}
        className="w-full"
      >
        Marcar como Revisado
      </Button>
    </>
  );

  /* -----------------------------------------------------------------------
   * Main Render
   * ----------------------------------------------------------------------- */

  return (
    <div className="h-[calc(100vh-64px)] lg:h-[calc(100vh-64px)] flex flex-col overflow-hidden -m-6 lg:-m-8">
      {/* Toast */}
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* ── DESKTOP LAYOUT ─────────────────────────────────────────── */}
      <div className="hidden lg:flex flex-1 gap-0 overflow-hidden">
        {/* Left: Chat Panel */}
        <div className="flex-1 flex flex-col border-r border-white/5 overflow-hidden">
          {renderChatPanel()}
        </div>

        {/* Right: AI Panel */}
        <div className="w-[420px] flex flex-col overflow-hidden shrink-0">{renderAiPanel()}</div>
      </div>

      {/* ── MOBILE LAYOUT ──────────────────────────────────────────── */}
      <div className="lg:hidden flex flex-col flex-1 overflow-hidden">
        {/* Mobile Tab Switcher */}
        <div className="flex shrink-0 border-b border-white/5">
          {MOBILE_PANELS.map((panel) => (
            <button
              key={panel.key}
              onClick={() => setMobilePanel(panel.key)}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 py-3 text-sm font-bold uppercase tracking-widest transition-all",
                mobilePanel === panel.key
                  ? "text-primary border-b-2 border-primary bg-primary/5"
                  : "text-stone-500 hover:text-stone-300",
              )}
            >
              <MaterialIcon icon={panel.icon} size="sm" />
              {panel.label}
            </button>
          ))}
        </div>

        {/* Mobile Content */}
        <div className="flex-1 overflow-hidden">
          {mobilePanel === "chat" ? renderChatPanel() : renderAiPanel()}
        </div>
      </div>

      {/* Custom scrollbar styles */}
      <style jsx>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.02);
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(163, 201, 58, 0.2);
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(163, 201, 58, 0.4);
        }
        .no-scrollbar::-webkit-scrollbar {
          display: none;
        }
        .no-scrollbar {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
        @keyframes slideInRight {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
        .animate-slide-in-right {
          animation: slideInRight 0.3s ease-out forwards;
        }
      `}</style>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Sub-Components
 * --------------------------------------------------------------------------- */

/** Vital sign single item */
function VitalItem({
  label,
  value,
  unit,
  icon,
}: {
  label: string;
  value: string;
  unit: string;
  icon: string;
}) {
  return (
    <div className="bg-white/5 border border-white/5 rounded-lg p-2.5 flex items-center gap-2">
      <MaterialIcon icon={icon} size="sm" className="text-primary shrink-0" />
      <div className="min-w-0">
        <p className="text-[10px] text-stone-500 uppercase">{label}</p>
        <p className="text-sm font-bold text-on-surface font-mono">
          {value}
          <span className="text-[10px] text-stone-500 font-normal ml-0.5">{unit}</span>
        </p>
      </div>
    </div>
  );
}

/** Medical record entry card */
function MedicalRecordEntryCard({ entry }: { entry: MedicalRecordEntry }) {
  const date = new Date(entry.created_at).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="bg-white/5 border border-white/5 rounded-xl p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge tone="neutral">{entry.entry_type}</Badge>
          <Badge tone={entry.status === "revisado" ? "success" : "neutral"}>{entry.status}</Badge>
        </div>
        <span className="text-[10px] text-stone-500">{date}</span>
      </div>
      {entry.author_name && (
        <p className="text-[10px] text-stone-500">
          Por: <span className="text-stone-400">{entry.author_name}</span>
        </p>
      )}
      {entry.medical_observations && (
        <div>
          <p className="text-[10px] text-stone-500 uppercase font-bold">Observacoes</p>
          <p className="text-xs text-stone-300 leading-relaxed">{entry.medical_observations}</p>
        </div>
      )}
      {entry.clinical_assessment && (
        <div>
          <p className="text-[10px] text-stone-500 uppercase font-bold">Avaliacao</p>
          <p className="text-xs text-stone-300 leading-relaxed">{entry.clinical_assessment}</p>
        </div>
      )}
      {entry.conduct && (
        <div>
          <p className="text-[10px] text-stone-500 uppercase font-bold">Conduta</p>
          <p className="text-xs text-stone-300 leading-relaxed">{entry.conduct}</p>
        </div>
      )}
      {entry.requested_exams.length > 0 && (
        <div>
          <p className="text-[10px] text-stone-500 uppercase font-bold">Exames</p>
          <div className="flex flex-wrap gap-1 mt-0.5">
            {entry.requested_exams.map((ex, i) => (
              <span
                key={i}
                className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full"
              >
                {ex}
              </span>
            ))}
          </div>
        </div>
      )}
      {entry.follow_up_plan && (
        <div>
          <p className="text-[10px] text-stone-500 uppercase font-bold">Retorno</p>
          <p className="text-xs text-stone-300 leading-relaxed">{entry.follow_up_plan}</p>
        </div>
      )}
    </div>
  );
}
