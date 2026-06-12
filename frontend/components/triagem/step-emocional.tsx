"use client";

import { MaterialIcon } from "@/components/ui-tw/material-icon";
import { ToggleSwitch } from "@/components/ui-tw/toggle-switch";
import { useWizard } from "./wizard-engine";
import type { TriagemEstadoEmocional } from "@/lib/types-triagem";

/* ─── Question config ──────────────────────────────────────────────── */

interface EmocionalQuestion {
  key: keyof TriagemEstadoEmocional;
  label: string;
}

const QUESTIONS: EmocionalQuestion[] = [
  { key: "perde_foco", label: "Perde o foco facilmente?" },
  { key: "problemas_memoria", label: "Tem problemas de memoria?" },
  { key: "facilmente_irritado", label: "Fica facilmente irritado ou triste?" },
  { key: "problemas_estresse", label: "Possui problemas com estresse?" },
  { key: "episodios_panico", label: "Ja teve episodios de panico?" },
  {
    key: "diagnostico_esquizofrenia_psicose",
    label: "Ja recebeu diagnostico de esquizofrenia ou psicose?",
  },
  {
    key: "parente_esquizofrenia_psicose",
    label: "Algum parente proximo tem esquizofrenia ou psicose?",
  },
  {
    key: "diagnostico_ansiedade_depressao",
    label: "Ja teve diagnosticado de ansiedade ou depressao?",
  },
];

/* ─── Component ────────────────────────────────────────────────────── */

export function StepEmocional() {
  const { formData, updateEmocional } = useWizard();
  const emocional = formData.estado_emocional;

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h2 className="text-2xl md:text-3xl font-headline font-extrabold text-on-surface leading-tight mb-2">
          Estado Emocional
        </h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-3">
          Sobre o seu estado emocional atual:
        </p>
        {/* Warning */}
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <MaterialIcon icon="warning" filled size="sm" className="text-amber-400" />
          <span className="text-xs font-semibold text-amber-400">Responda com muita atencao</span>
        </div>
      </div>

      {/* Toggle list */}
      <div className="divide-y divide-white/5">
        {QUESTIONS.map((q) => (
          <div key={q.key} className="flex items-center justify-between py-4 gap-4">
            <span className="text-sm font-medium text-on-surface leading-snug flex-1">
              {q.label}
            </span>
            <ToggleSwitch
              checked={emocional[q.key]}
              onChange={(val) => updateEmocional({ [q.key]: val })}
            />
          </div>
        ))}
      </div>

      {/* Privacy note */}
      <div className="flex items-center justify-center gap-2 text-stone-500 pt-2">
        <MaterialIcon icon="lock" filled size="sm" />
        <p className="text-[11px] uppercase tracking-wide font-medium">
          Respostas protegidas por sigilo medico
        </p>
      </div>
    </div>
  );
}
