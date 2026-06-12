"use client";

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { getClinicConfig, updateClinicConfig } from "@/lib/api";
import { Badge, Button, Card, Input, MaterialIcon, ToggleSwitch } from "@/components/ui-tw";

/* ── Types ─────────────────────────────────────────────────────────── */

type ClinicConfig = {
  // identidade
  brandName: string;
  logoUrl: string;
  primaryColor: string;
  accentColor: string;
  subdomain: string;
  // cadastro
  name: string;
  cnpj: string;
  address: string;
  phone: string;
  email: string;
  // operacional
  weekdayOpen: string;
  weekdayClose: string;
  weekendOpen: string;
  weekendClose: string;
  sundayClosed: boolean;
  consultationPrice: string;
  consultationDuration: string;
  modalityPresencial: boolean;
  modalityOnline: boolean;
  // integracoes
  whatsappNumber: string;
  apiKeyMeta: string;
  apiKeyOpenAI: string;
  apiKeyGemini: string;
  smtpHost: string;
  smtpUser: string;
  smtpPassword: string;
  // dna do negocio
  businessMission: string;
  targetPatientProfile: string;
  agentToneOfVoice: string;
  internalPolicies: string;
  // notificacoes
  notifyEmailNewPatient: boolean;
  notifyEmailAppointment: boolean;
  notifyEmailBilling: boolean;
  notifyWhatsappReminder: boolean;
  notifyWhatsappFollowup: boolean;
  notifyWhatsappBilling: boolean;
};

const defaultConfig: ClinicConfig = {
  brandName: "",
  logoUrl: "",
  primaryColor: "#A3C93A",
  accentColor: "#29522E",
  subdomain: "",
  name: "",
  cnpj: "",
  address: "",
  phone: "",
  email: "",
  weekdayOpen: "08:00",
  weekdayClose: "19:00",
  weekendOpen: "08:00",
  weekendClose: "12:00",
  sundayClosed: true,
  consultationPrice: "0",
  consultationDuration: "45",
  modalityPresencial: true,
  modalityOnline: true,
  whatsappNumber: "",
  apiKeyMeta: "",
  apiKeyOpenAI: "",
  apiKeyGemini: "",
  smtpHost: "",
  smtpUser: "",
  smtpPassword: "",
  businessMission: "",
  targetPatientProfile: "",
  agentToneOfVoice: "",
  internalPolicies: "",
  notifyEmailNewPatient: true,
  notifyEmailAppointment: true,
  notifyEmailBilling: false,
  notifyWhatsappReminder: true,
  notifyWhatsappFollowup: true,
  notifyWhatsappBilling: true,
};

const COLOR_PRESETS = [
  { label: "Verde Cannabia", value: "#A3C93A" },
  { label: "Verde Escuro", value: "#29522E" },
  { label: "Roxo", value: "#741E80" },
  { label: "Azul", value: "#1E5080" },
  { label: "Dourado", value: "#C9A33A" },
  { label: "Coral", value: "#E07A5F" },
];

type TabKey = "identidade" | "cadastro" | "operacional" | "integracoes" | "dna" | "notificacoes";

const TABS: Array<{ key: TabKey; label: string; icon: string; hint: string }> = [
  {
    key: "identidade",
    label: "Identidade Visual",
    icon: "palette",
    hint: "Logo, cores, marca, subdominio",
  },
  {
    key: "cadastro",
    label: "Clinica/Associacao",
    icon: "medical_information",
    hint: "Razao social, CNPJ, contato",
  },
  {
    key: "operacional",
    label: "Operacional",
    icon: "schedule",
    hint: "Horarios, consultas, modalidades",
  },
  { key: "integracoes", label: "Integracoes", icon: "cable", hint: "WhatsApp, IA, Email, Pix" },
  {
    key: "dna",
    label: "DNA do Negocio",
    icon: "auto_awesome",
    hint: "Missao, perfil de paciente, tom dos agentes",
  },
  {
    key: "notificacoes",
    label: "Notificacoes",
    icon: "notifications_active",
    hint: "Email + WhatsApp por evento",
  },
];

