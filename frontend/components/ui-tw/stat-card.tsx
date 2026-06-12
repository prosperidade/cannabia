import { cn } from "@/lib/cn";
import { MaterialIcon } from "./material-icon";

export interface StatCardProps {
  icon: string;
  label: string;
  value: string | number;
  delta?: string;
  deltaType?: "up" | "down" | "neutral";
  className?: string;
}

const deltaColors = {
  up: "text-emerald-400",
  down: "text-error",
  neutral: "text-stone-400",
} as const;

const deltaIcons = {
  up: "trending_up",
  down: "trending_down",
  neutral: "trending_flat",
} as const;

export function StatCard({
  icon,
  label,
  value,
  delta,
  deltaType = "neutral",
  className,
}: StatCardProps) {
  return (
    <div className={cn("glass-panel rounded-2xl p-5 flex flex-col gap-3", className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10">
          <MaterialIcon icon={icon} size="lg" className="text-primary" />
        </div>
        {delta && (
          <div className={cn("flex items-center gap-1 text-xs font-bold", deltaColors[deltaType])}>
            <MaterialIcon icon={deltaIcons[deltaType]} size="sm" />
            <span>{delta}</span>
          </div>
        )}
      </div>
      <div>
        <p className="text-2xl font-black text-primary font-headline">{value}</p>
        <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mt-1">
          {label}
        </p>
      </div>
    </div>
  );
}
