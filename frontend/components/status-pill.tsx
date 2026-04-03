type StatusPillProps = {
  label: string;
  tone?: "neutral" | "ok" | "warn" | "danger" | "info";
};

const toneToLabel: Record<string, string> = {
  ok: "sucesso",
  warn: "atenção",
  danger: "erro",
  info: "informação",
  neutral: "",
};

export function StatusPill({ label, tone = "neutral" }: StatusPillProps) {
  const srPrefix = toneToLabel[tone];
  return (
    <span className={`status-pill tone-${tone}`} role="status">
      {srPrefix ? <span className="sr-only">{srPrefix}: </span> : null}
      {label}
    </span>
  );
}
