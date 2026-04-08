"use client";

import { type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { SidebarLayout, type SidebarNavItem } from "@/components/layouts/sidebar-layout";
import { useApiSession } from "@/lib/use-api-session";
import { logout as apiLogout } from "@/lib/api";

const navItems: SidebarNavItem[] = [
  { label: "Painel", icon: "dashboard", href: "/org/dashboard" },
  { label: "Pacientes", icon: "group", href: "/org/pacientes" },
  { label: "Medicos", icon: "medical_services", href: "/org/medicos" },
  { label: "Agendamentos", icon: "calendar_month", href: "/org/agendamentos" },
  { label: "Campanhas", icon: "campaign", href: "/org/campanhas" },
  { label: "Estoque", icon: "inventory_2", href: "/org/estoque" },
  { label: "Faturamento", icon: "receipt_long", href: "/org/faturamento" },
  { label: "Financeiro", icon: "payments", href: "/org/financeiro" },
  { label: "Configuracoes", icon: "settings", href: "/org/config" },
  { label: "Relatorios", icon: "analytics", href: "/org/relatorios" },
  { label: "Conformidade", icon: "verified_user", href: "/org/compliance" },
  { label: "Mensagens", icon: "chat", href: "/org/mensagens" },
];

export default function OrgLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { loading, data, error } = useApiSession();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-surface text-on-surface">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-sm text-stone-500 font-headline tracking-widest uppercase">
            Carregando...
          </p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    router.push("/login");
    return null;
  }

  return (
    <SidebarLayout
      navItems={navItems}
      brandTitle="Cannab'IA"
      brandSubtitle="Gestao Organizacional"
      user={data ? { name: data.user?.username ?? "Admin", role: data.user?.role ?? "Organizacao" } : undefined}
      onLogout={async () => {
        try { await apiLogout(data?.csrf_token ?? ""); } catch { /* best-effort */ }
        router.replace("/login");
      }}
    >
      {children}
    </SidebarLayout>
  );
}
