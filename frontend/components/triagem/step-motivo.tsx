"use client";

import { cn } from "@/lib/cn";
import { MaterialIcon } from "@/components/ui-tw/material-icon";
import { useWizard } from "./wizard-engine";

/* ─── Objective data ───────────────────────────────────────────────── */

interface Objetivo {
  id: string;
  label: string;
  description: string;
  icon: string;
}

const OBJETIVOS_PRINCIPAIS: Objetivo[] = [
  {
    id: "melhora_sono",
    label: "Melhora do Sono",
    description: "Ciclos mais profundos e reparadores",
    icon: "bedtime",
  },
  { id: "mais_calma", label: "Mais Calma", description: "Tranquilidade no dia a dia", icon: "spa" },
  {
    id: "aumento_foco",
    label: "Aumento do Foco",
    description: "Concentracao e produtividade",
    icon: "center_focus_strong",
  },
  {
    id: "menos_estresse",
    label: "Menos Estresse",
    description: "Reducao do cortisol diario",
    icon: "self_improvement",
  },
  {
    id: "controle_ansiedade",
    label: "Controle da Ansiedade",
    description: "Equilibrio emocional constante",
    icon: "psychology",
  },
  {
    id: "dor_cronica",
    label: "Dor Cronica",
    description: "Alivio de tensoes e inflamacoes",
    icon: "healing",
  },
  {
    id: "melhora_esporte",
    label: "Melhora no Esporte",
    description: "Performance e recuperacao",
    icon: "fitness_center",
  },
  {
    id: "aumento_libido",
    label: "Aumento da Libido",
    description: "Saude sexual e bem-estar",
    icon: "favorite",
  },
  {
    id: "enxaqueca",
    label: "Enxaqueca",
    description: "Reducao da frequencia e intensidade",
    icon: "bolt",
  },
  {
    id: "controle_tpm",
    label: "Controle da TPM",
    description: "Equilibrio hormonal feminino",
    icon: "cycle",
  },
];

const OUTROS_MOTIVOS: { id: string; label: string }[] = [
  { id: "tdah", label: "TDAH" },
  { id: "depressao", label: "Depressao" },
  { id: "fibromialgia", label: "Fibromialgia" },
  { id: "autismo_tea", label: "Autismo (TEA)" },
  { id: "obesidade", label: "Obesidade" },
  { id: "bruxismo", label: "Bruxismo" },
  { id: "menopausa", label: "Menopausa" },
  { id: "cancer_suporte", label: "Cancer (suporte)" },
  { id: "esclerose_multipla", label: "Esclerose Multipla" },
  { id: "asma", label: "Asma" },
  { id: "demencia", label: "Demencia" },
  { id: "glaucoma", label: "Glaucoma" },
  { id: "cuidados_paliativos", label: "Cuidados Paliativos" },
  { id: "anorexia", label: "Anorexia" },
  { id: "outros", label: "Outros" },
];

/* ─── Component ────────────────────────────────────────────────────── */

export function StepMotivo() {
  const { formData, updateMotivo } = useWizard();
  const selected = formData.motivo.objetivo_principal;
  const outrosSelected = formData.motivo.outros_motivos ?? [];

  const handleSelectPrincipal = (id: string) => {
    updateMotivo({ objetivo_principal: id });
  };

  const toggleOutro = (id: string) => {
    const next = outrosSelected.includes(id)
      ? outrosSelected.filter((o) => o !== id)
      : [...outrosSelected, id];
    updateMotivo({ outros_motivos: next });
  };

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h2 className="text-2xl md:text-3xl font-headline font-extrabold text-on-surface leading-tight mb-3">
          Selecione o principal objetivo que busca com o tratamento
        </h2>
        {/* AI hint */}
        <div className="flex gap-3 p-4 rounded-xl bg-surface-container-high/50 border border-outline-variant/30">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
            <MaterialIcon icon="psychology" filled size="md" className="text-primary" />
          </div>
          <p className="text-sm text-on-surface-variant leading-relaxed">
            A nossa IA correlacionara os seus sintomas com os perfis de terpenos ideais para voce.
          </p>
        </div>
      </div>

      {/* Main objectives grid */}
      <div className="grid grid-cols-2 gap-3">
        {OBJETIVOS_PRINCIPAIS.map((obj) => {
          const isActive = selected === obj.id;
          return (
            <button
              key={obj.id}
              onClick={() => handleSelectPrincipal(obj.id)}
              className={cn(
                "group text-left p-4 rounded-2xl transition-all duration-300 border",
                isActive
                  ? "bg-primary/15 border-primary-container shadow-[0_0_20px_rgba(190,230,84,0.1)]"
                  : "bg-white/5 border-white/5 hover:border-primary/30 hover:bg-white/10",
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <div
                  className={cn(
                    "w-10 h-10 rounded-xl flex items-center justify-center transition-transform group-hover:scale-110",
                    isActive ? "bg-primary text-on-primary" : "bg-primary/10 text-primary",
                  )}
                >
                  <MaterialIcon icon={obj.icon} filled={isActive} size="md" />
                </div>
                <div
                  className={cn(
                    "w-5 h-5 rounded-full border-2 flex items-center justify-center",
                    isActive ? "border-primary" : "border-outline-variant",
                  )}
                >
                  {isActive && <div className="w-2.5 h-2.5 bg-primary rounded-full" />}
                </div>
              </div>
              <h3
                className={cn(
                  "font-headline font-semibold text-sm leading-tight",
                  isActive ? "text-primary" : "text-on-surface",
                )}
              >
                {obj.label}
              </h3>
              <p className="text-[11px] text-on-surface-variant mt-0.5 leading-snug">
                {obj.description}
              </p>
            </button>
          );
        })}
      </div>

      {/* Outros motivos */}
      <div>
        <h3 className="font-headline font-bold text-sm text-on-surface-variant uppercase tracking-wider mb-3">
          Outros Motivos
        </h3>
        <div className="flex flex-wrap gap-2">
          {OUTROS_MOTIVOS.map((m) => {
            const isActive = outrosSelected.includes(m.id);
            return (
              <button
                key={m.id}
                onClick={() => toggleOutro(m.id)}
                className={cn(
                  "px-3 py-1.5 rounded-full text-xs font-semibold border transition-all",
                  isActive
                    ? "bg-primary/15 border-primary text-primary"
                    : "bg-white/5 border-white/10 text-on-surface-variant hover:border-primary/40",
                )}
              >
                {m.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="flex items-start gap-2 p-3 rounded-lg bg-surface-container-low/50 border border-outline-variant/20">
        <MaterialIcon icon="info" size="sm" className="text-on-surface-variant mt-0.5" />
        <p className="text-[11px] text-on-surface-variant leading-relaxed">
          <strong>Informacoes Importantes:</strong> As informacoes coletadas serao usadas
          exclusivamente para personalizar seu protocolo terapeutico. Seus dados sao protegidos por
          criptografia de ponta a ponta.
        </p>
      </div>
    </div>
  );
}
