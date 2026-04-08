"use client";

import { cn } from "@/lib/cn";
import { MaterialIcon } from "@/components/ui-tw/material-icon";
import { useWizard } from "./wizard-engine";

/* ─── Component ────────────────────────────────────────────────────── */

export function StepDadosFisicos() {
  const { formData, updateDadosFisicos } = useWizard();
  const dados = formData.dados_fisicos;

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h2 className="text-2xl md:text-3xl font-headline font-extrabold text-on-surface leading-tight mb-2">
          Dados Fisicos
        </h2>
        <p className="text-sm text-on-surface-variant leading-relaxed">
          Informacoes sobre suas caracteristicas fisicas para calibrar a dosagem ideal.
        </p>
      </div>

      {/* Altura slider */}
      <div className="bg-white/5 border border-white/5 rounded-2xl p-6 space-y-4">
        <div className="flex justify-between items-center">
          <label className="font-headline text-sm font-semibold flex items-center gap-2 text-on-surface">
            <MaterialIcon icon="straighten" filled size="md" className="text-primary" />
            Altura
          </label>
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-headline font-bold text-primary">
              {dados.altura_cm ?? 170}
            </span>
            <span className="text-sm text-on-surface-variant">cm</span>
          </div>
        </div>
        <input
          type="range"
          min={120}
          max={220}
          step={1}
          value={dados.altura_cm ?? 170}
          onChange={(e) => updateDadosFisicos({ altura_cm: Number(e.target.value) })}
          className="slider-custom w-full"
        />
        <div className="flex justify-between text-[10px] text-on-surface-variant uppercase tracking-tighter">
          <span>120 cm</span>
          <span>220 cm</span>
        </div>
      </div>

      {/* Peso slider */}
      <div className="bg-white/5 border border-white/5 rounded-2xl p-6 space-y-4">
        <div className="flex justify-between items-center">
          <label className="font-headline text-sm font-semibold flex items-center gap-2 text-on-surface">
            <MaterialIcon icon="monitor_weight" filled size="md" className="text-primary" />
            Peso
          </label>
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-headline font-bold text-primary">
              {dados.peso_kg ?? 70}
            </span>
            <span className="text-sm text-on-surface-variant">kg</span>
          </div>
        </div>
        <input
          type="range"
          min={30}
          max={200}
          step={1}
          value={dados.peso_kg ?? 70}
          onChange={(e) => updateDadosFisicos({ peso_kg: Number(e.target.value) })}
          className="slider-custom w-full"
        />
        <div className="flex justify-between text-[10px] text-on-surface-variant uppercase tracking-tighter">
          <span>30 kg</span>
          <span>200 kg</span>
        </div>
      </div>

      {/* Sexo Biologico */}
      <div className="bg-white/5 border border-white/5 rounded-2xl p-6 space-y-4">
        <label className="font-headline text-sm font-semibold text-on-surface block mb-3">
          Sexo Biologico
        </label>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => updateDadosFisicos({ sexo_biologico: "masculino" })}
            className={cn(
              "flex items-center justify-center gap-2 p-4 rounded-2xl font-headline font-semibold text-sm transition-all border",
              dados.sexo_biologico === "masculino"
                ? "bg-primary text-on-primary border-primary shadow-lg shadow-primary/20"
                : "bg-white/5 border-outline-variant text-on-surface-variant hover:bg-white/10 hover:border-primary/40",
            )}
          >
            <MaterialIcon icon="male" size="md" />
            Masculino
          </button>
          <button
            onClick={() => updateDadosFisicos({ sexo_biologico: "feminino" })}
            className={cn(
              "flex items-center justify-center gap-2 p-4 rounded-2xl font-headline font-semibold text-sm transition-all border",
              dados.sexo_biologico === "feminino"
                ? "bg-primary text-on-primary border-primary shadow-lg shadow-primary/20"
                : "bg-white/5 border-outline-variant text-on-surface-variant hover:bg-white/10 hover:border-primary/40",
            )}
          >
            <MaterialIcon icon="female" size="md" />
            Feminino
          </button>
        </div>
      </div>

      {/* Custom slider styles */}
      <style jsx>{`
        .slider-custom {
          -webkit-appearance: none;
          appearance: none;
          width: 100%;
          background: transparent;
          height: 6px;
        }
        .slider-custom::-webkit-slider-runnable-track {
          width: 100%;
          height: 6px;
          cursor: pointer;
          background: #2f3824;
          border-radius: 3px;
        }
        .slider-custom::-webkit-slider-thumb {
          height: 24px;
          width: 24px;
          border-radius: 50%;
          background: #a3c93a;
          cursor: pointer;
          -webkit-appearance: none;
          margin-top: -9px;
          box-shadow: 0 0 15px rgba(163, 201, 58, 0.4);
        }
        .slider-custom::-moz-range-track {
          width: 100%;
          height: 6px;
          cursor: pointer;
          background: #2f3824;
          border-radius: 3px;
        }
        .slider-custom::-moz-range-thumb {
          height: 24px;
          width: 24px;
          border-radius: 50%;
          background: #a3c93a;
          cursor: pointer;
          border: none;
          box-shadow: 0 0 15px rgba(163, 201, 58, 0.4);
        }
      `}</style>
    </div>
  );
}
