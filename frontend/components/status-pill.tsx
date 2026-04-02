type StatusPillProps = {
  label: string;
  tone?: "neutral" | "ok" | "warn" | "danger" | "info";
};

export function StatusPill({ label, tone = "neutral" }: StatusPillProps) {
  return <span className={`status-pill tone-${tone}`}>{label}</span>;
}
