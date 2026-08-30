import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { CampaignSummary } from "./types";

interface ExperimentRow {
  id: string;
  campaign_id: string;
  name: string;
  status: string;
  start_at: string | null;
  end_at: string | null;
  control_pct: number;
  arms: { variant_id: string; allocation_pct: number }[];
}

interface ResultArm {
  arm: string;
  variant_id: string | null;
  devices: number;
  playback_count: number;
}

interface VariantRow {
  id: string;
  name: string;
}

interface CampaignDetail {
  id: string;
  variants: VariantRow[];
}

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600",
  running: "bg-emerald-100 text-emerald-700",
  completed: "bg-sky-100 text-sky-700",
};

/** P3-06 Experiment Manager: A/B arms over campaign variants with stable
 * per-device assignment and per-arm results. */
export function ExperimentsTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("campaigns.manage");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ campaign_id: "", name: "", variant_id: "", pct: "50" });
  const [resultsFor, setResultsFor] = useState<string | null>(null);

  const experimentsQuery = useQuery({
    queryKey: ["experiments"],
    queryFn: () => api.get<ExperimentRow[]>("/experiments"),
    retry: false,
  });
  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get<CampaignSummary[]>("/campaigns?page_size=100"),
  });
  const campaignDetailQuery = useQuery({
    queryKey: ["campaign-detail", form.campaign_id],
    queryFn: () => api.get<CampaignDetail>(`/campaigns/${form.campaign_id}`),
    enabled: !!form.campaign_id,
  });
  const resultsQuery = useQuery({
    queryKey: ["experiment-results", resultsFor],
    queryFn: () =>
      api.get<{ control_pct: number; arms: ResultArm[] }>(
        `/experiments/${resultsFor}/results`,
      ),
    enabled: resultsFor != null,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["experiments"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const create = useMutation({
    mutationFn: () =>
      api.post("/experiments", {
        campaign_id: form.campaign_id,
        name: form.name,
        arms: [{ variant_id: form.variant_id, allocation_pct: Number(form.pct) }],
      }),
    onSuccess: () => {
      refresh();
      setError(null);
      setForm({ campaign_id: "", name: "", variant_id: "", pct: "50" });
    },
    onError,
  });
  const transition = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "start" | "stop" }) =>
      api.post(`/experiments/${id}/transition`, { action }),
    onSuccess: () => refresh(),
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/experiments/${id}`),
    onSuccess: () => refresh(),
    onError,
  });

  if (experimentsQuery.isError)
    return (
      <p className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
        {experimentsQuery.error instanceof ApiError
          ? experimentsQuery.error.message
          : "Experiments unavailable."}
      </p>
    );

  const experiments = experimentsQuery.data?.data ?? [];
  const campaigns = campaignsQuery.data?.data ?? [];
  const variants = campaignDetailQuery.data?.data?.variants ?? [];
  const campaignName = (id: string) => campaigns.find((c) => c.id === id)?.name ?? id.slice(0, 8);

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <div className="mt-4 space-y-6">
      <p className="text-xs text-slate-400">
        An experiment A/B-tests a campaign's variants: each device lands in a
        stable arm (same device, same arm, always); the remainder plays the
        base creative as control. Stopping reverts every device instantly.
      </p>

      {canManage && (
        <form
          className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
          onSubmit={onCreate}
        >
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Campaign</span>
            <select
              required
              value={form.campaign_id}
              onChange={(e) =>
                setForm((p) => ({ ...p, campaign_id: e.target.value, variant_id: "" }))
              }
              className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
            >
              <option value="">Select…</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Variant (arm B)</span>
            <select
              required
              value={form.variant_id}
              onChange={(e) => setForm((p) => ({ ...p, variant_id: e.target.value }))}
              className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
            >
              <option value="">Select…</option>
              {variants.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Allocation %</span>
            <input
              type="number"
              min={1}
              max={100}
              value={form.pct}
              onChange={(e) => setForm((p) => ({ ...p, pct: e.target.value }))}
              className="mt-0.5 w-20 rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Name</span>
            <input
              required
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              className="mt-0.5 w-48 rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Create experiment
          </button>
        </form>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Experiments
        </h2>
        <table className="mt-2 w-full text-left text-sm">
          <tbody>
            {experiments.length === 0 && (
              <tr>
                <td className="py-3 text-sm text-slate-400">No experiments yet.</td>
              </tr>
            )}
            {experiments.map((exp) => (
              <tr key={exp.id} className="border-t border-slate-100">
                <td className="py-2 pr-4 font-medium text-slate-800">{exp.name}</td>
                <td className="py-2 pr-4 text-xs text-slate-500">
                  {campaignName(exp.campaign_id)} · control {exp.control_pct}%
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      STATUS_STYLE[exp.status] ?? ""
                    }`}
                  >
                    {exp.status}
                  </span>
                </td>
                <td className="py-2">
                  <div className="flex items-center gap-1.5">
                    {canManage && exp.status === "draft" && (
                      <button
                        type="button"
                        onClick={() => transition.mutate({ id: exp.id, action: "start" })}
                        className="rounded-md bg-emerald-600 px-2 py-1 text-xs font-medium text-white"
                      >
                        Start
                      </button>
                    )}
                    {canManage && exp.status === "running" && (
                      <button
                        type="button"
                        onClick={() => transition.mutate({ id: exp.id, action: "stop" })}
                        className="rounded-md border border-amber-400 px-2 py-1 text-xs font-medium text-amber-700"
                      >
                        Stop
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setResultsFor(resultsFor === exp.id ? null : exp.id)}
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                    >
                      Results
                    </button>
                    {canManage && exp.status !== "running" && (
                      <button
                        type="button"
                        onClick={() => remove.mutate(exp.id)}
                        className="rounded-md border border-red-300 px-2 py-1 text-xs font-medium text-red-600"
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {resultsFor && resultsQuery.data?.data && (
          <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
            <h3 className="text-xs font-semibold uppercase text-slate-400">Results by arm</h3>
            <table className="mt-1 w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase text-slate-400">
                  <th className="py-1 pr-4">Arm</th>
                  <th className="py-1 pr-4">Devices</th>
                  <th className="py-1">Playbacks</th>
                </tr>
              </thead>
              <tbody>
                {resultsQuery.data.data.arms.map((arm) => (
                  <tr key={arm.arm} className="border-t border-slate-200">
                    <td className="py-1 pr-4">{arm.arm}</td>
                    <td className="py-1 pr-4">{arm.devices}</td>
                    <td className="py-1">{arm.playback_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
