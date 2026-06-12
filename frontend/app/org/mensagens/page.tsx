"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import {
  listConversations,
  getConversation,
  sendConversationMessage,
  markConversationRead,
  ApiError,
} from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import type { Conversation, ConversationMessage } from "@/lib/types";
import { Card, Badge, Button, MaterialIcon, SearchBar, Avatar } from "@/components/ui-tw";

/* ── helpers ── */

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffH = diffMs / 3_600_000;
    if (diffH < 1) return `${Math.max(1, Math.floor(diffMs / 60_000))} min`;
    if (diffH < 24) return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  } catch {
    return "";
  }
}

function contactLabel(c: Conversation) {
  return c.patient_name_resolved || c.contact_name || c.contact_phone;
}

const STATUS_BADGE: Record<string, { tone: "success" | "warning" | "neutral"; label: string }> = {
  open: { tone: "success", label: "Aberta" },
  closed: { tone: "neutral", label: "Fechada" },
};

/* ── Page ── */

export default function InboxPage() {
  const session = useApiSession();
  const csrf = session.data?.csrf_token ?? "";

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "open" | "closed">("open");

  // Thread detail
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);
  const [threadLoading, setThreadLoading] = useState(false);
  const [composing, setComposing] = useState("");
  const [sending, setSending] = useState(false);
  const threadEndRef = useRef<HTMLDivElement>(null);

  // Fetch conversations — Sprint 3 Page-Migration: envelope `Paginated<T>`.
  const fetchConversations = useCallback(
    async (opts?: { append?: boolean }) => {
      setLoading(true);
      setError(null);
      try {
        const nextOffset = opts?.append ? offset : 0;
        const env = await listConversations({
          status: statusFilter === "all" ? undefined : statusFilter,
          search: search || undefined,
          limit: 50,
          offset: nextOffset,
        });
        setConversations((prev) => (opts?.append ? [...prev, ...env.items] : env.items));
        setHasMore(env.has_more);
        setOffset(nextOffset + env.items.length);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Falha ao carregar conversas.");
      } finally {
        setLoading(false);
      }
    },
    [statusFilter, search, offset],
  );

  const loadMoreConvs = useCallback(() => {
    void fetchConversations({ append: true });
  }, [fetchConversations]);

  useEffect(() => {
    if (!session.loading && session.data?.authenticated) {
      void fetchConversations();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.loading, session.data?.authenticated, statusFilter, search]);

  // Open thread
  async function openThread(convId: number) {
    setActiveConvId(convId);
    setThreadLoading(true);
    try {
      const detail = await getConversation(convId);
      setActiveConv(detail.conversation);
      setMessages(detail.messages);
      // Mark as read
      if (detail.conversation.unread_count > 0) {
        await markConversationRead(convId, csrf);
        setConversations((prev) =>
          prev.map((c) => (c.id === convId ? { ...c, unread_count: 0 } : c)),
        );
      }
    } catch {
      setMessages([]);
    } finally {
      setThreadLoading(false);
    }
  }

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Send message
  async function handleSend() {
    if (!composing.trim() || !activeConvId) return;
    setSending(true);
    try {
      await sendConversationMessage(activeConvId, csrf, composing.trim());
      setComposing("");
      // Refresh thread
      const detail = await getConversation(activeConvId);
      setMessages(detail.messages);
      void fetchConversations();
    } catch {
      // ignore
    } finally {
      setSending(false);
    }
  }

  // Stats
  const totalUnread = conversations.reduce((s, c) => s + c.unread_count, 0);
  const openCount = conversations.filter((c) => c.status === "open").length;

  if (session.loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl md:text-3xl font-headline font-extrabold text-on-surface tracking-tight">
          Inbox de Mensagens
        </h2>
        <p className="text-stone-400 text-sm mt-1 flex items-center gap-2">
          <MaterialIcon icon="forum" size="sm" className="text-primary" />
          {openCount} conversas abertas
          {totalUnread > 0 && <Badge tone="danger">{totalUnread} nao lidas</Badge>}
        </p>
      </div>

      {/* Main grid: conversation list + thread */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[60vh]">
        {/* Left: Conversation list */}
        <div className="lg:col-span-4 space-y-4">
          <SearchBar value={search} onChange={setSearch} placeholder="Buscar contato..." />
          <div className="flex gap-2">
            {(["open", "closed", "all"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-widest transition-all",
                  statusFilter === s
                    ? "bg-primary/15 text-primary border border-primary/30"
                    : "glass-panel text-stone-400 hover:text-on-surface",
                )}
              >
                {s === "all" ? "Todas" : s === "open" ? "Abertas" : "Fechadas"}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="flex justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          ) : error ? (
            <p className="text-sm text-error text-center py-4">{error}</p>
          ) : conversations.length === 0 ? (
            <Card padding="lg" className="text-center">
              <MaterialIcon icon="forum" size="xl" className="text-stone-600 mb-3" />
              <p className="text-sm text-stone-400">Nenhuma conversa encontrada.</p>
            </Card>
          ) : (
            <div className="space-y-2 max-h-[60vh] overflow-y-auto">
              {hasMore && (
                <div className="flex justify-center py-2">
                  <Button variant="ghost" size="sm" icon="expand_more" onClick={loadMoreConvs}>
                    Carregar mais
                  </Button>
                </div>
              )}
              {conversations.map((conv) => {
                const isActive = activeConvId === conv.id;
                const sb = STATUS_BADGE[conv.status] ?? STATUS_BADGE.open;
                return (
                  <button
                    key={conv.id}
                    onClick={() => void openThread(conv.id)}
                    className={cn(
                      "w-full text-left p-4 rounded-2xl transition-all border",
                      isActive
                        ? "bg-primary/10 border-primary/30"
                        : "glass-panel border-transparent hover:bg-white/5",
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <Avatar name={contactLabel(conv)} size="md" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-bold text-sm text-on-surface truncate">
                            {contactLabel(conv)}
                          </span>
                          <span className="text-[10px] text-stone-500 shrink-0">
                            {conv.last_message_at ? formatTime(conv.last_message_at) : ""}
                          </span>
                        </div>
                        <p className="text-xs text-stone-400 truncate mt-0.5">
                          {conv.last_message_preview || "Sem mensagens"}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge tone={sb.tone} className="text-[9px]">
                            {sb.label}
                          </Badge>
                          <span className="text-[10px] text-stone-500">{conv.channel}</span>
                          {conv.unread_count > 0 && (
                            <span className="ml-auto w-5 h-5 rounded-full bg-primary text-on-primary text-[10px] font-bold flex items-center justify-center">
                              {conv.unread_count}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right: Thread detail */}
        <div className="lg:col-span-8">
          {!activeConvId ? (
            <Card padding="lg" className="h-full flex items-center justify-center text-center">
              <div>
                <MaterialIcon
                  icon="chat_bubble_outline"
                  size="xl"
                  className="text-stone-600 mb-4"
                />
                <p className="text-stone-400">
                  Selecione uma conversa para visualizar as mensagens.
                </p>
              </div>
            </Card>
          ) : threadLoading ? (
            <div className="flex items-center justify-center py-20">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          ) : (
            <Card padding="sm" className="flex flex-col h-[70vh] !p-0">
              {/* Thread header */}
              {activeConv && (
                <div className="p-4 border-b border-white/5 flex items-center gap-4">
                  <Avatar name={contactLabel(activeConv)} size="md" />
                  <div className="flex-1 min-w-0">
                    <h3 className="font-bold text-on-surface truncate">
                      {contactLabel(activeConv)}
                    </h3>
                    <p className="text-xs text-stone-500">
                      {activeConv.contact_phone} - {activeConv.channel}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="close"
                    onClick={() => {
                      setActiveConvId(null);
                      setMessages([]);
                      setActiveConv(null);
                    }}
                  />
                </div>
              )}

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.length === 0 ? (
                  <p className="text-center text-stone-500 text-sm py-8">
                    Nenhuma mensagem nesta conversa.
                  </p>
                ) : (
                  messages.map((msg) => {
                    const isOutbound = msg.direction === "outbound";
                    return (
                      <div
                        key={msg.id}
                        className={cn("flex", isOutbound ? "justify-end" : "justify-start")}
                      >
                        <div
                          className={cn(
                            "max-w-[75%] px-4 py-3 rounded-2xl text-sm",
                            isOutbound
                              ? "bg-primary/20 text-on-surface rounded-br-md"
                              : "bg-surface-container-high text-on-surface rounded-bl-md",
                          )}
                        >
                          <p className="whitespace-pre-wrap break-words">
                            {msg.message_text || "(sem texto)"}
                          </p>
                          <p
                            className={cn(
                              "text-[10px] mt-1",
                              isOutbound ? "text-primary/60 text-right" : "text-stone-500",
                            )}
                          >
                            {msg.sender_name && (
                              <span className="font-bold mr-2">{msg.sender_name}</span>
                            )}
                            {formatTime(msg.created_at)}
                          </p>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={threadEndRef} />
              </div>

              {/* Compose */}
              <div className="p-4 border-t border-white/5">
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={composing}
                    onChange={(e) => setComposing(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        void handleSend();
                      }
                    }}
                    placeholder="Digite sua mensagem..."
                    className="flex-1 bg-surface-container-low border border-outline-variant/30 rounded-xl px-4 py-3 text-sm text-on-surface placeholder:text-stone-500 focus:border-primary focus:outline-none transition-colors"
                  />
                  <Button
                    icon="send"
                    loading={sending}
                    disabled={!composing.trim()}
                    onClick={() => void handleSend()}
                  >
                    <span className="hidden sm:inline">Enviar</span>
                  </Button>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
