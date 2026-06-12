"use client";

/**
 * Componente compartilhado da Base Cientifica.
 *
 * Pool global e colaborativo: Admin global, AdminClinica e Medico
 * leem, buscam e adicionam. Recepcao/Financeiro/Paciente nao acessam
 * (bloqueio no backend). Cada item lembra `created_by` (autoria) —
 * Admin global deleta qualquer um, demais so o que adicionaram.
 *
 * Usado em /org/conhecimento. /med/conhecimento e redirect.
 * /admin/knowledge mantem a UI completa com gestao de monitors.
 */

import { useEffect, useMemo, useState } from "react";

import { Badge, Button, Card, MaterialIcon } from "@/components/ui-tw";
import { deleteKnowledgeCatalogItem, getKnowledgeCatalog, triggerAutoSearch } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";

type KnowledgeCatalogItem = {
  id: number;
  title: string;
  doc_type: string;
  source: string;
  source_url?: string | null;
  doi?: string | null;
  category?: string | null;
  tags?: string[] | null;
  authors?: string[] | null;
  journal?: string | null;
  published_date?: string | null;
  norm_number?: string | null;
  abstract?: string | null;
  status?: string | null;
  created_at?: string | null;
  created_by?: number | null;
};

type DocTypeFilter = "all" | "article" | "legislation" | "guideline" | "protocol";

