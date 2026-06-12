"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function OldMensagensRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/org/mensagens");
  }, [router]);
  return (
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <p className="text-on-surface/50">Redirecionando...</p>
    </div>
  );
}
