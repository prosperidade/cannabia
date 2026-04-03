"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { startTransition, type ReactNode, useState } from "react";

import { logout } from "@/lib/api";
import type { ApiSessionResponse } from "@/lib/types";

type AppShellProps = {
  session: ApiSessionResponse;
  title: string;
  subtitle?: string;
  children: ReactNode;
};

export function AppShell({ session, title, subtitle, children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLogout() {
    setBusy(true);
    setError(null);
    try {
      await logout(session.csrf_token);
      router.push("/login");
      router.refresh();
    } catch (logoutError) {
      setError(logoutError instanceof Error ? logoutError.message : "Falha ao sair.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-frame">
      <aside className="side-rail">
        <div className="brand-mark">
          <div className="brand-orb" />
          <div>
            <div className="brand-kicker">CannabIA</div>
            <strong>Clinical Console</strong>
          </div>
        </div>

        <nav className="rail-nav">
          <Link
            className={pathname.startsWith("/dashboard") ? "active" : ""}
            href="/dashboard"
          >
            Overview
          </Link>
          <Link
            className={pathname.startsWith("/atendimentos") ? "active" : ""}
            href="/atendimentos"
          >
            Atendimentos
          </Link>
          <Link
            className={pathname.startsWith("/agendamentos") ? "active" : ""}
            href="/agendamentos"
          >
            Agendamentos
          </Link>
          <Link
            className={pathname.startsWith("/mensagens") ? "active" : ""}
            href="/mensagens"
          >
            Mensagens
          </Link>
          <Link
            className={pathname.startsWith("/auditoria-ia") ? "active" : ""}
            href="/auditoria-ia"
          >
            Auditoria IA
          </Link>
        </nav>

        <div className="rail-meta">
          <div className="meta-block">
            <span className="meta-label">Usuario</span>
            <strong>{session.user?.username ?? "--"}</strong>
          </div>
          <div className="meta-grid">
            <div>
              <span className="meta-label">Clinica</span>
              <strong>#{session.context?.clinic_id ?? "--"}</strong>
            </div>
            <div>
              <span className="meta-label">Tenant</span>
              <strong>#{session.context?.tenant_id ?? "--"}</strong>
            </div>
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
          {error ? <div className="inline-error">{error}</div> : null}
        </div>
      </aside>

      <main className="workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Frontend Next.js bootstrap</p>
            <h1>{title}</h1>
            {subtitle ? <p className="lead">{subtitle}</p> : null}
          </div>
          <div className="context-chip">
            <span>{session.context?.tenant_type ?? "clinic"}</span>
            <strong>{session.user?.role ?? "User"}</strong>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