/* ── Page ─────────────────────────────────────────────────────────── */

export default function ConfiguracoesPage() {
  const { data: session } = useApiSession();
  const [tab, setTab] = useState<TabKey>("identidade");
  const [config, setConfig] = useState<ClinicConfig>(defaultConfig);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getClinicConfig();
      const remote = res.data as Record<string, unknown>;
      setConfig((prev) => ({ ...prev, ...remote }) as ClinicConfig);
    } catch {
      // mantem defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchConfig();
  }, [fetchConfig]);

  const update = <K extends keyof ClinicConfig>(key: K, value: ClinicConfig[K]) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  async function handleSave() {
    setSaving(true);
    try {
      const csrfToken = (session as Record<string, unknown>)?.csrf_token as string | undefined;
      await updateClinicConfig(csrfToken ?? "", config as unknown as Record<string, unknown>);
      setSavedAt(new Date());
    } catch (error) {
      console.warn("[configuracoes] falha ao salvar", error);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <MaterialIcon icon="hourglass_empty" size="xl" className="text-primary animate-spin" />
          <p className="text-stone-400 text-sm">Carregando configuracoes...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* ── Sticky header com Save ───────────────────────────────── */}
      <header className="sticky top-0 z-20 -mx-4 md:-mx-8 px-4 md:px-8 py-4 bg-surface/80 backdrop-blur-xl border-b border-outline-variant/20">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-headline font-extrabold tracking-tight text-on-surface">
              Configuracoes
            </h1>
            <p className="text-sm text-stone-500">
              Personalize a clinica/associacao, integracoes e o comportamento dos agentes IA.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {savedAt && !saving && (
              <span className="hidden md:inline-flex items-center gap-1 text-xs text-primary">
                <MaterialIcon icon="check_circle" size="sm" />
                Salvo {savedAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
            <Button icon="save" loading={saving} onClick={handleSave}>
              Salvar
            </Button>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* ── Side tabs ────────────────────────────────────────── */}
        <nav className="lg:col-span-3">
          <ul className="flex flex-row lg:flex-col gap-2 overflow-x-auto lg:overflow-visible -mx-1 px-1 pb-2 lg:pb-0">
            {TABS.map((t) => (
              <li key={t.key} className="flex-shrink-0 lg:flex-shrink lg:w-full">
                <button
                  type="button"
                  onClick={() => setTab(t.key)}
                  aria-current={tab === t.key ? "page" : undefined}
                  className={cn(
                    "w-full flex items-center gap-3 px-4 py-3 rounded-xl border transition-colors text-left",
                    tab === t.key
                      ? "bg-primary/15 border-primary/40 text-on-surface shadow-sm"
                      : "bg-surface-container/40 border-outline-variant/20 text-stone-400 hover:bg-surface-container/70 hover:text-on-surface",
                  )}
                >
                  <MaterialIcon
                    icon={t.icon}
                    className={tab === t.key ? "text-primary" : "text-stone-500"}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold leading-tight whitespace-nowrap lg:whitespace-normal">
                      {t.label}
                    </p>
                    <p className="hidden lg:block text-[11px] text-stone-500 mt-0.5 leading-snug">
                      {t.hint}
                    </p>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* ── Conteudo da aba ──────────────────────────────────── */}
        <main className="lg:col-span-9 space-y-6">
          {tab === "identidade" && <IdentidadeTab config={config} update={update} />}
          {tab === "cadastro" && <CadastroTab config={config} update={update} />}
          {tab === "operacional" && <OperacionalTab config={config} update={update} />}
          {tab === "integracoes" && <IntegracoesTab config={config} update={update} />}
          {tab === "dna" && <DnaTab config={config} update={update} />}
          {tab === "notificacoes" && <NotificacoesTab config={config} update={update} />}
        </main>
      </div>
    </div>
  );
}

/* ── Tab components ──────────────────────────────────────────────── */

type TabProps = {
  config: ClinicConfig;
  update: <K extends keyof ClinicConfig>(key: K, value: ClinicConfig[K]) => void;
};

function SectionHeader({ icon, title, desc }: { icon: string; title: string; desc?: string }) {
  return (
    <div className="flex items-start gap-3 mb-5">
      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
        <MaterialIcon icon={icon} className="text-primary" />
      </div>
      <div>
        <h3 className="text-lg font-headline font-bold text-on-surface leading-tight">{title}</h3>
        {desc && <p className="text-xs text-stone-500 mt-0.5">{desc}</p>}
      </div>
    </div>
  );
}

function IdentidadeTab({ config, update }: TabProps) {
  return (
    <>
      <Card padding="lg">
        <SectionHeader
          icon="palette"
          title="Identidade da marca"
          desc="Aparece no painel, documentos exportados e mensagens automaticas dos agentes."
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-5">
            <Input
              label="Nome da marca"
              value={config.brandName}
              onChange={(e) => update("brandName", e.target.value)}
              placeholder="Cannabia Associacao"
            />
            <Input
              label="Subdominio (white-label)"
              value={config.subdomain}
              onChange={(e) => update("subdomain", e.target.value)}
              placeholder="minha-clinica"
              icon="link"
            />
            <Input
              label="URL do logo"
              value={config.logoUrl}
              onChange={(e) => update("logoUrl", e.target.value)}
              placeholder="https://..."
              icon="image"
            />
            <p className="text-[11px] text-stone-500 -mt-3">
              Em breve: upload direto. Por enquanto, hospede a imagem em servico publico (S3,
              Cloudinary, etc.) e cole o link.
            </p>
          </div>

          <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant/30 flex flex-col items-center justify-center text-center">
            <p className="text-[10px] uppercase tracking-widest text-primary font-bold mb-4">
              Pre-visualizacao
            </p>
            <div
              className="w-44 h-12 rounded-full flex items-center px-4 mb-4 shadow-lg"
              style={{ backgroundColor: config.primaryColor }}
            >
              {config.logoUrl ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img src={config.logoUrl} alt="Logo" className="h-7 w-auto mr-3" />
              ) : (
                <div className="w-6 h-6 bg-black/30 rounded-full mr-3" />
              )}
              <div className="h-2 w-20 bg-black/20 rounded-full" />
            </div>
            <p className="text-sm font-bold text-on-surface mb-1">
              {config.brandName || "Sua marca"}
            </p>
            <div
              className="mt-3 w-12 h-12 rounded-xl"
              style={{ backgroundColor: config.accentColor }}
            />
            <p className="mt-3 text-[11px] text-stone-500">Cor primaria + destaque em tempo real</p>
          </div>
        </div>
      </Card>

      <Card padding="lg">
        <SectionHeader icon="format_color_fill" title="Paleta de cores" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <ColorPicker
            label="Cor primaria"
            value={config.primaryColor}
            onChange={(v) => update("primaryColor", v)}
          />
          <ColorPicker
            label="Cor de destaque"
            value={config.accentColor}
            onChange={(v) => update("accentColor", v)}
          />
        </div>
      </Card>
    </>
  );
}

function ColorPicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-stone-400">{label}</label>
      <div className="flex flex-wrap gap-3">
        {COLOR_PRESETS.map((c) => (
          <button
            key={c.value}
            type="button"
            onClick={() => onChange(c.value)}
            aria-label={c.label}
            title={c.label}
            className={cn(
              "w-10 h-10 rounded-full border-4 transition-transform hover:scale-110",
              value === c.value
                ? "border-white ring-2 ring-primary scale-110"
                : "border-surface-container-highest",
            )}
            style={{ backgroundColor: c.value }}
          />
        ))}
        <label className="w-10 h-10 rounded-full border-4 border-dashed border-outline-variant/40 flex items-center justify-center cursor-pointer hover:border-primary transition-colors">
          <input
            type="color"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="opacity-0 w-0 h-0"
          />
          <MaterialIcon icon="add" size="sm" className="text-stone-500" />
        </label>
      </div>
      <p className="text-[11px] text-stone-500 font-mono">{value}</p>
    </div>
  );
}

