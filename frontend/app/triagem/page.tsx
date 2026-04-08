"use client";

import { WizardLayout } from "@/components/layouts/wizard-layout";
import { useWizard } from "@/components/triagem/wizard-engine";
import { StepMotivo } from "@/components/triagem/step-motivo";
import { StepSintomas } from "@/components/triagem/step-sintomas";
import { StepDadosFisicos } from "@/components/triagem/step-dados-fisicos";
import { StepEmocional } from "@/components/triagem/step-emocional";
import { StepHabitos } from "@/components/triagem/step-habitos";
import { StepHistorico } from "@/components/triagem/step-historico";
import { StepRevisao } from "@/components/triagem/step-revisao";

/* ─── Step renderer ────────────────────────────────────────────────── */

function CurrentStep() {
  const { state } = useWizard();

  switch (state.currentStep) {
    case "motivo":
      return <StepMotivo />;
    case "sintomas":
      return <StepSintomas />;
    case "dados_fisicos":
      return <StepDadosFisicos />;
    case "emocional":
      return <StepEmocional />;
    case "habitos":
      return <StepHabitos />;
    case "historico":
      return <StepHistorico />;
    case "revisao":
      return <StepRevisao />;
    default:
      return null;
  }
}

/* ─── Page ─────────────────────────────────────────────────────────── */

export default function TriagemPage() {
  const {
    currentStepIndex,
    totalSteps,
    stepLabel,
    canAdvance,
    goNext,
    goBack,
    state,
    submitWizard,
  } = useWizard();

  const isLastStep = state.currentStep === "revisao";

  const handleNext = () => {
    if (isLastStep) {
      submitWizard();
    } else {
      goNext();
    }
  };

  return (
    <WizardLayout
      currentStep={currentStepIndex}
      totalSteps={totalSteps}
      stepLabel={stepLabel}
      onNext={handleNext}
      onBack={goBack}
      canAdvance={canAdvance}
      isSubmitting={state.isSubmitting}
    >
      <CurrentStep />
    </WizardLayout>
  );
}
