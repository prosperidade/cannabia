"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { startTransition, type ReactNode, useState } from "react";

import { logout } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import { useSystemStatus } from "@/lib/use-system-status";
import { SystemStatusBar } from "@/components/system-status-bar";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton } from "@/components/ui/skeleton";

type AdminNavItem = {
  href: string;
  label: string;
};

const NAV_ITEMS: AdminNavItem[] = [
  { href: "/admin", label: "Visão geral" },
  { href: "/admin/tenants", label: "Tenants" },
];

export default function AdminLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useApiSession();
  const status = useSystemStatus();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLogout() {
    setBusy(true);
    setError(null);
    try {
      await logout(session.data?.csrf_token ?? "");
      router.push("/login");
      router.refresh();
    } catch (logoutError) {
      setError(logoutError instanceof Error ? logoutError.message : "Falha ao sair.");
    } finally {
      setBusy(false);
    }
  }

  if (session.loading) {
    return (
      <div className="loading-screen">
        <CardSkeleton lines={4} />
      </div>
    );
  }

  if (!session.data?.authenticated) {
    router.replace("/login");
    return null;
  }

  const isActive = (href: string) => {
    if (href === "/admin") return pathname === "/admin";
    return pathname.startsWith(href);
  };

  return (
    <div className="app-frame">
      <aside aria-label="Menu administrativo" className="side-rail">
        <div className="brand-mark">
          <div className="brand-orb" />
          <div>
            <div className="brand-kicker">CannabIA</div>
            <strong>Admin Console</strong>
          </div>
        </div>

        <nav aria-label="Navegação administrativa" className="rail-nav">
          {NAV_ITEMS.map((item) => (
            <Link
              aria-current={isActive(item.href) ? "page" : undefined}
              className={isActive(item.href) ? "active" : ""}
              href={item.href}
              key={item.href}
            >
              {item.label}
            </Link>
          ))}

          <hr style={{ border: "none", borderTop: "1px solid var(--line)", margin: "8px 0" }} />

          <Link
            aria-current={pathname.startsWith("/dashboard") ? "page" : undefined}
            className={pathname.startsWith("/dashboard") ? "active" : ""}
            href="/dashboard"
          >
            ← Painel clínico
          </Link>
        </nav>

        <div className="rail-meta">
          <div className="meta-block">
            <span className="meta-label">Admin</span>
            <strong>{session.data.user?.username ?? "--"}</strong>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="meta-label">Sistema</span>
            <Badge
              pulse={status.overall !== "healthy"}
              tone={
                status.overall === "healthy"
                  ? "success"
                  : status.overall === "degraded"
                    ? "warning"
                    : status.overall === "offline"
                      ? "danger"
                      : status.overall === "unhealthy"
                        ? "danger"
                        : "neutral"
              }
            >
              {status.overall === "healthy"
                ? "Operacional"
                : status.overall === "degraded"
                  ? "Degradado"
                  : status.overall === "unhealthy"
                    ? "Indisponível"
                    : status.overall === "offline"
                      ? "Offline"
                      : "Verificando..."}
            </Badge>
          </div>
          <button
            className="ghost-button"
            disabled={busy}
            onClick={() => {
              startTransition(() => {
                void handleLogout();
              });
            }}
            type="button"
          >
            {busy ? "Saindo..." : "Sair"}
          </button>
          {error ? (
            <div aria-live="assertive" className="inline-error" role="alert">
              {error}
            </div>
          ) : null}
        </div>
      </aside>

      <main className="workspace" id="main-content">
        <SystemStatusBar status={status} />
        {children}
      </main>
    </div>
  );
}
