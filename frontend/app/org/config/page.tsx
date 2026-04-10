"use client";

import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { getClinicConfig, updateClinicConfig } from "@/lib/api";
import {
  Card,
  Badge,
  Button,
  Input,
  MaterialIcon,
  ToggleSwitch,
} from "@/components/ui-tw";

/* ── Types ─────────────────────────────────────────────────────────── */

type ClinicConfig = {
  name: string;
  cnpj: string;
  address: string;
  phone: string;
  email: string;
  weekdayOpen: string;
  weekdayClose: string;
  weekendOpen: string;
  weekendClose: string;
  sundayClosed: boolean;
  consultationPrice: string;
  consultationDuration: string;
  modalityPresencial: boolean;
  modalityOnline: boolean;
  whatsappNumber: string;
  apiKeyMeta: string;
  apiKeyOpenAI: string;
  primaryColor: string;
  accentColor: string;
  notifyEmailNewPatient: boolean;
  notifyEmailAppointment: boolean;
  notifyEmailBilling: boolean;
  notifyWhatsappReminder: boolean;
  notifyWhatsappFollowup: boolean;
  notifyWhatsappBilling: boolean;
};

/* ── Defaults ─────────────────────────────────────────────────────── */

const defaultConfig: ClinicConfig = {
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
  primaryColor: "#A3C93A",
  accentColor: "#29522E",
  notifyEmailNewPatient: true,
  notifyEmailAppointment: true,
  notifyEmailBilling: false,
  notifyWhatsappReminder: true,
  notifyWhatsappFollowup: true,
  notifyWhatsappBilling: true,
};

const colorPresets = [
  { label: "Verde Primario", value: "#A3C93A" },
  { label: "Verde Escuro", value: "#29522E" },
  { label: "Roxo", value: "#741E80" },
  { label: "Azul", value: "#1E5080" },
  { label: "Dourado", value: "#C9A33A" },
];

/* ── Page Component ────────────────────────────────────────────────── */

