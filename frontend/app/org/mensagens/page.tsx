"use client";

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { listMessages, listMessageContacts, ApiError } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import type { MessageItem, MessageContactOption, ApiListMeta } from "@/lib/types";
import {
  Card,
  StatCard,
  Badge,
  Button,
  MaterialIcon,
  SearchBar,
} from "@/components/ui-tw";

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function MensagensPage() {
  const session = useApiSession();

  /* ---------- state ---------- */
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [contacts, setContacts] = useState<MessageContactOption[]>([]);
  const [meta, setMeta] = useState<ApiListMeta>({ page: 1, page_size: 20, total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [sender, setSender] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  /* ---------- derived ---------- */
  const totalPages = Math.max(1, Math.ceil(meta.total / pageSize));
  const uniqueContacts = contacts.length;
  const todayStr = new Date().toISOString().slice(0, 10);
  const todayCount = messages.filter((m) => m.timestamp?.startsWith(todayStr)).length;
  const withText = messages.filter((m) => m.message_text?.trim()).length;

  /* ---------- data fetching ---------- */
  const fetchMessages = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listMessages(page, pageSize, {
        sender: sender || undefined,
        search: search || undefined,
      });
      setMessages(result.items);
      setMeta(result.meta);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao carregar mensagens.");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, sender, search]);

  const fetchContacts = useCallback(async () => {
    try {
      const data = await listMessageContacts();
      setContacts(data);
    } catch {
      // silently ignore
    }
  }, []);

  useEffect(() => {
    if (session.loading) return;
    void fetchContacts();
  }, [session.loading, fetchContacts]);

  useEffect(() => {
    if (session.loading) return;
    void fetchMessages();
  }, [session.loading, fetchMessages]);

  /* Reset page on filter change */
  useEffect(() => {
    setPage(1);
  }, [search, sender, pageSize]);

  /* ---------- helpers ---------- */
  function formatTs(ts: string) {
    try {
      const d = new Date(ts);
      return d.toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return ts;
    }
  }

  function isOutgoing(senderVal: string) {
    return senderVal?.startsWith("system") || senderVal?.startsWith("bot") || senderVal?.includes("clinic");
  }

  /* ---------- render ---------- */
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">
          Historico de Mensagens
        </h2>
        <p className="text-stone-400 text-sm mt-1 italic">
          Todas as mensagens do WhatsApp Business
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
        <StatCard icon="chat" label="Total Mensagens" value={meta.total.toLocaleString("pt-BR")} />
        <StatCard icon="contacts" label="Contatos Unicos" value={uniqueContacts} />
        <StatCard icon="today" label="Mensagens Hoje" value={todayCount} />
        <StatCard icon="text_fields" label="Com Texto" value={withText} />
      </div>

      {/* Filters */}
      <Card padding="md">
        <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-end">
          {/* Search */}
          <div className="flex-1">
            <SearchBar
              value={search}
              onChange={setSearch}
              placeholder="Buscar no conteudo das mensagens..."
            />
          </div>

          {/* Sender select */}
          <div className="w-full md:w-64">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold block mb-1.5">
              Contato
            </label>
            <select
              value={sender}
              onChange={(e) => setSender(e.target.value)}
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors text-sm"
            >
              <option value="">Todos os contatos</option>
              {contacts.map((c) => (
                <option key={c.sender} value={c.sender}>
                  {c.label} ({c.count})
                </option>
              ))}
            </select>
          </div>

          {/* Page size */}
          <div className="w-full md:w-36">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold block mb-1.5">
              Por Pagina
            </label>
            <select
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors text-sm"
            >
              {[10, 20, 50].map((n) => (
                <option key={n} value={n}>
                  {n} itens
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {/* Error */}
      {error && (
        <Card padding="md" className="border-l-4 border-error/50 bg-error/5">
          <div className="flex items-center gap-3">
            <MaterialIcon icon="error" className="text-error" />
            <div>
              <p className="text-sm font-bold text-on-surface">Erro ao carregar mensagens</p>
              <p className="text-xs text-stone-400">{error}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={fetchMessages} className="ml-auto">
              Tentar novamente
            </Button>
          </div>
        </Card>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-4">
            <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
            <p className="text-sm text-stone-500 font-headline tracking-widest uppercase">
              Carregando...
            </p>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && messages.length === 0 && (
        <Card padding="lg" className="text-center">
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="p-4 bg-white/5 rounded-full">
              <MaterialIcon icon="forum" size="xl" className="text-stone-600" />
            </div>
            <div>
              <p className="text-lg font-headline font-bold text-stone-400">
                Nenhuma mensagem encontrada
              </p>
              <p className="text-sm text-stone-600 mt-1">
                {search || sender
                  ? "Tente ajustar os filtros de busca."
                  : "As mensagens do WhatsApp aparecerão aqui."}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Message list */}
      {!loading && messages.length > 0 && (
        <div className="space-y-3">
          {messages.map((msg) => {
            const outgoing = isOutgoing(msg.sender);
            return (
              <Card key={msg.id} padding="sm" className="hover:bg-white/5 transition-colors">
                <div className="flex items-start gap-4 p-2">
                  {/* Avatar placeholder */}
                  <div
                    className={cn(
                      "w-10 h-10 md:w-12 md:h-12 rounded-xl flex items-center justify-center shrink-0",
                      outgoing ? "bg-primary/10" : "bg-secondary/10",
                    )}
                  >
                    <MaterialIcon
                      icon={outgoing ? "send" : "person"}
                      className={outgoing ? "text-primary" : "text-secondary"}
                      size="sm"
                    />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="text-sm font-bold text-on-surface truncate">
                        {msg.contact_name || msg.sender}
                      </span>
                      <Badge tone={outgoing ? "primary" : "info"}>
                        {outgoing ? "Enviada" : "Recebida"}
                      </Badge>
                      <span className="text-[10px] text-stone-500 font-mono ml-auto shrink-0">
                        {formatTs(msg.timestamp)}
                      </span>
                    </div>
                    <p className="text-sm text-stone-400 line-clamp-2">
                      {msg.message_text || (
                        <span className="italic text-stone-600">(sem conteudo de texto)</span>
                      )}
                    </p>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {!loading && meta.total > 0 && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-stone-500">
            Mostrando {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, meta.total)} de{" "}
            {meta.total} mensagens
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              icon="chevron_left"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Anterior
            </Button>
            <span className="text-sm text-stone-400 px-3">
              {page} / {totalPages}
            </span>
            <Button
              variant="ghost"
              size="sm"
              icon="chevron_right"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Proxima
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
