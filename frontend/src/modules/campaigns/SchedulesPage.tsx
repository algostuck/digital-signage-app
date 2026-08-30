import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import {
  isoDate,
  minuteLabel,
  WEEKDAYS,
  type CalendarData,
  type CampaignSummary,
  type ConflictOverlap,
  type Schedule,
} from "./types";

function startOfWeek(base: Date): Date {
  const date = new Date(base);
  const day = (date.getDay() + 6) % 7; // Monday = 0
  date.setDate(date.getDate() - day);
  date.setHours(0, 0, 0, 0);
  return date;
}

function addDays(base: Date, days: number): Date {
  const date = new Date(base);
  date.setDate(date.getDate() + days);
  return date;
}

/** SCR-21 / P2-11 Schedule Calendar: week + month views, blackouts,
 * recurrence exceptions, conflict indicators. */
export function SchedulesPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("schedules.manage");
  const queryClient = useQueryClient();
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [view, setView] = useState<"week" | "month">("week");
  const [createOpen, setCreateOpen] = useState(false);

  // Month view spans 6 calendar weeks starting from the Monday on/before
  // the 1st; well inside the API's 62-day cap.
  const monthAnchor = new Date(weekStart.getFullYear(), weekStart.getMonth(), 1);
  const rangeStart = view === "week" ? weekStart : startOfWeek(monthAnchor);
  const rangeEnd = addDays(rangeStart, view === "week" ? 6 : 41);
  const calendarQuery = useQuery({
    queryKey: ["calendar", view, isoDate(rangeStart)],
    queryFn: () =>
      api.get<CalendarData>(
        `/schedules/calendar?from=${isoDate(rangeStart)}&to=${isoDate(rangeEnd)}`,
      ),
  });
  const schedulesQuery = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api.get<Schedule[]>("/schedules"),
  });
  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get<CampaignSummary[]>("/campaigns?page_size=100"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["calendar"] });
    queryClient.invalidateQueries({ queryKey: ["schedules"] });
    queryClient.invalidateQueries({ queryKey: ["campaigns"] });
  };

  const removeSchedule = useMutation({
    mutationFn: (id: string) => api.delete(`/schedules/${id}`),
    onSuccess: refresh,
    onError: (err) => window.alert(err instanceof ApiError ? err.message : "Delete failed"),
  });

  const calendar = calendarQuery.data?.data ?? null;
  const campaignsById = new Map(
    (campaignsQuery.data?.data ?? []).map((c) => [c.id, c] as const),
  );

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-slate-900">Schedule Calendar</h1>
        <div className="flex items-center gap-2">
          <div className="flex overflow-hidden rounded-md border border-slate-300" role="tablist">
            {(["week", "month"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                role="tab"
                aria-selected={view === mode}
                onClick={() => setView(mode)}
                className={`px-3 py-1.5 text-sm capitalize ${
                  view === mode ? "bg-slate-900 text-white" : "text-slate-600"
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setWeekStart((w) => addDays(w, view === "week" ? -7 : -28))}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600"
          >
            ← Prev
          </button>
          <span className="text-sm text-slate-600">
            {isoDate(rangeStart)} — {isoDate(rangeEnd)}
          </span>
          <button
            type="button"
            onClick={() => setWeekStart((w) => addDays(w, view === "week" ? 7 : 28))}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600"
          >
            Next →
          </button>
          {canManage && (
            <button
              type="button"
              onClick={() => setCreateOpen(true)}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
            >
              New schedule
            </button>
          )}
        </div>
      </div>

      {calendar && calendar.conflict_count > 0 && (
        <p className="mt-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
          {calendar.conflict_count} scheduling conflict{calendar.conflict_count === 1 ? "" : "s"}{" "}
          this week: overlapping windows at equal campaign priority. Adjust priorities or times.
        </p>
      )}

      {calendarQuery.isLoading ? (
        <Spinner label="Loading calendar…" />
      ) : (
        <div className="mt-4 grid grid-cols-7 gap-2">
          {Array.from({ length: view === "week" ? 7 : 42 }, (_, index) => {
            const day = addDays(rangeStart, index);
            const dayIso = isoDate(day);
            const inMonth = day.getMonth() === monthAnchor.getMonth();
            const events = (calendar?.events ?? [])
              .filter((e) => e.date === dayIso)
              .sort((a, b) => a.start_minute - b.start_minute);
            return (
              <div
                key={dayIso}
                className={`rounded-lg border border-slate-200 p-2 ${
                  view === "week" ? "min-h-40" : "min-h-24"
                } ${view === "month" && !inMonth ? "bg-slate-50 opacity-60" : "bg-white"}`}
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  {WEEKDAYS[index % 7]} <span className="font-normal">{day.getDate()}</span>
                </p>
                <div className="mt-1 space-y-1">
                  {events.map((event) => (
                    <div
                      key={`${event.schedule_id}-${event.date}`}
                      className={`rounded px-1.5 py-1 text-xs ${
                        event.kind === "blackout"
                          ? "bg-slate-800 text-slate-100"
                          : event.conflict
                            ? "border border-red-300 bg-red-50 text-red-800"
                            : "bg-slate-100 text-slate-700"
                      }`}
                      title={`${event.campaign_name} · priority ${event.campaign_priority}${
                        event.timezone ? ` · ${event.timezone}` : ""
                      }${event.kind === "blackout" ? " · blackout window" : ""}`}
                    >
                      <span className="font-medium">
                        {event.kind === "blackout" ? "⛔ " : ""}
                        {event.campaign_name}
                      </span>
                      {view === "week" && (
                        <>
                          <br />
                          {minuteLabel(event.start_minute)}–{minuteLabel(event.end_minute)}
                          {event.overnight ? "↦" : ""}
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <h2 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-400">
        All schedules
      </h2>
      {(schedulesQuery.data?.data ?? []).length === 0 ? (
        <p className="mt-2 rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
          No schedules yet.
        </p>
      ) : (
        <ul className="mt-2 space-y-1">
          {(schedulesQuery.data?.data ?? []).map((schedule) => (
            <li
              key={schedule.id}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm"
            >
              <span className="font-medium text-slate-800">
                {campaignsById.get(schedule.campaign_id)?.name ?? "…"}
              </span>
              {schedule.kind === "blackout" && (
                <span className="rounded bg-slate-800 px-1.5 py-0.5 text-xs font-medium text-white">
                  blackout
                </span>
              )}
              {schedule.name && <span className="text-slate-500">{schedule.name}</span>}
              <span className="text-slate-500">
                {schedule.start_date ?? "∞"} → {schedule.end_date ?? "∞"} ·{" "}
                {schedule.start_time?.slice(0, 5) ?? "00:00"}–
                {schedule.end_time?.slice(0, 5) ?? "24:00"}
              </span>
              {schedule.days_of_week && (
                <span className="text-slate-400">
                  {schedule.days_of_week.map((d) => WEEKDAYS[d]).join(" ")}
                </span>
              )}
              {schedule.recurrence_json?.days_of_month && (
                <span className="text-slate-400">
                  monthly: {schedule.recurrence_json.days_of_month.join(", ")}
                </span>
              )}
              {(schedule.exception_dates_json?.length ?? 0) > 0 && (
                <span className="text-slate-400">
                  {schedule.exception_dates_json!.length} exception
                  {schedule.exception_dates_json!.length === 1 ? "" : "s"}
                </span>
              )}
              {schedule.timezone && <span className="text-slate-400">{schedule.timezone}</span>}
              <span className="text-slate-400">p{schedule.priority}</span>
              {schedule.expired && (
                <span className="rounded bg-slate-200 px-1.5 text-xs text-slate-500">expired</span>
              )}
              {canManage && (
                <button
                  type="button"
                  onClick={() => removeSchedule.mutate(schedule.id)}
                  className="ml-auto text-xs font-medium text-red-600 hover:underline"
                >
                  Delete
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {createOpen && (
        <CreateScheduleModal
          campaigns={campaignsQuery.data?.data ?? []}
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            refresh();
            setCreateOpen(false);
          }}
        />
      )}
    </div>
  );
}

function CreateScheduleModal({
  campaigns,
  onClose,
  onCreated,
}: {
  campaigns: CampaignSummary[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [campaignId, setCampaignId] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"play" | "blackout">("play");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [days, setDays] = useState<number[]>([]);
  const [monthDays, setMonthDays] = useState("");
  const [exceptions, setExceptions] = useState("");
  const [timezone, setTimezone] = useState("");
  const [priority, setPriority] = useState("50");
  const [error, setError] = useState<string | null>(null);
  const [conflictResult, setConflictResult] = useState<{
    overlaps: ConflictOverlap[];
    conflict_count: number;
  } | null>(null);

  function payload() {
    const parsedMonthDays = monthDays
      .split(",")
      .map((part) => Number.parseInt(part.trim(), 10))
      .filter((n) => !Number.isNaN(n));
    const parsedExceptions = exceptions
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    return {
      campaign_id: campaignId,
      kind,
      start_date: startDate || null,
      end_date: endDate || null,
      start_time: startTime || null,
      end_time: endTime || null,
      days_of_week: days.length ? days : null,
      recurrence_json: parsedMonthDays.length ? { days_of_month: parsedMonthDays } : null,
      exception_dates_json: parsedExceptions.length ? parsedExceptions : null,
      timezone: timezone || null,
      priority: Number(priority) || 50,
    };
  }

  const create = useMutation({
    mutationFn: () => api.post("/schedules", { ...payload(), name: name || null }),
    onSuccess: onCreated,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create schedule"),
  });

  const checkConflicts = useMutation({
    mutationFn: () =>
      api.post<{ overlaps: ConflictOverlap[]; conflict_count: number }>(
        "/schedules/conflicts",
        payload(),
      ),
    onSuccess: (envelope) => {
      setConflictResult(envelope.data!);
      setError(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Conflict check failed"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!campaignId) {
      setError("Choose a campaign");
      return;
    }
    setError(null);
    create.mutate();
  }

  function toggleDay(day: number) {
    setDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort(),
    );
  }

  return (
    <Modal title="New schedule" open onClose={onClose}>
      <form className="space-y-3" onSubmit={onSubmit}>
        <div>
          <label htmlFor="schedule-campaign" className="block text-sm font-medium text-slate-700">
            Campaign
          </label>
          <select
            id="schedule-campaign"
            value={campaignId}
            onChange={(e) => setCampaignId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">— choose —</option>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} (p{c.priority})
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Label (optional)">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input-base"
            />
          </Field>
          <div>
            <label htmlFor="schedule-kind" className="block text-sm font-medium text-slate-700">
              Kind
            </label>
            <select
              id="schedule-kind"
              value={kind}
              onChange={(e) => setKind(e.target.value as "play" | "blackout")}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="play">Play window</option>
              <option value="blackout">Blackout (suppress campaign)</option>
            </select>
          </div>
          <Field label="Priority">
            <input
              type="number"
              min={1}
              max={100}
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="input-base"
            />
          </Field>
          <Field label="Days of month (e.g. 1, 15 — empty = any)">
            <input
              value={monthDays}
              onChange={(e) => setMonthDays(e.target.value)}
              placeholder="1, 15"
              className="input-base"
            />
          </Field>
          <Field label="Start date">
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="input-base"
            />
          </Field>
          <Field label="End date">
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="input-base"
            />
          </Field>
          <Field label="Daily from">
            <input
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="input-base"
            />
          </Field>
          <Field label="Daily until">
            <input
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className="input-base"
            />
          </Field>
        </div>
        <div>
          <span className="block text-sm font-medium text-slate-700">Days (empty = every day)</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {WEEKDAYS.map((label, index) => (
              <button
                key={label}
                type="button"
                onClick={() => toggleDay(index)}
                aria-pressed={days.includes(index)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                  days.includes(index)
                    ? "bg-slate-900 text-white"
                    : "border border-slate-300 text-slate-600"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <Field label="Exception dates (ISO, comma-separated — skipped days)">
          <input
            value={exceptions}
            onChange={(e) => setExceptions(e.target.value)}
            placeholder="2026-12-25, 2027-01-01"
            className="input-base"
          />
        </Field>
        <Field label="Timezone (IANA, empty = inherit device/location/org)">
          <input
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            placeholder="e.g. Asia/Kolkata"
            className="input-base"
          />
        </Field>
        {conflictResult && (
          <div
            className={`rounded-md px-3 py-2 text-sm ${
              conflictResult.conflict_count > 0
                ? "bg-red-50 text-red-800"
                : "bg-emerald-50 text-emerald-800"
            }`}
          >
            {conflictResult.overlaps.length === 0 ? (
              "No overlaps with other campaigns in the checked range."
            ) : (
              <>
                <p className="font-medium">
                  {conflictResult.overlaps.length} overlap
                  {conflictResult.overlaps.length === 1 ? "" : "s"}
                  {conflictResult.conflict_count > 0 &&
                    ` — ${conflictResult.conflict_count} at equal priority`}
                </p>
                <ul className="mt-1 space-y-0.5 text-xs">
                  {conflictResult.overlaps.slice(0, 5).map((row, index) => (
                    <li key={index}>
                      {row.date} {minuteLabel(row.window[0])}–{minuteLabel(row.window[1])} vs{" "}
                      {row.campaigns
                        .map((c) => c.campaign_name)
                        .filter((n, i, all) => all.indexOf(n) === i)
                        .join(" / ")}{" "}
                      → winner: <span className="font-medium">{row.winner_campaign_name}</span>
                      {row.conflict ? " (conflict)" : ""}
                    </li>
                  ))}
                  {conflictResult.overlaps.length > 5 && (
                    <li>… and {conflictResult.overlaps.length - 5} more</li>
                  )}
                </ul>
              </>
            )}
          </div>
        )}
        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={checkConflicts.isPending || !campaignId}
            onClick={() => checkConflicts.mutate()}
            className="rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-800 disabled:opacity-50"
          >
            {checkConflicts.isPending ? "Checking…" : "Check conflicts"}
          </button>
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create schedule"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700">{label}</label>
      <div className="mt-1 [&>input]:block [&>input]:w-full [&>input]:rounded-md [&>input]:border [&>input]:border-slate-300 [&>input]:px-3 [&>input]:py-2 [&>input]:text-sm">
        {children}
      </div>
    </div>
  );
}
