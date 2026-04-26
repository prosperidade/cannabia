"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Compat: a tela antiga /settings standalone foi consolidada em
 * /org/configuracoes (com abas). Este redirect mantem URLs e
 * bookmarks antigos funcionando.
 */
export default function SettingsRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/org/configuracoes");
  }, [router]);
  return (
    <div className="min-h-screen flex items-center justify-center bg-surface">
      <p className="text-on-surface/50 text-sm">Redirecionando para Configuracoes...</p>
    </div>
  );
}
