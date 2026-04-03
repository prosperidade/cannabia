"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ApiError, listMessageContacts, listMessages } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useApiSession } from "@/lib/use-api-session";
import type { ApiListMeta, MessageContactOption, MessageItem } from "@/lib/types";

export default function MessagesPage() {
  const router = useRouter();
  const session = useApiSession();
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [contacts, setContacts] = useState<MessageContactOption[]>([]);
  const [meta, setMeta] = useState<ApiListMeta>({
    page: 1,
    page_size: 20,
    total: 0,
  });
  const [loading, setLoading] = useState(true);
  const [contactsLoading, setContactsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [queryInput, setQueryInput] = useState("");
  const [senderInput, setSenderInput] = useState("all");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [appliedSender, setAppliedSender] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  async function loadContacts(search = "") {
    setContactsLoading(true);
    try {
      const data = await listMessageContacts(search);
      setContacts(data);
    } finally {
      setContactsLoading(false);
    }
  }

  async function loadMessages(
    nextPage = page,
    nextPageSize = pageSize,
    nextQuery = appliedQuery,
    nextSender = appliedSender,
  ) {
    setLoading(true);
    setError(null);
    try {
      const response = await listMessages(nextPage, nextPageSize, {
        search: nextQuery || undefined,
        sender: nextSender !== "all" ? nextSender : undefined,
      });
      setMessages(response.items);
      setMeta(response.meta);
    } catch (loadError) {
      setError(loadError instanceof ApiError ? loadError.message : "Falha ao carregar mensagens.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (session.loading) {
      return;
    }
    if (!session.data?.authenticated) {
      router.replace("/login");
      return;
    }
    void loadMessages();
  }, [appliedQuery, appliedSender, page, pageSize, router, session.data, session.loading]);

  useEffect(() => {
    if (session.loading || !session.data?.authenticated) {
      return;
    }
    void loadContacts();
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

  const distinctContacts = contacts.length;
  const withTextCount = messages.filter((message) => Boolean(message.message_text?.trim())).length;
  const latestMessage =
    [...messages].sort(
      (left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime(),
    )[0] ?? null;
  const totalPages = Math.max(1, Math.ceil(meta.total / meta.page_size));

  return (
    <AppShell
      session={session.data}
      subtitle="Histórico operacional do canal conversacional, puxado pela API v1 sem depender da tela legada em Jinja."
      title="Mensagens"
    >
      <section className="overview-grid">
        <article className="overview-band">
          <span className="meta-label">Total</span>
          <h2>{meta.total}</h2>
          <p className="lead">Mensagens disponíveis no histórico atual da clínica ativa.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">Contatos</span>
          <h2>{distinctContacts}</h2>
          <p className="lead">Remetentes distintos disponíveis no histórico consultado.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">Com texto</span>
          <h2>{withTextCount}</h2>
          <p className="lead">Mensagens com conteúdo textual visível nesta página.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">Página</span>
          <h2>
            {meta.page}/{totalPages}
          </h2>
          <p className="lead">
            {latestMessage
              ? `Última da página: ${formatDateTime(latestMessage.timestamp)}`
              : "Nenhuma mensagem recente registrada."}
          </p>
        </article>
      </section>

      <section className="attendance-toolbar">
        <input
          className="filter-input"
          onChange={(event) => setQueryInput(event.target.value)}
          placeholder="Buscar por contato, telefone ou conteúdo"
          value={queryInput}
        />
        <select
          className="filter-select"
          onChange={(event) => setSenderInput(event.target.value)}
          value={senderInput}
        >
          <option value="all">Todos os remetentes</option>
          {contacts.map((contact) => (
            <option key={contact.sender} value={contact.sender}>
              {contact.label} ({contact.count})
            </option>
          ))}
        </select>
        <button
          className="button-primary"
          onClick={() => {
            setPage(1);
            setAppliedQuery(queryInput.trim());
            setAppliedSender(senderInput);
            void loadContacts(queryInput.trim());
          }}
          type="button"
        >
          Aplicar filtros
        </button>
        <button
          className="button-secondary"
          onClick={() => {
            setQueryInput("");
            setSenderInput("all");
            setAppliedQuery("");
            setAppliedSender("all");
            setPage(1);
            void loadContacts();
          }}
          type="button"
        >
          Limpar filtros
        </button>
        <select
          className="filter-select"
          onChange={(event) => {
            const nextPageSize = Number(event.target.value);
            setPage(1);
            setPageSize(nextPageSize);
          }}
          value={pageSize}
        >
          <option value={10}>10 por página</option>
          <option value={20}>20 por página</option>
          <option value={50}>50 por página</option>
        </select>
        <button
          className="button-secondary"
          onClick={() => {
            void loadMessages(page, pageSize, appliedQuery, appliedSender);
          }}
          type="button"
        >
          Recarregar feed
        </button>
      </section>

      {error ? <div className="inline-error">{error}</div> : null}

      <section className="analytics-grid">
        <article className="grid-panel">
          <header className="split-line">
            <div>
              <p className="eyebrow">Canal ativo</p>
              <h2>WhatsApp da clínica</h2>
            </div>
            <span className="context-chip">API v1 /messages</span>
          </header>
          <p className="lead">
            O frontend novo assume aqui a leitura do histórico operacional sem depender da
            tabela HTML antiga do Flask.
          </p>
          <div className="kpi-line">
            <span className="meta-label">Itens carregados</span>
            <strong>{messages.length}</strong>
          </div>
          <div className="kpi-line">
            <span className="meta-label">Faixa atual</span>
            <strong>
              {messages.length ? `${(meta.page - 1) * meta.page_size + 1}-${(meta.page - 1) * meta.page_size + messages.length}` : "0"}
            </strong>
          </div>
          <div className="kpi-line">
            <span className="meta-label">Busca atual</span>
            <strong>{appliedQuery || "sem filtro textual"}</strong>
          </div>
          <div className="kpi-line">
            <span className="meta-label">Remetente</span>
            <strong>
              {appliedSender === "all"
                ? "todos"
                : contacts.find((contact) => contact.sender === appliedSender)?.label ?? appliedSender}
            </strong>
          </div>
        </article>

        <article className="content-card">
          <header className="split-line">
            <div>
              <p className="eyebrow">Transição controlada</p>
              <h2>Próximo encaixe natural</h2>
            </div>
          </header>
          <p className="lead">
            Depois do histórico, a expansão mais próxima é ligar esta superfície a eventos
            realtime e trilhas de auditoria operacional.
          </p>
          <div className="kpi-line">
            <span className="meta-label">Catálogo de remetentes</span>
            <strong>{contactsLoading ? "..." : contacts.length}</strong>
          </div>
        </article>
      </section>

      {loading ? (
        <div className="inline-empty">Carregando mensagens...</div>
      ) : messages.length ? (
        <>
          <section className="action-cluster" style={{ marginTop: 22 }}>
            <button
              className="button-secondary"
              disabled={meta.page <= 1}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              type="button"
            >
              Página anterior
            </button>
            <span className="context-chip">
              Página {meta.page} de {totalPages}
            </span>
            <button
              className="button-secondary"
              disabled={meta.page >= totalPages}
              onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              type="button"
            >
              Próxima página
            </button>
          </section>

          <section className="message-list">
            {messages.map((message) => (
              <article className="message-item" key={message.id}>
                <header>
                  <strong>{message.contact_name || "Contato sem nome"}</strong>
                  <span>{formatDateTime(message.timestamp)}</span>
                </header>
                <div className="kpi-line">
                  <span className="mono">{message.sender}</span>
                  <span>Mensagem #{message.id}</span>
                </div>
                <p className="lead">{message.message_text || "Mensagem sem texto disponível."}</p>
              </article>
            ))}
          </section>
        </>
      ) : (
        <div className="inline-empty">Nenhuma mensagem encontrada para o recorte remoto atual.</div>
      )}
    </AppShell>
  );
}
