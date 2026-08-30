import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { LocationNode } from "../locations/types";
import { DeviceDetailModal } from "./DeviceDetailModal";
import { GroupsTab } from "./GroupsTab";
import { BundlesTab } from "./BundlesTab";
import { WallsTab } from "./WallsTab";
import { timeAgo, type Device, type DeviceGroup } from "./types";

const STATUS_FILTERS = ["", "pending", "active", "rejected", "decommissioned"];

interface SavedViewRow {
  id: string;
  name: string;
  filter_json: { q?: string; status?: string };
}

/** SCR-08 Device List + SCR-10 Groups (tabs); SCR-09 details in modal. */
export function DevicesPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("devices.manage");
  const queryClient = useQueryClient();

  const [tab, setTab] = useState<"devices" | "groups" | "walls" | "bundles">("devices");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [keyVisible, setKeyVisible] = useState(false);
  const pageSize = 20;

  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) params.set("q", search);
  if (statusFilter) params.set("status", statusFilter);

  const devicesQuery = useQuery({
    queryKey: ["devices", params.toString()],
    queryFn: () => api.get<Device[]>(`/devices?${params.toString()}`),
    refetchInterval: 30_000,
  });

  const keyQuery = useQuery({
    queryKey: ["enrollment-key"],
    queryFn: () => api.get<{ enrollment_key: string }>("/devices/enrollment-key"),
    enabled: canManage && keyVisible,
  });

  // P2-SRC-002 saved views + P2-SRC-003 bulk edit state.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [savingView, setSavingView] = useState(false);
  const [viewName, setViewName] = useState("");
  const [bulkGroup, setBulkGroup] = useState("");
  const [bulkLocation, setBulkLocation] = useState("");
  const [bulkTag, setBulkTag] = useState("");

  const viewsQuery = useQuery({
    queryKey: ["saved-views", "devices"],
    queryFn: () => api.get<SavedViewRow[]>("/saved-views?module=devices"),
  });
  const groupsQuery = useQuery({
    queryKey: ["device-groups"],
    queryFn: () => api.get<DeviceGroup[]>("/device-groups"),
    enabled: canManage,
  });
  const locationsQuery = useQuery({
    queryKey: ["locations-flat"],
    queryFn: () => api.get<LocationNode[]>("/locations?page_size=200"),
    enabled: canManage,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["devices"] });

  const saveView = useMutation({
    mutationFn: () =>
      api.post("/saved-views", {
        module: "devices",
        name: viewName.trim(),
        filter_json: { q: search, status: statusFilter },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-views", "devices"] });
      setSavingView(false);
      setViewName("");
    },
    onError: (err) => window.alert(err instanceof ApiError ? err.message : "Save failed"),
  });
  const deleteView = useMutation({
    mutationFn: (id: string) => api.delete(`/saved-views/${id}`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["saved-views", "devices"] }),
  });
  const bulkApply = useMutation({
    mutationFn: () => {
      const [tagKey, tagValue] = bulkTag.split("=").map((part) => part.trim());
      return api.post("/devices/bulk", {
        device_ids: Array.from(selected),
        ...(bulkGroup ? { group_id: bulkGroup } : {}),
        ...(bulkLocation ? { location_id: bulkLocation } : {}),
        ...(tagKey ? { add_tags: [{ key: tagKey, value: tagValue ?? "" }] } : {}),
      });
    },
    onSuccess: () => {
      setSelected(new Set());
      setBulkGroup("");
      setBulkLocation("");
      setBulkTag("");
      invalidate();
    },
    onError: (err) =>
      window.alert(err instanceof ApiError ? err.message : "Bulk update failed"),
  });

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const lifecycle = useMutation({
    mutationFn: ({ id, verb }: { id: string; verb: string }) =>
      api.post(`/devices/${id}/${verb}`),
    onSuccess: invalidate,
    onError: (err) => window.alert(err instanceof ApiError ? err.message : "Action failed"),
  });

  const devices = devicesQuery.data?.data ?? [];
  const total = devicesQuery.data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Devices</h1>
        {canManage && tab === "devices" && (
          <div className="text-right">
            <button
              type="button"
              onClick={() => setKeyVisible((v) => !v)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
            >
              {keyVisible ? "Hide enrollment key" : "Show enrollment key"}
            </button>
            {keyVisible && keyQuery.data?.data && (
              <p className="mt-1 rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700">
                {keyQuery.data.data.enrollment_key}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="mt-4 border-b border-slate-200" role="tablist">
        {(["devices", "groups", "walls", "bundles"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize ${
              tab === t
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "bundles" ? (
        <div className="mt-4">
          <BundlesTab />
        </div>
      ) : tab === "walls" ? (
        <div className="mt-4">
          <WallsTab />
        </div>
      ) : tab === "groups" ? (
        <div className="mt-4">
          <GroupsTab />
        </div>
      ) : (
        <div className="mt-4">
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search name, serial, model…"
              aria-label="Search devices"
              className="w-72 rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm"
            />
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              aria-label="Filter by status"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm capitalize"
            >
              {STATUS_FILTERS.map((s) => (
                <option key={s} value={s}>
                  {s || "All statuses"}
                </option>
              ))}
            </select>

            <select
              value=""
              onChange={(e) => {
                const view = (viewsQuery.data?.data ?? []).find(
                  (v) => v.id === e.target.value,
                );
                if (view) {
                  setSearch(view.filter_json.q ?? "");
                  setStatusFilter(view.filter_json.status ?? "");
                  setPage(1);
                }
              }}
              aria-label="Saved views"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm"
            >
              <option value="">Saved views…</option>
              {(viewsQuery.data?.data ?? []).map((view) => (
                <option key={view.id} value={view.id}>
                  {view.name}
                </option>
              ))}
            </select>
            {savingView ? (
              <span className="flex items-center gap-1">
                <input
                  value={viewName}
                  onChange={(e) => setViewName(e.target.value)}
                  placeholder="View name"
                  aria-label="View name"
                  className="w-36 rounded-md border border-slate-300 px-2 py-2 text-sm"
                />
                <button
                  type="button"
                  disabled={!viewName.trim() || saveView.isPending}
                  onClick={() => saveView.mutate()}
                  className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => setSavingView(false)}
                  className="px-2 text-sm text-slate-500"
                >
                  ✕
                </button>
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setSavingView(true)}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-600"
              >
                Save view
              </button>
            )}
            {(viewsQuery.data?.data ?? []).length > 0 && (
              <button
                type="button"
                onClick={() => {
                  const views = viewsQuery.data?.data ?? [];
                  const target = views.find(
                    (v) => v.filter_json.q === search && (v.filter_json.status ?? "") === statusFilter,
                  );
                  if (target && window.confirm(`Delete saved view "${target.name}"?`)) {
                    deleteView.mutate(target.id);
                  }
                }}
                className="text-xs text-slate-400 underline"
                title="Deletes the saved view matching the current filters"
              >
                Delete current view
              </button>
            )}
          </div>

          {canManage && selected.size > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md border border-slate-300 bg-slate-50 px-3 py-2 text-sm">
              <span className="font-medium text-slate-700">{selected.size} selected</span>
              <select
                value={bulkGroup}
                onChange={(e) => setBulkGroup(e.target.value)}
                aria-label="Bulk assign group"
                className="rounded-md border border-slate-300 px-2 py-1.5"
              >
                <option value="">— group —</option>
                {(groupsQuery.data?.data ?? []).map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
              <select
                value={bulkLocation}
                onChange={(e) => setBulkLocation(e.target.value)}
                aria-label="Bulk assign location"
                className="rounded-md border border-slate-300 px-2 py-1.5"
              >
                <option value="">— location —</option>
                {(locationsQuery.data?.data ?? []).map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.name}
                  </option>
                ))}
              </select>
              <input
                value={bulkTag}
                onChange={(e) => setBulkTag(e.target.value)}
                placeholder="tag key=value"
                aria-label="Bulk add tag"
                className="w-36 rounded-md border border-slate-300 px-2 py-1.5"
              />
              <button
                type="button"
                disabled={
                  bulkApply.isPending || (!bulkGroup && !bulkLocation && !bulkTag.trim())
                }
                onClick={() => bulkApply.mutate()}
                className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {bulkApply.isPending ? "Applying…" : "Apply to selected"}
              </button>
              <button
                type="button"
                onClick={() => setSelected(new Set())}
                className="text-xs text-slate-500 underline"
              >
                Clear selection
              </button>
            </div>
          )}

          {devicesQuery.isLoading ? (
            <Spinner label="Loading devices…" />
          ) : devices.length === 0 ? (
            <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
              No devices found. Players register using the enrollment key and appear
              here for approval.
            </p>
          ) : (
            <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    {canManage && (
                      <th className="px-3 py-3">
                        <input
                          type="checkbox"
                          aria-label="Select all on page"
                          checked={
                            devices.length > 0 && devices.every((d) => selected.has(d.id))
                          }
                          onChange={(e) => {
                            setSelected((prev) => {
                              const next = new Set(prev);
                              for (const d of devices) {
                                if (e.target.checked) next.add(d.id);
                                else next.delete(d.id);
                              }
                              return next;
                            });
                          }}
                        />
                      </th>
                    )}
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">Serial</th>
                    <th className="px-4 py-3">Platform</th>
                    <th className="px-4 py-3">Group</th>
                    <th className="px-4 py-3">Lifecycle</th>
                    <th className="px-4 py-3">Connection</th>
                    <th className="px-4 py-3">Last heartbeat</th>
                    {canManage && <th className="px-4 py-3 text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {devices.map((device) => (
                    <tr key={device.id} className="hover:bg-slate-50">
                      {canManage && (
                        <td className="px-3 py-3">
                          <input
                            type="checkbox"
                            aria-label={`Select ${device.name}`}
                            checked={selected.has(device.id)}
                            onChange={() => toggleSelected(device.id)}
                          />
                        </td>
                      )}
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() => setDetailId(device.id)}
                          className="font-medium text-slate-800 hover:underline"
                        >
                          {device.name}
                        </button>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">
                        {device.serial_no}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {device.manufacturer ?? "—"} {device.platform ? `· ${device.platform}` : ""}
                      </td>
                      <td className="px-4 py-3 text-slate-600">{device.group?.name ?? "—"}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={device.status} />
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={device.connection_status} />
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {timeAgo(device.last_heartbeat_at)}
                      </td>
                      {canManage && (
                        <td className="space-x-3 px-4 py-3 text-right">
                          {device.status === "pending" && (
                            <>
                              <button
                                type="button"
                                onClick={() => lifecycle.mutate({ id: device.id, verb: "approve" })}
                                className="text-sm font-medium text-emerald-700 hover:underline"
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                onClick={() => lifecycle.mutate({ id: device.id, verb: "reject" })}
                                className="text-sm font-medium text-red-600 hover:underline"
                              >
                                Reject
                              </button>
                            </>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
              <span>
                Page {page} of {totalPages} · {total} devices
              </span>
              <div className="space-x-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {detailId && (
        <DeviceDetailModal
          deviceId={detailId}
          onClose={() => setDetailId(null)}
          onChanged={invalidate}
        />
      )}
    </div>
  );
}
