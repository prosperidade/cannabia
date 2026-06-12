"use client";

import { cn } from "@/lib/cn";

export interface ToggleSwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  className?: string;
}

export function ToggleSwitch({
  checked,
  onChange,
  label,
  disabled = false,
  className,
}: ToggleSwitchProps) {
  return (
    <label
      className={cn(
        "inline-flex items-center gap-3 select-none",
        disabled ? "opacity-50 pointer-events-none" : "cursor-pointer",
        className,
      )}
    >
      <div className="relative">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
          className="sr-only peer"
        />
        <div
          className={cn(
            "w-14 h-7 rounded-full transition-colors",
            "peer-checked:bg-primary/20 bg-surface-container-highest",
          )}
        />
        <div
          className={cn(
            "absolute top-0.5 left-1 h-6 w-6 rounded-full border border-gray-300 transition-all",
            "bg-primary-container",
            "peer-checked:translate-x-full peer-checked:translate-x-7",
            checked ? "translate-x-7" : "translate-x-0",
          )}
          style={{
            backgroundColor: "#A3C93A",
            transform: checked ? "translateX(28px)" : "translateX(0)",
            transition: "transform 200ms ease",
          }}
        />
      </div>
      {label && <span className="text-sm font-semibold text-on-surface">{label}</span>}
    </label>
  );
}
