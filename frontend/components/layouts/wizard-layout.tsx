"use client";

import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface WizardLayoutProps {
  currentStep: number;
  totalSteps: number;
  stepLabel?: string;
  onNext?: () => void;
  onBack?: () => void;
  canAdvance?: boolean;
  isSubmitting?: boolean;
  children: ReactNode;
}

export function WizardLayout({
  currentStep,
  totalSteps,
  stepLabel,
  onNext,
  onBack,
  canAdvance = true,
  isSubmitting = false,
  children,
}: WizardLayoutProps) {
  const progressPercent = Math.round((currentStep / totalSteps) * 100);
  const isFirstStep = currentStep <= 1;
  const isLastStep = currentStep >= totalSteps;

  return (
    <div className="min-h-screen bg-background text-on-background font-body flex flex-col selection:bg-primary selection:text-on-primary">
      {/* ── Top App Bar ── */}
      <header className="fixed top-0 w-full z-50 flex items-center justify-between px-6 h-16 bg-stone-900/80 backdrop-blur-md rounded-b-3xl border-b border-stone-800/50 shadow-xl shadow-primary/5">
        {/* Back button */}
        <button
          onClick={onBack}
          disabled={isFirstStep}
          className={cn(
            "p-2 rounded-full transition-colors",
            isFirstStep
              ? "text-stone-600 cursor-not-allowed"
              : "text-stone-400 hover:text-on-surface hover:bg-white/5"
          )}
          aria-label="Voltar"
        >
          <span className="material-symbols-outlined">arrow_back</span>
        </button>

        {/* Center: Logo */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
            <span className="material-symbols-outlined text-primary text-base">
              eco
            </span>
          </div>
          <span className="font-headline font-black text-primary-container tracking-widest text-sm">
            Cannab&apos;IA
          </span>
        </div>

        {/* Right: Step counter */}
        <div className="flex flex-col items-end gap-1 min-w-[100px]">
          <span className="text-[10px] font-bold tracking-widest text-stone-400 uppercase">
            Etapa {currentStep} de {totalSteps}
          </span>
          <div className="w-full h-1.5 bg-stone-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-primary-container rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      </header>

      {/* ── Background decorative blobs ── */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 -right-20 w-96 h-96 bg-primary/10 blur-[120px] rounded-full" />
        <div className="absolute bottom-1/4 -left-20 w-80 h-80 bg-secondary/10 blur-[100px] rounded-full" />
      </div>

      {/* ── Main Content ── */}
      <main className="flex-1 pt-24 pb-32 px-6 flex flex-col items-center justify-center relative z-10">
        <section className="w-full max-w-lg">
          {/* Step label */}
          {stepLabel && (
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-primary-container/20 rounded-full flex items-center justify-center">
                <span
                  className="material-symbols-outlined text-primary"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  psychology
                </span>
              </div>
              <span className="text-primary-fixed-dim font-headline text-sm font-semibold tracking-wide uppercase">
                {stepLabel}
              </span>
            </div>
          )}

          {/* Card content */}
          <div className="bg-stone-900/40 border border-stone-800/60 p-8 md:p-12 rounded-xl backdrop-blur-xl shadow-2xl">
            {children}
          </div>
        </section>
      </main>

      {/* ── Bottom Navigation: Back / Next ── */}
      <nav className="fixed bottom-0 left-0 w-full z-50 flex justify-between items-center px-10 py-8 bg-stone-900/90 backdrop-blur-xl rounded-t-[2rem] border-t border-stone-800/50 shadow-[0_-10px_40px_rgba(0,0,0,0.5)]">
        {/* Back */}
        <button
          onClick={onBack}
          disabled={isFirstStep}
          className={cn(
            "flex items-center gap-2 border rounded-full px-8 py-3 transition-all active:scale-95 group",
            isFirstStep
              ? "border-stone-800 text-stone-600 cursor-not-allowed"
              : "border-stone-700 text-stone-400 hover:brightness-110"
          )}
        >
          <span className="material-symbols-outlined text-sm group-hover:-translate-x-1 transition-transform">
            arrow_back_ios
          </span>
          <span className="font-headline font-semibold text-[11px] uppercase tracking-widest">
            Voltar
          </span>
        </button>

        {/* Next / Submit */}
        <button
          onClick={onNext}
          disabled={!canAdvance || isSubmitting}
          className={cn(
            "flex items-center gap-2 rounded-full px-8 py-3 transition-all active:scale-105 group",
            canAdvance && !isSubmitting
              ? "bg-primary text-on-primary font-bold hover:brightness-110"
              : "bg-stone-800 text-stone-500 cursor-not-allowed"
          )}
        >
          {isSubmitting ? (
            <>
              <span className="material-symbols-outlined text-sm animate-spin">
                progress_activity
              </span>
              <span className="font-headline font-semibold text-[11px] uppercase tracking-widest">
                Enviando...
              </span>
            </>
          ) : (
            <>
              <span className="font-headline font-semibold text-[11px] uppercase tracking-widest">
                {isLastStep ? "Finalizar" : "Próximo"}
              </span>
              <span className="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">
                {isLastStep ? "check" : "arrow_forward_ios"}
              </span>
            </>
          )}
        </button>
      </nav>
    </div>
  );
}
