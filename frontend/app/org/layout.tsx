"use client";

import { useMemo, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import { logout as apiLogout } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import { ORG_NAV, filterNav, type AppRole } from "@/lib/nav";
import { SidebarLayout } from "@/components/layouts/sidebar-layout";

function resolveActiveHref(pathname: string, items: { href: string }[]): string {
  const match = [...items]
    .filter((item) => pathname === item.href || pathname.startsWith(item.href + "/"))
    .sort((a, b) => b.href.length - a.href.length)[0];
  return match?.href ?? items[0]?.href ?? "/org/dashboard";
}

export default function OrgLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { loading, data, error } = useApiSession();

  const role = (data?.user?.role as AppRole | undefined) ?? null;
  const isClinicAdmin = !!data?.user?.is_clinic_admin;
  const tenantType = data?.context?.tenant_type ?? null;

  const navItems = useMemo(
    () => filterNav(ORG_NAV, { role, isClinicAdmin, tenantType }),
    [role, isClinicAdmin, tenantType],
  );

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

  if (error || !data?.authenticated) {
    router.replace("/login");
    return null;
  }

  // Paciente nao entra em /org. Super admin global tambem nao deveria
  // estar aqui — mas nao bloqueamos pra ele inspecionar os dados de
  // qualquer tenant via /admin -> /org se quiser.
  if (role === "Paciente") {
    router.replace("/p/dashboard");
    return null;
  }

  return (
    <SidebarLayout
      navItems={navItems}
      activeHref={resolveActiveHref(pathname, navItems)}
      brandTitle="Cannab'IA"
      brandSubtitle="Painel da Clinica"
      user={
        data.user
          ? {
              name: data.user.username ?? "Usuario",
              role: data.user.role ?? "",
            }
          : undefined
      }
      onLogout={async () => {
        try {
          await apiLogout(data.csrf_token ?? "");
        } catch (error) {
          console.warn("[logout] backend retornou erro; deslogando localmente.", error);
        } finally {
          window.location.href = "/login";
        }
      }}
    >
      {children}
    </SidebarLayout>
  );
}