function CadastroTab({ config, update }: TabProps) {
  return (
    <Card padding="lg">
      <SectionHeader
        icon="medical_information"
        title="Dados da clinica/associacao"
        desc="Razao social, CNPJ, endereco e canais oficiais."
      />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Input
          label="Nome / Razao social"
          value={config.name}
          onChange={(e) => update("name", e.target.value)}
        />
        <Input
          label="CNPJ"
          value={config.cnpj}
          onChange={(e) => update("cnpj", e.target.value)}
          placeholder="00.000.000/0001-00"
        />
        <div className="md:col-span-2">
          <Input
            label="Endereco completo"
            value={config.address}
            onChange={(e) => update("address", e.target.value)}
          />
        </div>
        <Input
          label="Telefone"
          value={config.phone}
          onChange={(e) => update("phone", e.target.value)}
          icon="phone"
        />
        <Input
          label="Email institucional"
          value={config.email}
          onChange={(e) => update("email", e.target.value)}
          icon="mail"
        />
      </div>
    </Card>
  );
}

function OperacionalTab({ config, update }: TabProps) {
  return (
    <>
      <Card padding="lg">
        <SectionHeader icon="schedule" title="Horario de funcionamento" />
        <div className="space-y-5">
          <TimeRange
            label="Segunda a sexta"
            open={config.weekdayOpen}
            close={config.weekdayClose}
            onOpen={(v) => update("weekdayOpen", v)}
            onClose={(v) => update("weekdayClose", v)}
          />
          <TimeRange
            label="Sabado"
            open={config.weekendOpen}
            close={config.weekendClose}
            onOpen={(v) => update("weekendOpen", v)}
            onClose={(v) => update("weekendClose", v)}
          />
          <div className="flex items-center justify-between p-4 bg-surface-container-low rounded-xl border border-outline-variant/20">
            <div>
              <p className="text-sm font-bold text-on-surface">Domingo</p>
              <p className="text-xs text-stone-500">Aberto ou fechado</p>
            </div>
            <ToggleSwitch
              checked={!config.sundayClosed}
              onChange={(v) => update("sundayClosed", !v)}
              label={config.sundayClosed ? "Fechado" : "Aberto"}
            />
          </div>
        </div>
      </Card>

      <Card padding="lg">
        <SectionHeader icon="event_available" title="Consultas" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Input
            label="Valor padrao (R$)"
            value={config.consultationPrice}
            onChange={(e) => update("consultationPrice", e.target.value)}
            icon="payments"
          />
          <Input
            label="Duracao (min)"
            value={config.consultationDuration}
            onChange={(e) => update("consultationDuration", e.target.value)}
            icon="schedule"
          />
          <div className="md:col-span-2 p-4 bg-surface-container-low rounded-xl border border-outline-variant/20 space-y-3">
            <p className="text-xs text-stone-400 font-bold uppercase tracking-wider">
              Modalidades de atendimento
            </p>
            <ToggleSwitch
              checked={config.modalityPresencial}
              onChange={(v) => update("modalityPresencial", v)}
              label="Presencial"
            />
            <ToggleSwitch
              checked={config.modalityOnline}
              onChange={(v) => update("modalityOnline", v)}
              label="Online (telemedicina)"
            />
          </div>
        </div>
      </Card>
    </>
  );
}

