"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import {
  Card,
  Badge,
  Button,
  MaterialIcon,
  ProgressBar,
} from "@/components/ui-tw";

/* ────────────────────────────────────────────
   Onboarding Wizard - Doctor credentialing flow.
   All data is mock/UI only.
   TODO: connect to backend API for real persistence.
   ──────────────────────────────────────────── */

const STEPS = [
  { label: "Boas-vindas", icon: "waving_hand" },
  { label: "Perfil", icon: "person" },
  { label: "Preferencias", icon: "tune" },
  { label: "Tutorial", icon: "school" },
];

const BENEFITS = [
  {
    icon: "psychology",
    title: "Inteligencia Artificial Clinica",
    description:
      "Analises preditivas e recomendacoes terapeuticas baseadas em evidencias cientificas com GPT-4 e Gemini.",
  },
  {
    icon: "biotech",
    title: "Laboratorio de Precisao Botanica",
    description:
      "Perfis moleculares detalhados de canabinoides e terpenos para formulacoes personalizadas.",
  },
  {
    icon: "assignment",
    title: "Anamnese Automatizada",
    description:
      "Anamnese automatizada via WhatsApp com perguntas guiadas e geracao automatica de relatorios.",
  },
  {
    icon: "groups",
    title: "Gestao de Multiplas Clinicas",
    description:
      "Gerencie pacientes de diferentes clinicas com separacao segura de dados e controle de acesso.",
  },
];

const SPECIALTIES = [
  "Neurologia",
  "Oncologia",
  "Reumatologia",
  "Psiquiatria",
  "Geriatria",
  "Dor Cronica",
  "Ortopedia",
  "Dermatologia",
  "Outra",
];

