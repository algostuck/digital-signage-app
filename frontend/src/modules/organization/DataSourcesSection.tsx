import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface DataSourceRow {
  id: string;
  name: string;
  type: string;
  endpoint: string;
  auth_header: string | null;
  auth_token_ref: string | null;
  cache_ttl_seconds: number;
  refresh_seconds: number;
  state: string;
  last_ok_at: string | null;
  last_error: string | null;
  schema: { required: string[] } | null;
}

interface TestResult {
  ok: boolean;
  error: string | null;
  sample: unknown;
}

const STATE_STYLE: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  error: "bg-red-100 text-red-700",
  paused: "bg-slate-100 text-slate-500",
};

/** P3-03 Data Source Manager: guarded external feeds for dynamic widgets.
 * Credentials never leave the server — sources reference an env-var NAME. */
export function DataSourcesSection() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("settings.manage");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [testResult, setTestResult] = useState<{ id: string; result: TestResult } | null>(null);
  const [form, setForm] = useState({
    name: "",
    type: "rest_json",
    endpoint: "",
    auth_header: "",
    auth_token_ref: "",
    cache_ttl_seconds: "300",
    refresh_seconds: "900",
    required_paths: "",
  });

  const sourcesQuery = useQuery({
    queryKey: ["data-sources"],
    queryFn: () => api.get<DataSourceRow[]>("/data-sources"),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["data-sources"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const create = useMutation({
    mutationFn: () => {
      const required = form.required_paths
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);
      return api.post("/data-sources", {
        name: form.name,
        type: form.type,
        endpoint: form.endpoint,
        auth_header: form.auth_header || null,
        auth_token_ref: form.auth_token_ref || null,
        cache_ttl_seconds: Number(form.cache_ttl_seconds),
        refresh_seconds: Number(form.refresh_seconds),
        schema_spec: required.length ? { required } : null,
      });
    },
    onSuccess: () => {
      refresh();
      setError(null);
      setCreateOpen(false);
      setForm({
        name: "", type: "rest_json", endpoint: "", auth_header: "",
        auth_token_ref: "", cache_ttl_seconds: "300", refresh_seconds: "900",
        required_paths: "",
      });
    },
    onError,
  });
  const test = useMutation({
    mutationFn: (id: string) => api.post<TestResult>(`/data-sources/${id}/test`, {}),
    onSuccess: (envelope, id) => setTestResult({ id, result: envelope.data! }),
    onError,
  });
  const refreshNow = useMutation({
    mutationFn: (id: string) => api.post(`/data-sources/${id}/refresh`, {}),
    onSuccess: () => refresh(),
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/data-sources/${id}`),
    onSuccess: () => refresh(),
    onError,
  });

  const sources = sourcesQuery.data?.data ?? [];

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <div className="mt-8">
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Data sources
            </h2>
            <p className="mt-0.5 text-xs text-slate-400">
              Live REST/JSON and RSS feeds for dynamic widgets. Fetched
              server-side with SSRF guards; devices only receive validated
              snapshots — a downed feed degrades to last-known-good, then to
              the widget fallback.
            </p>
          </div>
          {canManage && (
            <button
              type="button"
              onClick={() => setCreateOpen((v) => !v)}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
            >
              {createOpen ? "Close" : "Add source"}
            </button>
          )}
        </div>

        {createOpen && (
          <form
            className="mt-3 grid grid-cols-1 gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 sm:grid-cols-3"
            onSubmit={onCreate}
          >
            {(
              [
                ["name", "Name", "text", ""],
                ["endpoint", "Endpoint URL (https)", "url", ""],
                ["auth_header", "Auth header (optional)", "text", "Authorization"],
                ["auth_token_ref", "Token env-var NAME (optional)", "text", "DS_FEED_TOKEN"],
                ["cache_ttl_seconds", "Cache TTL (s)", "number", ""],
                ["refresh_seconds", "Refresh every (s)", "number", ""],
              ] as const
            ).map(([key, label, type, placeholder]) => (
              <label key={key} className="block text-sm">
                <span className="block text-xs text-slate-500">{label}</span>
                <input
                  type={type}
                  required={key === "name" || key === "endpoint"}
                  value={form[key]}
                  placeholder={placeholder}
                  onChange={(e) => setForm((p) => ({ ...p, [key]: e.target.value }))}
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
                />
              </label>
            ))}
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">Type</span>
              <select
                value={form.type}
                onChange={(e) => setForm((p) => ({ ...p, type: e.target.value }))}
                className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
              >
                <option value="rest_json">REST / JSON</option>
                <option value="rss">RSS / Atom</option>
              </select>
            </label>
            <label className="block text-sm sm:col-span-2">
              <span className="block text-xs text-slate-500">
                Required paths (schema, comma-separated — e.g. city, items)
              </span>
              <input
                value={form.required_paths}
                onChange={(e) => setForm((p) => ({ ...p, required_paths: e.target.value }))}
                className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
              />
            </label>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={create.isPending}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                Create source
              </button>
            </div>
          </form>
        )}

        <table className="mt-3 w-full text-left text-sm">
          <thead>
            <tr className="text-xs uppercase text-slate-400">
              <th className="py-1.5 pr-4">Name</th>
              <th className="py-1.5 pr-4">Type</th>
              <th className="py-1.5 pr-4">Endpoint</th>
              <th className="py-1.5 pr-4">Health</th>
              {canManage && <th className="py-1.5">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {sources.length === 0 && (
              <tr>
                <td colSpan={5} className="py-3 text-sm text-slate-400">
                  No data sources yet.
                </td>
              </tr>
            )}
            {sources.map((s) => (
              <tr key={s.id} className="border-t border-slate-100 align-top">
                <td className="py-2 pr-4 font-medium text-slate-800">{s.name}</td>
                <td className="py-2 pr-4 text-xs">{s.type}</td>
                <td className="max-w-xs truncate py-2 pr-4 font-mono text-xs">{s.endpoint}</td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      STATE_STYLE[s.state] ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {s.state}
                  </span>
                  {s.last_error && (
                    <p className="mt-0.5 max-w-xs truncate text-xs text-red-500">
                      {s.last_error}
                    </p>
                  )}
                </td>
                {canManage && (
                  <td className="py-2">
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => test.mutate(s.id)}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                      >
                        Test
                      </button>
                      <button
                        type="button"
                        onClick={() => refreshNow.mutate(s.id)}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                      >
                        Refresh
                      </button>
                      <button
                        type="button"
                        onClick={() => remove.mutate(s.id)}
                        className="rounded-md border border-red-300 px-2 py-1 text-xs font-medium text-red-600"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>

        {testResult && (
          <div
            className={`mt-3 rounded-md px-3 py-2 text-sm ${
              testResult.result.ok
                ? "bg-emerald-50 text-emerald-800"
                : "bg-red-50 text-red-700"
            }`}
          >
            <p className="font-medium">
              Test {testResult.result.ok ? "passed" : "failed"}
              {testResult.result.error && ` — ${testResult.result.error}`}
            </p>
            {testResult.result.sample != null && (
              <pre className="mt-1 max-h-40 overflow-auto rounded bg-white/60 p-2 font-mono text-xs">
                {JSON.stringify(testResult.result.sample, null, 2)}
              </pre>
            )}
          </div>
        )}

        {error && (
          <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
      </section>
    </div>
  );
}
