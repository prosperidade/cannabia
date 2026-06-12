"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useApiSession } from "@/lib/use-api-session";
import { Button } from "@/components/ui-tw";

function getRoleRedirect(role?: string): string {
  switch (role?.toLowerCase()) {
    case "admin":
      return "/admin";
    case "atendente":
      return "/org/dashboard";
    case "paciente":
      return "/p/dashboard";
    case "medico":
      return "/med/dashboard";
    default:
      return "/med/dashboard";
  }
}

export default function HomePage() {
  const router = useRouter();
  const session = useApiSession();

  useEffect(() => {
    if (session.loading) return;
    if (session.data?.authenticated) {
      router.replace(getRoleRedirect(session.data.user?.role));
    }
  }, [session.loading, session.data, router]);

  if (session.loading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <p className="text-on-surface/50">Carregando...</p>
      </div>
    );
  }

  if (session.data?.authenticated) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <p className="text-on-surface/50">Redirecionando...</p>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-surface flex flex-col items-center justify-center px-4 overflow-hidden">
      {/* Decorative background blurs */}
      <div className="pointer-events-none absolute -top-32 -left-32 h-[500px] w-[500px] rounded-full bg-primary/10 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 h-[400px] w-[400px] rounded-full bg-primary-container/15 blur-[100px]" />

      <div className="relative z-10 flex flex-col items-center text-center max-w-lg w-full">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/20 border border-primary/30 shadow-lg shadow-primary/10">
            <span className="text-4xl font-headline font-bold text-primary">C</span>
          </div>
          <h1 className="text-4xl font-headline font-bold text-on-surface tracking-tight">
            Cannab<span className="text-primary">IA</span>
          </h1>
        </div>

        {/* Tagline */}
        <p className="text-sm uppercase tracking-[0.25em] text-primary font-bold mb-4">
          Plataforma de Inteligencia Clinica Canabica
        </p>

        {/* Description */}
        <p className="text-on-surface/60 text-base leading-relaxed mb-10 max-w-md">
          Anamnese inteligente, planos terapeuticos personalizados e evidencias cientificas em tempo
          real para medicina canabinoide.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto">
          <Link href="/login" className="w-full sm:w-auto">
            <Button variant="primary" size="lg" icon="login" className="w-full sm:w-auto">
              Entrar
            </Button>
          </Link>
          <Link href="/triagem" className="w-full sm:w-auto">
            <Button variant="secondary" size="lg" icon="assignment" className="w-full sm:w-auto">
              Acessar Triagem
            </Button>
          </Link>
        </div>

        {/* Security badge */}
        <div className="mt-16 glass-panel rounded-xl px-5 py-3 flex items-center gap-3">
          <span className="material-symbols-rounded text-primary text-xl">verified_user</span>
          <p className="text-xs text-on-surface/50 leading-snug">
            Ambiente seguro e em conformidade com as normas de saude
          </p>
        </div>
      </div>
    </div>
  );
}
