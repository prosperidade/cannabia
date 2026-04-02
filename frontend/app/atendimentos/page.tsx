"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDeferredValue, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { StatusPill } from "@/components/status-pill";
import { ApiError, listAttendances } from "@/lib/api";
import { formatDateTime, humanize } from "@/lib/format";
import { useApiSession } from "@/lib/use-api-session";
import type { AttendanceListItem } from "@/lib/types";

function statusTone(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("revis")) return "ok" as const;
  if (normalized.includes("pend")) return "warn" as const;
  return "info" as const;
}

export default function AttendancesPage() {
  const router = useRouter();
  const session = useApiSession();
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<AttendanceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(query);

  useEffect(() => {
    if (session.loading) {
      return;
    }
    if (!session.data?.authenticated) {
      router.replace("/login");
      return;
    }

    async function loadAttendances() {
      setLoading(true);
      setError(null);
      try {
        const reports = await listAttendances(status);
        setItems(reports);
      } catch (loadError) {
        setError(loadError instanceof ApiError ? loadError.message : "Falha ao carregar atendimentos.");
      } finally {
        setLoading(false);
      }
    }

    void loadAttendances();
  }, [router, session.data, session.loading, status]);

  if (session.loading || !session.data) {
    return (
      <div className="loading-screen">
        <div className="loading-card">
          <h2>Carregando sessao</h2>
          <p className="lead">Aguardando contexto autenticado do backend.</p>
        </div>
      </div>
    );
  }

  if (!session.data.authenticated) {
    return null;
  }

  const visibleItems = items.filter((item) => {
    const normalizedQuery = deferredQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return true;
    }

    return (
      item.patient_name.toLowerCase().includes(normalizedQuery) ||
      item.phone.toLowerCase().includes(normalizedQuery) ||
      item.report_model.toLowerCase().includes(normalizedQuery)
    );
  });

  const pendingCount = items.filter((item) => item.status === "pendente").length;
  const reviewedCount = items.filter((item) => item.status === "revisado").length;

  return (
    <AppShell
      session={session.data}
      subtitle="Primeira tela operacional portada para o frontend novo. Lista, filtro e acesso ao detalhe clinico."
      title="Atendimentos"
    >
      <section className="overview-grid">
        <article className="overview-band">
          <span className="meta-label">Total</span>
          <h2>{items.length}</h2>
          <p className="lead">Relatorios clinicos gerados pela jornada de anamnese.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">Pendentes</span>
          <h2>{pendingCount}</h2>
          <p className="lead">Casos aguardando validacao clinica.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">Revisados</span>
          <h2>{reviewedCount}</h2>
          <p className="lead">Casos ja encaminhados ao prontuario.</p>
        </article>
      </section>

      <section className="attendance-toolbar">
        <input
          className="filter-input"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar por paciente, telefone ou modelo"
          value={query}
        />
        <select
          className="filter-select"
          onChange={(event) => setStatus(event.target.value)}
          value={status}
        >
          <option value="all">Todos os status</option>
          <option value="pendente">Pendente</option>
          <option value="revisado">Revisado</option>
        </select>
      </section>

      {error ? <div className="inline-error">{error}</div> : null}

      {loading ? (
        <div className="inline-empty">Carregando relatorios...</div>
      ) : visibleItems.length ? (
        <section className="attendance-grid">
          {visibleItems.map((item) => (
            <article className="attendance-card" key={item.id}>
              <header>
                <div>
                  <p className="eyebrow">Atendimento #{item.id}</p>
                  <h2>{item.patient_name}</h2>
                </div>
                <StatusPill label={humanize(item.status)} tone={statusTone(item.status)} />
              </header>
              <div className="kpi-line">
                <span className="mono">{item.phone}</span>
                <span>{formatDateTime(item.created_at)}</span>
              </div>
              <div className="pill-row">
                <span className="mini-pill">{item.report_model}</span>
                <span className="mini-pill">{item.rag_chunks_used} chunks RAG</span>
                <span className="mini-pill">
                  {item.patient_id ? `Paciente #${item.patient_id}` : "Paciente em vinculacao"}
                </span>
              </div>
              <p className="lead">
                Caso pronto para revisao, timeline e prontuario no cockpit novo.
              </p>
              <Link className="button-primary" href={`/atendimentos/${item.id}`}>
                Abrir detalhe
              </Link>
            </article>
          ))}
        </section>
      ) : (
        <div className="inline-empty">Nenhum atendimento encontrado para o filtro atual.</div>
      )}
    </AppShell>
  );
}
