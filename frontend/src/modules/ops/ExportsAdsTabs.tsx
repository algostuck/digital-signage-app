import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { ExportButtons } from "./AnalyticsTabs";

interface ExportRow {
  id: string;
  name: string;
  dataset: string;
  state: string;
  last_run_at: string | null;
  last_error: string | null;
  last_object_key: string | null;
}

interface AdPerfRow {
  booking_id: string;
  advertiser: string;
  inventory: string | null;
  campaign: string | null;
  status: string;
  booked_units: number;
  delivered_billable: number;
  delivered_total: number;
  fill_rate_pct: number;
}

const DATASETS = ["playback_events", "analytics_aggregates", "ad_performance"];

/** P3-22 Analytics Data Export: scheduled dataset dumps to storage. */
export function ExportsTab() {
  const { hasPermission } = useAuth();
  const canExport = hasPermission("reports.export");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", dataset: "playback_events" });

  const exportsQuery = useQuery({
    queryKey: ["data-exports"],
    queryFn: () => api.get<ExportRow[]>("/data-exports"),
    enabled: canExport,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["data-exports"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const create = useMutation({
    mutationFn: () => api.post("/data-exports", { name: form.name, dataset: form.dataset }),
    onSuccess: () => {
      refresh();
      setError(null);
      setForm({ name: "", dataset: "playback_events" });
    },
    onError,
  });
  const run = useMutation({
    mutationFn: (id: string) => api.post(`/data-exports/${id}/run`, {}),
    onSuccess: () => refresh(),
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/data-exports/${id}`),
    onSuccess: () => refresh(),
    onError,
  });

  if (!canExport)
    return <p className="text-sm text-slate-500">Requires the reports.export permission.</p>;

  const rows = exportsQuery.data?.data ?? [];

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">
        Scheduled exports run nightly for the previous day and land as CSV in
        the platform object storage — the hand-off point to your own
        warehouse. "Run now" exports yesterday's window immediately.
      </p>
      <form
        className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
        onSubmit={onCreate}
      >
        <label className="block text-sm">
          <span className="block text-xs text-slate-500">Name</span>
          <input
            required
            value={form.name}
            onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            className="mt-0.5 w-56 rounded-md border border-slate-300 px-2 py-1.5"
          />
        </label>
        <label className="block text-sm">
          <span className="block text-xs text-slate-500">Dataset</span>
          <select
            value={form.dataset}
            onChange={(e) => setForm((p) => ({ ...p, dataset: e.target.value }))}
            className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
          >
            {DATASETS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={create.isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Create export
        </button>
      </form>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <table className="w-full text-left text-sm">
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td className="py-3 text-sm text-slate-400">No scheduled exports yet.</td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-slate-100 align-top">
                <td className="py-2 pr-4 font-medium text-slate-800">{row.name}</td>
                <td className="py-2 pr-4 font-mono text-xs">{row.dataset}</td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      row.state === "idle"
                        ? "bg-emerald-100 text-emerald-700"
                        : row.state === "error"
                          ? "bg-red-100 text-red-700"
                          : "bg-sky-100 text-sky-700"
                    }`}
                  >
                    {row.state}
                  </span>
                  {row.last_error && (
                    <p className="mt-0.5 max-w-xs truncate text-xs text-red-500">
                      {row.last_error}
                    </p>
                  )}
                </td>
                <td className="py-2 pr-4 text-xs text-slate-500">
                  {row.last_run_at
                    ? `last ${new Date(row.last_run_at).toLocaleString()}`
                    : "never run"}
                  {row.last_object_key && (
                    <p className="max-w-xs truncate font-mono">{row.last_object_key}</p>
                  )}
                </td>
                <td className="py-2">
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => run.mutate(row.id)}
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                    >
                      Run now
                    </button>
                    <button
                      type="button"
                      onClick={() => remove.mutate(row.id)}
                      className="rounded-md border border-red-300 px-2 py-1 text-xs font-medium text-red-600"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}

/** P3-11 Ad Performance: booked vs delivered vs fill rate (billing-ready). */
export function AdsReportTab() {
  const reportQuery = useQuery({
    queryKey: ["ad-performance"],
    queryFn: () => api.get<AdPerfRow[]>("/reports/ad-performance"),
    retry: false,
  });

  if (reportQuery.isError)
    return (
      <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
        Ad performance unavailable.
      </p>
    );

  const rows = reportQuery.data?.data ?? [];
  return (
    <div className="space-y-3">
      <ExportButtons report="ad-performance" filters={{}} />
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-xs uppercase text-slate-400">
              <th className="py-1.5 pr-4">Advertiser</th>
              <th className="py-1.5 pr-4">Slot / campaign</th>
              <th className="py-1.5 pr-4">Status</th>
              <th className="py-1.5 pr-4">Booked</th>
              <th className="py-1.5 pr-4">Delivered (billable)</th>
              <th className="py-1.5">Fill rate</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="py-3 text-sm text-slate-400">
                  No ad bookings yet.
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.booking_id} className="border-t border-slate-100">
                <td className="py-1.5 pr-4 font-medium text-slate-800">{row.advertiser}</td>
                <td className="py-1.5 pr-4 text-xs text-slate-500">
                  {row.inventory} · {row.campaign}
                </td>
                <td className="py-1.5 pr-4 text-xs">{row.status}</td>
                <td className="py-1.5 pr-4">{row.booked_units}</td>
                <td className="py-1.5 pr-4">{row.delivered_billable}</td>
                <td className="py-1.5 font-medium">
                  <span
                    className={
                      row.fill_rate_pct >= 100 ? "text-emerald-600" : "text-amber-600"
                    }
                  >
                    {row.fill_rate_pct}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
