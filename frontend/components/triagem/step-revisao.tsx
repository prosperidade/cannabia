"use client";

import { cn } from "@/lib/cn";
import { MaterialIcon } from "@/components/ui-tw/material-icon";
import { useWizard } from "./wizard-engine";
import type { TriagemStep } from "@/lib/types-triagem";

/* ─── Helpers ──────────────────────────────────────────────────────── */

function boolLabel(val: boolean): string {
  return val ? "Sim" : "Nao";
}

/* ─── Section component ────────────────────────────────────────────── */

interface SectionProps {
  icon: string;
  title: string;
  step: TriagemStep;
  onEdit: (step: TriagemStep) => void;
  children: React.ReactNode;
}

function ReviewSection({ icon, title, step, onEdit, children }: SectionProps) {
  return (
    <div className="bg-white/5 border border-white/5 rounded-2xl p-5 space-y-3 relative group">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
            <MaterialIcon icon={icon} filled size="sm" className="text-primary" />
          </div>
          <h3 className="font-headline font-semibold text-sm text-on-surface">{title}</h3>
        </div>
        <button
          onClick={() => onEdit(step)}
          className="text-primary/60 hover:text-primary transition-colors p-1"
          aria-label={`Editar ${title}`}
        >
          <MaterialIcon icon="edit" size="sm" />
        </button>
      </div>
      <div className="text-sm text-on-surface-variant space-y-1.5">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-on-surface-variant/70 text-xs uppercase tracking-wider font-medium">
        {label}
      </span>
      <span className="text-on-surface font-medium text-right text-sm">{value}</span>
    </div>
  );
}

/* ─── Component ────────────────────────────────────────────────────── */

