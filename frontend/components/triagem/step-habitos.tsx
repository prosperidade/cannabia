"use client";

import { MaterialIcon } from "@/components/ui-tw/material-icon";
import { ToggleSwitch } from "@/components/ui-tw/toggle-switch";
import { useWizard } from "./wizard-engine";

/* ─── Component ────────────────────────────────────────────────────── */

export function StepHabitos() {
  const { formData, updateHabitos } = useWizard();
  const habitos = formData.habitos;

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h2 className="text-2xl md:text-3xl font-headline font-extrabold text-on-surface leading-tight mb-2">
          Habitos de Saude
        </h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-3">Sobre a sua saude:</p>
        {/* Warning */}
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <MaterialIcon icon="warning" filled size="sm" className="text-amber-400" />
          <span className="text-xs font-semibold text-amber-400">Responda com muita atencao</span>
        </div>
      </div>

      {/* Toggle list */}
      <div className="divide-y divide-white/5">
        {/* Acorda cansado */}
        <div className="flex items-center justify-between py-4 gap-4">
          <span className="text-sm font-medium text-on-surface leading-snug flex-1">
            Acorda cansado?
          </span>
          <ToggleSwitch
            checked={habitos.acorda_cansado}
            onChange={(val) => updateHabitos({ acorda_cansado: val })}
          />
        </div>

        {/* Fuma */}
        <div className="py-4 space-y-3">
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm font-medium text-on-surface leading-snug flex-1">
              Voce fuma?
            </span>
            <ToggleSwitch
              checked={habitos.fuma}
              onChange={(val) =>
                updateHabitos({ fuma: val, frequencia_fumo: val ? habitos.frequencia_fumo : "" })
              }
            />
          </div>
          {habitos.fuma && (
            <input
              type="text"
              value={habitos.frequencia_fumo ?? ""}
              onChange={(e) => updateHabitos({ frequencia_fumo: e.target.value })}
              placeholder="Com que frequencia?"
              className="w-full bg-surface-container-lowest border border-outline-variant rounded-xl px-4 py-3 text-sm text-on-surface focus:border-primary-container focus:ring-1 focus:ring-primary-container transition-all placeholder:text-stone-600"
            />
          )}
        </div>

        {/* Uso de alcool */}
        <div className="flex items-center justify-between py-4 gap-4">
          <span className="text-sm font-medium text-on-surface leading-snug flex-1">
            Faz uso de bebida alcoolica?
          </span>
          <ToggleSwitch
            checked={habitos.uso_alcool}
            onChange={(val) => updateHabitos({ uso_alcool: val })}
          />
        </div>

        {/* Cannabis */}
        <div className="py-4 space-y-3">
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm font-medium text-on-surface leading-snug flex-1">
              Ja usou cannabis (maconha)?
            </span>
            <ToggleSwitch
              checked={habitos.ja_usou_cannabis}
              onChange={(val) =>
                updateHabitos({
                  ja_usou_cannabis: val,
                  frequencia_cannabis: val ? habitos.frequencia_cannabis : "",
                })
              }
            />
          </div>
          {habitos.ja_usou_cannabis && (
            <input
              type="text"
              value={habitos.frequencia_cannabis ?? ""}
              onChange={(e) => updateHabitos({ frequencia_cannabis: e.target.value })}
              placeholder="Com que frequencia? Ha quanto tempo?"
              className="w-full bg-surface-container-lowest border border-outline-variant rounded-xl px-4 py-3 text-sm text-on-surface focus:border-primary-container focus:ring-1 focus:ring-primary-container transition-all placeholder:text-stone-600"
            />
          )}
        </div>

        {/* Arritmia */}
        <div className="flex items-center justify-between py-4 gap-4">
          <span className="text-sm font-medium text-on-surface leading-snug flex-1">
            Possui arritmia cardiaca?
          </span>
          <ToggleSwitch
            checked={habitos.arritmia_cardiaca}
            onChange={(val) => updateHabitos({ arritmia_cardiaca: val })}
          />
        </div>

        {/* Historico psicose */}
        <div className="flex items-center justify-between py-4 gap-4">
          <span className="text-sm font-medium text-on-surface leading-snug flex-1">
            Historico de psicose, esquizofrenia?
          </span>
          <ToggleSwitch
            checked={habitos.historico_psicose}
            onChange={(val) => updateHabitos({ historico_psicose: val })}
          />
        </div>
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