function TimeRange({
  label,
  open,
  close,
  onOpen,
  onClose,
}: {
  label: string;
  open: string;
  close: string;
  onOpen: (v: string) => void;
  onClose: (v: string) => void;
}) {
  const inputCls =
    "bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary";
  return (
    <div>
      <p className="text-xs text-stone-400 font-bold uppercase mb-2">{label}</p>
      <div className="flex items-center gap-3">
        <input
          type="time"
          value={open}
          onChange={(e) => onOpen(e.target.value)}
          className={inputCls}
        />
        <span className="text-stone-500">ate</span>
        <input
          type="time"
          value={close}
          onChange={(e) => onClose(e.target.value)}
          className={inputCls}
        />
      </div>
    </div>
  );
}

function IntegracoesTab({ config, update }: TabProps) {
  return (
    <>
      <Card padding="lg">
        <SectionHeader
          icon="chat"
          title="WhatsApp Business"
          desc="Numero oficial e token Meta para envio de mensagens automatizadas dos agentes."
        />
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Badge tone={config.apiKeyMeta ? "success" : "warning"}>
              {config.apiKeyMeta ? "Conectado" : "Pendente"}
            </Badge>
            <span className="text-xs text-stone-500">
              {config.apiKeyMeta ? "Token ativo" : "Configure o token Meta para ativar"}
            </span>
          </div>
          <Input
            label="Numero do WhatsApp"
            value={config.whatsappNumber}
            onChange={(e) => update("whatsappNumber", e.target.value)}
            icon="phone"
            placeholder="+55 11 9...."
          />
          <Input
            label="Meta API Token"
            type="password"
            value={config.apiKeyMeta}
            onChange={(e) => update("apiKeyMeta", e.target.value)}
            icon="key"
            placeholder="EAA..."
          />
        </div>
      </Card>

      <Card padding="lg">
        <SectionHeader
          icon="psychology"
          title="Agentes IA"
          desc="Chaves de API usadas pelos agentes (alem das chaves globais da plataforma)."
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Input
            label="OpenAI API Key"
            type="password"
            value={config.apiKeyOpenAI}
            onChange={(e) => update("apiKeyOpenAI", e.target.value)}
            icon="key"
            placeholder="sk-..."
          />
          <Input
            label="Google Gemini API Key"
            type="password"
            value={config.apiKeyGemini}
            onChange={(e) => update("apiKeyGemini", e.target.value)}
            icon="key"
            placeholder="AIza..."
          />
        </div>
        <p className="text-[11px] text-stone-500 mt-3">
          Sem chave especifica, os agentes usam as chaves globais da plataforma (configuradas pelo
          super admin).
        </p>
      </Card>

      <Card padding="lg">
        <SectionHeader
          icon="mail"
          title="Email / SMTP"
          desc="Servidor de envio de emails transacionais (notificacoes, faturas)."
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="md:col-span-2">
            <Input
              label="Host SMTP"
              value={config.smtpHost}
              onChange={(e) => update("smtpHost", e.target.value)}
              placeholder="smtp.gmail.com"
            />
          </div>
          <Input
            label="Usuario"
            value={config.smtpUser}
            onChange={(e) => update("smtpUser", e.target.value)}
            icon="person"
          />
          <Input
            label="Senha"
            type="password"
            value={config.smtpPassword}
            onChange={(e) => update("smtpPassword", e.target.value)}
            icon="lock"
          />
        </div>
      </Card>

      <Card padding="lg">
        <div className="flex items-center justify-between">
          <SectionHeader icon="qr_code_2" title="Pix" />
          <Badge tone="success">Vinculado</Badge>
        </div>
        <p className="text-xs text-stone-500">
          Em breve: configuracao detalhada da chave Pix institucional.
        </p>
      </Card>
    </>
  );
}

