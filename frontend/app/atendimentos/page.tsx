"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function OldAtendimentosRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/med/fila");
  }, [router]);
  return <div className="min-h-screen bg-surface flex items-center justify-center"><p className="text-on-surface/50">Redirecionando...</p></div>;
}
