"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Status de cada componente do backend (espelha /api/v1/health).
 */
type ComponentStatus = {
  status: "healthy" | "degraded" | "unhealthy" | "unknown";
  latency_ms?: number;
  detail?: string;
};

type HealthResponse = {
  status: "healthy" | "degraded" | "unhealthy";
  components: Record<string, ComponentStatus>;
  timestamp?: string;
};

export type SystemStatus = {
  /** Status global do sistema */
  overall: "healthy" | "degraded" | "unhealthy" | "offline" | "unknown";
  /** Estamos sem rede? */
  offline: boolean;
  /** Detalhes por componente */
  components: Record<string, ComponentStatus>;
  /** Último fetch com sucesso */
  lastChecked: Date | null;
  /** Erro de conectividade */
  error: string | null;
  /** Forçar re-check */
  refresh: () => void;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";
const POLL_INTERVAL = 30_000; // 30s
const TIMEOUT = 8_000;

export function useSystemStatus(): SystemStatus {
  const [state, setState] = useState<Omit<SystemStatus, "refresh">>({
    overall: "unknown",
    offline: typeof navigator !== "undefined" ? !navigator.onLine : false,
    components: {},
    lastChecked: null,
    error: null,
  });

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const check = useCallback(async () => {
    // Offline check
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      setState((prev) => ({ ...prev, overall: "offline", offline: true, error: "Sem conexão com a internet" }));
      return;
    }

    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), TIMEOUT);

      const res = await fetch(`${API_BASE}/health`, {
        signal: controller.signal,
        credentials: "include",
        cache: "no-store",
      });
      clearTimeout(timer);

      if (!res.ok) {
        const overall = res.status === 503 ? "unhealthy" as const : "degraded" as const;
        // Try to parse body anyway
        try {
          const data = (await res.json()) as HealthResponse;
          setState({
            overall,
            offline: false,
            components: data.components ?? {},
            lastChecked: new Date(),
            error: null,
          });
        } catch {
          setState((prev) => ({
            ...prev,
            overall,
            offline: false,
            lastChecked: new Date(),
            error: `Backend respondeu ${res.status}`,
          }));
        }
        return;
      }

      const data = (await res.json()) as { data: HealthResponse };
      const health = data.data ?? (data as unknown as HealthResponse);

      setState({
        overall: health.status,
        offline: false,
        components: health.components ?? {},
        lastChecked: new Date(),
        error: null,
      });
    } catch (err) {
      const isAbort = err instanceof DOMException && err.name === "AbortError";
      setState((prev) => ({
        ...prev,
        overall: "unhealthy",
        offline: typeof navigator !== "undefined" ? !navigator.onLine : false,
        lastChecked: new Date(),
        error: isAbort ? "Health check expirou (timeout)" : "Falha ao conectar com o backend",
      }));
    }
  }, []);

  const refresh = useCallback(() => {
    void check();
  }, [check]);

  // Poll — defer first check to avoid sync setState in effect body
  useEffect(() => {
    const initial = setTimeout(() => void check(), 0);
    intervalRef.current = setInterval(() => void check(), POLL_INTERVAL);

    return () => {
      clearTimeout(initial);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [check]);

  // Online/offline events
  useEffect(() => {
    function onOnline() {
      setState((prev) => ({ ...prev, offline: false }));
      void check();
    }
    function onOffline() {
      setState((prev) => ({ ...prev, overall: "offline", offline: true, error: "Sem conexão com a internet" }));
    }

    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, [check]);

  return { ...state, refresh };
}