export default function ConfigPage() {
  const { data: session } = useApiSession();
  const [config, setConfig] = useState<ClinicConfig>(defaultConfig);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getClinicConfig();
      const d = res.data as Record<string, unknown>;
      setConfig((prev) => ({ ...prev, ...d } as ClinicConfig));
    } catch {
      // keep defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const update = <K extends keyof ClinicConfig>(key: K, value: ClinicConfig[K]) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const csrfToken = (session as Record<string, unknown>)?.csrf_token as string | undefined;
      await updateClinicConfig(csrfToken ?? "", config as unknown as Record<string, unknown>);
    } catch {
      // handle error silently for now
    } finally {
      setSaving(false);
    }
  };

  const maskApiKey = (key: string) => {
    if (key.length <= 8) return key;
    return key.slice(0, 4) + "****" + key.slice(-4);
  };

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
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <header>
          <h1 className="text-3xl md:text-4xl font-headline font-extrabold tracking-tight text-on-surface">
            Personalizacao do Perfil
          </h1>
          <p className="text-on-surface/60 mt-1 text-sm md:text-base">da Clinica</p>
        </header>
        <Button
          icon="save"
          loading={saving}
          onClick={handleSave}
          className="self-start md:self-auto"
        >
          Salvar Alteracoes
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* ── Left Column ─────────────────────────────────────────── */}
        <div className="lg:col-span-8 space-y-8">
          {/* Logo Upload */}
          <Card padding="lg">
            <div className="flex items-center gap-3 mb-6">
              <MaterialIcon icon="palette" filled className="text-primary" />
              <h3 className="text-xl font-headline font-bold">Identidade Visual</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-stone-400 mb-3">
                    Logo da Clinica
                  </label>
                  <div className="flex items-center gap-6">
                    <div className="w-28 h-28 rounded-2xl bg-surface-container-highest flex items-center justify-center overflow-hidden border border-outline-variant/30">
                      <MaterialIcon icon="local_florist" size="xl" className="text-primary/40" />
                    </div>
                    <div className="space-y-2">
                      <Button variant="secondary" size="sm" icon="upload_file">
                        Alterar Logo
                      </Button>
                      <p className="text-[10px] text-stone-500">
                        PNG, JPG ou SVG. Max 2MB.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Color Picker */}
                <div className="space-y-3">
                  <label className="block text-sm font-medium text-stone-400">
                    Cor Primaria
                  </label>
                  <div className="flex flex-wrap gap-3">
                    {colorPresets.map((c) => (
                      <button
                        key={c.value}
                        onClick={() => update("primaryColor", c.value)}
                        className={cn(
                          "w-10 h-10 rounded-full border-4 transition-transform hover:scale-110",
                          config.primaryColor === c.value
                            ? "border-white ring-2 ring-primary scale-110"
                            : "border-surface-container-highest",
                        )}
                        style={{ backgroundColor: c.value }}
                        title={c.label}
                      />
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="block text-sm font-medium text-stone-400">
                    Cor de Destaque
                  </label>
                  <div className="flex flex-wrap gap-3">
                    {colorPresets.map((c) => (
                      <button
                        key={c.value}
                        onClick={() => update("accentColor", c.value)}
                        className={cn(
                          "w-10 h-10 rounded-full border-4 transition-transform hover:scale-110",
                          config.accentColor === c.value
                            ? "border-white ring-2 ring-primary scale-110"
                            : "border-surface-container-highest",
                        )}
                        style={{ backgroundColor: c.value }}
                        title={c.label}
                      />
                    ))}
                  </div>
                </div>
              </div>

              {/* Live Preview */}
              <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant/30 flex flex-col items-center justify-center text-center">
                <p className="text-[10px] uppercase tracking-widest text-primary font-bold mb-4">
                  Visualizacao em Tempo Real
                </p>
                <div
                  className="w-48 h-10 rounded-full flex items-center px-4 mb-4 shadow-lg"
                  style={{ backgroundColor: config.primaryColor }}
                >
                  <div className="w-5 h-5 bg-black/30 rounded-full mr-3" />
                  <div className="h-2 w-20 bg-black/20 rounded-full" />
                </div>
                <div className="space-y-2">
                  <div className="h-2 w-32 bg-surface-container-highest rounded-full mx-auto" />
                  <div className="h-2 w-24 bg-surface-container-highest rounded-full mx-auto opacity-50" />
                </div>
                <div
                  className="mt-4 w-12 h-12 rounded-xl"
                  style={{ backgroundColor: config.accentColor }}
                />
                <p className="mt-4 text-xs text-stone-500">
                  Sua marca aplicada aos documentos e interface.
                </p>
              </div>
            </div>
          </Card>

          {/* Clinic Info */}
          <Card padding="lg">
            <div className="flex items-center gap-3 mb-6">
              <MaterialIcon icon="medical_information" filled className="text-primary" />
              <h3 className="text-xl font-headline font-bold">Dados da Clinica</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <Input
                label="Nome da Organizacao"
                value={config.name}
                onChange={(e) => update("name", e.target.value)}
              />
              <Input
                label="CNPJ"
                value={config.cnpj}
                onChange={(e) => update("cnpj", e.target.value)}
              />
              <div className="md:col-span-2">
                <Input
                  label="Endereco Completo"
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
                label="Email"
                value={config.email}
                onChange={(e) => update("email", e.target.value)}
                icon="mail"
              />
            </div>
          </Card>

          {/* Operating Hours + Consultation */}
          <Card padding="lg">
            <div className="flex items-center gap-3 mb-6">
              <MaterialIcon icon="shutter_speed" filled className="text-primary" />
              <h3 className="text-xl font-headline font-bold">Operacional</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Hours */}
              <div className="bg-surface-container-low rounded-2xl p-6 border border-outline-variant/20">
                <div className="flex justify-between items-center mb-5">
                  <span className="font-bold text-on-surface">Horario de Funcionamento</span>
                </div>
                <div className="space-y-4">
                  <div>
                    <p className="text-xs text-stone-400 font-bold uppercase mb-2">Segunda a Sexta</p>
                    <div className="flex items-center gap-3">
                      <input
                        type="time"
                        value={config.weekdayOpen}
                        onChange={(e) => update("weekdayOpen", e.target.value)}
                        className="bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary-container"
                      />
                      <span className="text-stone-500">ate</span>
                      <input
                        type="time"
                        value={config.weekdayClose}
                        onChange={(e) => update("weekdayClose", e.target.value)}
                        className="bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary-container"
                      />
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-stone-400 font-bold uppercase mb-2">Sabado</p>
                    <div className="flex items-center gap-3">
                      <input
                        type="time"
                        value={config.weekendOpen}
                        onChange={(e) => update("weekendOpen", e.target.value)}
                        className="bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary-container"
                      />
                      <span className="text-stone-500">ate</span>
                      <input
                        type="time"
                        value={config.weekendClose}
                        onChange={(e) => update("weekendClose", e.target.value)}
                        className="bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary-container"
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-on-surface">Domingo</span>
                    <div className="flex items-center gap-3">
                      <ToggleSwitch
                        checked={config.sundayClosed}
                        onChange={(v) => update("sundayClosed", v)}
                      />
                      <span className={cn("text-sm font-medium", config.sundayClosed ? "text-error" : "text-primary")}>
                        {config.sundayClosed ? "Fechado" : "Aberto"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Consultation Settings */}
              <div className="space-y-5">
                <div className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/20">
                  <p className="text-xs text-stone-400 font-bold uppercase tracking-wider mb-2">
                    Valor Consulta Padrao (R$)
                  </p>
                  <Input
                    value={config.consultationPrice}
                    onChange={(e) => update("consultationPrice", e.target.value)}
                    icon="payments"
                  />
                </div>
                <div className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/20">
                  <p className="text-xs text-stone-400 font-bold uppercase tracking-wider mb-2">
                    Duracao da Consulta (min)
                  </p>
                  <Input
                    value={config.consultationDuration}
                    onChange={(e) => update("consultationDuration", e.target.value)}
                    icon="schedule"
                  />
                </div>
                <div className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/20">
                  <p className="text-xs text-stone-400 font-bold uppercase tracking-wider mb-3">
                    Modalidades de Atendimento
                  </p>
                  <div className="space-y-3">
                    <ToggleSwitch
                      checked={config.modalityPresencial}
                      onChange={(v) => update("modalityPresencial", v)}
                      label="Presencial"
                    />
                    <ToggleSwitch
                      checked={config.modalityOnline}
                      onChange={(v) => update("modalityOnline", v)}
                      label="Online (Telemedicina)"
                    />
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* ── Right Column ────────────────────────────────────────── */}
        <div className="lg:col-span-4 space-y-8">
          {/* Integration Settings */}
          <Card padding="md">
            <div className="flex items-center gap-3 mb-6">
              <MaterialIcon icon="cable" filled className="text-primary" />
              <h3 className="text-lg font-headline font-bold">Integracoes</h3>
            </div>
            <div className="space-y-4">
              {/* WhatsApp */}
              <div className="p-4 bg-surface-container-low rounded-2xl border border-outline-variant/20">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 bg-[#25D366]/10 rounded-full flex items-center justify-center">
                    <MaterialIcon icon="chat" className="text-[#25D366]" />
                  </div>
                  <div>
                    <p className="text-sm font-bold">WhatsApp Business</p>
                    <Badge tone="success">Ativo</Badge>
                  </div>
                </div>
                <Input
                  label="Numero WhatsApp"
                  value={config.whatsappNumber}
                  onChange={(e) => update("whatsappNumber", e.target.value)}
                  icon="phone"
                />
              </div>

              {/* API Keys */}
              <div className="p-4 bg-surface-container-low rounded-2xl border border-outline-variant/20">
                <p className="text-xs text-stone-400 font-bold uppercase tracking-wider mb-3">
                  Chaves de Integracao
                </p>
                <div className="space-y-3">
                  <div>
                    <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1 block">
                      Meta API Token
                    </label>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-stone-500 font-mono truncate">
                        {maskApiKey(config.apiKeyMeta)}
                      </div>
                      <button className="p-2 text-stone-400 hover:text-primary transition-colors">
                        <MaterialIcon icon="edit" size="sm" />
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1 block">
                      OpenAI API Key
                    </label>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-stone-500 font-mono truncate">
                        {maskApiKey(config.apiKeyOpenAI)}
                      </div>
                      <button className="p-2 text-stone-400 hover:text-primary transition-colors">
                        <MaterialIcon icon="edit" size="sm" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Pix */}
              <div className="p-4 bg-surface-container-low rounded-2xl border border-outline-variant/20 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center">
                    <MaterialIcon icon="qr_code_2" className="text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-bold">Pix Instantaneo</p>
                    <p className="text-[10px] text-stone-500">Chave vinculada</p>
                  </div>
                </div>
                <MaterialIcon icon="check_circle" className="text-primary" />
              </div>
            </div>
          </Card>

          {/* Notification Settings */}
          <Card padding="md">
            <div className="flex items-center gap-3 mb-6">
              <MaterialIcon icon="notifications_active" filled className="text-primary" />
              <h3 className="text-lg font-headline font-bold">Notificacoes</h3>
            </div>
            <div className="space-y-5">
              {/* Email */}
              <div>
                <p className="text-xs text-stone-400 font-bold uppercase tracking-wider mb-3 flex items-center gap-2">
                  <MaterialIcon icon="mail" size="sm" className="text-stone-500" />
                  Email
                </p>
                <div className="space-y-3">
                  <ToggleSwitch
                    checked={config.notifyEmailNewPatient}
                    onChange={(v) => update("notifyEmailNewPatient", v)}
                    label="Novo Paciente"
                  />
                  <ToggleSwitch
                    checked={config.notifyEmailAppointment}
                    onChange={(v) => update("notifyEmailAppointment", v)}
                    label="Agendamento"
                  />
                  <ToggleSwitch
                    checked={config.notifyEmailBilling}
                    onChange={(v) => update("notifyEmailBilling", v)}
                    label="Faturamento"
                  />
                </div>
              </div>

              {/* WhatsApp */}
              <div className="pt-4 border-t border-white/5">
                <p className="text-xs text-stone-400 font-bold uppercase tracking-wider mb-3 flex items-center gap-2">
                  <MaterialIcon icon="chat" size="sm" className="text-[#25D366]" />
                  WhatsApp
                </p>
                <div className="space-y-3">
                  <ToggleSwitch
                    checked={config.notifyWhatsappReminder}
                    onChange={(v) => update("notifyWhatsappReminder", v)}
                    label="Lembrete de Consulta"
                  />
                  <ToggleSwitch
                    checked={config.notifyWhatsappFollowup}
                    onChange={(v) => update("notifyWhatsappFollowup", v)}
                    label="Acompanhamento"
                  />
                  <ToggleSwitch
                    checked={config.notifyWhatsappBilling}
                    onChange={(v) => update("notifyWhatsappBilling", v)}
                    label="Cobranca"
                  />
                </div>
              </div>
            </div>
          </Card>

          {/* Support Card */}
          <div className="p-5 rounded-2xl bg-primary/5 border border-primary/10">
            <p className="text-xs font-bold text-primary mb-2 flex items-center gap-2">
              <MaterialIcon icon="support_agent" size="sm" />
              Suporte ao Administrador
            </p>
            <p className="text-[11px] text-stone-400 leading-relaxed mb-3">
              Problemas com chave de integracao ou certificado? Nossa equipe esta pronta para auxiliar.
            </p>
            <Button variant="secondary" size="sm" className="w-full">
              Abrir Chamado
            </Button>
          </div>
        </div>
      </div>

      {/* Mobile Save Button */}
      <div className="lg:hidden pt-4">
        <Button
          icon="save"
          loading={saving}
          onClick={handleSave}
          className="w-full"
          size="lg"
        >
          Salvar Alteracoes
        </Button>
      </div>
    </div>
  );
}
