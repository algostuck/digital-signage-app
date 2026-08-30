import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Modal } from "../../components/ui/Modal";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { LocationNode } from "../locations/types";
import { timeAgo, type DeviceCommand, type DeviceDetail, type DeviceGroup } from "./types";

const COMMAND_TYPES = [
  "RESTART_PLAYER",
  "RESTART_DEVICE",
  "SYNC_NOW",
  "CLEAR_CACHE",
  "SCREENSHOT",
  "VOLUME_SET",
];

interface Props {
  deviceId: string;
  onClose: () => void;
  onChanged: () => void;
}

/** SCR-09 Device Details: health, capabilities, assignment, commands. */
export function DeviceDetailModal({ deviceId, onClose, onChanged }: Props) {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("devices.manage");
  const canControl = hasPermission("devices.control");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [commandType, setCommandType] = useState(COMMAND_TYPES[0]);

  const deviceQuery = useQuery({
    queryKey: ["device", deviceId],
    queryFn: () => api.get<DeviceDetail>(`/devices/${deviceId}`),
  });
  const commandsQuery = useQuery({
    queryKey: ["device-commands", deviceId],
    queryFn: () => api.get<DeviceCommand[]>(`/devices/${deviceId}/commands`),
  });
  const screenshotsQuery = useQuery({
    queryKey: ["device-screenshots", deviceId],
    queryFn: () =>
      api.get<{ id: string; url: string; captured_at: string }[]>(
        `/devices/${deviceId}/screenshots`,
      ),
  });
  const eventsQuery = useQuery({
    queryKey: ["device-events", deviceId],
    queryFn: () =>
      api.get<
        { at: string; kind: string; type: string; title: string; state?: string }[]
      >(`/devices/${deviceId}/events?limit=20`),
  });
  const locationsQuery = useQuery({
    queryKey: ["locations-flat"],
    queryFn: () => api.get<LocationNode[]>("/locations?page_size=200"),
    enabled: canManage,
  });
  const groupsQuery = useQuery({
    queryKey: ["device-groups"],
    queryFn: () => api.get<DeviceGroup[]>("/device-groups"),
    enabled: canManage,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["device", deviceId] });
    queryClient.invalidateQueries({ queryKey: ["device-commands", deviceId] });
    onChanged();
  };

  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const assignLocation = useMutation({
    mutationFn: (locationId: string | null) =>
      api.post(`/devices/${deviceId}/assign-location`, { location_id: locationId }),
    onSuccess: refresh,
    onError,
  });
  const assignGroup = useMutation({
    mutationFn: (groupId: string | null) =>
      api.patch(`/devices/${deviceId}`, groupId ? { group_id: groupId } : { clear_group: true }),
    onSuccess: refresh,
    onError,
  });
  const lifecycle = useMutation({
    mutationFn: (verb: string) => api.post(`/devices/${deviceId}/${verb}`),
    onSuccess: refresh,
    onError,
  });
  const sendCommand = useMutation({
    mutationFn: () => api.post(`/devices/${deviceId}/commands`, { command_type: commandType }),
    onSuccess: refresh,
    onError,
  });

  const device = deviceQuery.data?.data ?? null;
  if (!device) {
    return (
      <Modal title="Device details" open onClose={onClose}>
        <p className="text-sm text-slate-500">Loading…</p>
      </Modal>
    );
  }

  return (
    <Modal title={device.name} open onClose={onClose}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={device.status} />
          <StatusBadge status={device.connection_status} />
          <span className="text-xs text-slate-500">
            Heartbeat {timeAgo(device.last_heartbeat_at)}
          </span>
          {device.has_credential && (
            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
              credential issued
            </span>
          )}
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <Info label="Serial" value={device.serial_no} mono />
          <Info label="Platform" value={device.platform ?? "—"} />
          <Info
            label="Hardware"
            value={[device.manufacturer, device.model].filter(Boolean).join(" ") || "—"}
          />
          <Info label="Player" value={device.player_version ?? "—"} />
          <Info label="OS" value={device.os_version ?? "—"} />
          <Info label="IP" value={device.ip_address ?? "—"} mono />
          <Info
            label="Resolution"
            value={
              device.screen_width && device.screen_height
                ? `${device.screen_width}×${device.screen_height}`
                : "—"
            }
          />
          <Info label="Timezone" value={device.timezone ?? "inherited"} />
        </dl>

        {canManage && device.status === "active" && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="device-location" className="block text-xs font-medium uppercase tracking-wide text-slate-400">
                Location
              </label>
              <select
                id="device-location"
                value={device.location_id ?? ""}
                onChange={(e) => assignLocation.mutate(e.target.value || null)}
                className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              >
                <option value="">— unassigned —</option>
                {(locationsQuery.data?.data ?? []).map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="device-group" className="block text-xs font-medium uppercase tracking-wide text-slate-400">
                Group
              </label>
              <select
                id="device-group"
                value={device.group?.id ?? ""}
                onChange={(e) => assignGroup.mutate(e.target.value || null)}
                className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              >
                <option value="">— no group —</option>
                {(groupsQuery.data?.data ?? []).map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {(screenshotsQuery.data?.data ?? []).length > 0 && (
          <div>
            <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Latest screenshot evidence
            </h3>
            <img
              src={screenshotsQuery.data!.data![0].url}
              alt={`Screen of ${device.name}`}
              className="mt-1 max-h-40 rounded-md border border-slate-200 object-contain"
            />
            <p className="mt-1 text-xs text-slate-400">
              captured {timeAgo(screenshotsQuery.data!.data![0].captured_at)} ·{" "}
              {screenshotsQuery.data!.data!.length} on record
            </p>
          </div>
        )}

        {device.capabilities.length > 0 && (
          <div>
            <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Capabilities
            </h3>
            <div className="mt-1 flex flex-wrap gap-1">
              {device.capabilities.map((c) => (
                <span
                  key={c.capability_code}
                  className={`rounded px-2 py-0.5 text-xs font-medium ${
                    c.supported ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-400 line-through"
                  }`}
                >
                  {c.capability_code}
                </span>
              ))}
            </div>
          </div>
        )}

        {canControl && device.status === "active" && (
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label htmlFor="command-type" className="block text-xs font-medium uppercase tracking-wide text-slate-400">
                Remote command
              </label>
              <select
                id="command-type"
                value={commandType}
                onChange={(e) => setCommandType(e.target.value)}
                className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              >
                {COMMAND_TYPES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={() => sendCommand.mutate()}
              disabled={sendCommand.isPending}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              Queue
            </button>
          </div>
        )}

        {(eventsQuery.data?.data ?? []).length > 0 && (
          <div>
            <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Event timeline
            </h3>
            <ul className="mt-1 max-h-40 space-y-1 overflow-y-auto text-sm text-slate-600">
              {(eventsQuery.data?.data ?? []).map((row, index) => (
                <li key={index} className="flex items-center gap-2">
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      row.kind === "incident"
                        ? "bg-red-500"
                        : row.kind === "recovery"
                          ? "bg-emerald-500"
                          : "bg-slate-300"
                    }`}
                  />
                  <span className="font-mono text-xs text-slate-400">{row.type}</span>
                  <span className="truncate">{row.title}</span>
                  <span className="ml-auto shrink-0 text-xs text-slate-400">
                    {timeAgo(row.at)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {(commandsQuery.data?.data ?? []).length > 0 && (
          <div>
            <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Recent commands
            </h3>
            <ul className="mt-1 space-y-1 text-sm text-slate-600">
              {(commandsQuery.data?.data ?? []).slice(0, 5).map((c) => (
                <li key={c.id} className="flex items-center gap-2">
                  <span className="font-mono text-xs">{c.command_type}</span>
                  <StatusBadge status={c.status} />
                  <span className="text-xs text-slate-400">{timeAgo(c.created_at)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}

        {canManage && (
          <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 pt-4">
            {device.status === "active" && (
              <button
                type="button"
                onClick={() => {
                  if (window.confirm("Reset this device's credential? It will re-enroll on next poll.")) {
                    lifecycle.mutate("reset-token");
                  }
                }}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
              >
                Reset credential
              </button>
            )}
            {device.status !== "decommissioned" && (
              <button
                type="button"
                onClick={() => {
                  if (window.confirm(`Decommission "${device.name}"? This revokes its credential.`)) {
                    lifecycle.mutate("decommission");
                  }
                }}
                className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600"
              >
                Decommission
              </button>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}

function Info({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className={`mt-0.5 text-slate-700 ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}
