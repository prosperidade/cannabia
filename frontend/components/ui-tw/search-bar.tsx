"use client";

import { cn } from "@/lib/cn";
import { MaterialIcon } from "./material-icon";

export interface SearchBarProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  className?: string;
}

export function SearchBar({
  value,
  onChange,
  placeholder = "Buscar...",
  className,
}: SearchBarProps) {
  return (
    <div className={cn("relative", className)}>
      <div className="absolute left-4 top-1/2 -translate-y-1/2 text-stone-500">
        <MaterialIcon icon="search" size="md" />
      </div>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full glass-panel rounded-xl pl-12 pr-4 py-3 text-on-surface placeholder:text-stone-600 focus:border-primary-container focus:outline-none transition-colors"
      />
    </div>
  );
}
