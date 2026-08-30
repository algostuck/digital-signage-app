import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo } from "../devices/types";

interface Rollup {
  total: number;
  online: number;
  warning: number;
  offline: number;
}

interface FleetHealth {
  thresholds: {
    warning_after_seconds: number;
    offline_after_seconds: number;
    storage_alert_percent: number;
    min_player_version: string | null;
  };
  organization: Rollup & { open_incidents: number; outdated_players: number };
  locations: (Rollup & { id: string; name: string; depth: number })[];
  groups: (Rollup & { id: string; name: string; group_type: string })[];
}

interface Incident {
  id: string;
  device_id: string | null;
  type: string;
  severity: string;
  state: string;
  title: string;
  opened_at: string;
  resolved_at: string | null;
  resolution: string | null;
}

const TABS = [
  { key: "health", label: "Fleet health" },
  { key: "incidents", label: "Incidents" },
] as const;

/** P2-13 Fleet Monitoring + P2-14 Incident Center. */
export function MonitoringPage() {
  const [tab, setTab] = useState<string>("health");

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Monitoring</h1>
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
      <div className="mt-4">{tab === "health" ? <FleetHealthTab /> : <IncidentsTab />}</div>
    </div>
  );
}

function FleetHealthTab() {
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("settings.manage");
  const queryClient = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const healthQuery = useQuery({
    queryKey: ["fleet-health"],
    queryFn: () => api.get<FleetHealth>("/monitoring/fleet-health"),
    refetchInterval: 30_000,
  });
  const health = healthQuery.data?.data ?? null;

  if (healthQuery.isLoading || !health) return <Spinner label="Loading fleet health…" />;
  const org = health.organization;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Tile label="Devices" value={org.total} />
        <Tile label="Online" value={org.online} tone="good" />
        <Tile label="Warning" value={org.warning} tone={org.warning ? "warn" : undefined} />
        <Tile label="Offline" value={org.offline} tone={org.offline ? "bad" : undefined} />
        <Tile
          label="Open incidents"
          value={org.open_incidents}
          tone={org.open_incidents ? "bad" : undefined}
        />
        <Tile
          label="Outdated players"
          value={org.outdated_players}
          tone={org.outdated_players ? "warn" : undefined}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
            By location (subtree rollup)
          </h3>
          <HealthTable
            rows={health.locations.map((row) => ({
              key: row.id,
              label: row.name,
              indent: row.depth,
              ...row,
            }))}
          />
        </div>
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
            By group
          </h3>
          <HealthTable
            rows={health.groups.map((row) => ({
              key: row.id,
              label: `${row.name}${row.group_type === "dynamic" ? " ⚡" : ""}`,
              indent: 0,
              ...row,
            }))}
          />
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
            Tenant thresholds
          </h3>
          {canEdit && (
            <button
              type="button"
              onClick={() => setEditOpen((v) => !v)}
              className="text-sm font-medium text-slate-600 underline"
            >
              {editOpen ? "Close" : "Edit"}
            </button>
          )}
        </div>
        <p className="mt-1 text-sm text-slate-600">
          warning after {health.thresholds.warning_after_seconds}s · offline after{" "}
          {health.thresholds.offline_after_seconds}s · storage alert at{" "}
          {health.thresholds.storage_alert_percent}% · min player version{" "}
          {health.thresholds.min_player_version ?? "—"}
        </p>
        {editOpen && (
          <ThresholdsForm
            current={health.thresholds}
            onSaved={() => {
              queryClient.invalidateQueries({ queryKey: ["fleet-health"] });
              setEditOpen(false);
              setError(null);
            }}
            onError={(message) => setError(message)}
          />
        )}
        {error && (
          <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}

function ThresholdsForm({
  current,
  onSaved,
  onError,
}: {
  current: FleetHealth["thresholds"];
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  const [warning, setWarning] = useState(String(current.warning_after_seconds));
  const [offline, setOffline] = useState(String(current.offline_after_seconds));
  const [storage, setStorage] = useState(String(current.storage_alert_percent));
  const [minVersion, setMinVersion] = useState(current.min_player_version ?? "");

  const save = useMutation({
    mutationFn: () =>
      api.put("/monitoring/thresholds", {
        warning_after_seconds: Number(warning),
        offline_after_seconds: Number(offline),
        storage_alert_percent: Number(storage),
        min_player_version: minVersion.trim() || null,
      }),
    onSuccess: onSaved,
    onError: (err) =>
      onError(err instanceof ApiError ? err.message : "Failed to save thresholds"),
  });

  return (
    <div className="mt-3 flex flex-wrap items-end gap-3 text-sm">
      <label className="block">
        <span className="block text-xs text-slate-500">Warning after (s)</span>
        <input
          type="number"
          value={warning}
          onChange={(e) => setWarning(e.target.value)}
          className="mt-0.5 w-28 rounded-md border border-slate-300 px-2 py-1.5"
        />
      </label>
      <label className="block">
        <span className="block text-xs text-slate-500">Offline after (s)</span>
        <input
          type="number"
          value={offline}
          onChange={(e) => setOffline(e.target.value)}
          className="mt-0.5 w-28 rounded-md border border-slate-300 px-2 py-1.5"
        />
      </label>
      <label className="block">
        <span className="block text-xs text-slate-500">Storage alert (%)</span>
        <input
          type="number"
          min={50}
          max={100}
          value={storage}
          onChange={(e) => setStorage(e.target.value)}
          className="mt-0.5 w-28 rounded-md border border-slate-300 px-2 py-1.5"
        />
      </label>
      <label className="block">
        <span className="block text-xs text-slate-500">Min player version</span>
        <input
          value={minVersion}
          onChange={(e) => setMinVersion(e.target.value)}
          placeholder="e.g. 2.5.0"
          className="mt-0.5 w-28 rounded-md border border-slate-300 px-2 py-1.5"
        />
      </label>
      <button
        type="button"
        onClick={() => save.mutate()}
        disabled={save.isPending}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {save.isPending ? "Saving…" : "Save thresholds"}
      </button>
    </div>
  );
}

function Tile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "good" | "warn" | "bad";
}) {
  const color =
    tone === "good"
      ? "text-emerald-600"
      : tone === "warn"
        ? "text-amber-600"
        : tone === "bad"
          ? "text-red-600"
          : "text-slate-900";
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function HealthTable({
  rows,
}: {
  rows: (Rollup & { key: string; label: string; indent: number })[];
}) {
  if (rows.length === 0) {
    return <p className="mt-2 text-sm text-slate-500">No devices assigned yet.</p>;
  }
  return (
    <table className="mt-2 w-full rounded-lg border border-slate-200 bg-white text-sm">
      <thead>
        <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
          <th className="px-3 py-2">Name</th>
          <th className="px-2 py-2 text-right">Total</th>
          <th className="px-2 py-2 text-right text-emerald-600">On</th>
          <th className="px-2 py-2 text-right text-amber-600">Warn</th>
          <th className="px-3 py-2 text-right text-red-600">Off</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key} className="border-t border-slate-100">
            <td className="px-3 py-1.5 text-slate-700">
              <span style={{ paddingLeft: `${row.indent * 12}px` }}>{row.label}</span>
            </td>
            <td className="px-2 py-1.5 text-right">{row.total}</td>
            <td className="px-2 py-1.5 text-right">{row.online}</td>
            <td className="px-2 py-1.5 text-right">{row.warning}</td>
            <td className="px-3 py-1.5 text-right">{row.offline}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const INCIDENT_TABS = [
  { key: "open", label: "Open" },
  { key: "acknowledged", label: "Acknowledged" },
  { key: "resolved", label: "Resolved" },
  { key: "", label: "All" },
] as const;

function IncidentsTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("incidents.manage");
  const queryClient = useQueryClient();
  const [state, setState] = useState<string>("open");
  const [error, setError] = useState<string | null>(null);

  const incidentsQuery = useQuery({
    queryKey: ["incidents", state],
    queryFn: () =>
      api.get<Incident[]>(`/incidents?page_size=100${state ? `&state=${state}` : ""}`),
    refetchInterval: 30_000,
  });

  const transition = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      api.post(`/incidents/${id}/${action}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
      queryClient.invalidateQueries({ queryKey: ["fleet-health"] });
      setError(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Action failed"),
  });

  const incidents = incidentsQuery.data?.data ?? [];

  return (
    <div>
      <div className="border-b border-slate-200" role="tablist">
        {INCIDENT_TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={state === t.key}
            onClick={() => setState(t.key)}
            className={`-mb-px border-b-2 px-3 py-1.5 text-sm font-medium ${
              state === t.key
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {error && (
        <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
      {incidentsQuery.isLoading ? (
        <Spinner label="Loading incidents…" />
      ) : incidents.length === 0 ? (
        <p className="mt-4 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No incidents here. Offline and storage alerts appear automatically.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {incidents.map((incident) => (
            <li
              key={incident.id}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm"
            >
              <StatusBadge status={incident.state} />
              <span
                className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                  incident.severity === "critical"
                    ? "bg-red-100 text-red-700"
                    : "bg-amber-50 text-amber-700"
                }`}
              >
                {incident.type}
              </span>
              <span className="font-medium text-slate-800">{incident.title}</span>
              <span className="text-xs text-slate-400">
                opened {timeAgo(incident.opened_at)}
                {incident.resolved_at && ` · resolved ${timeAgo(incident.resolved_at)}`}
                {incident.resolution && ` — ${incident.resolution}`}
              </span>
              {canManage && incident.state === "open" && (
                <span className="ml-auto space-x-2">
                  <button
                    type="button"
                    onClick={() => transition.mutate({ id: incident.id, action: "acknowledge" })}
                    className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600"
                  >
                    Acknowledge
                  </button>
                  <button
                    type="button"
                    onClick={() => transition.mutate({ id: incident.id, action: "resolve" })}
                    className="rounded-md bg-slate-900 px-3 py-1 text-xs font-medium text-white"
                  >
                    Resolve
                  </button>
                </span>
              )}
              {canManage && incident.state === "acknowledged" && (
                <button
                  type="button"
                  onClick={() => transition.mutate({ id: incident.id, action: "resolve" })}
                  className="ml-auto rounded-md bg-slate-900 px-3 py-1 text-xs font-medium text-white"
                >
                  Resolve
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
