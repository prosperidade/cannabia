"use client";

/**
 * Governance Hub — cadastro institucional + Dossie de Elegibilidade.
 * F1.7 do docs/BACKLOG_SCC.md.
 */

import { useCallback, useEffect, useState } from "react";
import { useApiSession } from "@/lib/use-api-session";
import { ApiError } from "@/lib/api";
import {
  getAssociation,
  getDossier,
  getEligibility,
  getLatestCapacityAssessment,
  listDocuments,
  listTechnicalResponsibles,
  refreshEligibility,
  createTechnicalResponsible,
  createDocument,
  upsertAssociation,
  type AssociationRecord,
  type CapacityAssessment,
  type DossierPayload,
  type EligibilityFinding,
  type EligibilityReport,
  type InstitutionalDocument,
  type TechnicalResponsible,
} from "@/lib/governance";
import { Badge, Button, Card, Input, MaterialIcon } from "@/components/ui-tw";

/* ------------------------------------------------------------------ */
/*  Helpers visuais                                                    */
/* ------------------------------------------------------------------ */

function findingTone(status: EligibilityFinding["status"]) {
  if (status === "pass") return "success" as const;
  if (status === "fail") return "danger" as const;
  return "warning" as const;
}

function findingIcon(status: EligibilityFinding["status"]) {
  if (status === "pass") return "check_circle";
  if (status === "fail") return "cancel";
  return "warning";
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("pt-BR");
  } catch {
    return iso;
  }
}

/* ------------------------------------------------------------------ */
/*  Secao: Status de elegibilidade                                      */
/* ------------------------------------------------------------------ */

