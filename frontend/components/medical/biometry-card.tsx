"use client";

import type { VitalSigns } from "@/lib/types-medical";
import { Card, CardHeader } from "@/components/ui";
import { cn } from "@/lib/cn";

type BiometryCardProps = {
  vitals: VitalSigns;
  className?: string;
};

type VitalConfig = {
  key: keyof VitalSigns;
  label: string;
  unit: string;
  icon: string;
  format?: (v: number) => string;
  warn?: (v: number) => boolean;
  danger?: (v: number) => boolean;
};

const VITAL_CONFIG: VitalConfig[] = [
  {
    key: "bp_systolic",
    label: "PA Sistolica",
    unit: "mmHg",
    icon: "tenso",
    warn: (v) => v >= 130 || v < 90,
    danger: (v) => v >= 160 || v < 80,
  },
  {
    key: "bp_diastolic",
    label: "PA Diastolica",
    unit: "mmHg",
    icon: "tenso",
    warn: (v) => v >= 85 || v < 60,
    danger: (v) => v >= 100 || v < 50,
  },
  {
    key: "heart_rate",
    label: "FC",
    unit: "bpm",
    icon: "pulse",
    warn: (v) => v >= 100 || v < 55,
    danger: (v) => v >= 120 || v < 45,
  },
  {
    key: "spo2",
    label: "SpO2",
    unit: "%",
    icon: "o2",
    warn: (v) => v < 95,
    danger: (v) => v < 90,
  },
  {
    key: "temperature",
    label: "Temp.",
    unit: "°C",
    icon: "temp",
    format: (v) => v.toFixed(1),
    warn: (v) => v >= 37.5 || v < 35.5,
    danger: (v) => v >= 38.5 || v < 35,
  },
  {
    key: "respiratory_rate",
    label: "FR",
    unit: "irpm",
    icon: "resp",
    warn: (v) => v >= 20 || v < 12,
    danger: (v) => v >= 25 || v < 10,
  },
  {
    key: "pain_level",
    label: "Dor",
    unit: "/10",
    icon: "pain",
    warn: (v) => v >= 5,
    danger: (v) => v >= 8,
  },
];

function getTone(value: number, cfg: VitalConfig): "ok" | "warn" | "danger" {
  if (cfg.danger?.(value)) return "danger";
  if (cfg.warn?.(value)) return "warn";
  return "ok";
}

const ICON_MAP: Record<string, string> = {
  tenso: "\u2764\uFE0F\u200D\uD83E\uDE79",
  pulse: "\uD83D\uDC93",
  o2: "\uD83E\uDE78",
  temp: "\uD83C\uDF21\uFE0F",
  resp: "\uD83E\uDEC1",
  pain: "\u26A1",
};

export function BiometryCard({ vitals, className }: BiometryCardProps) {
  const bmi =
    vitals.bmi ??
    (vitals.weight_kg && vitals.height_cm
      ? +(vitals.weight_kg / (vitals.height_cm / 100) ** 2).toFixed(1)
      : null);

  return (
    <Card className={cn("ds-biometry", className)}>
      <CardHeader title="Biometria" subtitle="Sinais vitais do paciente" eyebrow="MONITORAMENTO" />

      <div className="ds-biometry__grid">
        {VITAL_CONFIG.map((cfg) => {
          const raw = vitals[cfg.key];
          if (raw == null) return null;
          const value = raw as number;
          const tone = getTone(value, cfg);
          const display = cfg.format ? cfg.format(value) : String(value);

          return (
            <div key={cfg.key} className={cn("ds-vital", `ds-vital--${tone}`)}>
              <span className="ds-vital__icon" aria-hidden="true">
                {ICON_MAP[cfg.icon] ?? ""}
              </span>
              <div className="ds-vital__body">
                <span className="ds-vital__label">{cfg.label}</span>
                <span className="ds-vital__value">
                  {display}
                  <small className="ds-vital__unit">{cfg.unit}</small>
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {vitals.weight_kg || vitals.height_cm || bmi ? (
        <div className="ds-biometry__anthro">
          {vitals.weight_kg ? (
            <div className="ds-anthro-item">
              <span className="ds-anthro-item__label">Peso</span>
              <strong>{vitals.weight_kg} kg</strong>
            </div>
          ) : null}
          {vitals.height_cm ? (
            <div className="ds-anthro-item">
              <span className="ds-anthro-item__label">Altura</span>
              <strong>{vitals.height_cm} cm</strong>
            </div>
          ) : null}
          {bmi ? (
            <div className="ds-anthro-item">
              <span className="ds-anthro-item__label">IMC</span>
              <strong
                className={cn(
                  bmi >= 30 && "ds-anthro-item--warn",
                  bmi >= 35 && "ds-anthro-item--danger",
                )}
              >
                {bmi}
              </strong>
            </div>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
