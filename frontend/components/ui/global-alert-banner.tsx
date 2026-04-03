"use client";

import { useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

type BannerTone = "warning" | "error" | "info" | "offline";

type GlobalAlertBannerProps = {
  tone: BannerTone;
  children: ReactNode;
  dismissible?: boolean;
  icon?: string;
  /** Called when user dismisses */
  onDismiss?: () => void;
};

const defaultIcons: Record<BannerTone, string> = {
  warning: "⚠",
  error: "✕",
  info: "ℹ",
  offline: "⚡",
};

export function GlobalAlertBanner({
  tone,
  children,
  dismissible = true,
  icon,
  onDismiss,
}: GlobalAlertBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div
      aria-live="polite"
      className={cn("ds-alert-banner", `ds-alert-banner--${tone}`)}
      role="status"
    >
      <span aria-hidden="true" className="ds-alert-banner__icon">
        {icon ?? defaultIcons[tone]}
      </span>
      <span className="ds-alert-banner__text">{children}</span>
      {dismissible ? (
        <button
          aria-label="Fechar alerta"
          className="ds-alert-banner__dismiss"
          onClick={() => {
            setDismissed(true);
            onDismiss?.();
          }}
          type="button"
        >
          ✕
        </button>
      ) : null}
    </div>
  );
}
