"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { SidebarLayout, type SidebarNavItem } from "@/components/layouts";
import { useApiSession } from "@/lib/use-api-session";
import { logout as apiLogout } from "@/lib/api";

const navItems: SidebarNavItem[] = [
  { label: "Painel", icon: "dashboard", href: "/med/dashboard" },
  { label: "Fila de Atendimento", icon: "queue", href: "/med/fila" },
  { label: "Atendimentos", icon: "assignment", href: "/med/atendimentos" },
  { label: "Prescricoes", icon: "prescriptions", href: "/med/prescricao" },
  { label: "Meus Pacientes", icon: "group", href: "/med/pacientes" },
  { label: "Retornos", icon: "event_repeat", href: "/med/retornos" },
  { label: "Inteligencia Clinica", icon: "psychology", href: "/med/inteligencia" },
  { label: "Laboratorio IA", icon: "biotech", href: "/med/lab-ai" },
  { label: "Ensaios Clinicos", icon: "science", href: "/med/ensaios" },
  { label: "Precisao Botanica", icon: "eco", href: "/med/botanical" },
];

export default function MedLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { loading, data: session, error } = useApiSession();

  useEffect(() => {
    if (!loading && (!session?.authenticated || !session.user)) {
      router.replace("/login");
    }
  }, [loading, session, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando...</p>
        </div>
      </div>
    );
  }

  if (!session?.authenticated || !session.user) {
    return null;
  }

  const handleLogout = async () => {
    try {
      await apiLogout(session.csrf_token);
    } catch (error) {
      console.warn("[logout] backend retornou erro; deslogando localmente.", error);
    } finally {
      // window.location forca reload completo, descartando state
      // cacheado do React e do RSC. router.replace nao basta em alguns
      // casos (Next 15 + cookie clearing).
      window.location.href = "/login";
    }
  };

  return (
    <SidebarLayout
      navItems={navItems}
      brandTitle="Cannab'IA"
      brandSubtitle="Inteligencia Botanica"
      user={{
        name: session.user.username,
        role: session.context?.clinic_role ?? session.user.role ?? "Medico",
      }}
      onLogout={handleLogout}
    >
      {children}
    </SidebarLayout>
  );
}
