"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { WizardLayout } from "@/components/layouts/wizard-layout";
import { Button, MaterialIcon } from "@/components/ui-tw";
import { WizardProvider, useWizard } from "@/components/triagem/wizard-engine";
import { StepIdentificacao } from "@/components/triagem/step-identificacao";
import { StepMotivo } from "@/components/triagem/step-motivo";
import { StepSintomas } from "@/components/triagem/step-sintomas";
import { StepDadosFisicos } from "@/components/triagem/step-dados-fisicos";
import { StepEmocional } from "@/components/triagem/step-emocional";
import { StepHabitos } from "@/components/triagem/step-habitos";
import { StepHistorico } from "@/components/triagem/step-historico";
import { StepRevisao } from "@/components/triagem/step-revisao";
import { ApiError, resolveTriageLink } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import type { TriageLinkContext } from "@/lib/types";

function CurrentStep() {
  const { state } = useWizard();

  switch (state.currentStep) {
    case "identificacao":
      return <StepIdentificacao />;
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

function TriagemWizardScreen({ clinicLabel }: { clinicLabel?: string }) {
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
    <div className="min-h-screen">
      {clinicLabel ? (
        <div className="fixed top-16 left-0 right-0 z-40 px-4 md:px-6">
          <div className="mx-auto max-w-lg rounded-2xl border border-primary/20 bg-stone-950/85 px-4 py-3 text-xs text-primary backdrop-blur-xl">
            Link seguro validado para <strong>{clinicLabel}</strong>.
          </div>
        </div>
      ) : null}
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
    </div>
  );
}

function TriageAccessState({
  title,
  description,
  tone = "neutral",
}: {
  title: string;
  description: string;
  tone?: "neutral" | "error";
}) {
  const iconClass = tone === "error" ? "text-error" : "text-primary";
  const borderClass = tone === "error" ? "border-error/20" : "border-primary/20";

  return (
    <div className="min-h-screen bg-background text-on-background px-6 py-10 flex items-center justify-center">
      <div className={`w-full max-w-lg rounded-3xl border ${borderClass} bg-stone-950/85 p-8 backdrop-blur-xl`}>
        <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5">
          <MaterialIcon icon={tone === "error" ? "error" : "link"} size="lg" className={iconClass} />
        </div>
        <h1 className="text-2xl font-headline font-extrabold text-on-surface mb-3">{title}</h1>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-6">{description}</p>
        <div className="flex flex-col sm:flex-row gap-3">
          <Link href="/login" className="w-full sm:w-auto">
            <Button variant="primary" size="sm" icon="login" className="w-full sm:w-auto">
              Area da Clinica
            </Button>
          </Link>
          <Link href="/" className="w-full sm:w-auto">
            <Button variant="secondary" size="sm" icon="home" className="w-full sm:w-auto">
              Voltar
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}

function TriagemPageContent() {
  const searchParams = useSearchParams();
  const session = useApiSession();
  const token = (searchParams.get("token") ?? "").trim();
  const [linkContext, setLinkContext] = useState<TriageLinkContext | null>(null);
  const [linkLoading, setLinkLoading] = useState(true);
  const [linkError, setLinkError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function validateAccess() {
      if (session.loading) return;

      if (session.data?.authenticated) {
        if (!cancelled) {
          setLinkContext(null);
          setLinkError(null);
          setLinkLoading(false);
        }
        return;
      }

      if (!token) {
        if (!cancelled) {
          setLinkContext(null);
          setLinkError("Esta triagem agora exige um link seguro enviado pela clinica.");
          setLinkLoading(false);
        }
        return;
      }

      if (!cancelled) {
        setLinkLoading(true);
        setLinkError(null);
      }

      try {
        const context = await resolveTriageLink(token);
        if (!cancelled) {
          setLinkContext(context);
          setLinkError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setLinkContext(null);
          setLinkError(
            error instanceof ApiError ? error.message : "Nao foi possivel validar o link da triagem.",
          );
        }
      } finally {
        if (!cancelled) {
          setLinkLoading(false);
        }
      }
    }

    void validateAccess();
    return () => {
      cancelled = true;
    };
  }, [session.loading, session.data?.authenticated, token]);

  if (session.loading || linkLoading) {
    return (
      <div className="min-h-screen bg-background text-on-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-sm text-on-surface-variant">Validando acesso seguro...</p>
        </div>
      </div>
    );
  }

  if (!session.data?.authenticated && linkError) {
    return (
      <TriageAccessState
        title="Acesso Protegido"
        description={linkError}
        tone="error"
      />
    );
  }

  if (!session.data?.authenticated && !linkContext) {
    return (
      <TriageAccessState
        title="Link Necessario"
        description="Solicite a sua clinica um link individual de triagem para continuar com o intake."
      />
    );
  }

  return (
    <WizardProvider initialPatientName={linkContext?.patient_name}>
      <TriagemWizardScreen clinicLabel={linkContext?.clinic_label} />
    </WizardProvider>
  );
}

export default function TriagemPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-background text-on-background flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
            <p className="text-sm text-on-surface-variant">Carregando triagem...</p>
          </div>
        </div>
      }
    >
      <TriagemPageContent />
    </Suspense>
  );
}
