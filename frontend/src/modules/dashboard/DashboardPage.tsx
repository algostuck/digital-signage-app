import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api } from "../../lib/api";
import { timeAgo } from "../devices/types";

interface Summary {
  devices: { total: number; online: number; warning: number; offline: number; pending: number };
  content: { total: number; published: number; draft: number };
  campaigns: { published: number; pending_approval: number; approved: number; draft: number };
  deployments: { publishing: number; partial: number; published: number; failed: number };
  notifications_unread: number;
  recent_deployments: {
    id: string;
    campaign_name: string;
    version: number;
    status: string;
    total_devices: number;
    acknowledged: number;
    failed: number;
    created_at: string;
  }[];
  recent_activity: {
    id: string;
    action: string;
    entity_type: string;
    user_name: string | null;
    created_at: string;
  }[];
}

/** SCR-02 Dashboard: all critical health information at a glance. */
export function DashboardPage() {
  const summaryQuery = useQuery({
    queryKey: ["monitoring-summary"],
    queryFn: () => api.get<Summary>("/monitoring/summary"),
    refetchInterval: 30_000,
  });

  if (summaryQuery.isLoading) return <Spinner label="Loading dashboard…" />;
  const data = summaryQuery.data?.data;
  if (!data) {
    return (
      <p className="text-sm text-red-600" role="alert">
        Failed to load dashboard.
      </p>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
        {data.notifications_unread > 0 && (
          <Link
            to="/notifications"
            className="rounded-full bg-amber-100 px-3 py-1 text-sm font-medium text-amber-800"
          >
            {data.notifications_unread} unread notification
            {data.notifications_unread === 1 ? "" : "s"}
          </Link>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card
          title="Devices online"
          value={`${data.devices.online}/${data.devices.total}`}
          detail={`${data.devices.warning} warning · ${data.devices.offline} offline${
            data.devices.pending ? ` · ${data.devices.pending} pending approval` : ""
          }`}
          to="/devices"
          tone={data.devices.offline > 0 ? "warn" : "ok"}
        />
        <Card
          title="Content"
          value={String(data.content.total)}
          detail={`${data.content.published} published · ${data.content.draft} draft`}
          to="/content"
        />
        <Card
          title="Active campaigns"
          value={String(data.campaigns.published)}
          detail={`${data.campaigns.pending_approval} awaiting approval · ${data.campaigns.draft} draft`}
          to="/campaigns"
          tone={data.campaigns.pending_approval > 0 ? "warn" : undefined}
        />
        <Card
          title="Deployments"
          value={String(
            data.deployments.publishing + data.deployments.partial + data.deployments.published,
          )}
          detail={`${data.deployments.publishing + data.deployments.partial} in progress · ${
            data.deployments.failed
          } failed`}
          to="/deployments"
          tone={data.deployments.failed > 0 ? "bad" : undefined}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Recent deployments
          </h2>
          {data.recent_deployments.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">Nothing published yet.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {data.recent_deployments.map((deployment) => (
                <li key={deployment.id} className="flex items-center gap-3 text-sm">
                  <StatusBadge status={deployment.status} />
                  <span className="font-medium text-slate-800">{deployment.campaign_name}</span>
                  <span className="text-slate-500">
                    v{deployment.version} · {deployment.acknowledged}/{deployment.total_devices}{" "}
                    acked
                    {deployment.failed > 0 && (
                      <span className="text-red-600"> · {deployment.failed} failed</span>
                    )}
                  </span>
                  <span className="ml-auto text-xs text-slate-400">
                    {timeAgo(deployment.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Recent activity
          </h2>
          {data.recent_activity.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">No activity recorded yet.</p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {data.recent_activity.map((entry) => (
                <li key={entry.id} className="flex items-center gap-2 text-sm">
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
                    {entry.action}
                  </span>
                  <span className="text-slate-500">{entry.user_name ?? "system"}</span>
                  <span className="ml-auto text-xs text-slate-400">
                    {timeAgo(entry.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function Card({
  title,
  value,
  detail,
  to,
  tone,
}: {
  title: string;
  value: string;
  detail: string;
  to: string;
  tone?: "ok" | "warn" | "bad";
}) {
  const accent =
    tone === "ok"
      ? "text-emerald-600"
      : tone === "warn"
        ? "text-amber-600"
        : tone === "bad"
          ? "text-red-600"
          : "text-slate-900";
  return (
    <Link
      to={to}
      className="rounded-lg border border-slate-200 bg-white p-4 transition-shadow hover:shadow-md"
    >
      <p className="text-sm font-medium text-slate-500">{title}</p>
      <p className={`mt-1 text-2xl font-semibold ${accent}`}>{value}</p>
      <p className="mt-1 text-xs text-slate-500">{detail}</p>
    </Link>
  );
}
