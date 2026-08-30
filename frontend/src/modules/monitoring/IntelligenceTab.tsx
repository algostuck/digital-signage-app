import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface RuleRow {
  id: string;
  name: string;
  signal_type: string;
  threshold: Record<string, number>;
  window_hours: number;
  severity: string;
  active: boolean;
}

interface AnomalyRow {
  id: string;
  device_id: string;
  score: number;
  state: string;
  evidence: Record<string, unknown>;
  recommendation: string | null;
  opened_at: string | null;
}

const SIGNALS = ["heartbeat_gaps", "playback_failures", "error_events"];
const REMEDIATIONS = ["restart", "clear_cache", "refresh_content"];

const STATE_STYLE: Record<string, string> = {
  open: "bg-red-100 text-red-700",
  acknowledged: "bg-amber-100 text-amber-800",
  resolved: "bg-emerald-100 text-emerald-700",
};

/** P3-14/15 Fleet Intelligence: deterministic anomaly detection with
 * evidence, human-in-the-loop ack + whitelisted remediation. */
export function IntelligenceTab() {
  const { hasPermission } = useAuth();
  const canRules = hasPermission("settings.manage");
  const canAck = hasPermission("incidents.manage");
  const canRemediate = hasPermission("devices.control");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [ruleForm, setRuleForm] = useState({ name: "", signal_type: "playback_failures" });

  const rulesQuery = useQuery({
    queryKey: ["anomaly-rules"],
    queryFn: () => api.get<RuleRow[]>("/fleet-intelligence/rules"),
    retry: false,
  });
  const anomaliesQuery = useQuery({
    queryKey: ["anomalies"],
    queryFn: () => api.get<AnomalyRow[]>("/fleet-intelligence/anomalies?page_size=50"),
    retry: false,
    refetchInterval: 30000,
  });
  const devicesQuery = useQuery({
    queryKey: ["devices-brief"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/devices?page_size=200"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["anomaly-rules"] });
    queryClient.invalidateQueries({ queryKey: ["anomalies"] });
  };
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const createRule = useMutation({
    mutationFn: () =>
      api.post("/fleet-intelligence/rules", {
        name: ruleForm.name,
        signal_type: ruleForm.signal_type,
      }),
    onSuccess: () => {
      refresh();
      setError(null);
      setRuleForm({ name: "", signal_type: "playback_failures" });
    },
    onError,
  });
  const toggleRule = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.patch(`/fleet-intelligence/rules/${id}`, { active }),
    onSuccess: () => refresh(),
    onError,
  });
  const acknowledge = useMutation({
    mutationFn: (id: string) => api.post(`/fleet-intelligence/${id}/acknowledge`, {}),
    onSuccess: () => refresh(),
    onError,
  });
  const remediate = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      api.post(`/fleet-intelligence/${id}/remediation`, { action }),
    onSuccess: () => refresh(),
    onError,
  });

  if (rulesQuery.isError)
    return (
      <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
        {rulesQuery.error instanceof ApiError
          ? rulesQuery.error.message
          : "Fleet intelligence unavailable."}
      </p>
    );

  const rules = rulesQuery.data?.data ?? [];
  const anomalies = anomaliesQuery.data?.data ?? [];
  const devices = devicesQuery.data?.data ?? [];
  const deviceName = (id: string) => devices.find((d) => d.id === id)?.name ?? id.slice(0, 8);

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    createRule.mutate();
  }

  return (
    <div className="space-y-6">
      <p className="text-xs text-slate-400">
        Anomalies are explainable statistics over existing telemetry — every
        score shows its evidence, recommendations never auto-execute, and
        remediation is limited to whitelisted, non-destructive commands.
      </p>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Detection rules
          </h2>
          {canRules && (
            <form className="flex items-center gap-2" onSubmit={onCreate}>
              <input
                required
                value={ruleForm.name}
                onChange={(e) => setRuleForm((p) => ({ ...p, name: e.target.value }))}
                placeholder="Rule name"
                className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              />
              <select
                value={ruleForm.signal_type}
                onChange={(e) =>
                  setRuleForm((p) => ({ ...p, signal_type: e.target.value }))
                }
                className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              >
                {SIGNALS.map((s) => (
                  <option key={s} value={s}>
                    {s.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                disabled={createRule.isPending}
                className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                Add rule
              </button>
            </form>
          )}
        </div>
        <table className="mt-2 w-full text-left text-sm">
          <tbody>
            {rules.length === 0 && (
              <tr>
                <td className="py-3 text-sm text-slate-400">
                  No detection rules yet — anomalies appear once a rule is
                  active (hourly scan).
                </td>
              </tr>
            )}
            {rules.map((rule) => (
              <tr key={rule.id} className="border-t border-slate-100">
                <td className="py-2 pr-4 font-medium text-slate-800">{rule.name}</td>
                <td className="py-2 pr-4 font-mono text-xs">
                  {rule.signal_type} · {JSON.stringify(rule.threshold)} ·{" "}
                  {rule.window_hours}h
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      rule.active
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {rule.active ? "active" : "inactive"}
                  </span>
                </td>
                {canRules && (
                  <td className="py-2">
                    <button
                      type="button"
                      onClick={() => toggleRule.mutate({ id: rule.id, active: !rule.active })}
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                    >
                      {rule.active ? "Disable" : "Enable"}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Anomalies
        </h2>
        <table className="mt-2 w-full text-left text-sm">
          <tbody>
            {anomalies.length === 0 && (
              <tr>
                <td className="py-3 text-sm text-slate-400">No anomalies detected.</td>
              </tr>
            )}
            {anomalies.map((a) => (
              <tr key={a.id} className="border-t border-slate-100 align-top">
                <td className="py-2 pr-4 font-medium text-slate-800">
                  {deviceName(a.device_id)}
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                      a.score >= 2 ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    score {a.score}
                  </span>
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      STATE_STYLE[a.state] ?? ""
                    }`}
                  >
                    {a.state}
                  </span>
                </td>
                <td className="py-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => setExpanded(expanded === a.id ? null : a.id)}
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                    >
                      Evidence
                    </button>
                    {canAck && a.state === "open" && (
                      <button
                        type="button"
                        onClick={() => acknowledge.mutate(a.id)}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                      >
                        Acknowledge
                      </button>
                    )}
                    {canRemediate &&
                      a.state !== "resolved" &&
                      REMEDIATIONS.map((action) => (
                        <button
                          key={action}
                          type="button"
                          onClick={() => remediate.mutate({ id: a.id, action })}
                          className="rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-white"
                        >
                          {action.replace(/_/g, " ")}
                        </button>
                      ))}
                  </div>
                  {expanded === a.id && (
                    <div className="mt-2 max-w-lg rounded-md bg-slate-50 p-2">
                      {a.recommendation && (
                        <p className="text-xs text-slate-600">{a.recommendation}</p>
                      )}
                      <pre className="mt-1 max-h-32 overflow-auto font-mono text-xs text-slate-500">
                        {JSON.stringify(a.evidence, null, 2)}
                      </pre>
                    </div>
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
