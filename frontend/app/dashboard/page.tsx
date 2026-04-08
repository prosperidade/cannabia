"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useApiSession } from "@/lib/use-api-session";

export default function OldDashboardRedirect() {
  const router = useRouter();
  const { data } = useApiSession();
  useEffect(() => {
    const role = data?.user?.role?.toLowerCase();
    if (role === "admin") router.replace("/admin");
    else if (role === "atendente") router.replace("/org/dashboard");
    else if (role === "paciente") router.replace("/p/dashboard");
    else router.replace("/med/dashboard");
  }, [data, router]);
  return <div className="min-h-screen bg-surface flex items-center justify-center"><p className="text-on-surface/50">Redirecionando...</p></div>;
}