function EligibilityPanel({
  report,
  loading,
  onRefresh,
}: {
  report: EligibilityReport | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const failCount = report?.findings.filter((f) => f.status === "fail").length ?? 0;
  const warnCount = report?.findings.filter((f) => f.status === "warn").length ?? 0;

  return (
    <Card>
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h2 className="text-lg font-headline font-extrabold text-on-surface mb-1">
            Elegibilidade ao Sandbox
          </h2>
          <p className="text-xs text-stone-500">
            RDC 1.014/2026 — 4 criterios obrigatorios + estatuto recomendado
          </p>
        </div>
        <div className="flex items-center gap-2">
          {report && (
            <Badge tone={report.is_eligible ? "success" : "danger"}>
              {report.is_eligible
                ? "Apto a submissao"
                : `${failCount} pendencia${failCount !== 1 ? "s" : ""}`}
            </Badge>
          )}
          {report && warnCount > 0 && (
            <Badge tone="warning">
              {warnCount} aviso{warnCount !== 1 ? "s" : ""}
            </Badge>
          )}
          <Button
            variant="secondary"
            size="sm"
            icon="refresh"
            onClick={onRefresh}
            disabled={loading}
          >
            Revalidar
          </Button>
        </div>
      </div>

      {report ? (
        <div className="space-y-3">
          {report.findings.map((f) => (
            <div
              key={f.code}
              className="flex items-start gap-3 p-3 rounded-lg bg-surface-container-low border border-outline-variant/20"
            >
              <div
                className={`mt-0.5 text-${findingTone(f.status) === "success" ? "emerald-400" : findingTone(f.status) === "danger" ? "error" : "amber-400"}`}
              >
                <MaterialIcon icon={findingIcon(f.status)} size="sm" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-sm font-semibold text-on-surface">{f.code}</span>
                  <Badge tone={findingTone(f.status)}>{f.status}</Badge>
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">{f.message}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-stone-500">Carregando status...</p>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Secao: Cadastro institucional                                      */
/* ------------------------------------------------------------------ */

function AssociationSection({
  association,
  csrfToken,
  onSaved,
}: {
  association: AssociationRecord | null;
  csrfToken: string;
  onSaved: () => void;
}) {
  const [membersCount, setMembersCount] = useState(association?.members_count ?? 0);
  const [isJudicial, setIsJudicial] = useState(association?.is_judicial_operation ?? false);
  const [judicialAuth, setJudicialAuth] = useState(association?.judicial_authorization ?? "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    setMembersCount(association?.members_count ?? 0);
    setIsJudicial(association?.is_judicial_operation ?? false);
    setJudicialAuth(association?.judicial_authorization ?? "");
  }, [association]);

  async function save() {
    setSaving(true);
    setMsg(null);
    try {
      await upsertAssociation(csrfToken, {
        members_count: membersCount,
        is_judicial_operation: isJudicial,
        judicial_authorization: isJudicial ? judicialAuth || null : null,
        directive_board: association?.directive_board ?? [],
      });
      setMsg("Salvo com sucesso.");
      onSaved();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Falha ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <h2 className="text-lg font-headline font-extrabold text-on-surface mb-1">
        Cadastro institucional
      </h2>
      <p className="text-xs text-stone-500 mb-6">
        Dados minimos para completar o perfil da associacao.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <Input
          label="Numero de associados"
          type="number"
          min="0"
          value={membersCount}
          onChange={(e) => setMembersCount(Number(e.target.value) || 0)}
        />
        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
            Operacao sob autorizacao judicial
          </label>
          <div className="flex items-center gap-2 h-12 px-4 bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT">
            <input
              type="checkbox"
              checked={isJudicial}
              onChange={(e) => setIsJudicial(e.target.checked)}
              className="w-4 h-4 accent-primary"
            />
            <span className="text-sm text-on-surface">{isJudicial ? "Sim" : "Nao"}</span>
          </div>
        </div>
      </div>

      {isJudicial && (
        <Input
          label="Numero/referencia da autorizacao"
          value={judicialAuth}
          onChange={(e) => setJudicialAuth(e.target.value)}
          placeholder="Processo 000000-00.0000.0.00.0000"
        />
      )}

      <div className="flex items-center gap-3 mt-6">
        <Button variant="primary" size="sm" icon="save" onClick={save} disabled={saving}>
          {saving ? "Salvando..." : "Salvar"}
        </Button>
        {msg && <span className="text-xs text-stone-400">{msg}</span>}
      </div>

      {association?.sandbox_application_status && (
        <div className="mt-4 flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-widest text-stone-500">
            Status sandbox:
          </span>
          <Badge tone="info">{association.sandbox_application_status}</Badge>
          {association.eligibility_validated_at && (
            <span className="text-xs text-stone-400">
              validado em {formatDate(association.eligibility_validated_at)}
            </span>
          )}
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Secao: Responsaveis Tecnicos                                       */
/* ------------------------------------------------------------------ */

function RtSection({
  rts,
  csrfToken,
  onCreated,
}: {
  rts: TechnicalResponsible[];
  csrfToken: string;
  onCreated: () => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [fullName, setFullName] = useState("");
  const [council, setCouncil] = useState("CRM");
  const [number, setNumber] = useState("");
  const [state, setState] = useState("");
  const [habValidity, setHabValidity] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function resetForm() {
    setFullName("");
    setCouncil("CRM");
    setNumber("");
    setState("");
    setHabValidity("");
    setError(null);
    setShowForm(false);
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      await createTechnicalResponsible(csrfToken, {
        full_name: fullName,
        professional_council: council,
        council_number: number,
        council_state: state,
        habilitation_valid_until: habValidity || null,
      });
      resetForm();
      onCreated();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Falha ao cadastrar RT.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h2 className="text-lg font-headline font-extrabold text-on-surface mb-1">
            Responsaveis Tecnicos
          </h2>
          <p className="text-xs text-stone-500">
            {rts.length > 0
              ? `${rts.length} ativo${rts.length !== 1 ? "s" : ""}`
              : "Nenhum RT cadastrado"}
          </p>
        </div>
        {!showForm && (
          <Button variant="primary" size="sm" icon="add" onClick={() => setShowForm(true)}>
            Cadastrar RT
          </Button>
        )}
      </div>

      {rts.length > 0 && (
        <div className="space-y-2 mb-4">
          {rts.map((rt) => (
            <div
              key={rt.id}
              className="flex items-center justify-between gap-4 p-3 rounded-lg bg-surface-container-low border border-outline-variant/20"
            >
              <div className="flex-1">
                <div className="text-sm font-semibold text-on-surface">{rt.full_name}</div>
                <div className="text-xs text-stone-400">
                  {rt.professional_council} {rt.council_number}/{rt.council_state}
                  {" · "}
                  Habilitacao valida ate{" "}
                  <span className={!rt.habilitation_valid_until ? "text-amber-400" : ""}>
                    {rt.habilitation_valid_until
                      ? formatDate(rt.habilitation_valid_until)
                      : "[nao informado]"}
                  </span>
                </div>
              </div>
              <Badge tone="success">Ativo</Badge>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="mt-4 p-4 rounded-lg bg-surface-container-low border border-outline-variant/20">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            <Input
              label="Nome completo"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
            <Input
              label="Conselho"
              value={council}
              onChange={(e) => setCouncil(e.target.value.toUpperCase())}
              placeholder="CRM, CRF..."
            />
            <Input label="Numero" value={number} onChange={(e) => setNumber(e.target.value)} />
            <Input
              label="UF"
              value={state}
              onChange={(e) => setState(e.target.value.toUpperCase().slice(0, 2))}
              placeholder="SP"
            />
            <Input
              label="Habilitacao valida ate"
              type="date"
              value={habValidity}
              onChange={(e) => setHabValidity(e.target.value)}
            />
          </div>
          {error && <div className="text-xs text-error mb-3">{error}</div>}
          <div className="flex items-center gap-2">
            <Button variant="primary" size="sm" onClick={submit} disabled={submitting}>
              {submitting ? "Salvando..." : "Cadastrar"}
            </Button>
            <Button variant="secondary" size="sm" onClick={resetForm}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Secao: Documentos institucionais                                    */
/* ------------------------------------------------------------------ */

function DocumentsSection({
  documents,
  csrfToken,
  onCreated,
}: {
  documents: InstitutionalDocument[];
  csrfToken: string;
  onCreated: () => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [docType, setDocType] = useState("statute");
  const [title, setTitle] = useState("");
  const [version, setVersion] = useState("1.0");
  const [fileUri, setFileUri] = useState("");
  const [fileHash, setFileHash] = useState("");
  const [validFrom, setValidFrom] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function resetForm() {
    setDocType("statute");
    setTitle("");
    setVersion("1.0");
    setFileUri("");
    setFileHash("");
    setValidFrom("");
    setError(null);
    setShowForm(false);
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      await createDocument(csrfToken, {
        document_type: docType,
        title,
        version,
        file_uri: fileUri,
        file_hash: fileHash,
        valid_from: validFrom,
      });
      resetForm();
      onCreated();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Falha ao cadastrar documento.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h2 className="text-lg font-headline font-extrabold text-on-surface mb-1">
            Documentos institucionais
          </h2>
          <p className="text-xs text-stone-500">
            {documents.length > 0
              ? `${documents.length} ativo${documents.length !== 1 ? "s" : ""}`
              : "Nenhum documento vigente"}
          </p>
        </div>
        {!showForm && (
          <Button variant="primary" size="sm" icon="upload" onClick={() => setShowForm(true)}>
            Anexar documento
          </Button>
        )}
      </div>

      {documents.length > 0 && (
        <div className="space-y-2 mb-4">
          {documents.map((d) => (
            <div
              key={d.id}
              className="flex items-center gap-3 p-3 rounded-lg bg-surface-container-low border border-outline-variant/20"
            >
              <MaterialIcon icon="description" size="sm" className="text-primary" />
              <div className="flex-1">
                <div className="text-sm font-semibold text-on-surface">
                  {d.title} <span className="text-stone-500 font-normal">v{d.version}</span>
                </div>
                <div className="text-xs text-stone-400">
                  {d.document_type} · vigencia desde {formatDate(d.valid_from)}
                  {d.valid_until && ` ate ${formatDate(d.valid_until)}`}
                </div>
              </div>
              <Badge tone="neutral">{d.file_hash.slice(0, 8)}…</Badge>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="mt-4 p-4 rounded-lg bg-surface-container-low border border-outline-variant/20">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            <Input
              label="Tipo"
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              placeholder="statute, minutes, license..."
              hint="Estatuto: 'statute'"
            />
            <Input label="Versao" value={version} onChange={(e) => setVersion(e.target.value)} />
            <Input
              label="Titulo"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="md:col-span-2"
            />
            <Input
              label="URI do arquivo (S3, storage)"
              value={fileUri}
              onChange={(e) => setFileUri(e.target.value)}
              placeholder="s3://bucket/path/estatuto.pdf"
              className="md:col-span-2"
            />
            <Input
              label="Hash SHA-256 (64 chars)"
              value={fileHash}
              onChange={(e) => setFileHash(e.target.value)}
              hint="Calcule localmente com sha256sum antes do upload"
              className="md:col-span-2"
            />
            <Input
              label="Vigente desde"
              type="date"
              value={validFrom}
              onChange={(e) => setValidFrom(e.target.value)}
            />
          </div>
          {error && <div className="text-xs text-error mb-3">{error}</div>}
          <div className="flex items-center gap-2">
            <Button variant="primary" size="sm" onClick={submit} disabled={submitting}>
              {submitting ? "Salvando..." : "Anexar"}
            </Button>
            <Button variant="secondary" size="sm" onClick={resetForm}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Secao: Capacidade Tecnico-Operacional                              */
/* ------------------------------------------------------------------ */

function CapacityCard({ capacity }: { capacity: CapacityAssessment | null }) {
  return (
    <Card>
      <h2 className="text-lg font-headline font-extrabold text-on-surface mb-1">
        Capacidade Tecnico-Operacional
      </h2>
      <p className="text-xs text-stone-500 mb-6">
        Avaliacao mais recente de infraestrutura × equipe × processos × escala.
      </p>

      {capacity ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-4 p-3 rounded-lg bg-surface-container-low border border-outline-variant/20">
            <div>
              <div className="text-sm font-semibold text-on-surface">
                Avaliacao de {formatDate(capacity.assessment_date)}
              </div>
              <div className="text-xs text-stone-400">
                ID {capacity.id} · registrada em {formatDate(capacity.created_at)}
              </div>
            </div>
            {capacity.overall_readiness !== null && (
              <div className="text-right">
                <div className="text-2xl font-headline font-extrabold text-primary">
                  {Number(capacity.overall_readiness).toFixed(1)}
                </div>
                <div className="text-[10px] uppercase tracking-widest text-stone-500">de 100</div>
              </div>
            )}
          </div>
          <p className="text-xs text-stone-500">
            Nova avaliacao: use{" "}
            <code className="text-primary">POST /api/v1/governance/capacity</code> com os 4 scores
            JSONB + readiness.
          </p>
        </div>
      ) : (
        <div className="p-4 rounded-lg bg-amber-500/5 border border-amber-500/20">
          <div className="flex items-start gap-3">
            <MaterialIcon icon="warning" size="sm" className="text-amber-400 mt-0.5" />
            <div className="text-xs text-stone-300 leading-relaxed">
              Nenhuma avaliacao registrada. Capacidade Tecnico-Operacional e{" "}
              <strong>requisito obrigatorio</strong> para elegibilidade (RDC 1.014/2026). Registre a
              primeira avaliacao via API.
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Secao: Dossie                                                       */
/* ------------------------------------------------------------------ */

function DossierSection({
  dossier,
  loading,
  onLoad,
}: {
  dossier: DossierPayload | null;
  loading: boolean;
  onLoad: () => void;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h2 className="text-lg font-headline font-extrabold text-on-surface mb-1">
            Dossie de Elegibilidade
          </h2>
          <p className="text-xs text-stone-500">
            Documento submissivel a ANVISA no momento do Edital.
          </p>
        </div>
        <Button variant="primary" size="sm" icon="article" onClick={onLoad} disabled={loading}>
          {dossier ? "Regenerar" : "Gerar previa"}
        </Button>
      </div>

      {dossier && (
        <>
          <div className="flex items-center gap-3 mb-4 text-xs text-stone-400">
            <Badge tone={dossier.is_eligible ? "success" : "danger"}>
              {dossier.is_eligible ? "Apto" : "Nao apto"}
            </Badge>
            <span>template {dossier.template_version}</span>
            <span>·</span>
            <span>{dossier.markdown.length} caracteres</span>
            <span>·</span>
            <span>gerado em {new Date(dossier.generated_at).toLocaleString("pt-BR")}</span>
          </div>

          <div className="max-h-[600px] overflow-y-auto p-4 rounded-lg bg-surface-container-low border border-outline-variant/20">
            <pre className="whitespace-pre-wrap text-xs text-stone-300 leading-relaxed font-mono">
              {dossier.markdown}
            </pre>
          </div>

          <div className="mt-3 text-[11px] text-stone-500">
            Esta e a previa em Markdown. Conversao para PDF/A e assinatura eletronica fazem parte do
            fluxo de Regulatory Reporting (doc 27 §8).
          </div>
        </>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Pagina principal                                                   */
/* ------------------------------------------------------------------ */

export default function GovernanceHubPage() {
  const session = useApiSession();
  const csrfToken = session.data?.csrf_token ?? "";

  const [association, setAssociation] = useState<AssociationRecord | null>(null);
  const [rts, setRts] = useState<TechnicalResponsible[]>([]);
  const [documents, setDocuments] = useState<InstitutionalDocument[]>([]);
  const [capacity, setCapacity] = useState<CapacityAssessment | null>(null);
  const [report, setReport] = useState<EligibilityReport | null>(null);
  const [dossier, setDossier] = useState<DossierPayload | null>(null);

  const [loadingAll, setLoadingAll] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingDossier, setLoadingDossier] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const reloadAll = useCallback(async () => {
    setLoadingAll(true);
    setGlobalError(null);
    try {
      const [a, r, d, c, e] = await Promise.all([
        getAssociation(),
        listTechnicalResponsibles(true),
        listDocuments({ activeOnly: true }),
        getLatestCapacityAssessment(),
        getEligibility(),
      ]);
      setAssociation(a);
      setRts(r);
      setDocuments(d);
      setCapacity(c);
      setReport(e);
    } catch (err) {
      setGlobalError(
        err instanceof ApiError ? err.message : "Falha ao carregar dados de governance.",
      );
    } finally {
      setLoadingAll(false);
    }
  }, []);

  useEffect(() => {
    if (!session.loading && session.data?.authenticated) {
      void reloadAll();
    }
  }, [session.loading, session.data?.authenticated, reloadAll]);

  async function handleRefresh() {
    if (!csrfToken) return;
    setRefreshing(true);
    try {
      const fresh = await refreshEligibility(csrfToken);
      setReport(fresh);
      // refresh pode ter alterado o status da associacao
      const updated = await getAssociation();
      setAssociation(updated);
    } catch (err) {
      setGlobalError(err instanceof ApiError ? err.message : "Falha ao revalidar.");
    } finally {
      setRefreshing(false);
    }
  }

  async function handleLoadDossier() {
    setLoadingDossier(true);
    try {
      const d = await getDossier();
      setDossier(d);
    } catch (err) {
      setGlobalError(err instanceof ApiError ? err.message : "Falha ao gerar dossie.");
    } finally {
      setLoadingDossier(false);
    }
  }

  if (loadingAll && !report) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-sm text-stone-500">Carregando Governance Hub...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-10">
      <header>
        <div className="flex items-center gap-2 mb-2">
          <MaterialIcon icon="account_balance" size="sm" className="text-primary" />
          <span className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">
            Sandbox Regulatorio
          </span>
        </div>
        <h1 className="text-3xl font-headline font-extrabold text-on-surface">Governance Hub</h1>
        <p className="text-sm text-stone-400 mt-1 max-w-2xl">
          Dossie institucional e validacao automatica de elegibilidade ao Sandbox regulamentado pela
          RDC 1.014/2026.
        </p>
      </header>

      {globalError && (
        <div className="p-3 rounded-lg bg-error/10 border border-error/30 text-sm text-error">
          {globalError}
        </div>
      )}

      <EligibilityPanel report={report} loading={refreshing} onRefresh={handleRefresh} />

      <AssociationSection association={association} csrfToken={csrfToken} onSaved={reloadAll} />

      <RtSection rts={rts} csrfToken={csrfToken} onCreated={reloadAll} />

      <DocumentsSection documents={documents} csrfToken={csrfToken} onCreated={reloadAll} />

      <CapacityCard capacity={capacity} />

      <DossierSection dossier={dossier} loading={loadingDossier} onLoad={handleLoadDossier} />
    </div>
  );
}
