"use client";

import { useRouter } from "next/navigation";
import { startTransition, type FormEvent, useEffect, useState } from "react";

import { ApiError, login } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";

export default function LoginPage() {
  const router = useRouter();
  const session = useApiSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (session.data?.authenticated) {
      router.replace("/dashboard");
    }
  }, [router, session.data]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      await login(username, password);
      router.push("/dashboard");
      router.refresh();
    } catch (submitError) {
      setError(
        submitError instanceof ApiError ? submitError.message : "Falha ao autenticar.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-screen">
      <form
        className="login-card"
        onSubmit={(event) => {
          startTransition(() => {
            void handleSubmit(event);
          });
        }}
      >
        <p className="eyebrow">CannabIA frontend</p>
        <h1>Entrar no cockpit clinico</h1>
        <p className="login-copy">
          A autenticacao continua no Flask. Este frontend consome a sessao existente pela
          API v1.
        </p>

        <div className="field-stack">
          <label htmlFor="login-username">Usuário</label>
          <input
            aria-describedby={error ? "login-error" : undefined}
            aria-invalid={error ? true : undefined}
            autoComplete="username"
            className="login-field"
            id="login-username"
            onChange={(event) => setUsername(event.target.value)}
            placeholder="admin"
            required
            value={username}
          />
        </div>

        <div className="field-stack">
          <label htmlFor="login-password">Senha</label>
          <input
            aria-describedby={error ? "login-error" : undefined}
            aria-invalid={error ? true : undefined}
            autoComplete="current-password"
            className="login-field"
            id="login-password"
            onChange={(event) => setPassword(event.target.value)}
            placeholder="********"
            required
            type="password"
            value={password}
          />
        </div>

        {error ? <div aria-live="assertive" className="inline-error" id="login-error" role="alert">{error}</div> : null}
        {session.error ? <div aria-live="polite" className="inline-error" role="status">{session.error}</div> : null}

        <div className="button-row">
          <button className="button-primary" disabled={busy} type="submit">
            {busy ? "Entrando..." : "Entrar"}
          </button>
        </div>
      </form>
    </div>
  );
}