export function KnowledgeBaseView() {
  const { data: session } = useApiSession();
  const currentUserId = session?.user?.id ?? null;
  const isAdmin = (session?.user?.role ?? "").toLowerCase() === "admin";
  const csrfToken = session?.csrf_token ?? "";

  const [items, setItems] = useState<KnowledgeCatalogItem[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const [searchActive, setSearchActive] = useState("");
  const [docTypeFilter, setDocTypeFilter] = useState<DocTypeFilter>("all");
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [adding, setAdding] = useState(false);
  const [addTerm, setAddTerm] = useState("");
  const [addStatus, setAddStatus] = useState<string | null>(null);

  const reload = useMemo(
    () =>
      function reload() {
        setLoading(true);
        setErrorMsg(null);
        const params: Record<string, unknown> = {};
        if (searchActive.trim()) params.search = searchActive.trim();
        if (docTypeFilter !== "all") params.doc_type = docTypeFilter;
        params.page_size = 50;

        getKnowledgeCatalog(params)
          .then((resp) => {
            const data = resp.data as unknown as KnowledgeCatalogItem[] | undefined;
            setItems(Array.isArray(data) ? data : []);
          })
          .catch((err) => {
            const msg = err instanceof Error ? err.message : "Falha ao carregar a base cientifica.";
            setErrorMsg(msg);
            setItems([]);
          })
          .finally(() => setLoading(false));
      },
    [searchActive, docTypeFilter],
  );

  useEffect(() => {
    reload();
  }, [reload]);

  function canDelete(item: KnowledgeCatalogItem): boolean {
    if (isAdmin) return true;
    if (currentUserId == null || item.created_by == null) return false;
    return item.created_by === currentUserId;
  }

  async function handleDelete(item: KnowledgeCatalogItem) {
    const confirmed = window.confirm(`Remover "${item.title}" da base cientifica?`);
    if (!confirmed) return;
    try {
      await deleteKnowledgeCatalogItem(item.id, csrfToken);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha ao deletar.";
      window.alert(msg);
    }
  }

  async function handleAddViaPubmed() {
    const term = addTerm.trim();
    if (!term) {
      setAddStatus("Informe um termo de busca.");
      return;
    }
    setAdding(true);
    setAddStatus("Buscando no PubMed e ingerindo no catalogo...");
    try {
      const resp = await triggerAutoSearch(csrfToken, [term], 5);
      const data = resp.data as Record<string, unknown> | undefined;
      const total = Number(data?.total_registered ?? 0);
      setAddStatus(
        total > 0
          ? `${total} novo${total === 1 ? "" : "s"} artigo${
              total === 1 ? "" : "s"
            } adicionado${total === 1 ? "" : "s"}.`
          : "Busca concluida; nenhum artigo novo (possivel duplicidade).",
      );
      setAddTerm("");
      reload();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha na ingestao.";
      setAddStatus(`Erro: ${msg}`);
    } finally {
      setAdding(false);
    }
  }

  function applySearch() {
    setSearchActive(searchInput);
  }

  return (
    <section className="space-y-6">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-headline font-extrabold tracking-tight text-on-surface">
            Base Cientifica
          </h1>
          <p className="text-sm text-stone-500 mt-1">
            Pool colaborativo de artigos, legislacao e evidencias clinicas. Compartilhado por todos
            os profissionais credenciados.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-stone-500">
          <MaterialIcon icon="library_books" className="text-primary" />
          <span>
            {loading
              ? "carregando..."
              : `${items.length} item${items.length === 1 ? "" : "ns"} no recorte atual`}
          </span>
        </div>
      </header>

      {/* ── Filtros ─────────────────────────────────────── */}
      <Card padding="md" className="space-y-3">
        <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center">
          <div className="relative flex-1">
            <MaterialIcon
              icon="search"
              className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-500"
              size="sm"
            />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") applySearch();
              }}
              placeholder="Buscar por titulo, abstract ou norma..."
              className="w-full pl-10 pr-3 py-2 rounded-lg bg-surface-container-low border border-outline-variant/30 text-sm text-on-surface focus:outline-none focus:border-primary"
            />
          </div>
          <select
            value={docTypeFilter}
            onChange={(e) => setDocTypeFilter(e.target.value as DocTypeFilter)}
            className="px-3 py-2 rounded-lg bg-surface-container-low border border-outline-variant/30 text-sm text-on-surface"
          >
            <option value="all">Todos os tipos</option>
            <option value="article">Artigos</option>
            <option value="legislation">Legislacao</option>
            <option value="guideline">Diretrizes</option>
            <option value="protocol">Protocolos</option>
          </select>
          <Button onClick={applySearch} size="sm">
            Buscar
          </Button>
        </div>
      </Card>

      {/* ── Adicionar via PubMed ──────────────────────── */}
      <Card padding="md" className="space-y-3">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
            <MaterialIcon icon="add_circle" className="text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-bold text-on-surface">Adicionar via PubMed</h3>
            <p className="text-xs text-stone-500 mt-0.5">
              Informe um termo (ex.: &quot;cannabidiol epilepsy&quot;) e a IA ingere ate 5 artigos
              relevantes diretamente na base.
            </p>
          </div>
        </div>
        <div className="flex flex-col md:flex-row gap-2">
          <input
            type="text"
            value={addTerm}
            onChange={(e) => setAddTerm(e.target.value)}
            disabled={adding}
            placeholder="cannabidiol epilepsy"
            className="flex-1 px-3 py-2 rounded-lg bg-surface-container-low border border-outline-variant/30 text-sm text-on-surface focus:outline-none focus:border-primary disabled:opacity-50"
          />
          <Button onClick={handleAddViaPubmed} loading={adding} size="sm">
            Adicionar
          </Button>
        </div>
        {addStatus && <p className="text-xs text-stone-400 mt-1">{addStatus}</p>}
      </Card>

      {/* ── Lista ──────────────────────────────────── */}
      {errorMsg && (
        <Card padding="md" className="border-error/40 bg-error/5">
          <div className="flex items-center gap-3 text-error">
            <MaterialIcon icon="error" />
            <p className="text-sm">{errorMsg}</p>
          </div>
        </Card>
      )}

      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-20 rounded-xl bg-surface-container-low/60 animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card padding="lg">
          <div className="py-10 flex flex-col items-center justify-center text-center gap-2">
            <MaterialIcon icon="search_off" size="xl" className="text-stone-600" />
            <p className="text-sm font-bold text-on-surface">Nada encontrado neste recorte</p>
            <p className="text-xs text-stone-500 max-w-md">
              Tente outro termo, mude o filtro de tipo ou adicione um artigo via PubMed.
            </p>
          </div>
        </Card>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <CatalogRow
              key={item.id}
              item={item}
              expanded={expandedId === item.id}
              onToggle={() => setExpandedId((cur) => (cur === item.id ? null : item.id))}
              canDelete={canDelete(item)}
              onDelete={() => handleDelete(item)}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

/* ── Componentes internos ─────────────────────────────────────── */

function CatalogRow({
  item,
  expanded,
  onToggle,
  canDelete,
  onDelete,
}: {
  item: KnowledgeCatalogItem;
  expanded: boolean;
  onToggle: () => void;
  canDelete: boolean;
  onDelete: () => void;
}) {
  const dateLabel = formatDate(item.published_date || item.created_at || null);
  const typeTone = mapDocTypeTone(item.doc_type);
  return (
    <li className="rounded-xl bg-surface-container-low border border-outline-variant/20 hover:border-primary/30 transition-colors">
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left p-4 flex items-start gap-3"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <Badge tone={typeTone.tone}>{typeTone.label}</Badge>
            <span className="text-[11px] text-stone-500">{item.source || "—"}</span>
            {dateLabel && <span className="text-[11px] text-stone-500">{dateLabel}</span>}
          </div>
          <p className="text-sm font-bold text-on-surface leading-snug">{item.title}</p>
          {item.norm_number && <p className="text-xs text-stone-400 mt-0.5">{item.norm_number}</p>}
          {item.journal && (
            <p className="text-[11px] text-stone-500 mt-0.5 italic">{item.journal}</p>
          )}
        </div>
        <MaterialIcon
          icon={expanded ? "expand_less" : "expand_more"}
          size="sm"
          className="text-stone-500 mt-1"
        />
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-0 border-t border-outline-variant/10 mt-2">
          {item.abstract ? (
            <p className="text-xs text-stone-300 leading-relaxed mt-3 whitespace-pre-line">
              {item.abstract}
            </p>
          ) : (
            <p className="text-xs text-stone-500 italic mt-3">Sem resumo disponivel.</p>
          )}

          <div className="flex flex-wrap items-center gap-2 mt-4">
            {item.source_url && (
              <a
                href={item.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-bold text-primary hover:underline"
              >
                <MaterialIcon icon="open_in_new" size="sm" />
                Abrir fonte original
              </a>
            )}
            {item.doi && (
              <a
                href={`https://doi.org/${item.doi}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-bold text-primary hover:underline"
              >
                <MaterialIcon icon="link" size="sm" />
                DOI: {item.doi}
              </a>
            )}
            {canDelete && (
              <button
                type="button"
                onClick={onDelete}
                className="ml-auto inline-flex items-center gap-1 text-xs font-bold text-error hover:underline"
              >
                <MaterialIcon icon="delete" size="sm" />
                Remover
              </button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

/* ── Helpers ─────────────────────────────────────────────────── */

function formatDate(value: string | null): string | null {
  if (!value) return null;
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

function mapDocTypeTone(docType: string): {
  label: string;
  tone: "primary" | "info" | "warning" | "neutral";
} {
  const t = (docType || "").toLowerCase();
  if (t === "legislation") return { label: "Legislacao", tone: "warning" };
  if (t === "article") return { label: "Artigo", tone: "info" };
  if (t === "guideline") return { label: "Diretriz", tone: "primary" };
  if (t === "protocol") return { label: "Protocolo", tone: "primary" };
  return { label: docType || "—", tone: "neutral" };
}
