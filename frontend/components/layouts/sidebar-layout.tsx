"use client";

import { type ReactNode, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

export interface SidebarNavItem {
  label: string;
  icon: string;
  href: string;
}

export interface SidebarLayoutProps {
  navItems: SidebarNavItem[];
  activeHref?: string;
  user?: { name: string; role: string };
  brandTitle?: string;
  brandSubtitle?: string;
  onLogout?: () => void;
  children: ReactNode;
}

export function SidebarLayout({
  navItems,
  activeHref,
  user,
  brandTitle = "Cannab'IA",
  brandSubtitle = "Botanical Intelligence",
  onLogout,
  children,
}: SidebarLayoutProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (href: string) => {
    if (activeHref) return activeHref === href;
    return pathname === href || pathname.startsWith(href + "/");
  };

  return (
    <div className="flex min-h-screen bg-surface text-on-surface font-body">
      {/* ── Desktop Sidebar ── */}
      <aside className="hidden md:flex flex-col h-screen w-64 border-r border-white/10 bg-stone-950/80 backdrop-blur-xl py-6 sticky top-0 z-50">
        {/* Brand */}
        <div className="px-6 mb-10 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center">
            <span className="material-symbols-outlined text-primary text-xl">eco</span>
          </div>
          <div>
            <h1 className="text-xl font-black text-primary-container tracking-widest font-headline">
              {brandTitle}
            </h1>
            <p className="text-[10px] uppercase tracking-[0.2em] text-stone-500 font-bold">
              {brandSubtitle}
            </p>
          </div>
        </div>

        {/* Nav Items */}
        <nav className="flex-1 px-4 space-y-2 overflow-y-auto">
          {navItems.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 group",
                  active
                    ? "text-primary bg-primary/10 font-bold border-r-2 border-primary"
                    : "text-stone-400 hover:text-stone-200 hover:bg-white/5",
                )}
              >
                <span className="material-symbols-outlined">{item.icon}</span>
                <span className="font-headline tracking-tight text-sm">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Bottom Section */}
        <div className="px-4 mt-auto border-t border-white/5 pt-6 space-y-2">
          {user && (
            <div className="flex items-center gap-3 px-4 py-3">
              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary text-sm font-bold">
                {user.name.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-on-surface truncate">{user.name}</p>
                <p className="text-[10px] text-stone-500">{user.role}</p>
              </div>
              {onLogout && (
                <button
                  onClick={onLogout}
                  className="p-1.5 text-stone-500 hover:text-error transition-colors rounded-lg hover:bg-white/5"
                  aria-label="Sair"
                >
                  <span className="material-symbols-outlined text-lg">logout</span>
                </button>
              )}
            </div>
          )}
        </div>
      </aside>

      {/* ── Mobile Overlay ── */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        >
          <aside
            className="flex flex-col w-72 h-full bg-stone-950/95 backdrop-blur-xl border-r border-white/10 py-6 animate-in slide-in-from-left"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Brand */}
            <div className="px-6 mb-10 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center">
                <span className="material-symbols-outlined text-primary text-xl">eco</span>
              </div>
              <div>
                <h1 className="text-xl font-black text-primary-container tracking-widest font-headline">
                  {brandTitle}
                </h1>
                <p className="text-[10px] uppercase tracking-[0.2em] text-stone-500 font-bold">
                  {brandSubtitle}
                </p>
              </div>
            </div>

            {/* Nav Items */}
            <nav className="flex-1 px-4 space-y-2 overflow-y-auto">
              {navItems.map((item) => {
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      "flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 group",
                      active
                        ? "text-primary bg-primary/10 font-bold border-r-2 border-primary"
                        : "text-stone-400 hover:text-stone-200 hover:bg-white/5",
                    )}
                  >
                    <span className="material-symbols-outlined">{item.icon}</span>
                    <span className="font-headline tracking-tight text-sm">{item.label}</span>
                  </Link>
                );
              })}
            </nav>

            {/* Bottom */}
            <div className="px-4 mt-auto border-t border-white/5 pt-6 space-y-2">
              {user && (
                <div className="flex items-center gap-3 px-4 py-3">
                  <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary text-sm font-bold">
                    {user.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-bold text-on-surface truncate">{user.name}</p>
                    <p className="text-[10px] text-stone-500">{user.role}</p>
                  </div>
                  {onLogout && (
                    <button
                      onClick={onLogout}
                      className="p-1.5 text-stone-500 hover:text-error transition-colors rounded-lg hover:bg-white/5"
                      aria-label="Sair"
                    >
                      <span className="material-symbols-outlined text-lg">logout</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </aside>
        </div>
      )}

      {/* ── Main Content Area ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile Top Bar */}
        <header className="md:hidden fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-4 h-14 bg-stone-950/80 backdrop-blur-md border-b border-white/10">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-2 text-stone-400 hover:text-primary transition-colors"
            aria-label="Abrir menu"
          >
            <span className="material-symbols-outlined">menu</span>
          </button>
          <h1 className="text-sm font-black text-primary-container tracking-widest font-headline">
            {brandTitle}
          </h1>
          <div className="w-10" />
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto pt-14 md:pt-0">{children}</main>

        {/* Mobile Bottom Nav */}
        <nav className="md:hidden fixed bottom-0 left-0 w-full h-20 flex justify-around items-center px-4 pb-4 bg-zinc-900/90 backdrop-blur-xl z-40 rounded-t-[2rem] border-t border-white/5 shadow-[0_-10px_40px_rgba(0,0,0,0.5)]">
          {[
            {
              label: "Painel",
              icon: "dashboard",
              href: navItems.find((i) => i.icon === "dashboard")?.href ?? "/med/dashboard",
            },
            {
              label: "Fila",
              icon: "queue",
              href: navItems.find((i) => i.icon === "queue")?.href ?? "/med/fila",
            },
            {
              label: "Atendimentos",
              icon: "assignment",
              href: navItems.find((i) => i.icon === "assignment")?.href ?? "/med/atendimentos",
            },
            {
              label: "Prescricoes",
              icon: "prescriptions",
              href: navItems.find((i) => i.icon === "prescriptions")?.href ?? "/med/prescricao",
            },
          ].map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex flex-col items-center justify-center rounded-full px-3 py-2 transition-transform duration-300 active:scale-90",
                  active ? "bg-primary/10 text-primary" : "text-zinc-400 hover:bg-white/5",
                )}
              >
                <span
                  className="material-symbols-outlined"
                  style={active ? { fontVariationSettings: "'FILL' 1" } : undefined}
                >
                  {item.icon}
                </span>
                <span className="font-headline text-[10px] font-semibold tracking-tight">
                  {item.label}
                </span>
              </Link>
            );
          })}
          <button
            onClick={() => setMobileOpen(true)}
            className="flex flex-col items-center justify-center rounded-full px-3 py-2 transition-transform duration-300 active:scale-90 text-zinc-400 hover:bg-white/5"
          >
            <span className="material-symbols-outlined">more_horiz</span>
            <span className="font-headline text-[10px] font-semibold tracking-tight">Mais...</span>
          </button>
        </nav>
      </div>
    </div>
  );
}
