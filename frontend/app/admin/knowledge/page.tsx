"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import {
  getKnowledgeCatalog,
  getKnowledgeStats,
  getKnowledgeMonitors,
  createKnowledgeMonitor,
  toggleKnowledgeMonitor,
  runKnowledgeMonitors,
  triggerAutoSearch,
  searchPubMed,
  ApiError,
} from "@/lib/api";
import {
  Card,
  Badge,
  Button,
  StatCard,
  DataTable,
  MaterialIcon,
  SearchBar,
  type DataTableColumn,
} from "@/components/ui-tw";

/* ================================================================== */
/*  HELPERS                                                            */
/* ================================================================== */

function fmtDate(iso: string): string {
  if (!iso) return "--";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  });
}

function docTypeLabel(t: string): string {
  const map: Record<string, string> = {
    artigo: "Artigo",
    legislacao: "Legislacao",
    guideline: "Guideline",
    revisao: "Revisao",
    meta_analise: "Meta-analise",
    caso_clinico: "Caso Clinico",
  };
  return map[t] ?? t ?? "--";
}

function docTypeTone(t: string): "success" | "danger" | "warning" | "neutral" {
  if (t === "artigo" || t === "revisao" || t === "meta_analise") return "success";
  if (t === "legislacao") return "warning";
  if (t === "guideline") return "neutral";
  return "neutral";
}

function storageBadge(s: string): "success" | "danger" | "warning" | "neutral" {
  if (s === "chromadb") return "success";
  if (s === "google_files") return "warning";
  return "neutral";
}

function statusBadge(s: string): "success" | "danger" | "warning" | "neutral" {
  if (s === "indexed" || s === "active") return "success";
  if (s === "pending") return "warning";
  if (s === "error") return "danger";
  return "neutral";
}

/* ================================================================== */
/*  FILTER OPTIONS                                                     */
/* ================================================================== */

const TYPE_FILTERS = [
  { value: "", label: "Todos", icon: "apps" },
  { value: "artigo", label: "Artigos", icon: "article" },
  { value: "legislacao", label: "Legislacao", icon: "gavel" },
  { value: "guideline", label: "Guidelines", icon: "menu_book" },
];

/* ================================================================== */
/*  PAGE                                                               */
/* ================================================================== */

