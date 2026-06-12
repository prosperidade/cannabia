"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import {
  getTenant,
  getTenantBranding,
  updateTenantBranding,
  getTenantIntegrations,
  updateTenantIntegrations,
  getTenantPlan,
  updateTenantPlan,
  updateTenant,
  ApiError,
} from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import { Card, Badge, Button, Input, MaterialIcon, StatCard } from "@/components/ui-tw";
import type {
  TenantDetail,
  TenantBranding,
  TenantIntegrations,
  TenantPlanData,
} from "@/lib/types-admin";

type Tab = "branding" | "integrations" | "plan" | "info";

export default function TenantDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const tenantId = Number(params?.id);

  const session = useApiSession();
  const csrf = session.data?.csrf_token ?? "";

  const [tab, setTab] = useState<Tab>("info");
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [branding, setBranding] = useState<TenantBranding | null>(null);
  const [integrations, setIntegrations] = useState<TenantIntegrations | null>(null);
  const [plan, setPlan] = useState<TenantPlanData | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    if (!Number.isFinite(tenantId)) return;
    try {
      setLoading(true);
      setError(null);
      const [t, b, i, p] = await Promise.all([
        getTenant(tenantId),
        getTenantBranding(tenantId).catch(() => null),
        getTenantIntegrations(tenantId).catch(() => null),
        getTenantPlan(tenantId).catch(() => null),
      ]);
      setTenant(t as TenantDetail);
      setBranding(b as TenantBranding | null);
      setIntegrations(i as TenantIntegrations | null);
      setPlan(p as TenantPlanData | null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao carregar organizacao.");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  async function handleSaveBranding(data: Partial<TenantBranding>) {
    if (!csrf) return;
    try {
      setSaving(true);
      setSaveMessage(null);
      const updated = await updateTenantBranding(csrf, tenantId, data);
      setBranding(updated);
      setSaveMessage("Branding salvo com sucesso.");
    } catch (err) {
      setSaveMessage(err instanceof Error ? err.message : "Falha ao salvar branding.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveIntegrations(data: Partial<TenantIntegrations>) {
    if (!csrf) return;
    try {
      setSaving(true);
      setSaveMessage(null);
      // Remove campos sem alteracao (evita sobrescrever com null)
      const cleanPayload: Record<string, unknown> = {};
      Object.entries(data).forEach(([key, val]) => {
        if (val === undefined || val === "" || val === "***") return;
        cleanPayload[key] = val;
      });
      const updated = await updateTenantIntegrations(csrf, tenantId, cleanPayload);
      setIntegrations(updated);
      setSaveMessage("Integracoes salvas com sucesso.");
    } catch (err) {
      setSaveMessage(err instanceof Error ? err.message : "Falha ao salvar integracoes.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSavePlan(data: {
    billing_plan?: string;
    ai_limit_month?: number;
    user_limit?: number;
  }) {
    if (!csrf) return;
    try {
      setSaving(true);
      setSaveMessage(null);
      const updated = await updateTenantPlan(csrf, tenantId, data);
      setPlan(updated);
      setSaveMessage("Plano atualizado.");
    } catch (err) {
      setSaveMessage(err instanceof Error ? err.message : "Falha ao salvar plano.");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleStatus() {
    if (!csrf || !tenant) return;
    const nextStatus = tenant.status === "active" ? "suspended" : "active";
    try {
      setSaving(true);
      setSaveMessage(null);
      await updateTenant(csrf, tenantId, { status: nextStatus });
      await fetchAll();
      setSaveMessage(`Status atualizado para ${nextStatus}.`);
    } catch (err) {
      setSaveMessage(err instanceof Error ? err.message : "Falha ao atualizar status.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando organizacao...</p>
        </div>
      </div>
    );
  }

  if (error || !tenant) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center space-y-4">
          <MaterialIcon icon="error_outline" size="xl" className="text-error/60" />
          <p className="text-on-surface-variant text-sm">
            {error ?? "Organizacao nao encontrada."}
          </p>
          <Button variant="ghost" size="sm" onClick={() => router.push("/admin/tenants")}>
            Voltar
          </Button>
        </div>
      </div>
    );
  }

  const tabs: { value: Tab; label: string; icon: string }[] = [
    { value: "info", label: "Visao geral", icon: "dashboard" },
    { value: "branding", label: "Branding", icon: "palette" },
    { value: "integrations", label: "Integracoes", icon: "key" },
    { value: "plan", label: "Plano e quota", icon: "credit_card" },
  ];

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto space-y-6">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-stone-500 mb-2">
            <button onClick={() => router.push("/admin/tenants")} className="hover:text-primary">
              Organizacoes
            </button>
            <MaterialIcon icon="chevron_right" size="sm" />
            <span className="text-primary font-semibold">{tenant.name}</span>
          </nav>
          <h1 className="text-2xl md:text-3xl font-extrabold font-headline text-on-surface">
            {tenant.name}
          </h1>
          <p className="text-xs text-stone-500 mt-1">
            Slug: <span className="font-mono">{tenant.slug}</span> · Tipo:{" "}
            <Badge tone="primary" className="!text-[10px] !px-1.5">
              {tenant.tenant_type ?? "clinic"}
            </Badge>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            tone={tenant.status === "active" ? "success" : "danger"}
            pulse={tenant.status !== "active"}
          >
            {tenant.status}
          </Badge>
          <Button variant="ghost" size="sm" onClick={handleToggleStatus} disabled={saving}>
            {tenant.status === "active" ? "Suspender" : "Reativar"}
          </Button>
        </div>
      </header>

      {saveMessage && (
        <div className="rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary">
          {saveMessage}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={cn(
              "px-4 py-2 rounded-full text-xs font-bold uppercase tracking-widest transition-all active:scale-95 flex items-center gap-2",
              tab === t.value
                ? "bg-primary/20 text-primary border border-primary/30"
                : "bg-white/5 text-stone-400 border border-white/10 hover:border-stone-600",
            )}
          >
            <MaterialIcon icon={t.icon} size="sm" />
            {t.label}
          </button>
        ))}
      </div>

      {tab === "info" && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            icon="apartment"
            label="Clinicas"
            value={(tenant as unknown as { clinic_count?: number }).clinic_count ?? 1}
          />
          <StatCard
            icon="group"
            label="Usuarios"
            value={(tenant as unknown as { user_count?: number }).user_count ?? 0}
          />
          <StatCard
            icon="bolt"
            label="Uso IA (mes)"
            value={plan ? `${plan.ai_executions_month}/${plan.ai_limit_month}` : "--"}
          />
          <StatCard icon="verified" label="Plano" value={plan?.billing_plan ?? "starter"} />
        </div>
      )}

      {tab === "branding" && (
        <BrandingForm branding={branding} onSave={handleSaveBranding} saving={saving} />
      )}

      {tab === "integrations" && (
        <IntegrationsForm
          integrations={integrations}
          onSave={handleSaveIntegrations}
          saving={saving}
        />
      )}

      {tab === "plan" && <PlanForm plan={plan} onSave={handleSavePlan} saving={saving} />}
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────── */
/* Subcomponents                                                        */
/* ──────────────────────────────────────────────────────────────────── */

function BrandingForm({
  branding,
  onSave,
  saving,
}: {
  branding: TenantBranding | null;
  onSave: (data: Partial<TenantBranding>) => void;
  saving: boolean;
}) {
  const [brandName, setBrandName] = useState(branding?.brand_name ?? "");
  const [logoUrl, setLogoUrl] = useState(branding?.logo_url ?? "");
  const [primary, setPrimary] = useState(branding?.primary_color ?? "");
  const [secondary, setSecondary] = useState(branding?.secondary_color ?? "");
  const [subdomain, setSubdomain] = useState(branding?.subdomain ?? "");

  useEffect(() => {
    setBrandName(branding?.brand_name ?? "");
    setLogoUrl(branding?.logo_url ?? "");
    setPrimary(branding?.primary_color ?? "");
    setSecondary(branding?.secondary_color ?? "");
    setSubdomain(branding?.subdomain ?? "");
  }, [branding]);

  return (
    <Card variant="glass" padding="lg" className="space-y-5">
      <div className="flex items-center gap-3">
        <MaterialIcon icon="palette" className="text-primary text-2xl" />
        <div>
          <h2 className="font-bold text-on-surface">Identidade visual e subdominio</h2>
          <p className="text-xs text-stone-500 mt-0.5">
            Define como a organizacao aparece no portal e o endereco web proprio.
          </p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <Input
          label="Nome de marca"
          value={brandName}
          onChange={(e) => setBrandName(e.target.value)}
        />
        <Input
          label="Subdominio"
          placeholder="verde-vida"
          value={subdomain}
          onChange={(e) => setSubdomain(e.target.value)}
          hint="Parte antes do dominio raiz (ex.: verde-vida.cannabia.app)"
        />
        <Input
          label="URL do logo"
          placeholder="https://..."
          value={logoUrl}
          onChange={(e) => setLogoUrl(e.target.value)}
        />
        <Input
          label="Cor primaria"
          placeholder="#10b981"
          value={primary}
          onChange={(e) => setPrimary(e.target.value)}
        />
        <Input
          label="Cor secundaria"
          placeholder="#0f766e"
          value={secondary}
          onChange={(e) => setSecondary(e.target.value)}
        />
      </div>

      <div className="flex justify-end">
        <Button
          variant="primary"
          size="sm"
          icon="save"
          onClick={() =>
            onSave({
              brand_name: brandName || null,
              logo_url: logoUrl || null,
              primary_color: primary || null,
              secondary_color: secondary || null,
              subdomain: subdomain || null,
            })
          }
          disabled={saving}
        >
          {saving ? "Salvando..." : "Salvar branding"}
        </Button>
      </div>
    </Card>
  );
}

function IntegrationsForm({
  integrations,
  onSave,
  saving,
}: {
  integrations: TenantIntegrations | null;
  onSave: (data: Partial<TenantIntegrations>) => void;
  saving: boolean;
}) {
  const [wpPhoneId, setWpPhoneId] = useState(integrations?.whatsapp_phone_number_id ?? "");
  const [wpAccountId, setWpAccountId] = useState(integrations?.whatsapp_business_account_id ?? "");
  const [metaKey, setMetaKey] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [verifyToken, setVerifyToken] = useState("");

  const [emailFrom, setEmailFrom] = useState(integrations?.email_from ?? "");
  const [smtpServer, setSmtpServer] = useState(integrations?.smtp_server ?? "");
  const [smtpPort, setSmtpPort] = useState<string>(
    integrations?.smtp_port != null ? String(integrations.smtp_port) : "",
  );
  const [emailPassword, setEmailPassword] = useState("");
  const [doctorEmail, setDoctorEmail] = useState(integrations?.doctor_email ?? "");

  const [aiProvider, setAiProvider] = useState(integrations?.ai_provider ?? "gemini");
  const [aiKey, setAiKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");

  useEffect(() => {
    setWpPhoneId(integrations?.whatsapp_phone_number_id ?? "");
    setWpAccountId(integrations?.whatsapp_business_account_id ?? "");
    setEmailFrom(integrations?.email_from ?? "");
    setSmtpServer(integrations?.smtp_server ?? "");
    setSmtpPort(integrations?.smtp_port != null ? String(integrations.smtp_port) : "");
    setDoctorEmail(integrations?.doctor_email ?? "");
    setAiProvider(integrations?.ai_provider ?? "gemini");
  }, [integrations]);

  function submit() {
    const payload: Partial<TenantIntegrations> = {
      whatsapp_phone_number_id: wpPhoneId || null,
      whatsapp_business_account_id: wpAccountId || null,
      email_from: emailFrom || null,
      smtp_server: smtpServer || null,
      smtp_port: smtpPort ? Number(smtpPort) : null,
      doctor_email: doctorEmail || null,
      ai_provider: aiProvider || null,
    };
    // Segredos sao enviados apenas quando preenchidos (evita sobrescrever com vazio)
    if (metaKey) payload.meta_whatsapp_key = metaKey;
    if (appSecret) payload.whatsapp_app_secret = appSecret;
    if (verifyToken) payload.verify_token = verifyToken;
    if (emailPassword) payload.email_password = emailPassword;
    if (aiKey) payload.ai_api_key = aiKey;
    if (openaiKey) payload.openai_api_key = openaiKey;

    onSave(payload);
    setMetaKey("");
    setAppSecret("");
    setVerifyToken("");
    setEmailPassword("");
    setAiKey("");
    setOpenaiKey("");
  }

  const hasMetaKey = Boolean(integrations?.meta_whatsapp_key);
  const hasAppSecret = Boolean(integrations?.whatsapp_app_secret);
  const hasVerifyToken = Boolean(integrations?.verify_token);
  const hasEmailPw = Boolean(integrations?.email_password);
  const hasAiKey = Boolean(integrations?.ai_api_key);
  const hasOpenAi = Boolean(integrations?.openai_api_key);

  return (
    <div className="space-y-5">
      <Card variant="glass" padding="lg" className="space-y-4">
        <div className="flex items-center gap-3">
          <MaterialIcon icon="chat" className="text-primary text-2xl" />
          <div>
            <h2 className="font-bold text-on-surface">WhatsApp Business (Meta)</h2>
            <p className="text-xs text-stone-500 mt-0.5">
              Credenciais da API Meta para o canal WhatsApp desta organizacao.
            </p>
          </div>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <Input
            label="Phone number ID"
            value={wpPhoneId}
            onChange={(e) => setWpPhoneId(e.target.value)}
          />
          <Input
            label="WABA (business account) ID"
            value={wpAccountId}
            onChange={(e) => setWpAccountId(e.target.value)}
          />
          <SecretInput
            label="Token de acesso (META_WHATSAPP_KEY)"
            isSet={hasMetaKey}
            value={metaKey}
            onChange={setMetaKey}
          />
          <SecretInput
            label="App Secret (HMAC webhook)"
            isSet={hasAppSecret}
            value={appSecret}
            onChange={setAppSecret}
          />
          <SecretInput
            label="Verify Token"
            isSet={hasVerifyToken}
            value={verifyToken}
            onChange={setVerifyToken}
          />
        </div>
      </Card>

      <Card variant="glass" padding="lg" className="space-y-4">
        <div className="flex items-center gap-3">
          <MaterialIcon icon="mail" className="text-primary text-2xl" />
          <div>
            <h2 className="font-bold text-on-surface">E-mail (SMTP)</h2>
            <p className="text-xs text-stone-500 mt-0.5">
              Configuracao SMTP usada para envio de relatorios e notificacoes.
            </p>
          </div>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <Input
            label="De (from)"
            value={emailFrom}
            onChange={(e) => setEmailFrom(e.target.value)}
          />
          <Input
            label="E-mail do medico responsavel"
            value={doctorEmail}
            onChange={(e) => setDoctorEmail(e.target.value)}
          />
          <Input
            label="Servidor SMTP"
            placeholder="smtp.gmail.com"
            value={smtpServer}
            onChange={(e) => setSmtpServer(e.target.value)}
          />
          <Input
            label="Porta SMTP"
            placeholder="587"
            value={smtpPort}
            onChange={(e) => setSmtpPort(e.target.value)}
          />
          <SecretInput
            label="Senha SMTP"
            isSet={hasEmailPw}
            value={emailPassword}
            onChange={setEmailPassword}
          />
        </div>
      </Card>

      <Card variant="glass" padding="lg" className="space-y-4">
        <div className="flex items-center gap-3">
          <MaterialIcon icon="smart_toy" className="text-primary text-2xl" />
          <div>
            <h2 className="font-bold text-on-surface">Provedor de IA</h2>
            <p className="text-xs text-stone-500 mt-0.5">
              Modelo de linguagem usado pelos agentes clinicos. Gemini (Google) por padrao.
            </p>
          </div>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Provedor
            </label>
            <select
              value={aiProvider}
              onChange={(e) => setAiProvider(e.target.value)}
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors"
            >
              <option value="gemini">Google Gemini</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>
          <SecretInput
            label="Google API Key (Gemini)"
            isSet={hasAiKey}
            value={aiKey}
            onChange={setAiKey}
          />
          <SecretInput
            label="OpenAI API Key"
            isSet={hasOpenAi}
            value={openaiKey}
            onChange={setOpenaiKey}
          />
        </div>
      </Card>

      <div className="flex justify-end">
        <Button variant="primary" size="sm" icon="save" onClick={submit} disabled={saving}>
          {saving ? "Salvando..." : "Salvar integracoes"}
        </Button>
      </div>
    </div>
  );
}

function SecretInput({
  label,
  value,
  onChange,
  isSet,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  isSet: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold flex items-center gap-2">
        {label}
        {isSet && (
          <Badge tone="success" className="!text-[9px] !px-1.5">
            configurado
          </Badge>
        )}
      </label>
      <input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={isSet ? "Deixe em branco para manter o valor atual" : "Informe o segredo"}
        className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors"
      />
    </div>
  );
}

function PlanForm({
  plan,
  onSave,
  saving,
}: {
  plan: TenantPlanData | null;
  onSave: (data: { billing_plan?: string; ai_limit_month?: number; user_limit?: number }) => void;
  saving: boolean;
}) {
  const [billingPlan, setBillingPlan] = useState<string>(plan?.billing_plan ?? "starter");
  const [aiLimit, setAiLimit] = useState<string>(
    plan?.ai_limit_month != null ? String(plan.ai_limit_month) : "",
  );
  const [userLimit, setUserLimit] = useState<string>(
    plan?.user_limit != null ? String(plan.user_limit) : "",
  );

  useEffect(() => {
    setBillingPlan(plan?.billing_plan ?? "starter");
    setAiLimit(plan?.ai_limit_month != null ? String(plan.ai_limit_month) : "");
    setUserLimit(plan?.user_limit != null ? String(plan.user_limit) : "");
  }, [plan]);

  return (
    <Card variant="glass" padding="lg" className="space-y-5">
      <div className="flex items-center gap-3">
        <MaterialIcon icon="credit_card" className="text-primary text-2xl" />
        <div>
          <h2 className="font-bold text-on-surface">Plano comercial e quotas</h2>
          <p className="text-xs text-stone-500 mt-0.5">
            Define limite mensal de execucoes de IA, numero de usuarios e faturamento.
          </p>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
            Plano
          </label>
          <select
            value={billingPlan}
            onChange={(e) => setBillingPlan(e.target.value)}
            className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors"
          >
            <option value="starter">Starter</option>
            <option value="professional">Professional</option>
            <option value="enterprise">Enterprise</option>
          </select>
        </div>
        <Input
          label="Limite mensal de IA"
          value={aiLimit}
          onChange={(e) => setAiLimit(e.target.value)}
        />
        <Input
          label="Limite de usuarios"
          value={userLimit}
          onChange={(e) => setUserLimit(e.target.value)}
        />
      </div>

      <div className="flex justify-end">
        <Button
          variant="primary"
          size="sm"
          icon="save"
          onClick={() =>
            onSave({
              billing_plan: billingPlan,
              ai_limit_month: aiLimit ? Number(aiLimit) : undefined,
              user_limit: userLimit ? Number(userLimit) : undefined,
            })
          }
          disabled={saving}
        >
          {saving ? "Salvando..." : "Salvar plano"}
        </Button>
      </div>
    </Card>
  );
}
