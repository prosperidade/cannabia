"use client";

import { usePathname, useRouter } from "next/navigation";
import { startTransition, type ReactNode } from "react";

import { logout } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import { SidebarLayout, type SidebarNavItem } from "@/components/layouts/sidebar-layout";

const NAV_ITEMS: SidebarNavItem[] = [
  { label: "Visao Geral", icon: "dashboard", href: "/admin" },
  { label: "Organizacoes", icon: "apartment", href: "/admin/tenants" },
  { label: "Usuarios", icon: "manage_accounts", href: "/admin/usuarios" },
  { label: "Auditoria IA", icon: "monitoring", href: "/admin/auditoria" },
  { label: "Agentes IA", icon: "smart_toy", href: "/admin/agentes" },
  { label: "Base Cientifica", icon: "library_books", href: "/admin/knowledge" },
  { label: "Sistema", icon: "settings", href: "/admin/sistema" },
];

function resolveActiveHref(pathname: string): string {
  // Return the most specific nav item that matches the current pathname
  const match = [...NAV_ITEMS]
    .filter((item) => pathname === item.href || pathname.startsWith(item.href + "/"))
    .sort((a, b) => b.href.length - a.href.length)[0];
  return match?.href ?? "/admin";
}

export default function AdminLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useApiSession();

  async function handleLogout() {
    try {
      await logout(session.data?.csrf_token ?? "");
      router.push("/login");
      router.refresh();
    } catch {
      // silently fail
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

  return (
    <SidebarLayout
      navItems={NAV_ITEMS}
      activeHref={resolveActiveHref(pathname)}
      brandTitle="Cannab'IA"
      brandSubtitle="Painel Administrativo"
      user={
        session.data.user
          ? {
              name: session.data.user.username ?? "Admin",
              role: session.data.user.role ?? "administrator",
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
