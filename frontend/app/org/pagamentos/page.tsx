"use client";

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import {
  listPayments,
  getPaymentSummary,
  issuePixCharge,
  confirmPaymentManual,
  cancelPayment,
  ApiError,
} from "@/lib/api";
import {
  Card,
  Badge,
  Button,
  Input,
  MaterialIcon,
  StatCard,
} from "@/components/ui-tw";
import type {
  PaymentRequest,
  PaymentSummary,
} from "@/lib/types";

const fmtBRL = (cents: number) =>
  (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const statusTone: Record<PaymentRequest["status"], "success" | "warning" | "danger" | "neutral" | "info"> = {
  paid: "success",
  pending: "warning",
  expired: "danger",
  cancelled: "neutral",
  refunded: "info" as "warning",
};

const statusLabel: Record<PaymentRequest["status"], string> = {
  paid: "Pago",
  pending: "Pendente",
  expired: "Expirado",
  cancelled: "Cancelado",
  refunded: "Reembolsado",
};

export default function PagamentosPage() {
  const session = useApiSession();
  const csrf = session.data?.csrf_token ?? "";

  const [payments, setPayments] = useState<PaymentRequest[]>([]);
  const [summary, setSummary] = useState<PaymentSummary>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"" | PaymentRequest["status"]>("");

  const [showIssue, setShowIssue] = useState(false);
  const [issueAmount, setIssueAmount] = useState("");
  const [issueDescription, setIssueDescription] = useState("");
  const [issuePatient, setIssuePatient] = useState("");
  const [issuePixKey, setIssuePixKey] = useState("");
  const [issuing, setIssuing] = useState(false);
  const [issueError, setIssueError] = useState<string | null>(null);

  const [selected, setSelected] = useState<PaymentRequest | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [list, sum] = await Promise.all([
        listPayments({ status: statusFilter || undefined, limit: 100 }),
        getPaymentSummary().catch(() => ({})),
      ]);
      setPayments(Array.isArray(list.data) ? list.data : []);
      setSummary(sum as PaymentSummary);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao carregar pagamentos.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    if (!session.loading && session.data?.authenticated) void fetchAll();
  }, [session.loading, session.data?.authenticated, fetchAll]);

  async function handleIssue() {
    if (!csrf) return;
    const cents = Math.round(Number(issueAmount.replace(",", ".")) * 100);
    if (!Number.isFinite(cents) || cents <= 0) {
      setIssueError("Informe um valor valido.");
      return;
    }
    try {
      setIssuing(true);
      setIssueError(null);
      const created = await issuePixCharge(csrf, {
        amount_cents: cents,
        description: issueDescription || undefined,
        patient_id: issuePatient ? Number(issuePatient) : undefined,
        pix_key: issuePixKey || undefined,
      });
      setShowIssue(false);
      setIssueAmount("");
      setIssueDescription("");
      setIssuePatient("");
      setIssuePixKey("");
      await fetchAll();
      setSelected(created);
    } catch (err) {
      setIssueError(err instanceof Error ? err.message : "Falha ao emitir cobranca.");
    } finally {
      setIssuing(false);
    }
  }

  async function handleConfirm(id: number) {
    if (!csrf) return;
    try {
      await confirmPaymentManual(csrf, id);
      await fetchAll();
      if (selected?.id === id) setSelected(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Falha ao confirmar.");
    }
  }

  async function handleCancel(id: number) {
    if (!csrf) return;
    if (!confirm("Cancelar esta cobranca?")) return;
    try {
      await cancelPayment(csrf, id);
      await fetchAll();
      if (selected?.id === id) setSelected(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Falha ao cancelar.");
    }
  }

  function copyPix(text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopyFeedback("Codigo Pix copiado.");
      setTimeout(() => setCopyFeedback(null), 2000);
    });
  }

  const statusTabs: { value: "" | PaymentRequest["status"]; label: string }[] = [
    { value: "", label: "Todos" },
    { value: "pending", label: "Pendentes" },
    { value: "paid", label: "Pagos" },
    { value: "expired", label: "Expirados" },
    { value: "cancelled", label: "Cancelados" },
  ];

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-stone-500 mb-2">
            <span>Organizacao</span>
            <MaterialIcon icon="chevron_right" size="sm" />
            <span className="text-primary font-semibold">Pagamentos</span>
          </nav>
          <h1 className="text-3xl md:text-4xl font-extrabold font-headline text-on-surface">
            Cobrancas e pagamentos
          </h1>
          <p className="text-on-surface-variant mt-1 text-sm">
            Emita cobrancas Pix, acompanhe status e concilie pagamentos recebidos.
          </p>
        </div>
        <Button variant="primary" size="sm" icon="add" onClick={() => setShowIssue(true)}>
          Nova cobranca Pix
        </Button>
      </header>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon="schedule"
          label="Pendentes"
          value={summary.pending?.count ?? 0}
          delta={summary.pending ? fmtBRL(summary.pending.total_cents) : undefined}
          deltaType="neutral"
        />
        <StatCard
          icon="check_circle"
          label="Recebido (total)"
          value={summary.paid ? fmtBRL(summary.paid.paid_cents) : "R$ 0,00"}
        />
        <StatCard
          icon="block"
          label="Cancelados"
          value={summary.cancelled?.count ?? 0}
        />
        <StatCard
          icon="error_outline"
          label="Expirados"
          value={summary.expired?.count ?? 0}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {statusTabs.map((t) => (
          <button
            key={t.value}
            onClick={() => setStatusFilter(t.value)}
            className={cn(
              "px-4 py-2 rounded-full text-xs font-bold uppercase tracking-widest transition-all active:scale-95",
              statusFilter === t.value
                ? "bg-primary/20 text-primary border border-primary/30"
                : "bg-white/5 text-stone-400 border border-white/10 hover:border-stone-600",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-error/40 bg-error/10 px-3 py-2 text-sm text-error">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        </div>
      ) : payments.length === 0 ? (
        <Card variant="glass" padding="lg" className="text-center">
          <MaterialIcon icon="receipt_long" size="xl" className="text-stone-500 mb-3" />
          <p className="text-sm text-on-surface-variant">Nenhuma cobranca encontrada.</p>
        </Card>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {payments.map((p) => (
            <Card key={p.id} variant="glass" padding="md" className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge tone={statusTone[p.status]} pulse={p.status === "pending"}>
                      {statusLabel[p.status]}
                    </Badge>
                    <span className="text-[10px] font-mono text-stone-500">#{p.id}</span>
                  </div>
                  <div className="mt-2 text-lg font-bold text-on-surface font-headline">
                    {fmtBRL(p.amount_cents)}
                  </div>
                  <div className="text-xs text-stone-500 truncate">
                    {p.description || "Sem descricao"}
                  </div>
                </div>
                <div className="text-[10px] text-stone-500 text-right whitespace-nowrap">
                  {new Date(p.created_at).toLocaleString("pt-BR")}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <Button variant="ghost" size="sm" onClick={() => setSelected(p)}>
                  Ver detalhes
                </Button>
                {p.status === "pending" && (
                  <>
                    <Button variant="ghost" size="sm" icon="content_copy" onClick={() => p.pix_payload && copyPix(p.pix_payload)}>
                      Copiar Pix
                    </Button>
                    <Button variant="ghost" size="sm" icon="check" onClick={() => handleConfirm(p.id)}>
                      Confirmar
                    </Button>
                    <Button variant="ghost" size="sm" icon="close" onClick={() => handleCancel(p.id)}>
                      Cancelar
                    </Button>
                  </>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {copyFeedback && (
        <div className="fixed bottom-6 right-6 rounded-lg bg-primary/20 border border-primary/30 px-4 py-2 text-sm text-primary shadow-lg">
          {copyFeedback}
        </div>
      )}

      {/* Issue Modal */}
      {showIssue && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowIssue(false)}>
          <div className="glass-panel rounded-2xl p-6 w-full max-w-md space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold font-headline">Nova cobranca Pix</h2>
              <button onClick={() => setShowIssue(false)} className="p-2 text-stone-400 hover:text-on-surface hover:bg-white/5 rounded-lg">
                <MaterialIcon icon="close" />
              </button>
            </div>
            <Input label="Valor (R$)" placeholder="250,00" value={issueAmount} onChange={(e) => setIssueAmount(e.target.value)} />
            <Input label="Descricao" value={issueDescription} onChange={(e) => setIssueDescription(e.target.value)} />
            <Input label="Paciente (id, opcional)" value={issuePatient} onChange={(e) => setIssuePatient(e.target.value)} />
            <Input
              label="Chave Pix (opcional; usa padrao do tenant)"
              value={issuePixKey}
              onChange={(e) => setIssuePixKey(e.target.value)}
              hint="CPF, CNPJ, e-mail, telefone ou chave aleatoria."
            />
            {issueError && (
              <div className="rounded border border-error/40 bg-error/10 px-3 py-2 text-xs text-error">
                {issueError}
              </div>
            )}
            <div className="flex gap-2">
              <Button variant="ghost" size="md" className="flex-1" onClick={() => setShowIssue(false)} disabled={issuing}>
                Cancelar
              </Button>
              <Button variant="primary" size="md" icon="send" className="flex-1" onClick={handleIssue} disabled={issuing || !csrf}>
                {issuing ? "Emitindo..." : "Emitir Pix"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selected && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setSelected(null)}>
          <div className="glass-panel rounded-2xl p-6 w-full max-w-lg space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold font-headline">Cobranca #{selected.id}</h2>
                <div className="text-xs text-stone-500">{selected.external_id}</div>
              </div>
              <button onClick={() => setSelected(null)} className="p-2 text-stone-400 hover:text-on-surface hover:bg-white/5 rounded-lg">
                <MaterialIcon icon="close" />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-[10px] text-stone-500 uppercase tracking-widest">Valor</div>
                <div className="font-bold">{fmtBRL(selected.amount_cents)}</div>
              </div>
              <div>
                <div className="text-[10px] text-stone-500 uppercase tracking-widest">Status</div>
                <Badge tone={statusTone[selected.status]}>{statusLabel[selected.status]}</Badge>
              </div>
              <div>
                <div className="text-[10px] text-stone-500 uppercase tracking-widest">Criada em</div>
                <div>{new Date(selected.created_at).toLocaleString("pt-BR")}</div>
              </div>
              <div>
                <div className="text-[10px] text-stone-500 uppercase tracking-widest">Expira em</div>
                <div>{selected.expires_at ? new Date(selected.expires_at).toLocaleString("pt-BR") : "--"}</div>
              </div>
              {selected.paid_at && (
                <div className="col-span-2">
                  <div className="text-[10px] text-stone-500 uppercase tracking-widest">Pago em</div>
                  <div>{new Date(selected.paid_at).toLocaleString("pt-BR")}</div>
                </div>
              )}
            </div>
            {selected.pix_payload && (
              <div className="space-y-2">
                <div className="text-[10px] text-stone-500 uppercase tracking-widest">Codigo Pix (copia e cola)</div>
                <textarea
                  readOnly
                  value={selected.pix_payload}
                  className="w-full h-28 text-[11px] font-mono bg-surface-container-low border border-outline-variant/30 rounded-lg p-3"
                />
                <Button variant="ghost" size="sm" icon="content_copy" onClick={() => selected.pix_payload && copyPix(selected.pix_payload)}>
                  Copiar
                </Button>
              </div>
            )}
            {selected.status === "pending" && (
              <div className="flex gap-2 pt-2">
                <Button variant="ghost" size="sm" className="flex-1" onClick={() => handleCancel(selected.id)}>
                  Cancelar cobranca
                </Button>
                <Button variant="primary" size="sm" icon="check" className="flex-1" onClick={() => handleConfirm(selected.id)}>
                  Marcar como paga
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
