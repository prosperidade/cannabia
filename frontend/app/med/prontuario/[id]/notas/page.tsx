"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

import { cn } from "@/lib/cn";
import { getAttendance, saveMedicalRecord, ApiError } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import type { AttendanceDetail, MedicalRecordEntry, MedicalRecordPayload } from "@/lib/types";
import { MaterialIcon, Badge, Button, Card } from "@/components/ui-tw";

/* ---------------------------------------------------------------------------
 * Helpers
 * --------------------------------------------------------------------------- */

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/* ---------------------------------------------------------------------------
 * Sub-components
 * --------------------------------------------------------------------------- */

function PreviousNoteItem({ entry }: { entry: MedicalRecordEntry }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-2xl bg-black/20 border border-white/5 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors text-left"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-bold text-on-surface truncate">{entry.title}</h4>
            <Badge tone="neutral">{entry.status}</Badge>
          </div>
          <div className="flex items-center gap-3 mt-1 text-[10px] text-stone-500">
            {entry.author_name && (
              <span className="flex items-center gap-1">
                <MaterialIcon icon="person" size="sm" />
                {entry.author_name}
              </span>
            )}
            <span>{formatDate(entry.created_at)}</span>
          </div>
        </div>
        <MaterialIcon
          icon={expanded ? "expand_less" : "expand_more"}
          size="md"
          className="text-stone-400 ml-2"
        />
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-white/5 pt-3">
          {entry.medical_observations && (
            <div>
              <p className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-1">
                Observacoes
              </p>
              <p className="text-sm text-stone-300 leading-relaxed whitespace-pre-wrap">
                {entry.medical_observations}
              </p>
            </div>
          )}
          {entry.clinical_assessment && (
            <div>
              <p className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-1">
                Avaliacao Clinica
              </p>
              <p className="text-sm text-stone-300 leading-relaxed whitespace-pre-wrap">
                {entry.clinical_assessment}
              </p>
            </div>
          )}
          {entry.conduct && (
            <div>
              <p className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-1">
                Conduta
              </p>
              <p className="text-sm text-stone-300 leading-relaxed whitespace-pre-wrap">
                {entry.conduct}
              </p>
            </div>
          )}
          {entry.requested_exams.length > 0 && (
            <div>
              <p className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-1">
                Exames Solicitados
              </p>
              <div className="flex flex-wrap gap-1.5">
                {entry.requested_exams.map((exam) => (
                  <span
                    key={exam}
                    className="px-2 py-1 bg-primary/10 border border-primary/20 rounded-lg text-xs text-primary"
                  >
                    {exam}
                  </span>
                ))}
              </div>
            </div>
          )}
          {entry.follow_up_plan && (
            <div>
              <p className="text-[10px] font-black text-stone-500 uppercase tracking-widest mb-1">
                Plano de Acompanhamento
              </p>
              <p className="text-sm text-stone-300 leading-relaxed whitespace-pre-wrap">
                {entry.follow_up_plan}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Notes Form
 * --------------------------------------------------------------------------- */

type FormData = {
  medical_observations: string;
  clinical_assessment: string;
  conduct: string;
  requested_exams_text: string;
  follow_up_plan: string;
};

const INITIAL_FORM: FormData = {
  medical_observations: "",
  clinical_assessment: "",
  conduct: "",
  requested_exams_text: "",
  follow_up_plan: "",
};

function NotesForm({
  attendanceId,
  csrfToken,
  consultationEntry,
  onSaved,
}: {
  attendanceId: string;
  csrfToken: string;
  consultationEntry: MedicalRecordEntry | null;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<FormData>(() => {
    if (consultationEntry) {
      return {
        medical_observations: consultationEntry.medical_observations ?? "",
        clinical_assessment: consultationEntry.clinical_assessment ?? "",
        conduct: consultationEntry.conduct ?? "",
        requested_exams_text: consultationEntry.requested_exams.join(", "),
        follow_up_plan: consultationEntry.follow_up_plan ?? "",
      };
    }
    return INITIAL_FORM;
  });

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Collapsible sections for mobile
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    observations: true,
    assessment: true,
    conduct: true,
    exams: true,
    followup: true,
  });

  function toggleSection(key: string) {
    setExpandedSections((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function handleChange(field: keyof FormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setSaveSuccess(false);
    setSaveError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    const payload: MedicalRecordPayload = {
      consultation_status: "em_andamento",
      medical_observations: form.medical_observations.trim(),
      clinical_assessment: form.clinical_assessment.trim(),
      conduct: form.conduct.trim(),
      requested_exams: form.requested_exams_text
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      follow_up_plan: form.follow_up_plan.trim(),
    };

    try {
      await saveMedicalRecord(attendanceId, csrfToken, payload);
      setSaveSuccess(true);
      onSaved();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Falha ao salvar notas medicas.";
      setSaveError(message);
    } finally {
      setSaving(false);
    }
  }

  const sections = [
    {
      key: "observations",
      label: "Observacoes Medicas",
      icon: "visibility",
      field: "medical_observations" as keyof FormData,
      placeholder:
        "Descreva suas observacoes clinicas sobre o paciente, sintomas observados, evolucao do quadro...",
      rows: 5,
    },
    {
      key: "assessment",
      label: "Avaliacao Clinica",
      icon: "fact_check",
      field: "clinical_assessment" as keyof FormData,
      placeholder:
        "Registre sua avaliacao clinica, diagnostico diferencial, classificacao de risco...",
      rows: 4,
    },
    {
      key: "conduct",
      label: "Conduta",
      icon: "clinical_notes",
      field: "conduct" as keyof FormData,
      placeholder: "Descreva a conduta adotada, ajustes de dosagem, orientacoes ao paciente...",
      rows: 4,
    },
    {
      key: "exams",
      label: "Exames Solicitados",
      icon: "biotech",
      field: "requested_exams_text" as keyof FormData,
      placeholder: "Hemograma completo, Vitamina D, Perfil hepatico (separe por virgula)",
      rows: 2,
    },
    {
      key: "followup",
      label: "Plano de Acompanhamento",
      icon: "event_repeat",
      field: "follow_up_plan" as keyof FormData,
      placeholder: "Retorno em 30 dias, reavaliar dosagem, monitorar efeitos colaterais...",
      rows: 3,
    },
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {sections.map((section) => {
        const isExpanded = expandedSections[section.key];
        return (
          <div
            key={section.key}
            className="rounded-2xl bg-white/[0.02] border border-white/5 overflow-hidden"
          >
            {/* Section header - collapsible on mobile */}
            <button
              type="button"
              onClick={() => toggleSection(section.key)}
              className="w-full flex items-center justify-between p-4 md:cursor-default"
            >
              <div className="flex items-center gap-2">
                <MaterialIcon icon={section.icon} size="sm" className="text-primary" />
                <h4 className="text-sm font-bold text-on-surface">{section.label}</h4>
              </div>
              <MaterialIcon
                icon={isExpanded ? "expand_less" : "expand_more"}
                size="sm"
                className="text-stone-500 md:hidden"
              />
            </button>

            {/* Section content */}
            <div className={cn("px-4 pb-4 transition-all", !isExpanded && "hidden md:block")}>
              <textarea
                value={form[section.field]}
                onChange={(e) => handleChange(section.field, e.target.value)}
                placeholder={section.placeholder}
                rows={section.rows}
                className={cn(
                  "w-full bg-surface-container-low border border-outline-variant/30",
                  "rounded-xl p-4 text-sm text-on-surface leading-relaxed",
                  "placeholder:text-stone-600",
                  "focus:ring-2 focus:ring-primary/30 focus:border-primary/30",
                  "transition-all outline-none resize-none",
                )}
              />
            </div>
          </div>
        );
      })}

      {/* Status messages */}
      {saveError && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-error/10 border border-error/20 text-sm text-error">
          <MaterialIcon icon="error" size="sm" />
          {saveError}
        </div>
      )}
      {saveSuccess && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-sm text-emerald-400">
          <MaterialIcon icon="check_circle" size="sm" />
          Notas salvas com sucesso!
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2">
        <Link
          href={`/med/prontuario/${attendanceId}`}
          className="flex items-center justify-center gap-2 px-5 py-3 rounded-lg border border-white/10 hover:bg-white/5 transition-all text-sm text-stone-400 font-medium"
        >
          <MaterialIcon icon="arrow_back" size="sm" />
          Voltar ao Perfil
        </Link>
        <Button
          type="submit"
          variant="primary"
          size="md"
          icon="save"
          loading={saving}
          className="sm:w-auto"
        >
          Salvar Notas
        </Button>
      </div>
    </form>
  );
}

/* ---------------------------------------------------------------------------
 * Main Page Component
 * --------------------------------------------------------------------------- */

export default function NotasMedicasPage() {
  const params = useParams();
  const router = useRouter();
  const { data: session } = useApiSession();
  const id = params.id as string;

  const [detail, setDetail] = useState<AttendanceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAttendance(id);
      setDetail(data);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Falha ao carregar dados do atendimento.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  /* ---- Loading state ---- */
  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando notas...</p>
        </div>
      </div>
    );
  }

  /* ---- Error state ---- */
  if (error || !detail) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card variant="glass" padding="lg" className="max-w-md text-center">
          <MaterialIcon icon="error_outline" size="xl" className="text-error mb-4" />
          <h3 className="text-lg font-bold text-on-surface mb-2">Erro ao Carregar</h3>
          <p className="text-sm text-stone-400 mb-4">{error ?? "Atendimento nao encontrado."}</p>
          <div className="flex justify-center gap-3">
            <Button variant="secondary" size="sm" icon="arrow_back" onClick={() => router.back()}>
              Voltar
            </Button>
            <Button variant="primary" size="sm" icon="refresh" onClick={() => void loadData()}>
              Tentar Novamente
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  const previousEntries = [...detail.medical_record_entries].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  return (
    <section className="space-y-6 md:space-y-8 pb-8 max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-stone-500">
        <Link href="/med/atendimentos" className="hover:text-primary transition-colors">
          Atendimentos
        </Link>
        <MaterialIcon icon="chevron_right" size="sm" />
        <Link href={`/med/prontuario/${id}`} className="hover:text-primary transition-colors">
          Prontuario
        </Link>
        <MaterialIcon icon="chevron_right" size="sm" />
        <span className="text-on-surface font-medium">Notas Medicas</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold font-headline tracking-tighter text-on-surface">
            Editar Notas Medicas
          </h1>
          <p className="text-sm text-stone-400 mt-1">
            Paciente:{" "}
            <span className="text-on-surface font-medium">{detail.report.patient_name}</span>
            <span className="text-stone-600 ml-2">Cod. {detail.report.patient_id ?? id}</span>
          </p>
        </div>
        <Badge
          tone={
            detail.report.status === "revisado"
              ? "success"
              : detail.report.status === "em_revisao"
                ? "warning"
                : "info"
          }
        >
          {detail.report.status}
        </Badge>
      </div>

      {/* Notes Form */}
      <Card variant="glass" padding="lg" className="rounded-3xl">
        <div className="flex items-center gap-2 mb-6">
          <MaterialIcon icon="edit_note" className="text-primary" filled />
          <h2 className="text-lg font-bold font-headline text-on-surface">Nova Nota</h2>
        </div>
        <NotesForm
          attendanceId={id}
          csrfToken={session?.csrf_token ?? ""}
          consultationEntry={detail.consultation_entry}
          onSaved={() => void loadData()}
        />
      </Card>

      {/* Previous Notes */}
      {previousEntries.length > 0 && (
        <Card variant="glass" padding="lg" className="rounded-3xl space-y-4">
          <div className="flex items-center gap-2">
            <MaterialIcon icon="history" className="text-primary" />
            <h2 className="text-lg font-bold font-headline text-on-surface">Notas Anteriores</h2>
            <Badge tone="neutral" className="ml-auto">
              {previousEntries.length}
            </Badge>
          </div>
          <div className="space-y-3">
            {previousEntries.map((entry) => (
              <PreviousNoteItem key={entry.id} entry={entry} />
            ))}
          </div>
        </Card>
      )}
    </section>
  );
}
