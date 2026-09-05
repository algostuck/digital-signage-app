import dayjs from "dayjs";

/**
 * The one formatting module (docs/design-system/DESIGN_TOKENS.md and
 * ANTD_REFERENCE_ANALYSIS.md §3.6). Every date, number, size and
 * percentage shown to the user passes through here so the whole product
 * writes them the same way.
 *
 * Dates are rendered in the viewer's locale calendar; schedule wall-clock
 * values (which are tenant-zone minutes) have their own helpers in the
 * schedule module and never go through `Date`.
 */

export const EMPTY_VALUE = "—";

type DateInput = string | number | Date | null | undefined;

function toDate(value: DateInput): Date | null {
  if (value === null || value === undefined || value === "") return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "5 Sep 2026" */
export function formatDate(value: DateInput): string {
  const d = toDate(value);
  return d ? dayjs(d).format("D MMM YYYY") : EMPTY_VALUE;
}

/** "5 Sep 2026, 14:08" */
export function formatDateTime(value: DateInput): string {
  const d = toDate(value);
  return d ? dayjs(d).format("D MMM YYYY, HH:mm") : EMPTY_VALUE;
}

/** "14:08" */
export function formatTime(value: DateInput): string {
  const d = toDate(value);
  return d ? dayjs(d).format("HH:mm") : EMPTY_VALUE;
}

/** "Sep 5" — compact axis / chip label. */
export function formatDayShort(value: DateInput): string {
  const d = toDate(value);
  return d ? dayjs(d).format("D MMM") : EMPTY_VALUE;
}

/**
 * Relative time inside 24 hours ("just now", "12 min ago", "3 h ago"),
 * then the date. Pair with a Tooltip carrying formatDateTime().
 */
export function formatRelative(value: DateInput, now: Date = new Date()): string {
  const d = toDate(value);
  if (!d) return EMPTY_VALUE;
  const diffMs = now.getTime() - d.getTime();
  const future = diffMs < 0;
  const abs = Math.abs(diffMs);
  const minutes = Math.round(abs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return future ? `in ${minutes} min` : `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return future ? `in ${hours} h` : `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return future ? `in ${days} d` : `${days} d ago`;
  return formatDate(d);
}

/** "12,345" — thousands separators, no decimals unless given. */
export function formatNumber(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY_VALUE;
  return value.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/** "1.2M", "45K" for dense KPI surfaces. */
export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY_VALUE;
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

/** "12.3%" */
export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY_VALUE;
  return `${value.toFixed(decimals)}%`;
}

/** "512 MB" */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return EMPTY_VALUE;
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value < 10 && unit > 0 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

/** "1 h 30 min", "45 s" */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return EMPTY_VALUE;
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? `${h} h ${rest} min` : `${h} h`;
}

/** "12/30" progress fraction. */
export function formatFraction(done: number, total: number): string {
  return `${formatNumber(done)}/${formatNumber(total)}`;
}

/** Currency with symbol + grouped number (INR by default for the demo estate). */
export function formatCurrency(value: number | null | undefined, currency = "INR"): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY_VALUE;
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
}
