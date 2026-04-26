"use client";

import { useMemo, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { startTransition } from "react";

import { logout } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import { ADMIN_NAV, filterNav, type AppRole } from "@/lib/nav";
import { SidebarLayout } from "@/components/layouts/sidebar-layout";

function resolveActiveHref(pathname: string, items: { href: string }[]): string {
  const match = [...items]
    .filter((item) => pathname === item.href || pathname.startsWith(item.href + "/"))
    .sort((a, b) => b.href.length - a.href.length)[0];
  return match?.href ?? "/admin";
}

export default function AdminLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useApiSession();

  const role = (session.data?.user?.role as AppRole | undefined) ?? null;
  const isClinicAdmin = !!session.data?.user?.is_clinic_admin;
  const tenantType = session.data?.context?.tenant_type ?? null;

  const navItems = useMemo(
    () => filterNav(ADMIN_NAV, { role, isClinicAdmin, tenantType }),
    [role, isClinicAdmin, tenantType],
  );

  async function handleLogout() {
    const csrf = session.data?.csrf_token ?? "";
    try {
      await logout(csrf);
    } catch (error) {
      console.warn("[logout] backend retornou erro; deslogando localmente.", error);
    } finally {
      window.location.href = "/login";
    }
  }

  /* ── Loading state ── */
  if (session.loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-stone-500 font-headline uppercase tracking-widest">
            Carregando...
          </p>
        </div>
      </div>
    );
  }

  /* ── Auth guard ── */
  if (!session.data?.authenticated) {
    startTransition(() => {
      router.replace("/login");
    });
    return null;
  }

  /* ── Guard de role: so Admin entra em /admin ── */
  if (role !== "Admin") {
    startTransition(() => {
      router.replace("/login");
    });
    return null;
  }

  return (
    <SidebarLayout
      navItems={navItems}
      activeHref={resolveActiveHref(pathname, navItems)}
      brandTitle="Cannab'IA"
      brandSubtitle="Painel Administrativo"
      user={
        session.data.user
          ? {
              name: session.data.user.username ?? "Admin",
              role: session.data.user.role ?? "Admin",
            }
          : undefined
      }
      onLogout={() => {
        startTransition(() => {
          void handleLogout();
        });
      }}
    >
      {children}
    </SidebarLayout>
  );
}
