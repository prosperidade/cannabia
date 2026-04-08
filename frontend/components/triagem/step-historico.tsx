"use client";

import { MaterialIcon } from "@/components/ui-tw/material-icon";
import { ToggleSwitch } from "@/components/ui-tw/toggle-switch";
import { useWizard } from "./wizard-engine";
import type { TriagemHistorico } from "@/lib/types-triagem";

/* ─── Question config ──────────────────────────────────────────────── */

interface HistoricoQuestion {
  key: keyof TriagemHistorico;
  label: string;
}

const QUESTIONS: HistoricoQuestion[] = [
  { key: "casado", label: "Voce e casado(a)?" },
  { key: "tem_filhos", label: "Voce tem filhos?" },
  { key: "passou_por_aborto", label: "Passou por aborto?" },
  { key: "trabalha", label: "Voce trabalha?" },
  { key: "estuda", label: "Voce estuda?" },
  { key: "pratica_atividade_fisica", label: "Pratica atividades fisicas?" },
];

/* ─── Component ────────────────────────────────────────────────────── */

export function StepHistorico() {
  const { formData, updateHistorico } = useWizard();
  const historico = formData.historico;

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h2 className="text-2xl md:text-3xl font-headline font-extrabold text-on-surface leading-tight mb-2">
          Historico e Estilo de Vida
        </h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-3">
          Agora sobre a sua vida social:
        </p>
        {/* Warning */}
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <MaterialIcon icon="warning" filled size="sm" className="text-amber-400" />
          <span className="text-xs font-semibold text-amber-400">
            Responda com muita atencao
          </span>
        </div>
      </div>

      {/* Toggle list */}
      <div className="divide-y divide-white/5">
        {QUESTIONS.map((q) => (
          <div
            key={q.key}
            className="flex items-center justify-between py-4 gap-4"
          >
            <span className="text-sm font-medium text-on-surface leading-snug flex-1">
              {q.label}
            </span>
            <ToggleSwitch
              checked={historico[q.key]}
              onChange={(val) => updateHistorico({ [q.key]: val })}
            />
          </div>
        ))}
      </div>

      {/* Privacy note */}
      <div className="flex items-center justify-center gap-2 text-stone-500 pt-2">
        <MaterialIcon icon="lock" filled size="sm" />
        <p className="text-[11px] uppercase tracking-wide font-medium">
          Dados protegidos por criptografia
        </p>
      </div>
    </div>
  );
}