export default function KnowledgePage() {
  const session = useApiSession();
  const csrfToken = session.data?.csrf_token ?? "";

  /* ── State ── */
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<Record<string, unknown>[]>([]);
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  const [autoSearchLoading, setAutoSearchLoading] = useState(false);
  const [autoSearchResult, setAutoSearchResult] = useState<Record<string, unknown> | null>(null);

  const [pubmedQuery, setPubmedQuery] = useState("");
  const [pubmedLoading, setPubmedLoading] = useState(false);
  const [pubmedResults, setPubmedResults] = useState<Record<string, unknown> | null>(null);

  // Monitors
  const [monitors, setMonitors] = useState<Record<string, unknown>[]>([]);
  const [monitorsLoading, setMonitorsLoading] = useState(false);
  const [runningMonitors, setRunningMonitors] = useState(false);
  const [newMonitorName, setNewMonitorName] = useState("");
  const [newMonitorUrl, setNewMonitorUrl] = useState("");
  const [creatingMonitor, setCreatingMonitor] = useState(false);

  /* ── Fetch catalog ── */
  const fetchCatalog = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getKnowledgeCatalog({
        doc_type: typeFilter || undefined,
        search: search || undefined,
      });
      setCatalog(res.data ?? []);
      setMeta(res.meta ?? null);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Falha ao carregar catalogo.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [typeFilter, search]);

  /* ── Fetch stats ── */
  const fetchStats = useCallback(async () => {
    try {
      const res = await getKnowledgeStats();
      setStats(res.data ?? null);
    } catch {
      // Stats are non-critical
    }
  }, []);

  const fetchMonitors = useCallback(async () => {
    setMonitorsLoading(true);
    try {
      const data = await getKnowledgeMonitors();
      setMonitors(Array.isArray(data) ? data : []);
    } catch {
      // non-critical
    } finally {
      setMonitorsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchCatalog();
    void fetchStats();
    void fetchMonitors();
  }, [fetchCatalog, fetchStats, fetchMonitors]);

  async function handleRunMonitors() {
    setRunningMonitors(true);
    try {
      await runKnowledgeMonitors(csrfToken);
      void fetchMonitors();
      void fetchCatalog();
    } catch {
      // ignore
    } finally {
      setRunningMonitors(false);
    }
  }

  async function handleCreateMonitor() {
    if (!newMonitorName.trim() || !newMonitorUrl.trim()) return;
    setCreatingMonitor(true);
    try {
      await createKnowledgeMonitor(csrfToken, {
        name: newMonitorName.trim(),
        url: newMonitorUrl.trim(),
        source_type: "web",
      });
      setNewMonitorName("");
      setNewMonitorUrl("");
      void fetchMonitors();
    } catch {
      // ignore
    } finally {
      setCreatingMonitor(false);
    }
  }

  async function handleToggleMonitor(id: number, isActive: boolean) {
    try {
      await toggleKnowledgeMonitor(id, csrfToken, !isActive);
      void fetchMonitors();
    } catch {
      // ignore
    }
  }

  /* ── Auto search ── */
  async function handleAutoSearch() {
    setAutoSearchLoading(true);
    setAutoSearchResult(null);
    try {
      const res = await triggerAutoSearch(csrfToken);
      setAutoSearchResult(res.data ?? null);
      // Refresh catalog after auto-search
      void fetchCatalog();
      void fetchStats();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Falha na busca automatica.";
      setError(message);
    } finally {
      setAutoSearchLoading(false);
    }
  }

  /* ── PubMed search ── */
  async function handlePubmedSearch() {
    if (!pubmedQuery.trim()) return;
    setPubmedLoading(true);
    setPubmedResults(null);
    try {
      const res = await searchPubMed(csrfToken, pubmedQuery.trim());
      setPubmedResults(res.data ?? null);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Falha na busca PubMed.";
      setError(message);
    } finally {
      setPubmedLoading(false);
    }
  }

  /* ── Derived stats ── */
  const totalDocs = (stats as Record<string, unknown>)?.total_documents ?? 0;
  const chromadbChunks = (stats as Record<string, unknown>)?.chromadb_chunks ?? 0;
  const googleFiles = (stats as Record<string, unknown>)?.google_files_count ?? 0;
  const byType = ((stats as Record<string, unknown>)?.by_type ?? []) as Array<{
    doc_type: string;
    cnt: number;
  }>;

  /* ── Table columns ── */
  const columns: DataTableColumn[] = useMemo(
    () => [
      {
        key: "title",
        label: "Titulo",
        sortable: true,
        render: (val, row) => (
          <div className="max-w-xs">
            <p className="text-sm font-semibold text-on-surface truncate">{String(val || "--")}</p>
            {row.journal ? (
              <p className="text-[10px] text-stone-500 truncate">{String(row.journal)}</p>
            ) : null}
          </div>
        ),
      },
      {
        key: "doc_type",
        label: "Tipo",
        sortable: true,
        render: (val) => <Badge tone={docTypeTone(String(val))}>{docTypeLabel(String(val))}</Badge>,
      },
      {
        key: "source",
        label: "Fonte",
        sortable: true,
        render: (val) => (
          <span className="text-sm text-on-surface-variant">{String(val || "--")}</span>
        ),
      },
      {
        key: "storage_type",
        label: "Armazenamento",
        sortable: true,
        render: (val) => <Badge tone={storageBadge(String(val))}>{String(val || "--")}</Badge>,
      },
      {
        key: "status",
        label: "Status",
        sortable: true,
        render: (val) => <Badge tone={statusBadge(String(val))}>{String(val || "--")}</Badge>,
      },
      {
        key: "created_at",
        label: "Data",
        sortable: true,
        render: (val) => (
          <span className="text-sm text-stone-400 font-medium">{fmtDate(String(val))}</span>
        ),
      },
    ],
    [],
  );

  const tableData = useMemo(() => catalog as Record<string, unknown>[], [catalog]);

  /* ================================================================ */
  /*  RENDER                                                           */
  /* ================================================================ */

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold font-headline tracking-tighter text-on-surface mb-2">
            Base <span className="text-primary">Cientifica</span>
            <span className="text-on-surface-variant font-bold text-lg md:text-xl ml-2">
              e Documentos
            </span>
          </h1>
          <p className="text-on-surface-variant max-w-xl">
            Gerencie artigos, legislacao e guidelines indexados na base de conhecimento da IA.
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          <Button
            variant="secondary"
            icon="auto_awesome"
            size="sm"
            onClick={() => void handleAutoSearch()}
            loading={autoSearchLoading}
          >
            Busca Automatica
          </Button>
          <Button
            variant="ghost"
            icon="refresh"
            size="sm"
            onClick={() => {
              void fetchCatalog();
              void fetchStats();
            }}
            loading={loading}
          >
            Atualizar
          </Button>
        </div>
      </header>

      {/* ── Error state ── */}
      {error && (
        <Card variant="outline" padding="md" className="border-error/30">
          <div className="flex items-center gap-3">
            <MaterialIcon icon="error" className="text-error" />
            <div>
              <p className="text-sm font-bold text-error">Erro ao carregar dados</p>
              <p className="text-xs text-on-surface-variant">{error}</p>
            </div>
            <Button
              variant="danger"
              size="sm"
              className="ml-auto"
              onClick={() => {
                setError(null);
                void fetchCatalog();
              }}
            >
              Tentar novamente
            </Button>
          </div>
        </Card>
      )}

      {/* ── Auto-search result ── */}
      {autoSearchResult && (
        <Card variant="outline" padding="md" className="border-primary/20">
          <div className="flex items-center gap-3">
            <div className="bg-primary/20 p-2 rounded-full shrink-0">
              <MaterialIcon icon="check_circle" filled className="text-primary" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-bold text-on-surface">Busca automatica concluida</p>
              <p className="text-xs text-stone-400 mt-1">
                {String(autoSearchResult.total_found ?? 0)} encontrados,{" "}
                {String(autoSearchResult.total_registered ?? 0)} registrados,{" "}
                {String(autoSearchResult.terms_searched ?? 0)} termos pesquisados
                {autoSearchResult.duration_ms ? (
                  <> em {(Number(autoSearchResult.duration_ms) / 1000).toFixed(1)}s</>
                ) : null}
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setAutoSearchResult(null)}>
              Fechar
            </Button>
          </div>
        </Card>
      )}

      {/* ── Loading skeleton ── */}
      {loading && !catalog.length && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="glass-panel rounded-2xl p-5 h-28 animate-pulse" />
          ))}
        </div>
      )}

      {/* ── KPIs ── */}
      {stats && (
        <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            icon="library_books"
            label="Total de Documentos"
            value={Number(totalDocs).toLocaleString("pt-BR")}
          />
          <StatCard icon="article" label="Tipos Diferentes" value={String(byType.length)} />
          <StatCard
            icon="database"
            label="Vetores ChromaDB"
            value={Number(chromadbChunks).toLocaleString("pt-BR")}
          />
          <StatCard
            icon="cloud_upload"
            label="Arquivos Google"
            value={Number(googleFiles).toLocaleString("pt-BR")}
          />
        </section>
      )}

      {/* ── Type distribution ── */}
      {byType.length > 0 && (
        <Card variant="glass" padding="md">
          <h3 className="text-lg font-bold font-headline text-on-surface mb-4">
            Distribuicao por Tipo
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {byType.map((item) => (
              <div
                key={item.doc_type}
                className="flex items-center gap-3 p-4 bg-white/5 rounded-xl"
              >
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <MaterialIcon
                    icon={
                      item.doc_type === "artigo"
                        ? "article"
                        : item.doc_type === "legislacao"
                          ? "gavel"
                          : item.doc_type === "guideline"
                            ? "menu_book"
                            : "description"
                    }
                    filled
                    className="text-primary"
                  />
                </div>
                <div>
                  <p className="text-xl font-bold text-on-surface font-headline">{item.cnt}</p>
                  <p className="text-[10px] text-stone-500 uppercase tracking-widest font-bold">
                    {docTypeLabel(item.doc_type)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── PubMed Search ── */}
      <Card variant="glass" padding="md">
        <h3 className="text-lg font-bold font-headline text-on-surface mb-4">Buscar no PubMed</h3>
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={pubmedQuery}
            onChange={(e) => setPubmedQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void handlePubmedSearch();
            }}
            placeholder="Ex: cannabidiol epilepsy randomized trial"
            className="flex-1 glass-panel rounded-xl px-4 py-3 text-on-surface placeholder:text-stone-600 focus:border-primary-container focus:outline-none transition-colors"
          />
          <Button
            variant="primary"
            icon="search"
            size="sm"
            onClick={() => void handlePubmedSearch()}
            loading={pubmedLoading}
          >
            Buscar PubMed
          </Button>
        </div>
        {pubmedResults && (
          <div className="mt-4 p-4 bg-white/5 rounded-xl">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-bold text-on-surface">Resultados</p>
              <Button variant="ghost" size="sm" onClick={() => setPubmedResults(null)}>
                Fechar
              </Button>
            </div>
            <pre className="text-xs text-stone-400 overflow-auto max-h-48 whitespace-pre-wrap">
              {JSON.stringify(pubmedResults, null, 2)}
            </pre>
          </div>
        )}
      </Card>

      {/* ── Filters + Search ── */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Buscar por titulo, resumo ou numero..."
          className="flex-1"
        />
        <div className="flex gap-2 flex-wrap">
          {TYPE_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setTypeFilter(f.value)}
              className={cn(
                "glass-panel px-4 py-2 rounded-full flex items-center gap-2 text-sm font-medium transition-all",
                typeFilter === f.value
                  ? "bg-primary/20 text-primary border border-primary/30"
                  : "text-on-surface-variant hover:text-on-surface",
              )}
            >
              <MaterialIcon icon={f.icon} size="sm" />
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Catalog Table ── */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold font-headline text-on-surface">
            Catalogo de Documentos
          </h3>
          <span className="text-xs text-stone-500">
            {catalog.length} documento{catalog.length !== 1 ? "s" : ""}
            {meta && (meta as Record<string, unknown>).total !== undefined && (
              <> de {String((meta as Record<string, unknown>).total)}</>
            )}
          </span>
        </div>

        {/* Desktop table */}
        <div className="hidden md:block">
          <DataTable
            columns={columns}
            data={tableData}
            emptyMessage={
              loading
                ? "Carregando..."
                : "Nenhum documento encontrado para os filtros selecionados."
            }
          />
        </div>

        {/* Mobile cards */}
        <div className="md:hidden space-y-3">
          {catalog.length === 0 && !loading && (
            <Card variant="glass" padding="md">
              <p className="text-sm text-stone-500 text-center">Nenhum documento encontrado.</p>
            </Card>
          )}
          {catalog.map((doc) => (
            <Card
              key={String(doc.id)}
              variant="glass"
              padding="sm"
              className={cn(
                "border-l-2",
                String(doc.doc_type) === "artigo" && "border-l-emerald-400",
                String(doc.doc_type) === "legislacao" && "border-l-amber-400",
                String(doc.doc_type) === "guideline" && "border-l-stone-400",
              )}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-surface-container-highest flex items-center justify-center shrink-0">
                    <MaterialIcon icon="description" size="sm" className="text-primary" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-bold text-on-surface truncate">
                      {String(doc.title || "--")}
                    </p>
                    <p className="text-[10px] text-stone-500">
                      {fmtDate(String(doc.created_at ?? ""))} - {String(doc.source || "--")}
                    </p>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <Badge tone={docTypeTone(String(doc.doc_type))}>
                  {docTypeLabel(String(doc.doc_type))}
                </Badge>
                <Badge tone={storageBadge(String(doc.storage_type))}>
                  {String(doc.storage_type || "--")}
                </Badge>
                <Badge tone={statusBadge(String(doc.status))}>{String(doc.status || "--")}</Badge>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* ================================================================ */}
      {/*  MONITORS                                                        */}
      {/* ================================================================ */}
      <section className="space-y-6">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h3 className="text-xl font-bold font-headline text-on-surface">Monitores de Fontes</h3>
            <p className="text-xs text-stone-500 mt-1">
              URLs monitoradas automaticamente para novas publicacoes.
            </p>
          </div>
          <Button
            icon="play_arrow"
            variant="secondary"
            size="sm"
            loading={runningMonitors}
            onClick={() => void handleRunMonitors()}
          >
            Executar Monitores
          </Button>
        </div>

        {/* Create monitor form */}
        <Card padding="md">
          <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-end">
            <div className="flex-1">
              <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold block mb-1">
                Nome
              </label>
              <input
                type="text"
                value={newMonitorName}
                onChange={(e) => setNewMonitorName(e.target.value)}
                placeholder="Ex: PubMed Cannabis Pain"
                className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-on-surface placeholder:text-stone-500 focus:border-primary focus:outline-none transition-colors"
              />
            </div>
            <div className="flex-1">
              <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold block mb-1">
                URL
              </label>
              <input
                type="text"
                value={newMonitorUrl}
                onChange={(e) => setNewMonitorUrl(e.target.value)}
                placeholder="https://pubmed.ncbi.nlm.nih.gov/..."
                className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-on-surface placeholder:text-stone-500 focus:border-primary focus:outline-none transition-colors"
              />
            </div>
            <Button
              icon="add"
              size="sm"
              loading={creatingMonitor}
              disabled={!newMonitorName.trim() || !newMonitorUrl.trim()}
              onClick={() => void handleCreateMonitor()}
            >
              Criar
            </Button>
          </div>
        </Card>

        {/* Monitors list */}
        {monitorsLoading ? (
          <div className="flex justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : monitors.length === 0 ? (
          <Card padding="lg" className="text-center">
            <MaterialIcon icon="monitor_heart" size="xl" className="text-stone-600 mb-3" />
            <p className="text-sm text-stone-400">Nenhum monitor configurado.</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {monitors.map((mon) => {
              const isActive = mon.is_active === true;
              return (
                <Card
                  key={Number(mon.id)}
                  padding="md"
                  className={cn("hover:bg-white/5 transition-colors", !isActive && "opacity-60")}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-on-surface truncate">
                        {String(mon.name || "--")}
                      </p>
                      <p className="text-[10px] text-stone-500 truncate mt-0.5">
                        {String(mon.url || "--")}
                      </p>
                      <div className="flex items-center gap-2 mt-2">
                        <Badge tone={isActive ? "success" : "neutral"}>
                          {isActive ? "Ativo" : "Inativo"}
                        </Badge>
                        <span className="text-[10px] text-stone-500">
                          {String(mon.source_type || "web")}
                        </span>
                        {typeof mon.last_checked_at === "string" ? (
                          <span className="text-[10px] text-stone-500">
                            Ultima: {fmtDate(mon.last_checked_at)}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <button
                      onClick={() => void handleToggleMonitor(Number(mon.id), isActive)}
                      className={cn(
                        "p-2 rounded-lg border transition-colors text-xs",
                        isActive
                          ? "border-error/30 text-error hover:bg-error/10"
                          : "border-primary/30 text-primary hover:bg-primary/10",
                      )}
                    >
                      <MaterialIcon icon={isActive ? "pause" : "play_arrow"} size="sm" />
                    </button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
