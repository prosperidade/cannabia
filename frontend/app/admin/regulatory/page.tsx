"use client";

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import {
  listLegislationFiles,
  uploadLegislation,
  queryLegislation,
  ApiError,
} from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import {
  Card,
  Badge,
  Button,
  MaterialIcon,
  SearchBar,
  StatCard,
} from "@/components/ui-tw";

/* ── types ── */

type LegislationFile = {
  name: string;
  display_name?: string;
  mime_type?: string;
  size_bytes?: number;
  state?: string;
  create_time?: string;
};

type QueryResult = {
  answer?: string;
  structured?: Record<string, unknown>;
  sources?: string[];
  model?: string;
};

/* ── page ── */

export default function RegulatoryPage() {
  const session = useApiSession();
  const csrf = session.data?.csrf_token ?? "";

  // Files
  const [files, setFiles] = useState<LegislationFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(true);
  const [filesError, setFilesError] = useState<string | null>(null);

  // Upload
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<string | null>(null);

  // Query
  const [question, setQuestion] = useState("");
  const [querying, setQuerying] = useState(false);
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [structured, setStructured] = useState(false);

  // Fetch files
  const fetchFiles = useCallback(async () => {
    setFilesLoading(true);
    setFilesError(null);
    try {
      const data = await listLegislationFiles();
      setFiles(Array.isArray(data) ? data as LegislationFile[] : []);
    } catch (err) {
      setFilesError(err instanceof ApiError ? err.message : "Falha ao carregar arquivos.");
    } finally {
      setFilesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!session.loading && session.data?.authenticated) {
      void fetchFiles();
    }
  }, [session.loading, session.data?.authenticated, fetchFiles]);

  // Upload
  async function handleUpload() {
    setUploading(true);
    setUploadResult(null);
    try {
      const res = await uploadLegislation(csrf);
      const data = res.data as Record<string, unknown>;
      const uploaded = (data.uploaded as number) ?? 0;
      const skipped = (data.skipped as number) ?? 0;
      setUploadResult(`${uploaded} arquivo(s) enviado(s), ${skipped} ja existente(s).`);
      void fetchFiles();
    } catch (err) {
      setUploadResult(err instanceof ApiError ? err.message : "Falha no upload.");
    } finally {
      setUploading(false);
    }
  }

  // Query
  async function handleQuery() {
    if (!question.trim()) return;
    setQuerying(true);
    setQueryResult(null);
    setQueryError(null);
    try {
      const res = await queryLegislation(csrf, question.trim(), { structured });
      const data = res.data as QueryResult;
      setQueryResult(data);
    } catch (err) {
      setQueryError(err instanceof ApiError ? err.message : "Falha na consulta regulatoria.");
    } finally {
      setQuerying(false);
    }
  }

  // Stats
  const totalFiles = files.length;
  const activeFiles = files.filter((f) => f.state === "ACTIVE").length;

  if (session.loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h2 className="text-2xl md:text-3xl font-headline font-extrabold text-on-surface tracking-tight">
            Regulatorio e Legislacao
          </h2>
          <p className="text-stone-400 text-sm mt-1">
            Gerencie e consulte a base regulatoria da plataforma.
          </p>
        </div>
        <Button
          icon="cloud_upload"
          loading={uploading}
          onClick={() => void handleUpload()}
        >
          Sincronizar Legislacao
        </Button>
      </div>

      {/* Upload feedback */}
      {uploadResult && (
        <Card padding="sm" className="border-l-4 border-primary/50">
          <p className="text-sm text-on-surface">{uploadResult}</p>
        </Card>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon="gavel" label="Total Documentos" value={totalFiles} />
        <StatCard icon="check_circle" label="Ativos" value={activeFiles} />
        <StatCard icon="cloud_done" label="Google Files" value={totalFiles} />
        <StatCard icon="search" label="Consultas" value="--" />
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Files list */}
        <div className="lg:col-span-5 space-y-4">
          <h3 className="text-lg font-bold font-headline text-on-surface">
            Documentos Carregados
          </h3>

          {filesLoading ? (
            <div className="flex justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          ) : filesError ? (
            <Card padding="md">
              <p className="text-sm text-error">{filesError}</p>
              <Button variant="ghost" size="sm" onClick={fetchFiles} className="mt-2">
                Tentar novamente
              </Button>
            </Card>
          ) : files.length === 0 ? (
            <Card padding="lg" className="text-center">
              <MaterialIcon icon="folder_open" size="xl" className="text-stone-600 mb-3" />
              <p className="text-sm text-stone-400">
                Nenhum documento carregado. Clique em "Sincronizar Legislacao" para enviar os arquivos de data/legislation/.
              </p>
            </Card>
          ) : (
            <div className="space-y-2 max-h-[50vh] overflow-y-auto">
              {files.map((file, i) => (
                <Card key={file.name || i} padding="sm" className="hover:bg-white/5 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                      <MaterialIcon
                        icon={file.mime_type?.includes("pdf") ? "picture_as_pdf" : "description"}
                        className="text-primary"
                        size="sm"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-on-surface truncate">
                        {file.display_name || file.name}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <Badge tone={file.state === "ACTIVE" ? "success" : "neutral"}>
                          {file.state || "unknown"}
                        </Badge>
                        {file.size_bytes && (
                          <span className="text-[10px] text-stone-500">
                            {(file.size_bytes / 1024).toFixed(0)} KB
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Right: Query */}
        <div className="lg:col-span-7 space-y-4">
          <h3 className="text-lg font-bold font-headline text-on-surface">
            Consulta Regulatoria
          </h3>

          <Card padding="md" className="space-y-4">
            <div>
              <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold block mb-1.5">
                Pergunta
              </label>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ex: Quais sao os requisitos da RDC 327 para prescricao de cannabis medicinal?"
                rows={3}
                className="w-full bg-surface-container-low border border-outline-variant/30 rounded-xl px-4 py-3 text-sm text-on-surface placeholder:text-stone-500 focus:border-primary focus:outline-none transition-colors resize-none"
              />
            </div>

            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={structured}
                  onChange={(e) => setStructured(e.target.checked)}
                  className="rounded border-outline-variant/30 bg-surface-container-low text-primary focus:ring-primary"
                />
                <span className="text-xs text-stone-400">Resposta estruturada (JSON)</span>
              </label>

              <Button
                icon="search"
                loading={querying}
                disabled={!question.trim()}
                onClick={() => void handleQuery()}
                className="ml-auto"
              >
                Consultar
              </Button>
            </div>
          </Card>

          {/* Query error */}
          {queryError && (
            <Card padding="sm" className="border-l-4 border-error/50">
              <p className="text-sm text-error">{queryError}</p>
            </Card>
          )}

          {/* Query result */}
          {queryResult && (
            <Card padding="md" className="space-y-4">
              <div className="flex items-center gap-2">
                <MaterialIcon icon="auto_awesome" className="text-primary" />
                <h4 className="font-bold text-on-surface">Resultado</h4>
                {queryResult.model && (
                  <Badge tone="neutral">{queryResult.model}</Badge>
                )}
              </div>

              {queryResult.answer && (
                <div className="bg-surface-container/50 p-4 rounded-xl border border-white/5">
                  <p className="text-sm text-stone-300 leading-relaxed whitespace-pre-wrap">
                    {queryResult.answer}
                  </p>
                </div>
              )}

              {queryResult.structured && (
                <details className="group">
                  <summary className="text-xs text-primary font-bold cursor-pointer flex items-center gap-1">
                    <MaterialIcon icon="data_object" size="sm" />
                    Ver resposta estruturada
                  </summary>
                  <pre className="mt-2 bg-surface-container-high p-4 rounded-xl text-xs text-stone-400 overflow-x-auto">
                    {JSON.stringify(queryResult.structured, null, 2)}
                  </pre>
                </details>
              )}

              {queryResult.sources && queryResult.sources.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-2">
                    Fontes consultadas
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {queryResult.sources.map((src, i) => (
                      <Badge key={i} tone="neutral">{src}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