function DnaTab({ config, update }: TabProps) {
  return (
    <>
      <Card padding="lg">
        <SectionHeader
          icon="auto_awesome"
          title="DNA do negocio"
          desc="O que voce coloca aqui personaliza o comportamento dos agentes IA na sua clinica/associacao."
        />
        <div className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-stone-400 mb-2">
              Missao e proposito
            </label>
            <textarea
              value={config.businessMission}
              onChange={(e) => update("businessMission", e.target.value)}
              placeholder="Ex.: Acolher pacientes com dor cronica usando cannabis medicinal de forma cientifica e humanizada."
              rows={3}
              className="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-4 py-3 text-sm text-on-surface focus:outline-none focus:border-primary resize-y"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-400 mb-2">
              Perfil de paciente alvo (ICP)
            </label>
            <textarea
              value={config.targetPatientProfile}
              onChange={(e) => update("targetPatientProfile", e.target.value)}
              placeholder="Ex.: Adultos 30-70, dor cronica nao oncologica, ja tentaram tratamentos convencionais sem resposta."
              rows={3}
              className="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-4 py-3 text-sm text-on-surface focus:outline-none focus:border-primary resize-y"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-400 mb-2">
              Tom de voz dos agentes
            </label>
            <textarea
              value={config.agentToneOfVoice}
              onChange={(e) => update("agentToneOfVoice", e.target.value)}
              placeholder="Ex.: Acolhedor, claro e direto. Evitar jargoes medicos. Sempre validar a experiencia do paciente antes de orientar."
              rows={3}
              className="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-4 py-3 text-sm text-on-surface focus:outline-none focus:border-primary resize-y"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-400 mb-2">
              Politicas internas que os agentes devem respeitar
            </label>
            <textarea
              value={config.internalPolicies}
              onChange={(e) => update("internalPolicies", e.target.value)}
              placeholder="Ex.: Nunca prometer cura. Sempre encaminhar caso de evento adverso grave para medico humano. Em fim de semana, agendar para segunda-feira."
              rows={4}
              className="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-4 py-3 text-sm text-on-surface focus:outline-none focus:border-primary resize-y"
            />
          </div>
        </div>
      </Card>

      <div className="p-5 rounded-2xl bg-primary/5 border border-primary/10 flex gap-4">
        <MaterialIcon icon="info" size="md" className="text-primary flex-shrink-0 mt-0.5" />
        <div className="text-xs text-stone-400 leading-relaxed">
          <p className="font-bold text-primary mb-1">Por que isso importa</p>
          Os agentes (Triagem, Anamnese, Prescritor, Cientifico, Regulatorio, FollowUp) consultam o
          DNA antes de cada acao. Quanto mais preciso o DNA, mais alinhado o trabalho dos agentes
          com a sua identidade clinica.
        </div>
      </div>
    </>
  );
}

