"use client";

import * as ToastPrimitive from "@radix-ui/react-toast";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

/* ─── Types ──────────────────────────────────────────────────────────── */

type ToastTone = "success" | "warning" | "error" | "info";

type ToastPayload = {
  id: string;
  title: string;
  description?: string;
  tone?: ToastTone;
  duration?: number;
};

type ToastContextValue = {
  toast: (payload: Omit<ToastPayload, "id">) => void;
  dismiss: (id: string) => void;
};

/* ─── Context ────────────────────────────────────────────────────────── */

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast deve ser usado dentro de <ToastProvider>");
  return ctx;
}

/* ─── Provider ───────────────────────────────────────────────────────── */

let counter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastPayload[]>([]);

  const toast = useCallback((payload: Omit<ToastPayload, "id">) => {
    counter += 1;
    const id = `toast-${counter}-${Date.now()}`;
    setToasts((prev) => [...prev, { ...payload, id }]);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast, dismiss }}>
      <ToastPrimitive.Provider duration={5000} swipeDirection="right">
        {children}

        {toasts.map((t) => (
          <ToastPrimitive.Root
            className={cn("ds-toast", t.tone && `ds-toast--${t.tone}`)}
            duration={t.duration}
            key={t.id}
            onOpenChange={(open) => {
              if (!open) dismiss(t.id);
            }}
          >
            <div>
              <ToastPrimitive.Title className="ds-toast__title">{t.title}</ToastPrimitive.Title>
              {t.description ? (
                <ToastPrimitive.Description className="ds-toast__desc">
                  {t.description}
                </ToastPrimitive.Description>
              ) : null}
            </div>
            <ToastPrimitive.Close aria-label="Fechar notificação" className="ds-toast__close">
              ✕
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        ))}

        <ToastPrimitive.Viewport className="ds-toast-viewport" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}
