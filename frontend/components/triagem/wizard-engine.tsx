"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type {
  TriagemStep,
  TriagemFormData,
  WizardState,
  TriagemMotivo,
  TriagemSintoma,
  TriagemDadosFisicos,
  TriagemEstadoEmocional,
  TriagemHabitos,
  TriagemHistorico,
} from "@/lib/types-triagem";

/* ─── Constants ────────────────────────────────────────────────────── */

const STEPS: TriagemStep[] = [
  "motivo",
  "sintomas",
  "dados_fisicos",
  "emocional",
  "habitos",
  "historico",
  "revisao",
];

const STEP_LABELS: Record<TriagemStep, string> = {
  motivo: "Motivo do Atendimento",
  sintomas: "Sintomas e Intensidade",
  dados_fisicos: "Dados Fisicos",
  emocional: "Estado Emocional",
  habitos: "Habitos de Saude",
  historico: "Historico e Estilo de Vida",
  revisao: "Revisao e Conclusao",
};

/* ─── Default form data ────────────────────────────────────────────── */

const DEFAULT_MOTIVO: TriagemMotivo = {
  objetivo_principal: "",
  outros_motivos: [],
};

const DEFAULT_SINTOMAS: TriagemSintoma[] = [
  { nome: "", intensidade: 5, duracao: "", descricao_adicional: "" },
];

const DEFAULT_DADOS_FISICOS: TriagemDadosFisicos = {
  peso_kg: 70,
  altura_cm: 170,
  sexo_biologico: undefined,
};

const DEFAULT_EMOCIONAL: TriagemEstadoEmocional = {
  perde_foco: false,
  problemas_memoria: false,
  facilmente_irritado: false,
  problemas_estresse: false,
  episodios_panico: false,
  diagnostico_esquizofrenia_psicose: false,
  parente_esquizofrenia_psicose: false,
  diagnostico_ansiedade_depressao: false,
};

const DEFAULT_HABITOS: TriagemHabitos = {
  acorda_cansado: false,
  fuma: false,
  frequencia_fumo: "",
  uso_alcool: false,
  ja_usou_cannabis: false,
  frequencia_cannabis: "",
  arritmia_cardiaca: false,
  historico_psicose: false,
};

const DEFAULT_HISTORICO: TriagemHistorico = {
  casado: false,
  tem_filhos: false,
  passou_por_aborto: false,
  trabalha: false,
  estuda: false,
  pratica_atividade_fisica: false,
};

const DEFAULT_FORM_DATA: TriagemFormData = {
  motivo: DEFAULT_MOTIVO,
  sintomas: DEFAULT_SINTOMAS,
  dados_fisicos: DEFAULT_DADOS_FISICOS,
  estado_emocional: DEFAULT_EMOCIONAL,
  habitos: DEFAULT_HABITOS,
  historico: DEFAULT_HISTORICO,
};

/* ─── Context types ────────────────────────────────────────────────── */

interface WizardContextValue {
  state: WizardState;
  formData: TriagemFormData;
  currentStepIndex: number;
  totalSteps: number;
  stepLabel: string;
  canAdvance: boolean;
  goNext: () => void;
  goBack: () => void;
  goToStep: (step: TriagemStep) => void;
  updateMotivo: (data: Partial<TriagemMotivo>) => void;
  updateSintomas: (data: TriagemSintoma[]) => void;
  updateDadosFisicos: (data: Partial<TriagemDadosFisicos>) => void;
  updateEmocional: (data: Partial<TriagemEstadoEmocional>) => void;
  updateHabitos: (data: Partial<TriagemHabitos>) => void;
  updateHistorico: (data: Partial<TriagemHistorico>) => void;
  submitWizard: () => void;
}

const WizardContext = createContext<WizardContextValue | null>(null);

/* ─── Hook ─────────────────────────────────────────────────────────── */

export function useWizard(): WizardContextValue {
  const ctx = useContext(WizardContext);
  if (!ctx) throw new Error("useWizard must be used inside <WizardProvider>");
  return ctx;
}

/* ─── Provider ─────────────────────────────────────────────────────── */

