export function formatNumber(value: number, decimals = 2): string {
  if (!Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatMetricValue(
  value: number | boolean | string | null | undefined,
  unit?: string | null,
): string {
  if (value == null) return "—";
  if (typeof value === "boolean") return value ? "True" : "False";
  if (typeof value === "number") {
    const text = formatNumber(value);
    return unit ? `${text} ${unit}` : text;
  }
  return value;
}

export function formatDurationMs(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return "—";
  if (Math.abs(ms) < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function formatPercent(
  ratio: number | null | undefined,
  decimals = 1,
): string {
  if (ratio == null || !Number.isFinite(ratio)) return "—";
  return `${(ratio * 100).toFixed(decimals)}%`;
}

export function truncateId(
  id: string | null | undefined,
  prefixLength = 8,
  suffixLength = 4,
): string {
  if (!id) return "—";
  if (id.length <= prefixLength + suffixLength + 1) return id;
  const head = id.slice(0, prefixLength);
  const tail = id.slice(-suffixLength);
  return `${head}…${tail}`;
}

export function truncateHash(
  hash: string | null | undefined,
  length = 4,
): string {
  if (!hash) return "—";
  if (hash.length <= length * 2) return hash;
  return `${hash.slice(0, length)}…${hash.slice(-length)}`;
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatClockMs(ms: number): string {
  if (!Number.isFinite(ms)) return "—";
  return `${(ms / 1000).toFixed(3)}s`;
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return "just now";
  if (abs < 3600) return `${Math.round(abs / 60)}m ago`;
  if (abs < 86400) return `${Math.round(abs / 3600)}h ago`;
  if (abs < 172800) return "Yesterday";
  if (abs < 604800) return `${Math.round(abs / 86400)}d ago`;
  return formatTimestamp(iso);
}
