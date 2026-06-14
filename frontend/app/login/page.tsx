"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { startTransition, type FormEvent, useEffect, useState } from "react";

import { ApiError, login } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import { getRoleRedirect } from "@/lib/nav";
import { Button, Input } from "@/components/ui-tw";

export default function LoginPage() {
  const router = useRouter();
  const session = useApiSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (session.data?.authenticated) {
      router.replace(
        getRoleRedirect(session.data.user?.role, !!session.data.user?.is_clinic_admin),
      );
    }
  }, [router, session.data]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      const result = await login(username, password);
      const target = getRoleRedirect(result.user?.role, !!result.user?.is_clinic_admin);
      router.push(target);
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof ApiError ? submitError.message : "Falha ao autenticar.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative min-h-screen bg-surface flex items-center justify-center px-4 overflow-hidden">
      {/* Decorative background blurs */}
      <div className="pointer-events-none absolute -top-40 -left-40 h-[600px] w-[600px] rounded-full bg-primary/10 blur-[140px]" />
      <div className="pointer-events-none absolute -bottom-32 -right-32 h-[500px] w-[500px] rounded-full bg-primary-container/15 blur-[120px]" />
      <div className="pointer-events-none absolute top-1/3 left-1/2 h-[300px] w-[300px] -translate-x-1/2 rounded-full bg-primary/5 blur-[80px]" />

      <form
        className="relative z-10 glass-panel rounded-2xl p-8 sm:p-10 w-full max-w-md flex flex-col gap-6"
        onSubmit={(event) => {
          startTransition(() => {
            void handleSubmit(event);
          });
        }}
      >
        {/* Logo + branding */}
        <div className="flex flex-col items-center gap-3 mb-2">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/20 border border-primary/30 shadow-lg shadow-primary/10">
            <span className="text-3xl font-headline font-bold text-primary">C</span>
          </div>
          <h1 className="text-2xl font-headline font-bold text-on-surface tracking-tight">
            Cannab<span className="text-primary">IA</span>
          </h1>
        </div>

        {/* Title */}
        <div className="text-center">
          <h2 className="text-lg font-headline font-bold text-on-surface">Acessar sua conta</h2>
          <p className="text-sm text-on-surface/50 mt-1">
            Entre com suas credenciais para continuar
          </p>
        </div>

        {/* Fields */}
        <div className="flex flex-col gap-4">
          <Input
            label="Usuario"
            icon="person"
            autoComplete="username"
            placeholder="seu.usuario"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            aria-describedby={error ? "login-error" : undefined}
            aria-invalid={error ? true : undefined}
          />
          <Input
            label="Senha"
            icon="lock"
            type="password"
            autoComplete="current-password"
            placeholder="********"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-describedby={error ? "login-error" : undefined}
            aria-invalid={error ? true : undefined}
          />
        </div>

        {/* Error messages */}
        {error && (
          <div
            aria-live="assertive"
            className="rounded-lg bg-error/10 border border-error/30 px-4 py-3 text-sm text-error font-medium"
            id="login-error"
            role="alert"
          >
            {error}
          </div>
        )}
        {session.error && (
          <div
            aria-live="polite"
            className="rounded-lg bg-error/10 border border-error/30 px-4 py-3 text-sm text-error/70"
            role="status"
          >
            {session.error}
          </div>
        )}

        {/* Submit */}
        <Button
          type="submit"
          variant="primary"
          size="lg"
          loading={busy}
          icon={busy ? undefined : "login"}
          className="w-full"
        >
          {busy ? "Entrando..." : "Entrar"}
        </Button>

        {/* Triagem link */}
        <p className="text-center text-sm text-on-surface/40">
          Primeira vez?{" "}
          <Link
            href="/triagem"
            className="text-primary font-bold hover:underline transition-colors"
          >
            Acesse sua triagem
          </Link>
        </p>
      </form>
    </div>
  );
}
