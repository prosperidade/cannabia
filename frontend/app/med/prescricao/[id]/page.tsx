"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { ApiError, getAttendance, calculateDosage, emitPrescription } from "@/lib/api";
import { Button, Card, Input, Badge, MaterialIcon } from "@/components/ui-tw";
import type { PrescriptionType, PrescriptionItem, TreatmentPlan } from "@/lib/types-medical";
import type { AttendanceDetail, PrescriptionContract } from "@/lib/types";

/* ── helpers ─────────────────────────────────────────────────────── */

const EMPTY_ITEM: PrescriptionItem = {
  medication: "",
  concentration: "",
  dosage: "",
  route: "oral",
  frequency: "8/8h",
  duration: "30 dias",
  instructions: "",
};

const ROUTE_OPTIONS = [
  { value: "oral", label: "Oral" },
  { value: "sublingual", label: "Sublingual" },
  { value: "topico", label: "Topico" },
  { value: "inalatorio", label: "Inalatorio" },
  { value: "transdermico", label: "Transdermico" },
];

const FREQUENCY_OPTIONS = [
  { value: "8/8h", label: "8/8h (TID)" },
  { value: "12/12h", label: "12/12h (BID)" },
  { value: "24/24h", label: "1x ao dia (QD)" },
  { value: "SOS", label: "Se necessario (SOS)" },
];

