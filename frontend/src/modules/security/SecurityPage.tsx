import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface IdentityRow {
  device_id: string;
  device_name: string;
  identity_type: string;
  has_credential: boolean;
  fingerprint: string | null;
  issued_at: string | null;
  age_days: number | null;
  credential_history: number;
}

interface ViolationRow {
  id: string;
  entity_type: string;
  entity_id: string;
  severity: string;
  state: string;
  detail: string | null;
  detected_at: string | null;
}

interface Summary {
  open_violations: Record<string, number>;
  device_identities: number;
  credentials_missing: number;
  oldest_credential_days: number;
}

interface PolicyRow {
  id: string;
  scope_type: string;
  conditions: { max_age_days: number };
  severity: string;
  active: boolean;
}

/** P3-21 Security Center: identities + credential lifecycle, age policies,
 * violations. Rotation forces standard re-registration — no side channel. */
export function SecurityPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("settings.manage");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [ageDays, setAgeDays] = useState("180");

  const summaryQuery = useQuery({
    queryKey: ["security-summary"],
    queryFn: () => api.get<Summary>("/security/summary"),
    enabled: canManage,
    retry: false,
  });
  const identitiesQuery = useQuery({
    queryKey: ["security-identities"],
    queryFn: () => api.get<IdentityRow[]>("/security/devices/identities"),
  });
  const violationsQuery = useQuery({
    queryKey: ["security-violations"],
    queryFn: () => api.get<ViolationRow[]>("/security/policy-violations?page_size=50"),
    enabled: canManage,
  });
  const policiesQuery = useQuery({
    queryKey: ["security-policies"],
    queryFn: () => api.get<PolicyRow[]>("/security/policies"),
    enabled: canManage,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["security-summary"] });
    queryClient.invalidateQueries({ queryKey: ["security-identities"] });
    queryClient.invalidateQueries({ queryKey: ["security-violations"] });
    queryClient.invalidateQueries({ queryKey: ["security-policies"] });
  };
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const rotate = useMutation({
    mutationFn: (deviceId: string) => api.post(`/security/devices/${deviceId}/rotate`, {}),
    onSuccess: () => refresh(),
    onError,
  });
  const savePolicy = useMutation({
    mutationFn: (scope: string) =>
      api.post("/security/policies", {
        scope_type: scope,
        conditions: { max_age_days: Number(ageDays) },
      }),
    onSuccess: () => refresh(),
    onError,
  });
  const resolve = useMutation({
    mutationFn: (id: string) => api.post(`/security/policy-violations/${id}/resolve`, {}),
    onSuccess: () => refresh(),
    onError,
  });

  const summary = summaryQuery.data?.data ?? null;
  const identities = identitiesQuery.data?.data ?? [];
  const violations = violationsQuery.data?.data ?? [];
  const policies = policiesQuery.data?.data ?? [];

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Security Center</h1>
        <p className="mt-1 text-sm text-slate-500">
          Device credential lifecycle, age policies and violations. Rotation
          revokes the token — the player re-enrolls through the standard
          pipeline.
        </p>
      </div>

      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs uppercase text-slate-400">Identities</p>
            <p className="text-xl font-semibold text-slate-900">{summary.device_identities}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs uppercase text-slate-400">Open violations</p>
            <p className="text-xl font-semibold text-red-600">
              {Object.values(summary.open_violations).reduce((a, b) => a + b, 0)}
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs uppercase text-slate-400">Missing credentials</p>
            <p className="text-xl font-semibold text-amber-600">
              {summary.credentials_missing}
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs uppercase text-slate-400">Oldest credential</p>
            <p className="text-xl font-semibold text-slate-900">
              {summary.oldest_credential_days}d
            </p>
          </div>
        </div>
      )}

      {canManage && (
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Age policies
          </h2>
          <div className="mt-2 flex flex-wrap items-end gap-3">
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">Max credential age (days)</span>
              <input
                type="number"
                min={1}
                value={ageDays}
                onChange={(e) => setAgeDays(e.target.value)}
                className="mt-0.5 w-24 rounded-md border border-slate-300 px-2 py-1.5"
              />
            </label>
            <button
              type="button"
              onClick={() => savePolicy.mutate("device_credentials")}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
            >
              Apply to device tokens
            </button>
            <button
              type="button"
              onClick={() => savePolicy.mutate("api_keys")}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
            >
              Apply to API keys
            </button>
            {policies.map((p) => (
              <span
                key={p.id}
                className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600"
              >
                {p.scope_type}: {p.conditions.max_age_days}d ({p.severity})
              </span>
            ))}
          </div>
          <p className="mt-1 text-xs text-slate-400">
            The daily sweep opens violations for over-age credentials and
            auto-resolves them once rotated. Violations are surfaced, never
            auto-enforced.
          </p>
        </section>
      )}

      {canManage && violations.length > 0 && (
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Policy violations
          </h2>
          <table className="mt-2 w-full text-left text-sm">
            <tbody>
              {violations.map((v) => (
                <tr key={v.id} className="border-t border-slate-100">
                  <td className="py-1.5 pr-4 text-xs">{v.entity_type}</td>
                  <td className="py-1.5 pr-4 text-xs text-slate-500">{v.detail}</td>
                  <td className="py-1.5 pr-4">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        v.state === "open"
                          ? v.severity === "critical"
                            ? "bg-red-100 text-red-700"
                            : "bg-amber-100 text-amber-800"
                          : "bg-emerald-100 text-emerald-700"
                      }`}
                    >
                      {v.state} · {v.severity}
                    </span>
                  </td>
                  <td className="py-1.5">
                    {v.state === "open" && (
                      <button
                        type="button"
                        onClick={() => resolve.mutate(v.id)}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                      >
                        Resolve
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Device identities
        </h2>
        <table className="mt-2 w-full text-left text-sm">
          <thead>
            <tr className="text-xs uppercase text-slate-400">
              <th className="py-1.5 pr-4">Device</th>
              <th className="py-1.5 pr-4">Fingerprint</th>
              <th className="py-1.5 pr-4">Age</th>
              <th className="py-1.5 pr-4">History</th>
              {canManage && <th className="py-1.5">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {identities.map((row) => (
              <tr key={row.device_id} className="border-t border-slate-100">
                <td className="py-1.5 pr-4 font-medium text-slate-800">{row.device_name}</td>
                <td className="py-1.5 pr-4 font-mono text-xs">
                  {row.fingerprint ?? "— pending re-enrollment"}
                </td>
                <td className="py-1.5 pr-4 text-xs">
                  {row.age_days != null ? `${row.age_days}d` : "—"}
                </td>
                <td className="py-1.5 pr-4 text-xs">{row.credential_history}</td>
                {canManage && (
                  <td className="py-1.5">
                    {row.has_credential && (
                      <button
                        type="button"
                        onClick={() => rotate.mutate(row.device_id)}
                        className="rounded-md border border-amber-400 px-2 py-1 text-xs font-medium text-amber-700"
                      >
                        Rotate
                      </button>
                    )}
                  </td>
                )}
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
