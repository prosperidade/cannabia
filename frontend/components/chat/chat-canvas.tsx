"use client";

import { useRef, useEffect, type ReactNode } from "react";

/* ─── Header ────────────────────────────────────────────────────────── */

interface ChatHeaderProps {
  clinicName: string;
  clinicInitials?: string;
}

export function ChatHeader({ clinicName, clinicInitials }: ChatHeaderProps) {
  return (
    <header className="ds-chat-header">
      <div className="ds-chat-header__avatar">{clinicInitials ?? clinicName.charAt(0)}</div>
      <div className="ds-chat-header__info">
        <p className="ds-chat-header__name">{clinicName}</p>
        <span className="ds-chat-header__status">
          <span className="ds-chat-header__dot" />
          Triagem ativa
        </span>
      </div>
    </header>
  );
}

/* ─── Thread (scrollable area) ──────────────────────────────────────── */

interface ChatThreadProps {
  children: ReactNode;
}

export function ChatThread({ children }: ChatThreadProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  });

  return (
    <div className="ds-chat-thread" ref={ref} role="log" aria-live="polite">
      {children}
    </div>
  );
}

/* ─── Canvas (full page wrapper) ────────────────────────────────────── */

interface ChatCanvasProps {
  children: ReactNode;
}

export function ChatCanvas({ children }: ChatCanvasProps) {
  return <div className="ds-chat-root ds-chat-canvas">{children}</div>;
}
