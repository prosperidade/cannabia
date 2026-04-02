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

        <label>
          Usuario
          <input
            className="login-field"
            onChange={(event) => setUsername(event.target.value)}
            placeholder="admin"
            value={username}
          />
        </label>

        <label>
          Senha
          <input
            className="login-field"
            onChange={(event) => setPassword(event.target.value)}
            placeholder="********"
            type="password"
            value={password}
          />
        </label>

        {error ? <div className="inline-error">{error}</div> : null}
        {session.error ? <div className="inline-error">{session.error}</div> : null}

        <div className="button-row">
          <button className="button-primary" disabled={busy} type="submit">
            {busy ? "Entrando..." : "Entrar"}
          </button>
        </div>
      </form>
    </div>
  );
}