function NotificacoesTab({ config, update }: TabProps) {
  return (
    <>
      <Card padding="lg">
        <SectionHeader icon="mail" title="Notificacoes por email" />
        <div className="space-y-3">
          <ToggleSwitch
            checked={config.notifyEmailNewPatient}
            onChange={(v) => update("notifyEmailNewPatient", v)}
            label="Novo paciente cadastrado"
          />
          <ToggleSwitch
            checked={config.notifyEmailAppointment}
            onChange={(v) => update("notifyEmailAppointment", v)}
            label="Agendamento criado/alterado"
          />
          <ToggleSwitch
            checked={config.notifyEmailBilling}
            onChange={(v) => update("notifyEmailBilling", v)}
            label="Faturamento e cobrancas"
          />
        </div>
      </Card>

      <Card padding="lg">
        <SectionHeader icon="chat" title="Notificacoes via WhatsApp" />
        <div className="space-y-3">
          <ToggleSwitch
            checked={config.notifyWhatsappReminder}
            onChange={(v) => update("notifyWhatsappReminder", v)}
            label="Lembrete de consulta (24h antes)"
          />
          <ToggleSwitch
            checked={config.notifyWhatsappFollowup}
            onChange={(v) => update("notifyWhatsappFollowup", v)}
            label="Follow-up pos-consulta (D+3 / D+7 / D+15)"
          />
          <ToggleSwitch
            checked={config.notifyWhatsappBilling}
            onChange={(v) => update("notifyWhatsappBilling", v)}
            label="Cobranca e pagamento"
          />
        </div>
      </Card>
    </>
  );
}