const TUTORIAL_CARDS = [
  {
    icon: "chat",
    title: "Anamnese via WhatsApp",
    description:
      "O paciente responde perguntas estruturadas diretamente no WhatsApp. A IA processa e gera o relatorio automaticamente.",
  },
  {
    icon: "analytics",
    title: "Painel de Acompanhamento",
    description:
      "Visualize eficacia de tratamentos, correlacoes botanicas e alertas preventivos em tempo real.",
  },
  {
    icon: "science",
    title: "Laboratorio IA",
    description:
      "Analise molecular de formulacoes com perfis de canabinoides, terpenos e interacoes medicamentosas.",
  },
  {
    icon: "medication",
    title: "Prescricoes Inteligentes",
    description:
      "Sugestoes de dosagem baseadas no perfil do paciente, historico e evidencias cientificas atualizadas.",
  },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);

  // TODO: replace with real form state management
  const [profile, setProfile] = useState({
    name: "",
    crm: "",
    specialty: "",
  });

  const [prefs, setPrefs] = useState({
    notifications: true,
    aiLevel: "avancado",
  });

  const progress = ((step + 1) / STEPS.length) * 100;

  const handleNext = () => {
    if (step < STEPS.length - 1) {
      setStep(step + 1);
    }
  };

  const handleBack = () => {
    if (step > 0) {
      setStep(step - 1);
    }
  };

  const handleComplete = () => {
    // TODO: POST onboarding data to API
    router.push("/med/dashboard");
  };

  return (
    <section className="p-4 md:p-8 space-y-8 overflow-y-auto pb-28 md:pb-8">
      {/* ── Page Header ── */}
      <div>
        <h2 className="text-2xl md:text-3xl font-black text-on-surface font-headline tracking-tight">
          Credenciamento Medico
        </h2>
        <p className="text-stone-500 font-medium text-sm">
          Complete seu perfil para iniciar a gestao botanica de seus pacientes.
        </p>
      </div>

      {/* ── Progress Stepper ── */}
      <div className="space-y-4">
        <div className="flex justify-between items-end">
          <span className="text-xs font-bold text-primary uppercase tracking-widest">
            {Math.round(progress)}% Completo
          </span>
          <span className="text-[10px] text-stone-500">
            Etapa {step + 1} de {STEPS.length}
          </span>
        </div>
        <ProgressBar value={progress} variant="primary" glow size="md" />
        <nav className="flex justify-between gap-2 overflow-x-auto pb-2">
          {STEPS.map((s, i) => (
            <button
              key={s.label}
              onClick={() => i <= step && setStep(i)}
              className={cn(
                "flex items-center gap-2 shrink-0 transition-all",
                i <= step ? "cursor-pointer" : "cursor-default opacity-40",
              )}
            >
              {i < step ? (
                <span
                  className="material-symbols-outlined text-primary"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  check_circle
                </span>
              ) : (
                <span
                  className={cn(
                    "h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold",
                    i === step
                      ? "bg-primary text-on-primary"
                      : "bg-surface-container-highest text-stone-500",
                  )}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
              )}
              <span
                className={cn(
                  "text-xs font-semibold uppercase tracking-widest hidden sm:inline",
                  i === step
                    ? "text-primary"
                    : i < step
                      ? "text-primary"
                      : "text-stone-500",
                )}
              >
                {s.label}
              </span>
            </button>
          ))}
        </nav>
      </div>

      {/* ── Step Content ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <div className="lg:col-span-8 space-y-6">
          {/* Step 0: Welcome */}
          {step === 0 && (
            <Card variant="glass" padding="lg" className="rounded-3xl relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-[80px] -mr-32 -mt-32 pointer-events-none" />
              <div className="relative z-10 space-y-8">
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 bg-primary rounded-xl flex items-center justify-center shadow-lg shadow-primary/20">
                    <MaterialIcon icon="eco" className="text-on-primary" size="lg" />
                  </div>
                  <div>
                    <h3 className="text-xl md:text-2xl font-black text-on-surface font-headline">
                      Bem-vindo a Cannab&apos;IA
                    </h3>
                    <p className="text-stone-500 text-sm">
                      Plataforma de Inteligencia Botanica Clinica
                    </p>
                  </div>
                </div>

                <p className="text-stone-300 leading-relaxed">
                  Voce esta prestes a acessar a plataforma mais avancada de gestao terapeutica
                  botanica do Brasil. Nossa IA analisa dados clinicos em tempo real para fornecer
                  recomendacoes personalizadas baseadas em evidencias cientificas.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {BENEFITS.map((b) => (
                    <div
                      key={b.title}
                      className="p-4 rounded-2xl bg-surface-container/50 border border-white/5 flex gap-4 hover:border-primary/20 transition-all"
                    >
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                        <MaterialIcon icon={b.icon} className="text-primary" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-on-surface">{b.title}</h4>
                        <p className="text-xs text-stone-500 mt-1 leading-relaxed">
                          {b.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          )}

          {/* Step 1: Profile Setup */}
          {step === 1 && (
            <Card variant="glass" padding="lg" className="rounded-3xl">
              <div className="space-y-8">
                <div className="flex items-center gap-3">
                  <MaterialIcon icon="person" className="text-primary" size="lg" />
                  <div>
                    <h3 className="text-xl font-bold text-on-surface font-headline">
                      Configuracao de Perfil
                    </h3>
                    <p className="text-sm text-stone-500">
                      Preencha seus dados profissionais para validacao.
                    </p>
                  </div>
                </div>

                {/* Photo upload area */}
                <div className="flex flex-col items-center gap-4">
                  <div className="w-24 h-24 rounded-full border-2 border-dashed border-primary/30 bg-surface-container-highest flex flex-col items-center justify-center cursor-pointer hover:border-primary/60 transition-all group">
                    <MaterialIcon
                      icon="add_a_photo"
                      className="text-stone-500 group-hover:text-primary transition-colors"
                      size="lg"
                    />
                    <span className="text-[10px] text-stone-500 mt-1">Foto</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-widest text-stone-500">
                      Nome Completo
                    </label>
                    <input
                      type="text"
                      value={profile.name}
                      onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                      placeholder="Dr. Nome Sobrenome"
                      className="w-full bg-surface-container-highest border-none rounded-xl focus:ring-2 focus:ring-primary text-on-surface py-3 px-4 transition-all placeholder:text-stone-600"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-widest text-stone-500">
                      Numero do CRM
                    </label>
                    <input
                      type="text"
                      value={profile.crm}
                      onChange={(e) => setProfile({ ...profile, crm: e.target.value })}
                      placeholder="Ex: 123456/SP"
                      className="w-full bg-surface-container-highest border-none rounded-xl focus:ring-2 focus:ring-primary text-on-surface py-3 px-4 transition-all placeholder:text-stone-600"
                    />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <label className="text-xs font-bold uppercase tracking-widest text-stone-500">
                      Especialidade
                    </label>
                    <select
                      value={profile.specialty}
                      onChange={(e) => setProfile({ ...profile, specialty: e.target.value })}
                      className="w-full bg-surface-container-highest border-none rounded-xl focus:ring-2 focus:ring-primary text-on-surface py-3 px-4 transition-all appearance-none"
                    >
                      <option value="">Selecionar especialidade</option>
                      {SPECIALTIES.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Document uploads */}
                <div className="space-y-4">
                  <h4 className="text-sm font-bold text-stone-400 uppercase tracking-widest">
                    Upload de Documentos
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="group cursor-pointer border-2 border-dashed border-outline-variant hover:border-primary/50 bg-surface-container-low transition-all p-6 rounded-xl text-center flex flex-col items-center justify-center gap-3">
                      <div className="h-12 w-12 rounded-full bg-surface-container-highest flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
                        <MaterialIcon icon="upload_file" />
                      </div>
                      <div>
                        <p className="text-sm font-bold text-on-surface">Copia do CRM</p>
                        <p className="text-xs text-stone-500 mt-1">PDF, JPG (Max. 5MB)</p>
                      </div>
                    </div>
                    <div className="group cursor-pointer border-2 border-dashed border-outline-variant hover:border-primary/50 bg-surface-container-low transition-all p-6 rounded-xl text-center flex flex-col items-center justify-center gap-3">
                      <div className="h-12 w-12 rounded-full bg-surface-container-highest flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
                        <MaterialIcon icon="school" />
                      </div>
                      <div>
                        <p className="text-sm font-bold text-on-surface">Diploma de Graduacao</p>
                        <p className="text-xs text-stone-500 mt-1">Certificado reconhecido (PDF)</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Step 2: Preferences */}
          {step === 2 && (
            <Card variant="glass" padding="lg" className="rounded-3xl">
              <div className="space-y-8">
                <div className="flex items-center gap-3">
                  <MaterialIcon icon="tune" className="text-primary" size="lg" />
                  <div>
                    <h3 className="text-xl font-bold text-on-surface font-headline">
                      Preferencias
                    </h3>
                    <p className="text-sm text-stone-500">
                      Configure notificacoes e nivel de assistencia da IA.
                    </p>
                  </div>
                </div>

                {/* Notifications */}
                <div className="space-y-4">
                  <h4 className="text-sm font-bold text-stone-400 uppercase tracking-widest">
                    Notificacoes
                  </h4>
                  <div className="space-y-3">
                    {[
                      { label: "Novos resultados de anamnese", icon: "description" },
                      { label: "Alertas de interacao medicamentosa", icon: "warning" },
                      { label: "Atualizacoes de ensaios clinicos", icon: "science" },
                      { label: "Novos pacientes na fila", icon: "queue" },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className="flex items-center justify-between p-4 rounded-xl bg-surface-container/50 border border-white/5"
                      >
                        <div className="flex items-center gap-3">
                          <MaterialIcon icon={item.icon} className="text-primary" size="sm" />
                          <span className="text-sm text-on-surface">{item.label}</span>
                        </div>
                        <div
                          className={cn(
                            "w-12 h-6 rounded-full cursor-pointer transition-all relative",
                            prefs.notifications ? "bg-primary" : "bg-stone-700",
                          )}
                          onClick={() =>
                            setPrefs({ ...prefs, notifications: !prefs.notifications })
                          }
                        >
                          <div
                            className={cn(
                              "w-5 h-5 rounded-full bg-white absolute top-0.5 transition-all",
                              prefs.notifications ? "left-6" : "left-0.5",
                            )}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* AI Assistance Level */}
                <div className="space-y-4">
                  <h4 className="text-sm font-bold text-stone-400 uppercase tracking-widest">
                    Nivel de Assistencia IA
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                      {
                        key: "basico",
                        label: "Basico",
                        desc: "Sugestoes apenas quando solicitadas",
                        icon: "lightbulb",
                      },
                      {
                        key: "avancado",
                        label: "Avancado",
                        desc: "Sugestoes proativas e alertas automaticos",
                        icon: "psychology",
                      },
                      {
                        key: "completo",
                        label: "Completo",
                        desc: "IA atuando em todas as etapas clinicas",
                        icon: "smart_toy",
                      },
                    ].map((level) => (
                      <button
                        key={level.key}
                        onClick={() => setPrefs({ ...prefs, aiLevel: level.key })}
                        className={cn(
                          "p-5 rounded-xl border-2 text-left transition-all",
                          prefs.aiLevel === level.key
                            ? "border-primary bg-primary/5"
                            : "border-outline-variant/30 hover:border-primary/30 bg-surface-container/30",
                        )}
                      >
                        <MaterialIcon
                          icon={level.icon}
                          className={
                            prefs.aiLevel === level.key ? "text-primary" : "text-stone-500"
                          }
                          size="lg"
                        />
                        <h5 className="font-bold text-on-surface mt-3">{level.label}</h5>
                        <p className="text-xs text-stone-500 mt-1">{level.desc}</p>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Step 3: Tutorial */}
          {step === 3 && (
            <div className="space-y-6">
              <Card variant="glass" padding="lg" className="rounded-3xl">
                <div className="flex items-center gap-3 mb-6">
                  <MaterialIcon icon="school" className="text-primary" size="lg" />
                  <div>
                    <h3 className="text-xl font-bold text-on-surface font-headline">
                      Conheca a Plataforma
                    </h3>
                    <p className="text-sm text-stone-500">
                      Recursos principais que estao a sua disposicao.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {TUTORIAL_CARDS.map((card) => (
                    <div
                      key={card.title}
                      className="p-5 rounded-xl bg-surface-container/50 border border-white/5 hover:border-primary/20 transition-all space-y-3"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                          <MaterialIcon icon={card.icon} className="text-primary" />
                        </div>
                        <h5 className="font-bold text-on-surface text-sm">{card.title}</h5>
                      </div>
                      <p className="text-xs text-stone-400 leading-relaxed">{card.description}</p>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Completion Card */}
              <Card
                variant="glass"
                padding="lg"
                className="rounded-3xl border-primary/20 text-center"
              >
                <div className="space-y-4">
                  <div className="w-16 h-16 mx-auto rounded-full bg-primary/20 flex items-center justify-center">
                    <MaterialIcon
                      icon="check_circle"
                      className="text-primary"
                      size="lg"
                    />
                  </div>
                  <h3 className="text-xl font-black text-on-surface font-headline">
                    Tudo pronto!
                  </h3>
                  <p className="text-stone-400 max-w-md mx-auto">
                    Seu perfil esta configurado. Voce pode comecar a usar a plataforma agora
                    ou ajustar suas configuracoes a qualquer momento.
                  </p>
                  <Button onClick={handleComplete} className="mx-auto">
                    <MaterialIcon icon="dashboard" size="sm" />
                    <span className="ml-1">Ir para o Dashboard</span>
                  </Button>
                </div>
              </Card>
            </div>
          )}

          {/* Navigation Buttons */}
          <div className="flex justify-between items-center pt-4">
            <button
              onClick={handleBack}
              disabled={step === 0}
              className={cn(
                "flex items-center gap-2 font-semibold transition-colors",
                step === 0
                  ? "text-stone-600 cursor-not-allowed"
                  : "text-stone-400 hover:text-on-surface",
              )}
            >
              <MaterialIcon icon="arrow_back" size="sm" />
              Voltar
            </button>
            {step < STEPS.length - 1 && (
              <Button onClick={handleNext}>
                Proxima Etapa
                <MaterialIcon icon="arrow_forward" size="sm" className="ml-1" />
              </Button>
            )}
          </div>
        </div>

        {/* ── Sidebar ── */}
        <div className="lg:col-span-4 space-y-6">
          {/* Verification Status */}
          <Card variant="glass" padding="md" className="rounded-3xl relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10">
              <span className="material-symbols-outlined text-6xl">verified_user</span>
            </div>
            <h4 className="font-bold text-on-surface mb-4 font-headline">
              Verificacao de Credenciais
            </h4>
            <div className="space-y-4">
              {[
                { label: "Identidade Confirmada", done: true },
                { label: "Documentos Validados", done: step > 1 },
                { label: "Perfil Clinico", done: step > 2 },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-3">
                  <div
                    className={cn(
                      "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                      item.done ? "bg-primary/20" : "bg-surface-container-highest",
                    )}
                  >
                    <MaterialIcon
                      icon={item.done ? "done" : "schedule"}
                      size="sm"
                      className={item.done ? "text-primary" : "text-stone-500"}
                    />
                  </div>
                  <div>
                    <p
                      className={cn(
                        "text-sm font-bold",
                        item.done ? "text-on-surface" : "text-on-surface opacity-60",
                      )}
                    >
                      {item.label}
                    </p>
                    <p className="text-xs text-stone-500">
                      {item.done ? "Concluido" : "Aguardando..."}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Tip Card */}
          <div className="bg-primary-container p-6 rounded-2xl text-on-primary-container relative overflow-hidden">
            <div className="absolute -right-4 -top-4 opacity-10">
              <span
                className="material-symbols-outlined text-8xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                lightbulb
              </span>
            </div>
            <h4 className="font-bold font-headline mb-2">Dica de Especialista</h4>
            <p className="text-sm leading-relaxed opacity-90">
              Medicos com perfil clinico detalhado e especializacoes atualizadas recebem 40% mais
              solicitacoes de agendamento na plataforma Cannab&apos;IA.
            </p>
          </div>

          {/* Support */}
          <div className="p-5 border border-primary/10 rounded-2xl flex items-center justify-between">
            <div className="flex items-center gap-3">
              <MaterialIcon icon="support_agent" className="text-primary" />
              <div>
                <p className="text-sm font-bold text-on-surface">Precisa de ajuda?</p>
                <p className="text-xs text-stone-500">Fale com nosso suporte.</p>
              </div>
            </div>
            <div className="h-8 w-8 rounded-full bg-surface-container-highest flex items-center justify-center hover:bg-primary/20 transition-colors cursor-pointer">
              <MaterialIcon icon="open_in_new" size="sm" className="text-stone-400" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
