import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface BundleRow {
  id: string;
  name: string;
  version: number;
  group_id: string | null;
  state: string;
  expires_at: string | null;
  assets: number;
  devices: number;
  synced: number;
}

interface EdgeMetrics {
  bundles_by_state: Record<string, number>;
  published_coverage: { synced: number; pending: number };
  bandwidth_policy: { windows: { start: string; end: string }[]; concurrency: number };
}

const STATE_STYLE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600",
  published: "bg-emerald-100 text-emerald-700",
  expired: "bg-slate-100 text-slate-400",
};

/** P3-12/13 Offline Bundle Manager + edge delivery metrics: signed
 * prefetch packs with rollout coverage; downloads resume via Range. */
export function BundlesTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("devices.manage");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", group_id: "", ttl_days: "7" });

  const bundlesQuery = useQuery({
    queryKey: ["edge-bundles"],
    queryFn: () => api.get<BundleRow[]>("/edge/bundles"),
    retry: false,
  });
  const metricsQuery = useQuery({
    queryKey: ["edge-metrics"],
    queryFn: () => api.get<EdgeMetrics>("/edge/metrics"),
    retry: false,
  });
  const groupsQuery = useQuery({
    queryKey: ["device-groups"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/device-groups"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["edge-bundles"] });
    queryClient.invalidateQueries({ queryKey: ["edge-metrics"] });
  };
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const create = useMutation({
    mutationFn: () =>
      api.post("/edge/bundles", {
        name: form.name,
        group_id: form.group_id || null,
        ttl_days: Number(form.ttl_days),
      }),
    onSuccess: () => {
      refresh();
      setError(null);
      setForm({ name: "", group_id: "", ttl_days: "7" });
    },
    onError,
  });
  const publish = useMutation({
    mutationFn: (id: string) => api.post(`/edge/bundles/${id}/publish`, {}),
    onSuccess: () => refresh(),
    onError,
  });

  if (bundlesQuery.isError)
    return (
      <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
        {bundlesQuery.error instanceof ApiError
          ? bundlesQuery.error.message
          : "Edge bundles unavailable."}
      </p>
    );

  const bundles = bundlesQuery.data?.data ?? [];
  const metrics = metricsQuery.data?.data ?? null;
  const groups = groupsQuery.data?.data ?? [];

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <div className="space-y-6">
      {metrics && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs uppercase text-slate-400">Published bundles</p>
            <p className="text-xl font-semibold text-slate-900">
              {metrics.bundles_by_state.published ?? 0}
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs uppercase text-slate-400">Devices synced</p>
            <p className="text-xl font-semibold text-emerald-600">
              {metrics.published_coverage.synced}
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs uppercase text-slate-400">Downloads queued</p>
            <p className="text-xl font-semibold text-amber-600">
              {metrics.published_coverage.pending}
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs uppercase text-slate-400">Bandwidth window</p>
            <p className="text-sm font-medium text-slate-700">
              {metrics.bandwidth_policy.windows
                .map((w) => `${w.start}–${w.end}`)
                .join(", ")}{" "}
              · ×{metrics.bandwidth_policy.concurrency}
            </p>
          </div>
        </div>
      )}

      {canManage && (
        <form
          className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
          onSubmit={onCreate}
        >
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Bundle name</span>
            <input
              required
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              className="mt-0.5 w-52 rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Scope</span>
            <select
              value={form.group_id}
              onChange={(e) => setForm((p) => ({ ...p, group_id: e.target.value }))}
              className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
            >
              <option value="">All active devices</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Valid for (days)</span>
            <input
              type="number"
              min={1}
              max={90}
              value={form.ttl_days}
              onChange={(e) => setForm((p) => ({ ...p, ttl_days: e.target.value }))}
              className="mt-0.5 w-24 rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Build bundle
          </button>
        </form>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Offline bundles
        </h2>
        <p className="mt-0.5 text-xs text-slate-400">
          A bundle is a signed prefetch manifest built from the targets' live
          manifests — binaries stay in storage and downloads resume via HTTP
          Range. Publishing supersedes the previous bundle of the same scope.
        </p>
        <table className="mt-2 w-full text-left text-sm">
          <tbody>
            {bundles.length === 0 && (
              <tr>
                <td className="py-3 text-sm text-slate-400">No bundles yet.</td>
              </tr>
            )}
            {bundles.map((b) => (
              <tr key={b.id} className="border-t border-slate-100">
                <td className="py-2 pr-4 font-medium text-slate-800">
                  {b.name} <span className="font-mono text-xs text-slate-400">v{b.version}</span>
                </td>
                <td className="py-2 pr-4 text-xs text-slate-500">
                  {b.assets} asset{b.assets === 1 ? "" : "s"} · {b.synced}/{b.devices} synced
                  {b.expires_at &&
                    ` · expires ${new Date(b.expires_at).toLocaleDateString()}`}
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      STATE_STYLE[b.state] ?? ""
                    }`}
                  >
                    {b.state}
                  </span>
                </td>
                <td className="py-2">
                  {canManage && b.state === "draft" && (
                    <button
                      type="button"
                      onClick={() => publish.mutate(b.id)}
                      className="rounded-md bg-emerald-600 px-2 py-1 text-xs font-medium text-white"
                    >
                      Publish
                    </button>
                  )}
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
