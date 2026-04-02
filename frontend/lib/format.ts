export function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed);
}

export function humanize(value?: string | null) {
  if (!value) {
    return "--";
  }
  return value.replaceAll("_", " ");
}

export function toStringArray(value: unknown) {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}
