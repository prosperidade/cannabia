"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ApiError, getDashboard, getDashboardMessages } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useApiSession } from "@/lib/use-api-session";
import type { DashboardData, DashboardMessage } from "@/lib/types";

function percentage(value: number, max: number) {
  if (max <= 0) {
    return 8;
  }
  return Math.max(8, Math.round((value / max) * 100));
}

export default function DashboardPage() {
  const router = useRouter();
  const session = useApiSession();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [messages, setMessages] = useState<DashboardMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session.loading) {
      return;
    }
    if (!session.data?.authenticated) {
      router.replace("/login");
      return;
    }

    async function loadDashboard() {
      setLoading(true);
      setError(null);
      try {
        const [dashboardData, messageFeed] = await Promise.all([
          getDashboard(),
          getDashboardMessages(),
        ]);
        setDashboard(dashboardData);
        setMessages(messageFeed);
      } catch (loadError) {
        setError(loadError instanceof ApiError ? loadError.message : "Falha ao carregar o dashboard.");
      } finally {
        setLoading(false);
      }
    }

    void loadDashboard();
  }, [router, session.data, session.loading]);

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

  const metrics = dashboard?.metrics ?? {
    total_messages: 0,
    total_patients: 0,
    total_appointments: 0,
    total_ai: 0,
  };
  const contacts = dashboard?.charts.messages_by_contact ?? [];
  const days = dashboard?.charts.messages_by_day ?? [];
  const maxContactCount = Math.max(...contacts.map((item) => item.count), 0);
  const maxDayCount = Math.max(...days.map((item) => item.count), 0);

  return (
    <AppShell
      session={session.data}
      subtitle="Cockpit inicial do frontend novo, puxando sinais operacionais e clinicos direto da API v1."
      title="Overview"
    >
      <section className="overview-grid">
        <article className="overview-band">
          <span className="meta-label">Mensagens</span>
          <h2>{metrics.total_messages}</h2>
          <p className="lead">Volume capturado pelo canal conversacional da clinica ativa.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">Pacientes</span>
          <h2>{metrics.total_patients}</h2>
          <p className="lead">Pacientes ja registrados na base contextual atual.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">Agendamentos</span>
          <h2>{metrics.total_appointments}</h2>
          <p className="lead">Consultas que ja podem ser operadas no frontend novo.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">IA auditada</span>
          <h2>{metrics.total_ai}</h2>
          <p className="lead">Execucoes rastreadas no backend com trilha de auditoria.</p>
        </article>
      </section>

      <section className="analytics-grid">
        <article className="content-card">
          <header className="split-line">
            <div>
              <p className="eyebrow">Mensagens por contato</p>
              <h2>Ranking operacional</h2>
            </div>
            <Link className="button-secondary" href="/atendimentos">
              Abrir atendimentos
            </Link>
          </header>
          {loading ? (
            <div className="inline-empty">Carregando ranking...</div>
          ) : contacts.length ? (
            <div className="rank-list">
              {contacts.slice(0, 6).map((item, index) => (
                <div className="bar-row" key={`${item.label}-${index}`}>
                  <div className="rank-row">
                    <span className="rank-index">{index + 1}</span>
                    <div>
                      <strong>{item.label}</strong>
                      <p className="lead">Contato com maior volume recente de mensagens.</p>
                    </div>
                    <strong>{item.count}</strong>
                  </div>
                  <div className="bar-meter">
                    <div
                      className="bar-fill"
                      style={{ width: `${percentage(item.count, maxContactCount)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="inline-empty">Sem mensagens suficientes para montar ranking.</div>
          )}
        </article>

        <article className="content-card">
          <header className="split-line">
            <div>
              <p className="eyebrow">Mensagens por dia</p>
              <h2>Tracao recente</h2>
            </div>
            <Link className="button-secondary" href="/agendamentos">
              Abrir agenda
            </Link>
          </header>
          {loading ? (
            <div className="inline-empty">Carregando serie temporal...</div>
          ) : days.length ? (
            <div className="bar-list">
              {days.slice(-7).map((item) => (
                <div className="bar-row" key={item.date}>
                  <header>
                    <strong>{item.date}</strong>
                    <span>{item.count} mensagens</span>
                  </header>
                  <div className="bar-meter">
                    <div
                      className="bar-fill"
                      style={{ width: `${percentage(item.count, maxDayCount)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="inline-empty">Sem historico diario disponivel.</div>
          )}
        </article>
      </section>

      <section className="analytics-grid">
        <article className="grid-panel">
          <header className="split-line">
            <div>
              <p className="eyebrow">Feed operacional</p>
              <h2>Mensagens recentes</h2>
            </div>
          </header>
          {error ? <div className="inline-error">{error}</div> : null}
          {loading ? (
            <div className="inline-empty">Carregando feed...</div>
          ) : messages.length ? (
            <div className="message-list">
              {messages.map((message) => (
                <article className="message-item" key={message.id}>
                  <header>
                    <strong>{message.contact_name || message.sender}</strong>
                    <span>{formatDateTime(message.timestamp)}</span>
                  </header>
                  <div className="kpi-line">
                    <span className="mono">{message.sender}</span>
                    <span>Mensagem #{message.id}</span>
                  </div>
                  <p className="lead">{message.message_text || "Mensagem sem texto disponivel."}</p>
                </article>
              ))}
            </div>
          ) : (
            <div className="inline-empty">Nenhuma mensagem recente encontrada.</div>
          )}
        </article>

        <article className="grid-panel">
          <p className="eyebrow">Proxima frente</p>
          <h2>Escopo imediato do frontend</h2>
          <p className="lead">
            Este cockpit ja sai do modo demonstrativo: overview autenticado, lista clinica
            e agenda. A proxima expansao natural aqui e enriquecer timeline, prontuario e
            auditoria.
          </p>
          <div className="workspace-actions">
            <Link className="button-primary" href="/atendimentos">
              Revisar atendimentos
            </Link>
            <Link className="button-secondary" href="/agendamentos">
              Operar agenda
            </Link>
          </div>
        </article>
      </section>
    </AppShell>
  );
}
