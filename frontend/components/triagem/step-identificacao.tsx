"use client";

import { Input } from "@/components/ui-tw/input";
import { MaterialIcon } from "@/components/ui-tw/material-icon";
import { useWizard } from "./wizard-engine";

export function StepIdentificacao() {
  const { formData, updateIdentificacao } = useWizard();
  const identificacao = formData.identificacao;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl md:text-3xl font-headline font-extrabold text-on-surface leading-tight mb-3">
          Vamos comecar pela sua identificacao
        </h2>
        <p className="text-sm text-on-surface-variant leading-relaxed">
          Esses dados sao usados para abrir o atendimento clinico e vincular a triagem ao paciente.
        </p>
      </div>

      <div className="space-y-4 bg-white/5 border border-white/5 rounded-2xl p-6">
        <Input
          label="Nome completo"
          icon="person"
          placeholder="Como voce gostaria de ser identificado(a)?"
          value={identificacao.patient_name}
          onChange={(event) => updateIdentificacao({ patient_name: event.target.value })}
          autoComplete="name"
        />

        <Input
          label="Idade"
          icon="cake"
          type="number"
          min={0}
          max={120}
          placeholder="Ex: 42"
          value={identificacao.age ?? ""}
          onChange={(event) =>
            updateIdentificacao({
              age: event.target.value === "" ? undefined : Number(event.target.value),
            })
          }
          inputMode="numeric"
        />
      </div>

      <div className="flex items-start gap-2 p-3 rounded-lg bg-surface-container-low/50 border border-outline-variant/20">
        <MaterialIcon icon="info" size="sm" className="text-on-surface-variant mt-0.5" />
        <p className="text-[11px] text-on-surface-variant leading-relaxed">
          O nome e a idade entram no atendimento para liberar a leitura clinica, o prontuario e a
          prescricao segura sem retrabalho posterior.
        </p>
      </div>
    </div>
  );
}