export function StepRevisao() {
  const { formData, goToStep, submitWizard, state } = useWizard();
  const { identificacao, motivo, sintomas, dados_fisicos, estado_emocional, habitos, historico } =
    formData;

  const sintomaInfo = sintomas[0];

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h2 className="text-2xl md:text-3xl font-headline font-light tracking-tight text-on-surface leading-tight mb-2">
          Tudo pronto para a <span className="text-primary italic font-medium">analise</span> da
          nossa IA.
        </h2>
        <p className="text-sm text-on-surface-variant leading-relaxed">
          Revise suas respostas antes de finalizar. Clique no icone de edicao para alterar.
        </p>
      </div>

      {/* Summary card */}
      <div className="bg-white/[0.03] border border-primary/10 rounded-2xl p-5 space-y-3">
        <div className="flex items-center gap-3 border-b border-outline-variant/20 pb-3">
          <MaterialIcon icon="fact_check" size="md" className="text-primary" />
          <h3 className="font-headline font-semibold text-on-surface">Resumo da Triagem</h3>
        </div>

        <ReviewSection icon="badge" title="Identificacao" step="identificacao" onEdit={goToStep}>
          <Row label="Paciente" value={identificacao.patient_name || "Nao informado"} />
          <Row
            label="Idade"
            value={identificacao.age ? `${identificacao.age} anos` : "Nao informada"}
          />
        </ReviewSection>

        {/* Motivo */}
        <ReviewSection icon="medical_information" title="Motivo" step="motivo" onEdit={goToStep}>
          <Row
            label="Objetivo"
            value={motivo.objetivo_principal.replace(/_/g, " ") || "Nao informado"}
          />
          {(motivo.outros_motivos?.length ?? 0) > 0 && (
            <Row
              label="Outros"
              value={motivo.outros_motivos!.map((m) => m.replace(/_/g, " ")).join(", ")}
            />
          )}
        </ReviewSection>

        {/* Sintomas */}
        <ReviewSection icon="thermostat" title="Sintomas" step="sintomas" onEdit={goToStep}>
          <Row label="Intensidade" value={`${sintomaInfo?.intensidade ?? 0}/10`} />
          {sintomaInfo?.duracao && (
            <Row label="Duracao" value={sintomaInfo.duracao.replace(/_/g, " ")} />
          )}
          {sintomaInfo?.descricao_adicional && (
            <Row label="Descricao" value={sintomaInfo.descricao_adicional} />
          )}
        </ReviewSection>

        {/* Dados fisicos */}
        <ReviewSection
          icon="straighten"
          title="Dados Fisicos"
          step="dados_fisicos"
          onEdit={goToStep}
        >
          <Row label="Altura" value={`${dados_fisicos.altura_cm ?? "--"} cm`} />
          <Row label="Peso" value={`${dados_fisicos.peso_kg ?? "--"} kg`} />
          <Row label="Sexo" value={dados_fisicos.sexo_biologico ?? "Nao informado"} />
        </ReviewSection>

        {/* Emocional */}
        <ReviewSection
          icon="psychology"
          title="Estado Emocional"
          step="emocional"
          onEdit={goToStep}
        >
          <Row label="Perde foco" value={boolLabel(estado_emocional.perde_foco)} />
          <Row label="Prob. memoria" value={boolLabel(estado_emocional.problemas_memoria)} />
          <Row label="Irritado/triste" value={boolLabel(estado_emocional.facilmente_irritado)} />
          <Row label="Estresse" value={boolLabel(estado_emocional.problemas_estresse)} />
          <Row label="Panico" value={boolLabel(estado_emocional.episodios_panico)} />
          <Row
            label="Esquizofrenia/psicose"
            value={boolLabel(estado_emocional.diagnostico_esquizofrenia_psicose)}
          />
          <Row
            label="Parente c/ psicose"
            value={boolLabel(estado_emocional.parente_esquizofrenia_psicose)}
          />
          <Row
            label="Ansiedade/depressao"
            value={boolLabel(estado_emocional.diagnostico_ansiedade_depressao)}
          />
        </ReviewSection>

        {/* Habitos */}
        <ReviewSection
          icon="local_hospital"
          title="Habitos de Saude"
          step="habitos"
          onEdit={goToStep}
        >
          <Row label="Acorda cansado" value={boolLabel(habitos.acorda_cansado)} />
          <Row
            label="Fuma"
            value={habitos.fuma ? `Sim (${habitos.frequencia_fumo || "sem detalhe"})` : "Nao"}
          />
          <Row label="Alcool" value={boolLabel(habitos.uso_alcool)} />
          <Row
            label="Cannabis"
            value={
              habitos.ja_usou_cannabis
                ? `Sim (${habitos.frequencia_cannabis || "sem detalhe"})`
                : "Nao"
            }
          />
          <Row label="Arritmia" value={boolLabel(habitos.arritmia_cardiaca)} />
          <Row label="Hist. psicose" value={boolLabel(habitos.historico_psicose)} />
        </ReviewSection>

        {/* Historico */}
        <ReviewSection icon="groups" title="Historico Social" step="historico" onEdit={goToStep}>
          <Row label="Casado(a)" value={boolLabel(historico.casado)} />
          <Row label="Filhos" value={boolLabel(historico.tem_filhos)} />
          <Row label="Aborto" value={boolLabel(historico.passou_por_aborto)} />
          <Row label="Trabalha" value={boolLabel(historico.trabalha)} />
          <Row label="Estuda" value={boolLabel(historico.estuda)} />
          <Row label="Ativ. fisica" value={boolLabel(historico.pratica_atividade_fisica)} />
        </ReviewSection>
      </div>

      {/* Submit button */}
      <button
        onClick={submitWizard}
        disabled={state.isSubmitting}
        className={cn(
          "w-full font-headline font-extrabold text-lg py-5 rounded-2xl shadow-xl transition-all flex items-center justify-center gap-3",
          state.isSubmitting
            ? "bg-stone-800 text-stone-500 cursor-not-allowed"
            : "bg-primary text-on-primary hover:scale-[1.02] active:scale-95 shadow-primary/20",
        )}
      >
        {state.isSubmitting ? (
          <>
            <MaterialIcon icon="progress_activity" size="md" className="animate-spin" />
            Enviando...
          </>
        ) : (
          <>
            Finalizar Triagem
            <MaterialIcon icon="check_circle" filled size="md" />
          </>
        )}
      </button>

      {/* Error */}
      {state.error && <p className="text-center text-error text-sm">{state.error}</p>}

      {state.successMessage && (
        <div className="rounded-2xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-primary text-center">
          {state.successMessage}
        </div>
      )}

      {/* Privacy */}
      <div className="flex items-center justify-center gap-2 text-stone-500">
        <MaterialIcon icon="lock" filled size="sm" />
        <p className="text-xs uppercase tracking-wide font-medium">
          Dados protegidos por criptografia
        </p>
      </div>
    </div>
  );
}
