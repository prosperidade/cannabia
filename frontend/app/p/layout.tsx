"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { MobileLayout, type MobileNavItem } from "@/components/layouts";
import { useApiSession } from "@/lib/use-api-session";
import { getRoleRedirect } from "@/lib/nav";
import { MaterialIcon } from "@/components/ui-tw";

const patientNavItems: MobileNavItem[] = [
  { label: "Inicio", icon: "home", href: "/p/dashboard" },
  { label: "Tratamento", icon: "medication", href: "/p/tratamento" },
  { label: "Diario", icon: "edit_note", href: "/p/diario" },
  { label: "Consultas", icon: "chat", href: "/p/consultas" },
];

export default function PatientLayout({ children }: { children: React.ReactNode }) {
  const { loading, data } = useApiSession();
  const router = useRouter();

  useEffect(() => {
    if (!loading && (!data || !data.authenticated)) {
      router.replace("/login");
      return;
    }
    if (!loading && data?.user && data.user.role !== "Paciente") {
      router.replace(getRoleRedirect(data.user.role, data.user.is_clinic_admin));
    }
  }, [loading, data, router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <MaterialIcon icon="eco" filled className="text-primary text-4xl animate-pulse" />
          <span className="text-on-surface-variant text-sm">Carregando...</span>
        </div>
      </div>
    );
  }

  if (!data || !data.authenticated) {
    return null;
  }

  if (data.user?.role !== "Paciente") {
    return null;
  }

  return (
    <MobileLayout navItems={patientNavItems} topBarTitle="Cannab'IA">
      {children}
    </MobileLayout>
  );
}
