import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface UsageEntry {
  used: number;
  limit: number | null;
}

interface Usage {
  devices: UsageEntry;
  users: UsageEntry;
  storage_mb: UsageEntry;
}

interface RetentionEntry {
  days: number;
  floor: number;
  ceiling: number;
}

/** Usage vs effective limits (read-only — limits come from the plan and
 * Super-Admin quota overrides) + P2-AUD-003 retention policy. */
export function QuotasRetentionSection() {
  const { hasPermission } = useAuth();
  const canSettings = hasPermission("settings.manage");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const usageQuery = useQuery({
    queryKey: ["org-usage"],
    queryFn: () => api.get<Usage>("/organization/usage"),
  });
  const retentionQuery = useQuery({
    queryKey: ["org-retention"],
    queryFn: () => api.get<Record<string, RetentionEntry>>("/organization/retention"),
    enabled: canSettings,
  });

  const [days, setDays] = useState<Record<string, string>>({});
  const usage = usageQuery.data?.data ?? null;
  const retention = retentionQuery.data?.data ?? null;

  useEffect(() => {
    if (retention) {
      setDays(
        Object.fromEntries(
          Object.entries(retention).map(([key, entry]) => [key, String(entry.days)]),
        ),
      );
    }
  }, [retention]);

  const onError = (err: unknown) => {
    setOk(null);
    setError(err instanceof ApiError ? err.message : "Save failed");
  };
  const saveRetention = useMutation({
    mutationFn: () =>
      api.put(
        "/organization/retention",
        Object.fromEntries(Object.entries(days).map(([key, value]) => [key, Number(value)])),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-retention"] });
      setError(null);
      setOk("Retention policy saved.");
    },
    onError,
  });

  if (!usage) return null;

  const bars: { key: keyof Usage; label: string; unit: string }[] = [
    { key: "devices", label: "Devices", unit: "" },
    { key: "users", label: "Users", unit: "" },
    { key: "storage_mb", label: "Storage", unit: "MB" },
  ];

  return (
    <div className="mt-8 space-y-6">
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Usage &amp; limits
        </h2>
        <p className="mt-1 text-xs text-slate-400">
          Limits come from your subscription plan (and any platform override).
          To change them, upgrade your plan or contact the platform
          administrator.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {bars.map(({ key, label, unit }) => {
            const entry = usage[key];
            const pct =
              entry.limit != null
                ? Math.min(Math.round((entry.used / entry.limit) * 100), 100)
                : null;
            return (
              <div key={key}>
                <p className="text-sm text-slate-600">
                  <span className="font-medium text-slate-800">{label}</span>:{" "}
                  {entry.used}
                  {unit && ` ${unit}`}
                  {entry.limit != null ? ` of ${entry.limit}${unit ? ` ${unit}` : ""}` : " (no limit)"}
                </p>
                <div className="mt-1 h-2 overflow-hidden rounded bg-slate-100">
                  <div
                    className={`h-full ${
                      pct != null && pct >= 90 ? "bg-red-500" : "bg-emerald-500"
                    }`}
                    style={{ width: `${pct ?? 4}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {canSettings && retention && (
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Data retention (days)
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Pruned by the maintenance sweep. Platform floors apply — audit logs
            cannot go below {retention.audit_logs?.floor ?? 90} days.
          </p>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {Object.entries(retention).map(([key, entry]) => (
              <label key={key} className="block text-sm">
                <span className="block text-xs text-slate-500">
                  {key.replace(/_/g, " ")} ({entry.floor}–{entry.ceiling})
                </span>
                <input
                  type="number"
                  min={entry.floor}
                  max={entry.ceiling}
                  value={days[key] ?? ""}
                  onChange={(e) =>
                    setDays((prev) => ({ ...prev, [key]: e.target.value }))
                  }
                  className="mt-0.5 w-24 rounded-md border border-slate-300 px-2 py-1.5"
                />
              </label>
            ))}
          </div>
          <button
            type="button"
            disabled={saveRetention.isPending}
            onClick={() => saveRetention.mutate()}
            className="mt-3 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Save retention policy
          </button>
        </section>
      )}

      {ok && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{ok}</p>}
      {error && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
