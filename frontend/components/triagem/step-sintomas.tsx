"use client";

import { cn } from "@/lib/cn";
import { SliderRange } from "@/components/ui-tw/slider-range";
import { Badge } from "@/components/ui-tw/badge";
import { MaterialIcon } from "@/components/ui-tw/material-icon";
import { useWizard } from "./wizard-engine";

/* ─── Duration options ─────────────────────────────────────────────── */

const DURATION_OPTIONS = [
  { value: "menos_1_mes", label: "Menos de 1 mes" },
  { value: "1_6_meses", label: "1-6 meses" },
  { value: "6_12_meses", label: "6-12 meses" },
  { value: "mais_1_ano", label: "Mais de 1 ano" },
];

/* ─── Component ────────────────────────────────────────────────────── */

export function StepSintomas() {
  const { formData, updateSintomas } = useWizard();
  const sintoma = formData.sintomas[0] ?? {
    nome: formData.motivo.objetivo_principal,
    intensidade: 5,
    duracao: "",
    descricao_adicional: "",
  };

  const objetivo = formData.motivo.objetivo_principal;

  const update = (patch: Partial<typeof sintoma>) => {
    updateSintomas([{ ...sintoma, ...patch }]);
  };

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h2 className="text-2xl md:text-3xl font-headline font-extrabold text-on-surface leading-tight mb-3">
          Sobre os seus <span className="text-primary italic">sintomas</span>
        </h2>
        <p className="text-sm text-on-surface-variant leading-relaxed">
          Nos ajude a entender a intensidade e duracao dos seus sintomas.
        </p>
      </div>

      {/* Selected objective chip */}
      {objetivo && (
        <div className="flex items-center gap-2">
          <MaterialIcon icon="check_circle" filled size="sm" className="text-primary" />
          <Badge tone="primary" className="text-xs px-3 py-1 rounded-full">
            Objetivo: {objetivo.replace(/_/g, " ")}
          </Badge>
        </div>
      )}

      {/* Question 1: Intensity */}
      <div className="bg-white/5 border border-white/5 rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
            <MaterialIcon icon="speed" filled className="text-primary" />
          </div>
          <h3 className="font-headline font-semibold text-on-surface">
            Qual e a intensidade dos sintomas?
          </h3>
        </div>
        <SliderRange
          value={sintoma.intensidade}
          onChange={(val) => update({ intensidade: val })}
          min={0}
          max={10}
          step={1}
          showValue
        />
        <div className="flex justify-between text-[10px] uppercase tracking-tighter text-stone-500 font-bold -mt-1">
          <span>Leve</span>
          <span>Moderada</span>
          <span>Intensa</span>
        </div>
      </div>

      {/* Question 2: Duration */}
      <div className="bg-white/5 border border-white/5 rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
            <MaterialIcon icon="schedule" filled className="text-primary" />
          </div>
          <h3 className="font-headline font-semibold text-on-surface">
            Ha quanto tempo sente?
          </h3>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {DURATION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => update({ duracao: opt.value })}
              className={cn(
                "px-4 py-3 rounded-xl text-sm font-medium border transition-all text-center",
                sintoma.duracao === opt.value
                  ? "bg-primary/15 border-primary text-primary"
                  : "bg-white/5 border-white/10 text-on-surface-variant hover:border-primary/40",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Question 3: Additional description */}
      <div className="bg-white/5 border border-white/5 rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
            <MaterialIcon icon="edit_note" filled className="text-primary" />
          </div>
          <h3 className="font-headline font-semibold text-on-surface">
            Se houver, descreva mais informacoes:
          </h3>
        </div>
        <textarea
          value={sintoma.descricao_adicional ?? ""}
          onChange={(e) => update({ descricao_adicional: e.target.value })}
          placeholder="Descreva aqui informacoes adicionais sobre seus sintomas..."
          rows={4}
          className="w-full bg-surface-container-lowest border border-outline-variant rounded-xl p-4 text-sm text-on-surface focus:border-primary-container focus:ring-1 focus:ring-primary-container transition-all placeholder:text-stone-600 resize-none"
        />
      </div>
    </div>
  );
}
