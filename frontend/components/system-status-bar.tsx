"use client";

import { type SystemStatus } from "@/lib/use-system-status";
import { GlobalAlertBanner } from "@/components/ui/global-alert-banner";

type SystemStatusBarProps = {
  status: SystemStatus;
};

/**
 * Barra global de status do sistema.
 * Aparece automaticamente quando o sistema está degradado, unhealthy ou offline.
 * Não renderiza nada quando tudo está saudável.
 */
export function SystemStatusBar({ status }: SystemStatusBarProps) {
  if (status.overall === "healthy" || status.overall === "unknown") {
    return null;
  }

  if (status.offline) {
    return (
      <GlobalAlertBanner dismissible={false} tone="offline">
        <strong>Sem conexão.</strong> Você está offline. As operações serão retomadas quando a
        conexão for restabelecida.
      </GlobalAlertBanner>
    );
  }

  if (status.overall === "unhealthy") {
    return (
      <GlobalAlertBanner dismissible={false} tone="error">
        <strong>Sistema indisponível.</strong>{" "}
        {status.error ?? "O backend não está respondendo. Algumas funcionalidades podem não operar."}
      </GlobalAlertBanner>
    );
  }

  // Degraded — show which components are down
  const degradedComponents = Object.entries(status.components)
    .filter(([, c]) => c.status !== "healthy")
    .map(([name]) => name);

  const componentLabel =
    degradedComponents.length > 0
      ? ` Componentes afetados: ${degradedComponents.join(", ")}.`
      : "";

  return (
    <GlobalAlertBanner tone="warning">
      <strong>Modo degradado.</strong> O sistema está operando com capacidade reduzida.
      {componentLabel} O pipeline de IA pode estar mais lento ou indisponível.
    </GlobalAlertBanner>
  );
}