export function WizardProvider({ children }: { children: ReactNode }) {
  const [currentStep, setCurrentStep] = useState<TriagemStep>("motivo");
  const [completedSteps, setCompletedSteps] = useState<TriagemStep[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [formData, setFormData] = useState<TriagemFormData>(DEFAULT_FORM_DATA);

  const currentStepIndex = STEPS.indexOf(currentStep);
  const totalSteps = STEPS.length;

  /* ── Navigation ─────────────────────────────────────────────────── */

  const goNext = useCallback(() => {
    const idx = STEPS.indexOf(currentStep);
    if (idx < STEPS.length - 1) {
      if (!completedSteps.includes(currentStep)) {
        setCompletedSteps((prev) => [...prev, currentStep]);
      }
      setCurrentStep(STEPS[idx + 1]);
    }
  }, [currentStep, completedSteps]);

  const goBack = useCallback(() => {
    const idx = STEPS.indexOf(currentStep);
    if (idx > 0) {
      setCurrentStep(STEPS[idx - 1]);
    }
  }, [currentStep]);

  const goToStep = useCallback((step: TriagemStep) => {
    setCurrentStep(step);
  }, []);

  /* ── Updaters ───────────────────────────────────────────────────── */

  const updateMotivo = useCallback((data: Partial<TriagemMotivo>) => {
    setFormData((prev) => ({
      ...prev,
      motivo: { ...prev.motivo, ...data },
    }));
  }, []);

  const updateSintomas = useCallback((data: TriagemSintoma[]) => {
    setFormData((prev) => ({ ...prev, sintomas: data }));
  }, []);

  const updateDadosFisicos = useCallback(
    (data: Partial<TriagemDadosFisicos>) => {
      setFormData((prev) => ({
        ...prev,
        dados_fisicos: { ...prev.dados_fisicos, ...data },
      }));
    },
    [],
  );

  const updateEmocional = useCallback(
    (data: Partial<TriagemEstadoEmocional>) => {
      setFormData((prev) => ({
        ...prev,
        estado_emocional: { ...prev.estado_emocional, ...data },
      }));
    },
    [],
  );

  const updateHabitos = useCallback((data: Partial<TriagemHabitos>) => {
    setFormData((prev) => ({
      ...prev,
      habitos: { ...prev.habitos, ...data },
    }));
  }, []);

  const updateHistorico = useCallback((data: Partial<TriagemHistorico>) => {
    setFormData((prev) => ({
      ...prev,
      historico: { ...prev.historico, ...data },
    }));
  }, []);

  /* ── Submit ─────────────────────────────────────────────────────── */

  const submitWizard = useCallback(async () => {
    setIsSubmitting(true);
    setError(undefined);
    try {
      // TODO: integrate with backend API
      console.log("[CannabIA] Triagem submitted:", JSON.stringify(formData, null, 2));
      alert("Triagem finalizada com sucesso! Confira o console para os dados.");
    } catch (err) {
      setError("Erro ao enviar triagem. Tente novamente.");
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  }, [formData]);

  /* ── Validation (basic: motivo must be selected) ────────────────── */

  const canAdvance = useMemo(() => {
    switch (currentStep) {
      case "motivo":
        return formData.motivo.objetivo_principal !== "";
      case "dados_fisicos":
        return formData.dados_fisicos.sexo_biologico !== undefined;
      default:
        return true;
    }
  }, [currentStep, formData]);

  /* ── Aggregate state ────────────────────────────────────────────── */

  const state: WizardState = {
    currentStep,
    completedSteps,
    formData,
    isSubmitting,
    error,
  };

  const value: WizardContextValue = {
    state,
    formData,
    currentStepIndex: currentStepIndex + 1, // 1-indexed for display
    totalSteps,
    stepLabel: STEP_LABELS[currentStep],
    canAdvance,
    goNext,
    goBack,
    goToStep,
    updateMotivo,
    updateSintomas,
    updateDadosFisicos,
    updateEmocional,
    updateHabitos,
    updateHistorico,
    submitWizard,
  };

  return (
    <WizardContext.Provider value={value}>{children}</WizardContext.Provider>
  );
}
