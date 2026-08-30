import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo } from "../devices/types";
import type { DeploymentDeviceRow, DeploymentSummary } from "./types";

/** SCR-22 Publishing / Deployments: jobs, progress, retry, target status. */
export function DeploymentsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("deployments.manage");
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);

  const deploymentsQuery = useQuery({
    queryKey: ["deployments"],
    queryFn: () => api.get<DeploymentSummary[]>("/deployments?page_size=100"),
    refetchInterval: 15_000,
  });
  const devicesQuery = useQuery({
    queryKey: ["deployment-devices", expanded],
    queryFn: () => api.get<DeploymentDeviceRow[]>(`/deployments/${expanded}/devices`),
    enabled: expanded != null,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["deployments"] });
    queryClient.invalidateQueries({ queryKey: ["deployment-devices"] });
  };

  const action = useMutation({
    mutationFn: ({ id, verb }: { id: string; verb: string }) =>
      api.post(`/deployments/${id}/${verb}`),
    onSuccess: refresh,
    onError: (err) => window.alert(err instanceof ApiError ? err.message : "Action failed"),
  });

  const deployments = deploymentsQuery.data?.data ?? [];

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Publishing</h1>
      <p className="mt-1 text-sm text-slate-500">
        Deployment jobs with per-device delivery status. Players acknowledge after syncing.
      </p>

      {deploymentsQuery.isLoading ? (
        <Spinner label="Loading deployments…" />
      ) : deployments.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No deployments yet. Publish an approved campaign to create one.
        </p>
      ) : (
        <ul className="mt-4 space-y-2">
          {deployments.map((deployment) => {
            const done = deployment.acknowledged;
            const total = deployment.total_devices || 1;
            const percent = Math.round((done / total) * 100);
            return (
              <li key={deployment.id} className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-slate-800">
                      {deployment.campaign_name}
                      <span className="ml-2 text-sm font-normal text-slate-400">
                        v{deployment.version} · {timeAgo(deployment.created_at)}
                      </span>
                    </p>
                    <div className="mt-2 flex items-center gap-3">
                      <div className="h-2 w-48 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full ${
                            deployment.failed > 0 ? "bg-amber-500" : "bg-emerald-500"
                          }`}
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-500">
                        {deployment.acknowledged}/{deployment.total_devices} acknowledged
                        {deployment.failed > 0 && (
                          <span className="text-red-600"> · {deployment.failed} failed</span>
                        )}
                        {deployment.pending > 0 && ` · ${deployment.pending} pending`}
                      </span>
                    </div>
                  </div>
                  <StatusBadge status={deployment.status} />
                  <button
                    type="button"
                    onClick={() =>
                      setExpanded(expanded === deployment.id ? null : deployment.id)
                    }
                    className="text-sm font-medium text-slate-600 hover:underline"
                  >
                    {expanded === deployment.id ? "Hide devices" : "Devices"}
                  </button>
                  {canManage && deployment.failed > 0 && deployment.status !== "cancelled" && (
                    <button
                      type="button"
                      onClick={() => action.mutate({ id: deployment.id, verb: "retry" })}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
                    >
                      Retry failed
                    </button>
                  )}
                  {canManage &&
                    !["published", "cancelled"].includes(deployment.status) && (
                      <button
                        type="button"
                        onClick={() => {
                          if (window.confirm("Cancel this deployment?")) {
                            action.mutate({ id: deployment.id, verb: "cancel" });
                          }
                        }}
                        className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600"
                      >
                        Cancel
                      </button>
                    )}
                </div>

                {expanded === deployment.id && (
                  <div className="mt-3 border-t border-slate-100 pt-3">
                    {devicesQuery.isLoading ? (
                      <Spinner label="Loading device status…" />
                    ) : (
                      <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2 lg:grid-cols-3">
                        {(devicesQuery.data?.data ?? []).map((row) => (
                          <li
                            key={row.device_id}
                            className="flex items-center gap-2 rounded bg-slate-50 px-2 py-1.5 text-sm"
                          >
                            <StatusBadge status={row.status} />
                            <span className="truncate text-slate-700">{row.device_name}</span>
                            {row.last_error && (
                              <span className="truncate text-xs text-red-600" title={row.last_error}>
                                {row.last_error}
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