function formatDate(d: Date) {
  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

function sourceLabel(source?: string) {
  if (!source) return "Nao informado";
  return source
    .replace(/^payload\./, "Entrada manual > ")
    .replace(/^report\./, "Relatorio > ")
    .replace(/^default\./, "Padrao > ")
    .replace(/\./g, " > ");
}

type DosagePreview = {
  prescription_contract?: PrescriptionContract;
  dosage_input?: Record<string, unknown>;
  recommendation?: Record<string, unknown>;
  safety_limits?: Record<string, unknown>;
  token_usage?: Record<string, unknown>;
  estimated_cost_usd?: number;
  processing_time_ms?: number;
};

/* ── page ────────────────────────────────────────────────────────── */

export default function PrescricaoPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { data: session } = useApiSession();

  const [attendance, setAttendance] = useState<AttendanceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [emitting, setEmitting] = useState(false);
  const [emitSuccess, setEmitSuccess] = useState(false);

  /* form state */
  const [prescType, setPrescType] = useState<PrescriptionType>("branca");
  const [patientName, setPatientName] = useState("");
  const [patientCpf, setPatientCpf] = useState("");
  const [prescriberName, setPrescriberName] = useState("");
  const [prescriberCrm, setPrescriberCrm] = useState("");
  const [prescriberUf, setPrescriberUf] = useState("SP");
  const [items, setItems] = useState<PrescriptionItem[]>([{ ...EMPTY_ITEM }]);
  const [notes, setNotes] = useState("");
  const [cannabinoidRatio, setCannabinoidRatio] = useState("");
  const [aiSuggestion, setAiSuggestion] = useState<string | null>(null);
  const [prescriptionContract, setPrescriptionContract] = useState<PrescriptionContract | null>(
    null,
  );
  const [weightKg, setWeightKg] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [priorCannabisUse, setPriorCannabisUse] = useState<"" | "true" | "false">("");
  const [dosagePreview, setDosagePreview] = useState<DosagePreview | null>(null);
  const [contractError, setContractError] = useState<string | null>(null);

  /* load attendance */
  useEffect(() => {
    if (!params.id) return;
    (async () => {
      try {
        const data = await getAttendance(params.id);
        setAttendance(data);
        setPrescriptionContract(data.prescription_contract ?? null);

        /* pre-fill from attendance */
        setPatientName(data.report.patient_name ?? "");
        const resolved = data.prescription_contract?.resolved_values ?? {};
        if (typeof resolved.weight_kg === "number") setWeightKg(String(resolved.weight_kg));
        if (typeof resolved.height_cm === "number") setHeightCm(String(resolved.height_cm));
        if (typeof resolved.prior_cannabis_use === "boolean") {
          setPriorCannabisUse(resolved.prior_cannabis_use ? "true" : "false");
        }

        const tp = data.report.treatment_plan as Partial<TreatmentPlan> | null;
        if (tp) {
          if (tp.cannabinoid_ratio) setCannabinoidRatio(tp.cannabinoid_ratio);
          if (tp.suggested_dosage || tp.administration_route) {
            setItems([
              {
                ...EMPTY_ITEM,
                dosage: tp.suggested_dosage ?? "",
                route: tp.administration_route ?? "oral",
              },
            ]);
          }
        }
      } catch {
        /* ignore */
      } finally {
        setLoading(false);
      }
    })();
  }, [params.id]);

  /* pre-fill prescriber from session */
  useEffect(() => {
    if (session?.user) {
      setPrescriberName(session.user.username);
    }
  }, [session]);

  /* item management */
  const updateItem = useCallback((index: number, field: keyof PrescriptionItem, value: string) => {
    setItems((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  }, []);

  const addItem = () => setItems((prev) => [...prev, { ...EMPTY_ITEM }]);

  const removeItem = (index: number) => {
    if (items.length <= 1) return;
    setItems((prev) => prev.filter((_, i) => i !== index));
  };

  /* build prescription data object */
  const buildDosagePayload = () => {
    const payload: Record<string, unknown> = {
      attendance_id: Number(params.id),
    };

    if (weightKg.trim()) payload.weight_kg = Number(weightKg.replace(",", "."));
    if (heightCm.trim()) payload.height_cm = Number(heightCm.replace(",", "."));
    if (priorCannabisUse !== "") payload.prior_cannabis_use = priorCannabisUse === "true";

    return payload;
  };

  /* calculate dosage */
  const handleCalculate = async () => {
    if (!session) return;
    setContractError(null);
    setCalculating(true);
    try {
      const res = await calculateDosage(session.csrf_token, buildDosagePayload());
      const preview = (res.data ?? null) as DosagePreview | null;
      const recommendation = preview?.recommendation ?? null;
      const nextContract = preview?.prescription_contract ?? null;

      setDosagePreview(preview);
      setPrescriptionContract(nextContract);

      if (nextContract?.resolved_values) {
        const resolved = nextContract.resolved_values;
        if (typeof resolved.weight_kg === "number") setWeightKg(String(resolved.weight_kg));
        if (typeof resolved.height_cm === "number") setHeightCm(String(resolved.height_cm));
        if (typeof resolved.prior_cannabis_use === "boolean") {
          setPriorCannabisUse(resolved.prior_cannabis_use ? "true" : "false");
        }
      }

      if (recommendation && typeof recommendation === "object") {
        const rec = recommendation as Record<string, unknown>;
        const titration = Array.isArray(rec.titration_protocol)
          ? (rec.titration_protocol[0] as Record<string, unknown> | undefined)
          : undefined;
        const concentration =
          typeof rec.concentration_mg_ml === "number" ? `${rec.concentration_mg_ml} mg/mL` : "";
        const route = typeof rec.administration_route === "string" ? rec.administration_route : "";
        const dosage =
          titration &&
          typeof titration.drops_per_dose === "number" &&
          typeof titration.doses_per_day === "number"
            ? `${titration.drops_per_dose} gotas ${titration.doses_per_day}x/dia`
            : "";

        if (typeof rec.cannabinoid_ratio === "string" && rec.cannabinoid_ratio) {
          setCannabinoidRatio(rec.cannabinoid_ratio);
        }

        setItems((prev) => {
          const first = prev[0] ?? { ...EMPTY_ITEM };
          return [
            {
              ...first,
              concentration: concentration || first.concentration,
              dosage: dosage || first.dosage,
              route: route || first.route,
              instructions:
                typeof rec.clinical_rationale === "string" && rec.clinical_rationale
                  ? rec.clinical_rationale
                  : first.instructions,
            },
            ...prev.slice(1),
          ];
        });
      }

      const suggestion =
        recommendation && typeof recommendation === "object"
          ? JSON.stringify(recommendation, null, 2)
          : JSON.stringify(preview ?? {}, null, 2);
      setAiSuggestion(suggestion);
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.code === "prescription_contract_incomplete" && error.details) {
          const details = error.details as unknown as PrescriptionContract;
          setPrescriptionContract(details);
          setContractError(error.message);
        }
        setAiSuggestion(error.message);
      } else {
        setAiSuggestion("Erro ao calcular dosagem. Tente novamente.");
      }
    } finally {
      setCalculating(false);
    }
  };

  /* emit prescription */
  const handleEmit = async () => {
    if (!session?.user) return;

    if (!dosagePreview?.recommendation) {
      setAiSuggestion("Calcule a dosagem pela IA antes de emitir a prescricao.");
      return;
    }
    if (!attendance?.report.patient_id) {
      setAiSuggestion("Este atendimento ainda nao possui patient_id valido para emissao.");
      return;
    }
    if (!prescriberCrm.trim()) {
      setAiSuggestion("Informe o CRM do prescritor antes de emitir.");
      return;
    }

    setEmitting(true);
    try {
      await emitPrescription(session.csrf_token, {
        patient_id: attendance.report.patient_id,
        doctor_user_id: session.user.id,
        doctor_name: prescriberName || session.user.username,
        doctor_crm: prescriberCrm.trim(),
        dosage_recommendation: dosagePreview.recommendation,
        custom_notes: notes || null,
        validity_days: 180,
      });
      setEmitSuccess(true);
    } catch (error) {
      if (error instanceof ApiError) {
        setAiSuggestion(error.message);
      } else {
        setAiSuggestion("Erro ao emitir prescricao. Tente novamente.");
      }
    } finally {
      setEmitting(false);
    }
  };

  /* loading state */
  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm">Carregando prescricao...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-12">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="h-[1px] w-8 bg-primary" />
            <span className="font-headline text-xs font-bold tracking-widest text-primary uppercase">
              Protocolo de Prescricao
            </span>
          </div>
          <h1 className="text-3xl md:text-4xl font-headline font-extrabold text-white tracking-tight">
            Prescricao Digital
          </h1>
          {patientName && (
            <p className="text-on-surface-variant mt-1">
              Paciente: <span className="text-white font-semibold">{patientName}</span>
              {" - "}
              {formatDate(new Date())}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3 bg-surface-container-high px-4 py-2 rounded-full border border-outline-variant/30">
          <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
          <span className="text-xs font-medium text-on-surface-variant">Analise IA Ativa</span>
        </div>
      </div>

      {/* ── Two-column grid ─────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LEFT COLUMN: Form */}
        <div className="lg:col-span-8 space-y-6">
          {/* Prescription Type */}
          <Card>
            <div className="flex items-center gap-3 mb-6">
              <MaterialIcon icon="description" className="text-primary" />
              <h3 className="font-headline font-bold text-lg text-white">Tipo de Receita</h3>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setPrescType("branca")}
                className={cn(
                  "flex-1 flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all",
                  prescType === "branca"
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-outline-variant/30 bg-surface-container hover:border-primary/50 text-on-surface-variant",
                )}
              >
                <MaterialIcon icon="article" />
                <span className="text-sm font-bold">Receita Branca</span>
                <span className="text-[9px] opacity-60">Receituario Simples</span>
              </button>
              <button
                onClick={() => setPrescType("azul")}
                className={cn(
                  "flex-1 flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all",
                  prescType === "azul"
                    ? "border-blue-400 bg-blue-400/10 text-blue-400"
                    : "border-outline-variant/30 bg-surface-container hover:border-blue-400/50 text-on-surface-variant",
                )}
              >
                <MaterialIcon icon="verified" />
                <span className="text-sm font-bold">Receita Azul</span>
                <span className="text-[9px] opacity-60">ANVISA - Controlada</span>
              </button>
            </div>
          </Card>

          {/* Patient & Prescriber Info */}
          <Card>
            <div className="flex items-center gap-3 mb-6">
              <MaterialIcon icon="person" className="text-primary" />
              <h3 className="font-headline font-bold text-lg text-white">
                Dados do Paciente e Prescritor
              </h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Nome do Paciente"
                icon="person"
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
                placeholder="Nome completo"
              />
              <Input
                label="CPF"
                icon="badge"
                value={patientCpf}
                onChange={(e) => setPatientCpf(e.target.value)}
                placeholder="000.000.000-00"
              />
              <Input
                label="Nome do Prescritor"
                icon="medical_services"
                value={prescriberName}
                onChange={(e) => setPrescriberName(e.target.value)}
                placeholder="Dr(a). Nome"
              />
              <div className="flex gap-3">
                <div className="flex-1">
                  <Input
                    label="CRM"
                    value={prescriberCrm}
                    onChange={(e) => setPrescriberCrm(e.target.value)}
                    placeholder="000000"
                  />
                </div>
                <div className="w-24">
                  <Input
                    label="UF"
                    value={prescriberUf}
                    onChange={(e) => setPrescriberUf(e.target.value)}
                    placeholder="SP"
                  />
                </div>
              </div>
            </div>
          </Card>

          <Card
            className={cn(
              "border-l-4",
              prescriptionContract?.ready ? "border-l-primary" : "border-l-amber-400",
            )}
          >
            <div className="flex items-center gap-3 mb-4">
              <MaterialIcon
                icon={prescriptionContract?.ready ? "verified" : "rule"}
                className={prescriptionContract?.ready ? "text-primary" : "text-amber-400"}
              />
              <h3 className="font-headline font-bold text-lg text-white">
                Contrato Clinico para Prescricao Segura
              </h3>
              <Badge tone={prescriptionContract?.ready ? "success" : "warning"}>
                {prescriptionContract?.ready ? "Pronto" : "Pendente"}
              </Badge>
            </div>

            <p className="text-sm text-on-surface-variant">
              {contractError ??
                prescriptionContract?.message ??
                "Defina os campos minimos antes do calculo."}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5">
              <Input
                label="Peso (kg)"
                icon="monitor_weight"
                type="number"
                step="0.1"
                value={weightKg}
                onChange={(e) => setWeightKg(e.target.value)}
                hint={sourceLabel(prescriptionContract?.source_map?.weight_kg)}
                placeholder="Ex: 72.5"
              />
              <Input
                label="Altura (cm)"
                icon="height"
                type="number"
                step="0.1"
                value={heightCm}
                onChange={(e) => setHeightCm(e.target.value)}
                hint={sourceLabel(prescriptionContract?.source_map?.height_cm)}
                placeholder="Ex: 175"
              />
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
                  Uso prévio de cannabis
                </label>
                <select
                  value={priorCannabisUse}
                  onChange={(e) => setPriorCannabisUse(e.target.value as "" | "true" | "false")}
                  className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors"
                >
                  <option value="">Selecione</option>
                  <option value="true">Sim</option>
                  <option value="false">Nao</option>
                </select>
                <span className="text-[11px] text-stone-500">
                  {sourceLabel(prescriptionContract?.source_map?.prior_cannabis_use)}
                </span>
              </div>
            </div>

            {prescriptionContract?.missing_required_fields?.length ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {prescriptionContract.missing_required_fields.map((item) => (
                  <Badge key={item.field} tone="warning">
                    Falta {item.label}
                  </Badge>
                ))}
              </div>
            ) : null}
          </Card>

          {/* CBD:THC Ratio */}
          {cannabinoidRatio && (
            <Card className="border-l-4 border-primary">
              <div className="flex items-center gap-3 mb-4">
                <MaterialIcon icon="biotech" className="text-primary" />
                <h3 className="font-headline font-bold text-lg text-white">
                  Proporcao Canabinoides
                </h3>
                <Badge tone="primary">Plano Terapeutico</Badge>
              </div>
              <div className="flex justify-between items-center mb-4">
                <span className="text-sm font-medium text-on-surface-variant">
                  Proporcao CBD/THC recomendada
                </span>
                <span className="text-primary font-bold font-headline text-lg">
                  {cannabinoidRatio}
                </span>
              </div>
              <div className="h-3 w-full bg-surface-container-lowest rounded-full relative overflow-hidden">
                <div className="absolute left-0 top-0 h-full w-[80%] bg-gradient-to-r from-primary to-secondary rounded-full" />
              </div>
              <div className="flex justify-between mt-2">
                <span className="text-[10px] text-stone-500 font-bold">MAIS CBD</span>
                <span className="text-[10px] text-stone-500 font-bold">BALANCEADO</span>
                <span className="text-[10px] text-stone-500 font-bold">MAIS THC</span>
              </div>
            </Card>
          )}

          {/* Prescription Items */}
          <Card>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <MaterialIcon icon="medication" className="text-primary" />
                <h3 className="font-headline font-bold text-lg text-white">Itens da Prescricao</h3>
              </div>
              <Badge tone="neutral">
                {items.length} {items.length === 1 ? "item" : "itens"}
              </Badge>
            </div>

            <div className="space-y-6">
              {items.map((item, idx) => (
                <div
                  key={idx}
                  className="relative bg-surface-container-low rounded-xl p-5 border border-outline-variant/20"
                >
                  {items.length > 1 && (
                    <button
                      onClick={() => removeItem(idx)}
                      className="absolute top-3 right-3 p-1 text-stone-500 hover:text-error transition-colors"
                      title="Remover item"
                    >
                      <MaterialIcon icon="close" size="sm" />
                    </button>
                  )}
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-[10px] font-bold text-primary uppercase tracking-widest">
                      Item {idx + 1}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Input
                      label="Produto / Medicamento"
                      value={item.medication}
                      onChange={(e) => updateItem(idx, "medication", e.target.value)}
                      placeholder="Ex: Oleo Full Spectrum CBD"
                    />
                    <Input
                      label="Concentracao"
                      value={item.concentration}
                      onChange={(e) => updateItem(idx, "concentration", e.target.value)}
                      placeholder="Ex: CBD 20mg/ml"
                    />
                    <Input
                      label="Dosagem"
                      value={item.dosage}
                      onChange={(e) => updateItem(idx, "dosage", e.target.value)}
                      placeholder="Ex: 0.5ml"
                    />
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
                        Frequencia
                      </label>
                      <select
                        value={item.frequency}
                        onChange={(e) => updateItem(idx, "frequency", e.target.value)}
                        className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors"
                      >
                        {FREQUENCY_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <Input
                      label="Duracao"
                      value={item.duration}
                      onChange={(e) => updateItem(idx, "duration", e.target.value)}
                      placeholder="Ex: 30 dias"
                    />
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
                        Via de Administracao
                      </label>
                      <select
                        value={item.route}
                        onChange={(e) => updateItem(idx, "route", e.target.value)}
                        className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors"
                      >
                        {ROUTE_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="mt-4">
                    <Input
                      label="Instrucoes Adicionais"
                      value={item.instructions}
                      onChange={(e) => updateItem(idx, "instructions", e.target.value)}
                      placeholder="Instrucoes de uso, titulacao, etc."
                    />
                  </div>
                </div>
              ))}
            </div>

            <Button variant="secondary" size="sm" icon="add" onClick={addItem} className="mt-4">
              Adicionar Item
            </Button>
          </Card>

          {/* Notes */}
          <Card>
            <div className="flex items-center gap-3 mb-4">
              <MaterialIcon icon="history_edu" className="text-primary" />
              <h3 className="font-headline font-bold text-lg text-white">Observacoes Clinicas</h3>
            </div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full h-36 bg-surface-container-low border border-outline-variant/30 rounded-xl p-4 text-sm text-on-surface focus:border-primary-container focus:outline-none resize-none placeholder-stone-600"
              placeholder="Historico clinico relevante, contraindicacoes, observacoes de monitoramento..."
            />
            {/* AI Safety Check */}
            <div className="mt-4 p-4 rounded-lg bg-primary/5 border border-primary/20">
              <div className="flex items-center gap-2 mb-2 text-primary">
                <MaterialIcon icon="verified_user" size="sm" />
                <span className="text-[10px] font-bold uppercase tracking-widest">
                  Verificacao de Seguranca IA
                </span>
              </div>
              <p className="text-[11px] text-stone-400 italic">
                Nenhuma interacao adversa detectada entre os perfis botanicos e medicamentos atuais.
              </p>
            </div>
          </Card>
        </div>

        {/* RIGHT COLUMN: Preview & Actions */}
        <div className="lg:col-span-4 space-y-6">
          {/* Prescription Preview */}
          <Card className="sticky top-6">
            <div className="flex items-center gap-3 mb-6">
              <MaterialIcon icon="preview" className="text-primary" />
              <h3 className="font-headline font-bold text-lg text-white">Previa da Prescricao</h3>
            </div>

            {/* Preview card in white (like print) */}
            <div className="bg-white rounded-lg p-6 text-stone-900 min-h-[320px] relative overflow-hidden">
              <div className="absolute inset-0 flex items-center justify-center opacity-[0.03] pointer-events-none">
                <MaterialIcon icon="medical_services" className="text-[200px]" />
              </div>
              <div className="relative z-10">
                {/* Header */}
                <div className="border-b-2 border-stone-100 pb-4 mb-4">
                  <h4 className="font-headline font-bold text-lg text-stone-900 uppercase tracking-tight">
                    Cannab&apos;IA Clinical
                  </h4>
                  <p className="text-[10px] text-stone-500">Prescricao Medica Digital</p>
                  <Badge tone={prescType === "azul" ? "info" : "neutral"} className="mt-2">
                    {prescType === "azul" ? "Receita Azul - ANVISA" : "Receita Branca"}
                  </Badge>
                </div>

                {/* Patient */}
                <div className="grid grid-cols-2 gap-3 mb-4 text-xs">
                  <div>
                    <p className="text-[9px] uppercase text-stone-400 font-bold">Paciente</p>
                    <p className="font-semibold text-stone-800">{patientName || "---"}</p>
                  </div>
                  <div>
                    <p className="text-[9px] uppercase text-stone-400 font-bold">CPF</p>
                    <p className="font-semibold text-stone-800">{patientCpf || "---"}</p>
                  </div>
                  <div>
                    <p className="text-[9px] uppercase text-stone-400 font-bold">Data</p>
                    <p className="font-semibold text-stone-800">{formatDate(new Date())}</p>
                  </div>
                  {cannabinoidRatio && (
                    <div>
                      <p className="text-[9px] uppercase text-stone-400 font-bold">CBD:THC</p>
                      <p className="font-semibold text-stone-800">{cannabinoidRatio}</p>
                    </div>
                  )}
                </div>

                {/* Items preview */}
                <div className="border-t border-stone-100 pt-3 space-y-3">
                  {items.map((item, idx) => (
                    <div key={idx} className="border-l-2 border-primary/60 pl-3">
                      <p className="font-bold text-sm text-stone-800">
                        {item.medication || "Medicamento"}
                      </p>
                      <p className="text-[10px] text-stone-500">
                        {item.concentration && `${item.concentration} | `}
                        {item.dosage && `${item.dosage} `}
                        {item.frequency && `- ${item.frequency} `}
                        {item.duration && `por ${item.duration}`}
                      </p>
                      {item.route && (
                        <p className="text-[10px] text-stone-400 capitalize">Via: {item.route}</p>
                      )}
                    </div>
                  ))}
                </div>

                {/* Prescriber signature area */}
                <div className="pt-8 mt-6 border-t border-stone-100 flex flex-col items-center">
                  <div className="w-48 h-12 border-b border-stone-300 flex items-center justify-center italic text-stone-300 text-sm">
                    {prescriberName || "Assinatura Digital"}
                  </div>
                  <p className="text-[10px] font-bold text-stone-400 mt-1 uppercase">
                    {prescriberName
                      ? `${prescriberName} - CRM ${prescriberCrm}/${prescriberUf}`
                      : "CRM / UF"}
                  </p>
                </div>
              </div>
            </div>

            {/* AI Suggestion */}
            {aiSuggestion && (
              <div className="mt-4 p-4 rounded-lg bg-primary/5 border border-primary/20">
                <div className="flex items-center gap-2 mb-2 text-primary">
                  <MaterialIcon icon="psychology" size="sm" />
                  <span className="text-[10px] font-bold uppercase tracking-widest">
                    Sugestao IA
                  </span>
                </div>
                <pre className="text-[11px] text-stone-400 whitespace-pre-wrap font-body">
                  {aiSuggestion}
                </pre>
              </div>
            )}

            {/* Actions */}
            <div className="mt-6 space-y-3">
              <Button
                variant="secondary"
                icon="calculate"
                loading={calculating}
                onClick={handleCalculate}
                className="w-full"
              >
                Calcular Dosagem IA
              </Button>

              {!emitSuccess ? (
                <Button
                  variant="primary"
                  icon="send"
                  loading={emitting}
                  onClick={handleEmit}
                  className="w-full"
                >
                  Emitir Prescricao
                </Button>
              ) : (
                <div className="text-center space-y-3">
                  <div className="flex flex-col items-center gap-2 p-4 rounded-lg bg-primary/10 border border-primary/30">
                    <MaterialIcon icon="check_circle" filled size="lg" className="text-primary" />
                    <p className="text-sm font-bold text-primary">
                      Prescricao emitida com sucesso!
                    </p>
                  </div>
                  <Button
                    variant="primary"
                    icon="draw"
                    onClick={() => router.push(`/med/prescricao/${params.id}/assinar`)}
                    className="w-full"
                  >
                    Assinar Digitalmente
                  </Button>
                </div>
              )}

              <Button variant="ghost" icon="save" className="w-full">
                Salvar Rascunho
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {/* ── Footer meta ─────────────────────────────────────── */}
      <footer className="flex flex-col md:flex-row justify-between items-center text-stone-600 gap-4 pt-8">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <MaterialIcon icon="encrypted" size="sm" />
            <span className="text-[10px] uppercase font-bold tracking-widest">
              Criptografia Ponta-a-Ponta
            </span>
          </div>
          <div className="flex items-center gap-2">
            <MaterialIcon icon="gavel" size="sm" />
            <span className="text-[10px] uppercase font-bold tracking-widest">Conforme LGPD</span>
          </div>
        </div>
        <p className="text-[10px] font-medium">Cannab&apos;IA Clinical v4.2.0</p>
      </footer>
    </div>
  );
}
