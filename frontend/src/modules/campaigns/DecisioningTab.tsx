import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { CampaignSummary } from "./types";

interface RuleRow {
  id?: string;
  priority: number;
  conditions: Record<string, unknown>;
  actions: Record<string, unknown>;
}

interface PolicyRow {
  id: string;
  name: string;
  guardrails: { mandatory_campaign_ids: string[]; max_switches_per_hour: number };
  active: boolean;
  rules: RuleRow[];
}

interface PreviewResult {
  timezone: string;
  candidates: { id: string; name: string; priority: number; eligible_now: boolean }[];
  scheduler_campaign_id: string | null;
  decided_campaign_id: string | null;
  reasons: Record<string, unknown>[];
}

interface LogRow {
  id: string;
  device_id: string;
  campaign_id: string | null;
  reasons: Record<string, unknown>;
  decided_at: string | null;
}

/** P3-05 Decisioning Rules: deterministic pin/boost/exclude rules with
 * guardrails, a dry-run preview and the auditable decision log. */
export function DecisioningTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("campaigns.manage");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [rulesDraft, setRulesDraft] = useState<string>("");
  const [previewDevice, setPreviewDevice] = useState("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [newName, setNewName] = useState("");

  const policiesQuery = useQuery({
    queryKey: ["decision-policies"],
    queryFn: () => api.get<PolicyRow[]>("/decision-policies"),
  });
  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get<CampaignSummary[]>("/campaigns?page_size=100"),
  });
  const devicesQuery = useQuery({
    queryKey: ["devices-brief"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/devices?page_size=100"),
  });
  const logQuery = useQuery({
    queryKey: ["decision-log"],
    queryFn: () => api.get<LogRow[]>("/decision-log?page_size=15"),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["decision-policies"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const createPolicy = useMutation({
    mutationFn: () => api.post("/decision-policies", { name: newName }),
    onSuccess: () => {
      refresh();
      setError(null);
      setNewName("");
    },
    onError,
  });
  const toggleActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.patch(`/decision-policies/${id}`, { active }),
    onSuccess: () => refresh(),
    onError,
  });
  const deletePolicy = useMutation({
    mutationFn: (id: string) => api.delete(`/decision-policies/${id}`),
    onSuccess: () => {
      refresh();
      setSelected(null);
    },
    onError,
  });
  const saveRules = useMutation({
    mutationFn: () =>
      api.put(`/decision-policies/${selected}/rules`, { rules: JSON.parse(rulesDraft) }),
    onSuccess: () => {
      refresh();
      setError(null);
    },
    onError,
  });
  const runPreview = useMutation({
    mutationFn: () =>
      api.post<PreviewResult>("/decision-rules/preview", { device_id: previewDevice }),
    onSuccess: (envelope) => {
      setError(null);
      setPreview(envelope.data!);
    },
    onError,
  });

  const policies = policiesQuery.data?.data ?? [];
  const campaigns = campaignsQuery.data?.data ?? [];
  const devices = devicesQuery.data?.data ?? [];
  const logs = logQuery.data?.data ?? [];
  const campaignName = (id: string | null) =>
    campaigns.find((c) => c.id === id)?.name ?? (id ? id.slice(0, 8) : "—");

  function openRules(policy: PolicyRow) {
    setSelected(policy.id);
    setRulesDraft(
      JSON.stringify(
        policy.rules.map(({ priority, conditions, actions }) => ({
          priority,
          conditions,
          actions,
        })),
        null,
        2,
      ) || "[]",
    );
  }

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    createPolicy.mutate();
  }

  return (
    <div className="mt-4 space-y-6">
      <p className="text-xs text-slate-400">
        Rules pin, boost or exclude among the campaigns whose schedule window
        is live right now — schedule windows are never overridden, mandatory
        campaigns are never excluded, and the switch budget prevents
        flapping. Every applied rule is recorded as an auditable reason.
      </p>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Policies
          </h2>
          {canManage && (
            <form className="flex items-center gap-2" onSubmit={onCreate}>
              <input
                required
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="New policy name"
                className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              />
              <button
                type="submit"
                disabled={createPolicy.isPending}
                className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                Create
              </button>
            </form>
          )}
        </div>
        <table className="mt-2 w-full text-left text-sm">
          <tbody>
            {policies.length === 0 && (
              <tr>
                <td className="py-3 text-sm text-slate-400">No decision policies yet.</td>
              </tr>
            )}
            {policies.map((policy) => (
              <tr key={policy.id} className="border-t border-slate-100">
                <td className="py-2 pr-4 font-medium text-slate-800">{policy.name}</td>
                <td className="py-2 pr-4 text-xs text-slate-500">
                  {policy.rules.length} rule{policy.rules.length === 1 ? "" : "s"} · cap{" "}
                  {policy.guardrails.max_switches_per_hour}/h
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      policy.active
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {policy.active ? "active" : "inactive"}
                  </span>
                </td>
                {canManage && (
                  <td className="py-2">
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => openRules(policy)}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                      >
                        Rules
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          toggleActive.mutate({ id: policy.id, active: !policy.active })
                        }
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                      >
                        {policy.active ? "Deactivate" : "Activate"}
                      </button>
                      <button
                        type="button"
                        onClick={() => deletePolicy.mutate(policy.id)}
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

        {selected && canManage && (
          <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
            <h3 className="text-xs font-semibold uppercase text-slate-400">
              Rules (ordered by priority — JSON)
            </h3>
            <p className="mt-0.5 text-xs text-slate-400">
              Conditions: platform, manufacturer, location_id, tag{"{key,value}"},
              time{"{start,end,days}"}, data{"{source_id,path,op,value}"}. Actions:
              one of pin/boost/exclude (campaign id) + optional amount.
            </p>
            <textarea
              value={rulesDraft}
              onChange={(e) => setRulesDraft(e.target.value)}
              rows={10}
              className="mt-2 w-full rounded-md border border-slate-300 p-2 font-mono text-xs"
            />
            <button
              type="button"
              disabled={saveRules.isPending}
              onClick={() => {
                try {
                  JSON.parse(rulesDraft);
                  setError(null);
                  saveRules.mutate();
                } catch {
                  setError("Rules must be valid JSON");
                }
              }}
              className="mt-2 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              Save rules
            </button>
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Preview (dry-run)
        </h2>
        <div className="mt-2 flex items-end gap-2">
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Device</span>
            <select
              value={previewDevice}
              onChange={(e) => setPreviewDevice(e.target.value)}
              className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
            >
              <option value="">Select device…</option>
              {devices.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={!previewDevice || runPreview.isPending}
            onClick={() => runPreview.mutate()}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Run preview
          </button>
        </div>
        {preview && (
          <div className="mt-3 space-y-2 text-sm">
            <p>
              Scheduler picks{" "}
              <span className="font-medium">{campaignName(preview.scheduler_campaign_id)}</span>{" "}
              → decision:{" "}
              <span className="font-semibold text-slate-900">
                {campaignName(preview.decided_campaign_id)}
              </span>
            </p>
            <pre className="max-h-40 overflow-auto rounded bg-slate-50 p-2 font-mono text-xs">
              {JSON.stringify(preview.reasons, null, 2)}
            </pre>
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Decision log
        </h2>
        <table className="mt-2 w-full text-left text-sm">
          <tbody>
            {logs.length === 0 && (
              <tr>
                <td className="py-3 text-sm text-slate-400">
                  No decisions logged (log entries record actual switches only).
                </td>
              </tr>
            )}
            {logs.map((row) => (
              <tr key={row.id} className="border-t border-slate-100 align-top">
                <td className="py-1.5 pr-4 text-xs text-slate-500">
                  {row.decided_at ? new Date(row.decided_at).toLocaleString() : "—"}
                </td>
                <td className="py-1.5 pr-4">{campaignName(row.campaign_id)}</td>
                <td className="max-w-md truncate py-1.5 font-mono text-xs text-slate-500">
                  {JSON.stringify(row.reasons)}
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
