"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

export interface MobileNavItem {
  label: string;
  icon: string;
  href: string;
}

export interface MobileLayoutProps {
  navItems: MobileNavItem[];
  activeHref?: string;
  topBarTitle?: string;
  topBarActions?: ReactNode;
  children: ReactNode;
}

export function MobileLayout({
  navItems,
  activeHref,
  topBarTitle = "Cannab'IA",
  topBarActions,
  children,
}: MobileLayoutProps) {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (activeHref) return activeHref === href;
    return pathname === href || pathname.startsWith(href + "/");
  };

  return (
    <div className="min-h-screen bg-background text-on-background font-body">
      {/* ── Top App Bar ── */}
      <header className="fixed top-0 w-full z-50 border-b border-white/5 bg-zinc-950/80 backdrop-blur-md flex justify-between items-center px-6 h-16">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-primary"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            eco
          </span>
          <h1 className="font-headline uppercase tracking-widest text-xs font-bold text-primary">
            {topBarTitle}
          </h1>
        </div>

        {topBarActions ? (
          <div className="flex items-center gap-2">{topBarActions}</div>
        ) : (
          <div className="w-8 h-8 rounded-full border border-primary/30 bg-primary/10 flex items-center justify-center">
            <span className="material-symbols-outlined text-primary text-sm">
              person
            </span>
          </div>
        )}
      </header>

      {/* ── Main Content ── */}
      <main className="pt-16 pb-24 px-4 space-y-6">{children}</main>

      {/* ── Bottom Navigation ── */}
      <nav className="fixed bottom-0 left-0 w-full h-20 flex justify-around items-center px-4 pb-4 bg-zinc-900/90 backdrop-blur-xl z-50 rounded-t-[2rem] border-t border-white/5 shadow-[0_-10px_40px_rgba(0,0,0,0.5)]">
        {navItems.slice(0, 5).map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center justify-center rounded-full px-5 py-2 transition-transform duration-300 active:scale-90",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-zinc-400 hover:bg-white/5"
              )}
            >
              <span
                className="material-symbols-outlined"
                style={
                  active
                    ? { fontVariationSettings: "'FILL' 1" }
                    : undefined
                }
              >
                {item.icon}
              </span>
              <span className="font-headline text-[10px] font-semibold tracking-tight">
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
