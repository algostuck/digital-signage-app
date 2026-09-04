import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { DashboardRange, OrganizationDashboard, RangePreset } from "./types";

/** One query feeds every widget. The key carries the range so a range
 * change refetches, while the header bell keeps its own summary poll. */
export const dashboardKeys = {
  all: ["dashboard"] as const,
  organization: (from: string, to: string) => ["dashboard", "organization", from, to] as const,
};

export const DASHBOARD_POLL_MS = 30_000;

function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function daysAgo(n: number): Date {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d;
}

export function rangeForPreset(preset: RangePreset): DashboardRange {
  const today = isoDate(new Date());
  switch (preset) {
    case "today":
      return { preset, from: today, to: today };
    case "yesterday": {
      const y = isoDate(daysAgo(1));
      return { preset, from: y, to: y };
    }
    case "30d":
      return { preset, from: isoDate(daysAgo(29)), to: today };
    case "90d":
      return { preset, from: isoDate(daysAgo(89)), to: today };
    case "custom":
    case "7d":
    default:
      return { preset: preset === "custom" ? "custom" : "7d", from: isoDate(daysAgo(6)), to: today };
  }
}

export const PRESET_LABELS: Record<RangePreset, string> = {
  today: "Today",
  yesterday: "Yesterday",
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  "90d": "Last 90 days",
  custom: "Custom",
};

export function useDashboardRange() {
  const [range, setRange] = useState<DashboardRange>(() => rangeForPreset("7d"));
  const setPreset = useCallback((preset: RangePreset) => setRange(rangeForPreset(preset)), []);
  const setCustom = useCallback(
    (from: string, to: string) => setRange({ preset: "custom", from, to }),
    [],
  );
  return { range, setPreset, setCustom };
}

export function useOrganizationDashboard(range: DashboardRange) {
  const query = useQuery({
    queryKey: dashboardKeys.organization(range.from, range.to),
    queryFn: () =>
      api.get<OrganizationDashboard>(
        `/dashboard/organization?from=${range.from}&to=${range.to}`,
      ),
    refetchInterval: DASHBOARD_POLL_MS,
    // Keep the previous range on screen while the next one loads, so a
    // filter change never blanks the page.
    placeholderData: (previous) => previous,
  });
  const data = query.data?.data ?? null;
  return { data, query };
}

/** Refresh button: one call, all widgets. */
export function useDashboardRefresh() {
  const queryClient = useQueryClient();
  return useCallback(
    () => queryClient.invalidateQueries({ queryKey: dashboardKeys.all }),
    [queryClient],
  );
}

/** "Last updated 42 seconds ago" that re-renders on its own clock. */
export function useRelativeAge(iso: string | null | undefined, tickMs = 5_000): string | null {
  const [, force] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => force((n) => n + 1), tickMs);
    return () => window.clearInterval(id);
  }, [tickMs]);
  if (!iso) return null;
  const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return `${hours} h ago`;
}

export function pct(part: number, whole: number): number | null {
  return whole ? Math.round((part / whole) * 1000) / 10 : null;
}

export function formatCompact(n: number): string {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

export function minuteLabel(minute: number): string {
  const h = Math.floor(minute / 60) % 24;
  const m = minute % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}
