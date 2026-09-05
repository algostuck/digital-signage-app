import dayjs from "dayjs";

/**
 * Civil-date helpers for the schedule workspace.
 *
 * The calendar works in *tenant wall-clock* terms: dates are YYYY-MM-DD
 * strings and times are minutes-of-day, exactly as the API returns them.
 * The browser's own timezone never enters the arithmetic; "today" and
 * "now" come from the server clock projected into the tenant zone
 * (`tenantNow`). dayjs is only used for civil-date arithmetic on those
 * strings.
 */

export type ViewMode = "day" | "week" | "month";

export const DAY_MINUTES = 1440;

export function addDays(iso: string, days: number): string {
  return dayjs(iso).add(days, "day").format("YYYY-MM-DD");
}

/** Monday on or before the date. */
export function startOfWeek(iso: string): string {
  const d = dayjs(iso);
  const offset = (d.day() + 6) % 7;
  return d.subtract(offset, "day").format("YYYY-MM-DD");
}

export function startOfMonth(iso: string): string {
  return dayjs(iso).startOf("month").format("YYYY-MM-DD");
}

export function daysBetween(from: string, to: string): string[] {
  const days: string[] = [];
  let cursor = from;
  while (cursor <= to) {
    days.push(cursor);
    cursor = addDays(cursor, 1);
  }
  return days;
}

/** The API range for a view anchored on a date. Month = the six-week grid
 * (Monday before the 1st → 41 days later), inside the API's 62-day cap. */
export function rangeFor(view: ViewMode, anchor: string): { from: string; to: string } {
  if (view === "day") return { from: anchor, to: anchor };
  if (view === "week") {
    const from = startOfWeek(anchor);
    return { from, to: addDays(from, 6) };
  }
  const from = startOfWeek(startOfMonth(anchor));
  return { from, to: addDays(from, 41) };
}

export function stepAnchor(view: ViewMode, anchor: string, direction: -1 | 1): string {
  if (view === "day") return addDays(anchor, direction);
  if (view === "week") return addDays(anchor, 7 * direction);
  return dayjs(anchor).add(direction, "month").format("YYYY-MM-DD");
}

export function sameMonth(iso: string, anchor: string): boolean {
  return iso.slice(0, 7) === anchor.slice(0, 7);
}

export function formatDayLong(iso: string): string {
  return dayjs(iso).format("dddd, D MMMM YYYY");
}

export function formatDayShort(iso: string): string {
  return dayjs(iso).format("ddd D MMM");
}

export function weekdayShort(iso: string): string {
  return dayjs(iso).format("ddd");
}

export function dayNumber(iso: string): number {
  return dayjs(iso).date();
}

/** Human range for the header: "31 Aug – 6 Sep 2026", "September 2026",
 * "Saturday, 5 September 2026". */
export function formatRangeLabel(view: ViewMode, anchor: string): string {
  if (view === "day") return formatDayLong(anchor);
  if (view === "month") return dayjs(anchor).format("MMMM YYYY");
  const { from, to } = rangeFor("week", anchor);
  const a = dayjs(from);
  const b = dayjs(to);
  if (a.month() === b.month()) return `${a.format("D")} – ${b.format("D MMM YYYY")}`;
  if (a.year() === b.year()) return `${a.format("D MMM")} – ${b.format("D MMM YYYY")}`;
  return `${a.format("D MMM YYYY")} – ${b.format("D MMM YYYY")}`;
}

export function minuteLabel(minute: number): string {
  const clamped = Math.max(0, Math.min(DAY_MINUTES, minute));
  const h = Math.floor(clamped / 60) % 24;
  const m = clamped % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function windowLabel(start: number, end: number, overnight = false): string {
  return `${minuteLabel(start)}–${end >= DAY_MINUTES ? "24:00" : minuteLabel(end)}${overnight ? " ↦" : ""}`;
}

export function durationLabel(start: number, end: number): string {
  const minutes = Math.max(0, end - start);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

/** "HH:MM" or "HH:MM:SS" → minutes-of-day. */
export function timeToMinute(time: string | null | undefined, fallback: number): number {
  if (!time) return fallback;
  const [h, m] = time.split(":").map((part) => Number.parseInt(part, 10));
  if (Number.isNaN(h) || Number.isNaN(m)) return fallback;
  return h * 60 + m;
}

/** Current civil date + minute in an IANA zone, from an instant. */
export function tenantNow(timezone: string, at: Date = new Date()): { date: string; minute: number } {
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(at);
    const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "00";
    return {
      date: `${get("year")}-${get("month")}-${get("day")}`,
      minute: Number.parseInt(get("hour"), 10) * 60 + Number.parseInt(get("minute"), 10),
    };
  } catch {
    // Unknown zone: fall back to the browser clock rather than blanking the page.
    return {
      date: dayjs(at).format("YYYY-MM-DD"),
      minute: at.getHours() * 60 + at.getMinutes(),
    };
  }
}
