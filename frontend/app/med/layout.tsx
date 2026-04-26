"use client";

import { useEffect, useMemo, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import { logout as apiLogout } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import { MED_NAV, filterNav, type AppRole } from "@/lib/nav";
import { SidebarLayout } from "@/components/layouts";

function resolveActiveHref(pathname: string, items: { href: string }[]): string {
  const match = [...items]
    .filter((item) => pathname === item.href || pathname.startsWith(item.href + "/"))
    .sort((a, b) => b.href.length - a.href.length)[0];
  return match?.href ?? items[0]?.href ?? "/med/dashboard";
}

export default function MedLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { loading, data: session } = useApiSession();

  const role = (session?.user?.role as AppRole | undefined) ?? null;
  const isClinicAdmin = !!session?.user?.is_clinic_admin;
  const tenantType = session?.context?.tenant_type ?? null;

  const navItems = useMemo(
    () => filterNav(MED_NAV, { role, isClinicAdmin, tenantType }),
    [role, isClinicAdmin, tenantType],
  );

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

  // Apenas Medico (e Admin global) usa /med. Outros roles caem em /org.
  if (role !== "Medico" && role !== "Admin") {
    router.replace("/org/dashboard");
    return null;
  }

  const handleLogout = async () => {
    try {
      await apiLogout(session.csrf_token);
    } catch (error) {
      console.warn("[logout] backend retornou erro; deslogando localmente.", error);
    } finally {
      window.location.href = "/login";
    }
  };

  return (
    <SidebarLayout
      navItems={navItems}
      activeHref={resolveActiveHref(pathname, navItems)}
      brandTitle="Cannab'IA"
      brandSubtitle="Modo Medico"
      user={{
        name: session.user.username ?? "Medico",
        role: session.context?.clinic_role ?? session.user.role ?? "Medico",
      }}
      onLogout={handleLogout}
    >
      {children}
    </SidebarLayout>
  );
}
