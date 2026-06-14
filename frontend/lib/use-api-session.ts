"use client";

import { startTransition, useEffect, useState } from "react";

import { ApiError, getSession } from "@/lib/api";
import type { ApiSessionResponse } from "@/lib/types";

type SessionState = {
  loading: boolean;
  data: ApiSessionResponse | null;
  error: string | null;
};

export function useApiSession() {
  const [state, setState] = useState<SessionState>({
    loading: true,
    data: null,
    error: null,
  });

  async function loadSession() {
    try {
      const data = await getSession();
      setState({ loading: false, data, error: null });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Falha ao carregar a sessao.";
      setState({ loading: false, data: null, error: message });
    }
  }

  useEffect(() => {
    startTransition(() => {
      void loadSession();
    });
  }, []);

  return {
    ...state,
    refresh: loadSession,
  };
}
