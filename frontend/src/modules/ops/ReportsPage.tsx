import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api } from "../../lib/api";
import { CampaignAnalyticsTab, ProofOfPlayTab, UptimeTab } from "./AnalyticsTabs";

interface DeploymentRow {
  campaign_id: string;
  campaign_name: string;
  status: string;
  deployments: number;
  latest_version: number | null;
  acknowledged: number;
  failed: number;
  pending: number;
}

interface PlaybackRow {
  asset_id: string;
  asset_name: string;
  plays: number;
  devices_reached: number;
}

interface LocationRow {
  location_id: string;
  location_name: string;
  depth: number;
  devices: number;
  online: number;
  warning: number;
  offline: number;
}

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "pop", label: "Proof of play" },
  { key: "analytics", label: "Campaign analytics" },
  { key: "uptime", label: "Uptime" },
] as const;

/** SCR-24 Reports + P2-15/16/17 analytics & exports. */
export function ReportsPage() {
  const [tab, setTab] = useState<string>("overview");

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Reports</h1>
      <div className="mt-4 border-b border-slate-200" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t.key
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="mt-4">
        {tab === "overview" ? (
          <OverviewTab />
        ) : tab === "pop" ? (
          <ProofOfPlayTab />
        ) : tab === "analytics" ? (
          <CampaignAnalyticsTab />
        ) : (
          <UptimeTab />
        )}
      </div>
    </div>
  );
}

function OverviewTab() {
  const deploymentsQuery = useQuery({
    queryKey: ["report-deployments"],
    queryFn: () => api.get<DeploymentRow[]>("/reports/deployments"),
  });
  const playbackQuery = useQuery({
    queryKey: ["report-playback"],
    queryFn: () => api.get<PlaybackRow[]>("/reports/playback"),
  });
  const locationsQuery = useQuery({
    queryKey: ["report-locations"],
    queryFn: () => api.get<LocationRow[]>("/reports/locations"),
  });

  if (deploymentsQuery.isLoading || playbackQuery.isLoading || locationsQuery.isLoading) {
    return <Spinner label="Loading reports…" />;
  }

  const deployments = deploymentsQuery.data?.data ?? [];
  const playback = playbackQuery.data?.data ?? [];
  const locations = locationsQuery.data?.data ?? [];

  return (
    <div className="space-y-6">
      <ReportSection title="Campaign deployments" empty={deployments.length === 0}>
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Campaign</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Deployments</th>
              <th className="px-4 py-2">Latest</th>
              <th className="px-4 py-2">Acked</th>
              <th className="px-4 py-2">Failed</th>
              <th className="px-4 py-2">Pending</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {deployments.map((row) => (
              <tr key={row.campaign_id}>
                <td className="px-4 py-2 font-medium text-slate-800">{row.campaign_name}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={row.status} />
                </td>
                <td className="px-4 py-2 text-slate-600">{row.deployments}</td>
                <td className="px-4 py-2 text-slate-600">v{row.latest_version}</td>
                <td className="px-4 py-2 text-emerald-700">{row.acknowledged}</td>
                <td className="px-4 py-2 text-red-600">{row.failed}</td>
                <td className="px-4 py-2 text-slate-600">{row.pending}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ReportSection>

      <ReportSection title="Playback (proof-of-play foundation)" empty={playback.length === 0}>
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Content</th>
              <th className="px-4 py-2">Plays</th>
              <th className="px-4 py-2">Devices reached</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {playback.map((row) => (
              <tr key={row.asset_id}>
                <td className="px-4 py-2 font-medium text-slate-800">{row.asset_name}</td>
                <td className="px-4 py-2 text-slate-600">{row.plays}</td>
                <td className="px-4 py-2 text-slate-600">{row.devices_reached}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ReportSection>

      <ReportSection title="Device health by location" empty={locations.length === 0}>
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Location</th>
              <th className="px-4 py-2">Devices</th>
              <th className="px-4 py-2">Online</th>
              <th className="px-4 py-2">Warning</th>
              <th className="px-4 py-2">Offline</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {locations.map((row) => (
              <tr key={row.location_id}>
                <td className="px-4 py-2 font-medium text-slate-800">
                  <span style={{ paddingLeft: row.depth * 12 }}>{row.location_name}</span>
                </td>
                <td className="px-4 py-2 text-slate-600">{row.devices}</td>
                <td className="px-4 py-2 text-emerald-700">{row.online}</td>
                <td className="px-4 py-2 text-amber-600">{row.warning}</td>
                <td className="px-4 py-2 text-red-600">{row.offline}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ReportSection>
    </div>
  );
}

function ReportSection({
  title,
  empty,
  children,
}: {
  title: string;
  empty: boolean;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h2>
      {empty ? (
        <p className="mt-2 rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
          No data yet.
        </p>
      ) : (
        <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          {children}
        </div>
      )}
    </section>
  );
}
