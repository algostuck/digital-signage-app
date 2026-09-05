import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../../lib/api";
import type { CalendarData, CalendarEvent, ScheduleConflict } from "../types";
import { isoDate } from "../types";
import { rangeFor, stepAnchor, tenantNow, type ViewMode } from "./dates";

/** Filters map 1:1 onto `GET /schedules/calendar` query parameters and
 * live in the URL, so a filtered view is a shareable link. */
export interface ScheduleFilters {
  location_id?: string;
  group_id?: string;
  campaign_id: string[];
  status: string[];
  kind?: "play" | "blackout";
  priority_min?: number;
  priority_max?: number;
  conflicts_only: boolean;
}

export const EMPTY_FILTERS: ScheduleFilters = { campaign_id: [], status: [], conflicts_only: false };

export function activeFilterCount(filters: ScheduleFilters): number {
  return (
    (filters.location_id ? 1 : 0) +
    (filters.group_id ? 1 : 0) +
    (filters.campaign_id.length ? 1 : 0) +
    (filters.status.length ? 1 : 0) +
    (filters.kind ? 1 : 0) +
    (filters.priority_min !== undefined || filters.priority_max !== undefined ? 1 : 0) +
    (filters.conflicts_only ? 1 : 0)
  );
}

export function filtersToQuery(filters: ScheduleFilters): string {
  const params = new URLSearchParams();
  if (filters.location_id) params.set("location_id", filters.location_id);
  if (filters.group_id) params.set("group_id", filters.group_id);
  filters.campaign_id.forEach((id) => params.append("campaign_id", id));
  filters.status.forEach((status) => params.append("status", status));
  if (filters.kind) params.set("kind", filters.kind);
  if (filters.priority_min !== undefined) params.set("priority_min", String(filters.priority_min));
  if (filters.priority_max !== undefined) params.set("priority_max", String(filters.priority_max));
  if (filters.conflicts_only) params.set("conflicts_only", "true");
  return params.toString();
}

function readFilters(params: URLSearchParams): ScheduleFilters {
  const int = (key: string) => {
    const raw = params.get(key);
    if (raw === null) return undefined;
    const value = Number.parseInt(raw, 10);
    return Number.isNaN(value) ? undefined : value;
  };
  const kind = params.get("kind");
  return {
    location_id: params.get("location_id") ?? undefined,
    group_id: params.get("group_id") ?? undefined,
    campaign_id: params.getAll("campaign_id"),
    status: params.getAll("status"),
    kind: kind === "play" || kind === "blackout" ? kind : undefined,
    priority_min: int("priority_min"),
    priority_max: int("priority_max"),
    conflicts_only: params.get("conflicts_only") === "true",
  };
}

function readView(params: URLSearchParams): ViewMode {
  const view = params.get("view");
  return view === "day" || view === "month" ? view : "week";
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export const CALENDAR_QUERY_KEY = "schedule-calendar";

/**
 * All workspace state in one place: view, anchor date, selected day,
 * filters (URL-backed), the calendar query for the visible range and a
 * tenant-zone clock corrected to the server's time.
 */
export function useScheduleWorkspace() {
  const [searchParams, setSearchParams] = useSearchParams();
  const view = readView(searchParams);
  const filters = useMemo(() => readFilters(searchParams), [searchParams]);
  const anchorParam = searchParams.get("date");
  const [localToday] = useState(() => isoDate(new Date()));
  const anchor = anchorParam && ISO_DATE.test(anchorParam) ? anchorParam : localToday;
  const [selectedDate, setSelectedDate] = useState<string>(anchor);

  const update = useCallback(
    (patch: { view?: ViewMode; date?: string; filters?: ScheduleFilters }) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          if (patch.view) next.set("view", patch.view);
          if (patch.date) next.set("date", patch.date);
          if (patch.filters) {
            for (const key of [
              "location_id",
              "group_id",
              "campaign_id",
              "status",
              "kind",
              "priority_min",
              "priority_max",
              "conflicts_only",
            ]) {
              next.delete(key);
            }
            const encoded = new URLSearchParams(filtersToQuery(patch.filters));
            encoded.forEach((value, key) => next.append(key, value));
          }
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const setView = useCallback((next: ViewMode) => update({ view: next }), [update]);
  const setAnchor = useCallback(
    (next: string) => {
      update({ date: next });
      setSelectedDate(next);
    },
    [update],
  );
  const setFilters = useCallback((next: ScheduleFilters) => update({ filters: next }), [update]);
  const step = useCallback(
    (direction: -1 | 1) => setAnchor(stepAnchor(view, anchor, direction)),
    [anchor, setAnchor, view],
  );

  const range = useMemo(() => rangeFor(view, anchor), [view, anchor]);
  const filterQuery = filtersToQuery(filters);
  const calendarQuery = useQuery({
    queryKey: [CALENDAR_QUERY_KEY, range.from, range.to, filterQuery],
    queryFn: () =>
      api.get<CalendarData>(
        `/schedules/calendar?from=${range.from}&to=${range.to}${filterQuery ? `&${filterQuery}` : ""}`,
      ),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });
  const calendar = calendarQuery.data?.data ?? null;

  // Tenant clock: the server tells us its instant and zone; we keep a
  // minute-resolution clock from there so "now" never depends on the
  // browser's zone or a drifting local clock.
  const timezone = calendar?.timezone ?? "UTC";
  const serverAt = calendar?.now?.at ?? null;
  const [offsetMs, setOffsetMs] = useState(0);
  useEffect(() => {
    if (serverAt) setOffsetMs(new Date(serverAt).getTime() - Date.now());
  }, [serverAt]);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 30_000);
    return () => window.clearInterval(id);
  }, []);
  const clock = useMemo(
    () => tenantNow(timezone, new Date(Date.now() + offsetMs)),
    // `tick` is the deliberate refresh trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [timezone, offsetMs, tick],
  );
  const today = calendar?.now?.date ?? clock.date;

  const goToday = useCallback(() => setAnchor(today), [setAnchor, today]);

  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const event of calendar?.events ?? []) {
      const list = map.get(event.date);
      if (list) list.push(event);
      else map.set(event.date, [event]);
    }
    for (const list of map.values()) {
      list.sort(
        (a, b) =>
          a.start_minute - b.start_minute ||
          b.campaign_priority - a.campaign_priority ||
          a.campaign_name.localeCompare(b.campaign_name),
      );
    }
    return map;
  }, [calendar?.events]);

  const conflictsById = useMemo(() => {
    const map = new Map<string, ScheduleConflict>();
    for (const conflict of calendar?.conflicts ?? []) map.set(conflict.id, conflict);
    return map;
  }, [calendar?.conflicts]);

  return {
    view,
    setView,
    anchor,
    setAnchor,
    step,
    goToday,
    selectedDate,
    setSelectedDate,
    filters,
    setFilters,
    range,
    calendarQuery,
    calendar,
    eventsByDate,
    conflictsById,
    timezone,
    today,
    nowMinute: clock.minute,
  };
}
