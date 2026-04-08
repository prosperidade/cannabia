"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useApiSession } from "@/lib/use-api-session";
import {
  Card,
  Badge,
  Button,
  Input,
  ToggleSwitch,
  MaterialIcon,
} from "@/components/ui-tw";

export default function SettingsPage() {
  const router = useRouter();
  const { loading, data: session } = useApiSession();

  // Notification preferences (local state only)
  const [notifEmail, setNotifEmail] = useState(true);
  const [notifWhatsApp, setNotifWhatsApp] = useState(true);
  const [notifRetornos, setNotifRetornos] = useState(true);
  const [notifAlertasIA, setNotifAlertasIA] = useState(false);

  // Password fields (UI only)
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMsg, setPasswordMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && (!session?.authenticated || !session.user)) {
      router.replace("/login");
    }
  }, [loading, session, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando...</p>
        </div>
      </div>
    );
  }

  if (!session?.authenticated || !session.user) {
    return null;
  }

  const user = session.user;

  function handlePasswordSave() {
    if (!oldPassword || !newPassword || !confirmPassword) {
      setPasswordMsg("Preencha todos os campos.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordMsg("As senhas nao coincidem.");
      return;
    }
    if (newPassword.length < 6) {
      setPasswordMsg("A nova senha deve ter pelo menos 6 caracteres.");
      return;
    }
    setPasswordMsg("Funcionalidade em desenvolvimento.");
    setOldPassword("");
    setNewPassword("");
    setConfirmPassword("");
  }

  return (
    <section className="p-4 md:p-8 space-y-8 overflow-y-auto pb-28 md:pb-8">
      {/* Page Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.push("/dashboard")}
          className="w-10 h-10 rounded-lg glass-panel flex items-center justify-center hover:bg-white/5 transition-colors"
        >
          <MaterialIcon icon="arrow_back" size="md" className="text-stone-400" />
        </button>
        <div>
          <h2 className="text-2xl md:text-3xl font-black text-on-surface font-headline tracking-tight">
            Configuracoes da Conta
          </h2>
          <p className="text-stone-500 font-medium text-sm">
            Gerencie seu perfil e preferencias
          </p>
        </div>
      </div>

      {/* User Info */}
      <Card variant="glass" padding="lg">
        <div className="flex items-center gap-4 mb-4">
          <MaterialIcon icon="person" size="lg" className="text-primary" />
          <h3 className="text-lg font-bold text-on-surface font-headline">
            Informacoes do Usuario
          </h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1">
            <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">
              Usuario
            </p>
            <p className="text-on-surface font-semibold">{user.username}</p>
          </div>
          <div className="space-y-1">
            <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">
              Papel
            </p>
            <Badge tone="primary">{user.role}</Badge>
          </div>
          {user.global_role && user.global_role !== user.role && (
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">
                Papel Global
              </p>
              <Badge tone="info">{user.global_role}</Badge>
            </div>
          )}
        </div>
      </Card>

      {/* Notification Preferences */}
      <Card variant="glass" padding="lg">
        <div className="flex items-center gap-4 mb-6">
          <MaterialIcon icon="notifications" size="lg" className="text-primary" />
          <h3 className="text-lg font-bold text-on-surface font-headline">
            Preferencias de Notificacao
          </h3>
        </div>
        <div className="space-y-5">
          <ToggleSwitch
            checked={notifEmail}
            onChange={setNotifEmail}
            label="Notificacoes por E-mail"
          />
          <ToggleSwitch
            checked={notifWhatsApp}
            onChange={setNotifWhatsApp}
            label="Notificacoes por WhatsApp"
          />
          <ToggleSwitch
            checked={notifRetornos}
            onChange={setNotifRetornos}
            label="Alertas de Retornos Pendentes"
          />
          <ToggleSwitch
            checked={notifAlertasIA}
            onChange={setNotifAlertasIA}
            label="Alertas de Recomendacoes da IA"
          />
        </div>
      </Card>

      {/* Theme */}
      <Card variant="glass" padding="lg">
        <div className="flex items-center gap-4 mb-4">
          <MaterialIcon icon="palette" size="lg" className="text-primary" />
          <h3 className="text-lg font-bold text-on-surface font-headline">
            Tema
          </h3>
        </div>
        <div className="flex items-center gap-3">
          <Badge tone="success">Tema Escuro</Badge>
          <span className="text-xs text-stone-500">Ativo</span>
        </div>
      </Card>

      {/* Change Password */}
      <Card variant="glass" padding="lg">
        <div className="flex items-center gap-4 mb-6">
          <MaterialIcon icon="lock" size="lg" className="text-primary" />
          <h3 className="text-lg font-bold text-on-surface font-headline">
            Alterar Senha
          </h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Input
            label="Senha Atual"
            type="password"
            icon="lock"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            placeholder="Digite a senha atual"
          />
          <Input
            label="Nova Senha"
            type="password"
            icon="key"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Digite a nova senha"
          />
          <Input
            label="Confirmar Nova Senha"
            type="password"
            icon="key"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Confirme a nova senha"
          />
        </div>
        {passwordMsg && (
          <p className="text-sm text-amber-400 mt-3">{passwordMsg}</p>
        )}
        <div className="mt-4">
          <Button icon="save" onClick={handlePasswordSave}>
            Salvar Senha
          </Button>
        </div>
      </Card>

      {/* Back link */}
      <div className="flex justify-start">
        <Button
          variant="ghost"
          icon="arrow_back"
          onClick={() => router.push("/dashboard")}
        >
          Voltar ao Dashboard
        </Button>
      </div>
    </section>
  );
}
