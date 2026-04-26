"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * /med/conhecimento -> /org/conhecimento.
 *
 * Quando a Fase A2 unificar /med dentro de /org, este redirect
 * simplesmente desaparece (a rota canonica passa a ser
 * /org/conhecimento, ou /clinica/conhecimento se renomear).
 */
export default function MedConhecimentoRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/org/conhecimento");
  }, [router]);
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <p className="text-on-surface/50 text-sm">Redirecionando para Base Cientifica...</p>
    </div>
  );
}
