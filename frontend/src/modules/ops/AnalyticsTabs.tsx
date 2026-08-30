import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Spinner } from "../../components/ui/Spinner";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface PopRow {
  group_by: string;
  key_id: string | null;
  name: string;
  plays: number;
  completed: number;
  completion_rate: number;
  devices_reached: number;
  first_play: string | null;
  last_play: string | null;
}

interface PerformanceRow {
  campaign_id: string;
  campaign_name: string;
  status: string;
  acknowledged: number;
  pending: number;
  failed: number;
  plays: number;
  completed_plays: number;
  completion_rate: number;
  devices_played: number;
}

interface UptimeRow {
  device_id: string;
  device_name: string;
  heartbeats: number;
  covered_seconds: number;
  window_seconds: number;
  uptime_pct: number;
}

function isoDaysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

/** Shared export buttons (P2-RPT-004) — hidden without reports.export. */
export function ExportButtons({
  report,
  filters,
}: {
  report: string;
  filters: Record<string, unknown>;
}) {
  const { hasPermission } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  if (!hasPermission("reports.export")) return null;

  async function run(format: "csv" | "xlsx") {
    setBusy(format);
    setError(null);
    try {
      await api.download("/reports/export", { report, format, filters });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Export failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <span className="flex items-center gap-2">
      {(["csv", "xlsx"] as const).map((format) => (
        <button
          key={format}
          type="button"
          disabled={busy !== null}
          onClick={() => run(format)}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium uppercase text-slate-600 disabled:opacity-50"
        >
          {busy === format ? "…" : `Export ${format}`}
        </button>
      ))}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </span>
  );
}

const DIMENSIONS = ["campaign", "asset", "device", "location"] as const;

/** P2-15 Proof-of-Play + P2-17 builder-lite (dimension + filters + export). */
export function ProofOfPlayTab() {
  const [groupBy, setGroupBy] = useState<string>("campaign");
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(7));
  const [dateTo, setDateTo] = useState(isoDaysAgo(0));

  const query = useQuery({
    queryKey: ["report-pop", groupBy, dateFrom, dateTo],
    queryFn: () =>
      api.get<PopRow[]>(
        `/reports/proof-of-play?group_by=${groupBy}&date_from=${dateFrom}&date_to=${dateTo}`,
      ),
  });
  const rows = query.data?.data ?? [];
  const filters = { group_by: groupBy, date_from: dateFrom, date_to: dateTo };

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="block text-sm">
          <span className="block text-xs text-slate-500">Dimension</span>
          <select
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value)}
            className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          >
            {DIMENSIONS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="block text-xs text-slate-500">From</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </label>
        <label className="block text-sm">
          <span className="block text-xs text-slate-500">To</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </label>
        <ExportButtons report="proof-of-play" filters={filters} />
      </div>

      {query.isLoading ? (
        <Spinner label="Loading proof of play…" />
      ) : rows.length === 0 ? (
        <p className="mt-4 rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          No playback events in this range.
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2 capitalize">{groupBy}</th>
                <th className="px-4 py-2">Plays</th>
                <th className="px-4 py-2">Completed</th>
                <th className="px-4 py-2">Completion</th>
                <th className="px-4 py-2">Devices</th>
                <th className="px-4 py-2">Last play</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.key_id ?? "none"}>
                  <td className="px-4 py-2 font-medium text-slate-800">{row.name}</td>
                  <td className="px-4 py-2 text-slate-600">{row.plays}</td>
                  <td className="px-4 py-2 text-emerald-700">{row.completed}</td>
                  <td className="px-4 py-2 text-slate-600">
                    {Math.round(row.completion_rate * 100)}%
                  </td>
                  <td className="px-4 py-2 text-slate-600">{row.devices_reached}</td>
                  <td className="px-4 py-2 text-slate-500">
                    {row.last_play ? new Date(row.last_play).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** P2-16 Campaign Analytics. */
export function CampaignAnalyticsTab() {
  const query = useQuery({
    queryKey: ["report-campaign-performance"],
    queryFn: () => api.get<PerformanceRow[]>("/reports/campaign-performance"),
  });
  const rows = query.data?.data ?? [];

  return (
    <div>
      <div className="flex justify-end">
        <ExportButtons report="campaign-performance" filters={{}} />
      </div>
      {query.isLoading ? (
        <Spinner label="Loading analytics…" />
      ) : rows.length === 0 ? (
        <p className="mt-4 rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          No campaign activity yet.
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">Campaign</th>
                <th className="px-4 py-2">Delivered</th>
                <th className="px-4 py-2">Pending</th>
                <th className="px-4 py-2">Failed</th>
                <th className="px-4 py-2">Plays</th>
                <th className="px-4 py-2">Completion</th>
                <th className="px-4 py-2">Devices played</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.campaign_id}>
                  <td className="px-4 py-2 font-medium text-slate-800">{row.campaign_name}</td>
                  <td className="px-4 py-2 text-emerald-700">{row.acknowledged}</td>
                  <td className="px-4 py-2 text-slate-600">{row.pending}</td>
                  <td className="px-4 py-2 text-red-600">{row.failed}</td>
                  <td className="px-4 py-2 text-slate-600">{row.plays}</td>
                  <td className="px-4 py-2 text-slate-600">
                    {Math.round(row.completion_rate * 100)}%
                  </td>
                  <td className="px-4 py-2 text-slate-600">{row.devices_played}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** P2-RPT-003 Device uptime from heartbeat windows. */
export function UptimeTab() {
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(7));
  const [dateTo, setDateTo] = useState(isoDaysAgo(0));
  const query = useQuery({
    queryKey: ["report-uptime", dateFrom, dateTo],
    queryFn: () =>
      api.get<UptimeRow[]>(
        `/reports/device-uptime?date_from=${dateFrom}&date_to=${dateTo}`,
      ),
  });
  const rows = query.data?.data ?? [];
  const filters = { date_from: dateFrom, date_to: dateTo };

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="block text-sm">
          <span className="block text-xs text-slate-500">From</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </label>
        <label className="block text-sm">
          <span className="block text-xs text-slate-500">To</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </label>
        <ExportButtons report="device-uptime" filters={filters} />
      </div>
      {query.isLoading ? (
        <Spinner label="Loading uptime…" />
      ) : (
        <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">Device</th>
                <th className="px-4 py-2">Uptime</th>
                <th className="px-4 py-2">Heartbeats</th>
                <th className="px-4 py-2">Covered</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.device_id}>
                  <td className="px-4 py-2 font-medium text-slate-800">{row.device_name}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`font-semibold ${
                        row.uptime_pct >= 99
                          ? "text-emerald-600"
                          : row.uptime_pct >= 90
                            ? "text-amber-600"
                            : "text-red-600"
                      }`}
                    >
                      {row.uptime_pct}%
                    </span>
                    <span className="ml-2 inline-block h-1.5 w-24 overflow-hidden rounded bg-slate-100 align-middle">
                      <span
                        className="block h-full bg-emerald-500"
                        style={{ width: `${Math.min(row.uptime_pct, 100)}%` }}
                      />
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{row.heartbeats}</td>
                  <td className="px-4 py-2 text-slate-500">
                    {Math.round(row.covered_seconds / 3600)}h /{" "}
                    {Math.round(row.window_seconds / 3600)}h
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
