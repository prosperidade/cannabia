"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Compat: a tela antiga /org/config foi substituida por /org/configuracoes
 * (com abas e UI moderna). Este redirect mantem links e bookmarks
 * antigos funcionando.
 */
export default function OrgConfigRedirect() {
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
