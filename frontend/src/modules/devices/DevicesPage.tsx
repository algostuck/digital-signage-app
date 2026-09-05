import { CheckOutlined, CloseOutlined, KeyOutlined, SaveOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Input, Popconfirm, Select, Space, Tabs, Typography, type TableProps } from "antd";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { FilterBar } from "@/design-system";
import { SearchBar } from "@/design-system";
import { DataTable } from "@/design-system";
import { PageContainer } from "@/design-system";

import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { LocationNode } from "../locations/types";
import { BundlesTab } from "./BundlesTab";
import { DeviceDetailModal } from "./DeviceDetailModal";
import { GroupsTab } from "./GroupsTab";
import { WallsTab } from "./WallsTab";
import { timeAgo, type Device, type DeviceGroup } from "./types";

const STATUS_FILTERS = ["", "pending", "active", "rejected", "decommissioned"];
const CONNECTION_FILTERS = ["", "online", "warning", "offline"];

interface SavedViewRow {
  id: string;
  name: string;
  filter_json: { q?: string; status?: string };
}

/** SCR-08 Device List + SCR-10 Groups (tabs); SCR-09 details in modal. */
export function DevicesPage() {
  const { hasPermission } = useAuth();
  const { message } = App.useApp();
  const canManage = hasPermission("devices.manage");
  const queryClient = useQueryClient();

  const [tab, setTab] = useState<"devices" | "groups" | "walls" | "bundles">("devices");
  // Dashboard drill-downs arrive as ?status=, ?connection_status=, ?q=.
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") ?? "");
  const [connectionFilter, setConnectionFilter] = useState(
    searchParams.get("connection_status") ?? "",
  );
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [keyVisible, setKeyVisible] = useState(false);
  const pageSize = 20;

  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) params.set("q", search);
  if (statusFilter) params.set("status", statusFilter);
  if (connectionFilter) params.set("connection_status", connectionFilter);

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
      message.success("View saved");
    },
    onError: (err) => message.error(err instanceof ApiError ? err.message : "Save failed"),
  });
  const deleteView = useMutation({
    mutationFn: (id: string) => api.delete(`/saved-views/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["saved-views", "devices"] }),
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
      message.success("Bulk update applied");
      invalidate();
    },
    onError: (err) =>
      message.error(err instanceof ApiError ? err.message : "Bulk update failed"),
  });

  const lifecycle = useMutation({
    mutationFn: ({ id, verb }: { id: string; verb: string }) =>
      api.post(`/devices/${id}/${verb}`),
    onSuccess: invalidate,
    onError: (err) => message.error(err instanceof ApiError ? err.message : "Action failed"),
  });

  const devices = devicesQuery.data?.data ?? [];
  const total = devicesQuery.data?.meta.total ?? 0;
  const views = viewsQuery.data?.data ?? [];

  const columns: TableProps<Device>["columns"] = [
    {
      title: "Name",
      dataIndex: "name",
      fixed: "left",
      render: (_, device) => (
        <Typography.Link onClick={() => setDetailId(device.id)}>{device.name}</Typography.Link>
      ),
    },
    {
      title: "Serial",
      dataIndex: "serial_no",
      responsive: ["lg"],
      render: (serial: string) => (
        <Typography.Text code className="text-xs">
          {serial}
        </Typography.Text>
      ),
    },
    {
      title: "Platform",
      responsive: ["xl"],
      render: (_, device) =>
        `${device.manufacturer ?? "—"}${device.platform ? ` · ${device.platform}` : ""}`,
    },
    {
      title: "Group",
      responsive: ["lg"],
      render: (_, device) => device.group?.name ?? "—",
    },
    {
      title: "Lifecycle",
      dataIndex: "status",
      render: (status: string) => <StatusBadge status={status} />,
    },
    {
      title: "Connection",
      dataIndex: "connection_status",
      render: (status: string) => <StatusBadge status={status} />,
    },
    {
      title: "Last heartbeat",
      responsive: ["md"],
      render: (_, device) => timeAgo(device.last_heartbeat_at),
    },
    ...(canManage
      ? [
          {
            title: "Actions",
            align: "right" as const,
            render: (_: unknown, device: Device) =>
              device.status === "pending" ? (
                <Space>
                  <Button
                    size="small"
                    type="primary"
                    icon={<CheckOutlined />}
                    onClick={() => lifecycle.mutate({ id: device.id, verb: "approve" })}
                  >
                    Approve
                  </Button>
                  <Button
                    size="small"
                    danger
                    icon={<CloseOutlined />}
                    onClick={() => lifecycle.mutate({ id: device.id, verb: "reject" })}
                  >
                    Reject
                  </Button>
                </Space>
              ) : null,
          },
        ]
      : []),
  ];

  const devicesTab = (
    <div>
      <FilterBar
        search={<SearchBar value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Search name, serial, model…" label="Search devices" width={288} />}
        onReset={
          search || statusFilter || connectionFilter
            ? () => {
                setSearch("");
                setStatusFilter("");
                setConnectionFilter("");
                setPage(1);
              }
            : undefined
        }
      >
        <Select
          className="w-44"
          value={statusFilter}
          aria-label="Filter by status"
          onChange={(value) => {
            setStatusFilter(value);
            setPage(1);
          }}
          options={STATUS_FILTERS.map((s) => ({
            value: s,
            label: s ? s.charAt(0).toUpperCase() + s.slice(1) : "All statuses",
          }))}
        />
        <Select
          className="w-44"
          value={connectionFilter}
          aria-label="Filter by connection"
          onChange={(value) => {
            setConnectionFilter(value);
            setPage(1);
          }}
          options={CONNECTION_FILTERS.map((s) => ({
            value: s,
            label: s ? s.charAt(0).toUpperCase() + s.slice(1) : "Any connection",
          }))}
        />
        <Select
          className="w-44"
          value={undefined}
          placeholder="Saved views…"
          aria-label="Saved views"
          onChange={(id: string) => {
            const view = views.find((v) => v.id === id);
            if (view) {
              setSearch(view.filter_json.q ?? "");
              setStatusFilter(view.filter_json.status ?? "");
              setPage(1);
            }
          }}
          options={views.map((view) => ({ value: view.id, label: view.name }))}
          notFoundContent="No saved views"
        />
        {savingView ? (
          <Space.Compact>
            <Input
              autoFocus
              className="w-36"
              value={viewName}
              onChange={(e) => setViewName(e.target.value)}
              placeholder="View name"
              aria-label="View name"
              onPressEnter={() => viewName.trim() && saveView.mutate()}
            />
            <Button
              type="primary"
              disabled={!viewName.trim()}
              loading={saveView.isPending}
              onClick={() => saveView.mutate()}
            >
              Save
            </Button>
            <Button aria-label="Cancel saving view" icon={<CloseOutlined />} onClick={() => setSavingView(false)} />
          </Space.Compact>
        ) : (
          <Button icon={<SaveOutlined />} onClick={() => setSavingView(true)}>
            Save view
          </Button>
        )}
        {views.some(
          (v) => v.filter_json.q === search && (v.filter_json.status ?? "") === statusFilter,
        ) && (
          <Popconfirm
            title="Delete the saved view matching the current filters?"
            onConfirm={() => {
              const target = views.find(
                (v) =>
                  v.filter_json.q === search && (v.filter_json.status ?? "") === statusFilter,
              );
              if (target) deleteView.mutate(target.id);
            }}
          >
            <Button type="link" danger size="small">
              Delete current view
            </Button>
          </Popconfirm>
        )}
      </FilterBar>

      {canManage && selected.size > 0 && (
        <div
          className="mb-3 flex flex-wrap items-center gap-2 rounded-lg dsc-primary-bg px-3 py-2"
          role="region"
          aria-live="polite"
          aria-label="Bulk actions"
        >
          <Typography.Text strong>{selected.size} selected</Typography.Text>
          <Select
            className="w-40"
            value={bulkGroup || undefined}
            placeholder="Assign group"
            aria-label="Bulk assign group"
            allowClear
            onChange={(v) => setBulkGroup(v ?? "")}
            options={(groupsQuery.data?.data ?? []).map((group) => ({
              value: group.id,
              label: group.name,
            }))}
          />
          <Select
            className="w-40"
            value={bulkLocation || undefined}
            placeholder="Assign location"
            aria-label="Bulk assign location"
            allowClear
            onChange={(v) => setBulkLocation(v ?? "")}
            options={(locationsQuery.data?.data ?? []).map((location) => ({
              value: location.id,
              label: location.name,
            }))}
          />
          <Input
            className="w-36"
            value={bulkTag}
            onChange={(e) => setBulkTag(e.target.value)}
            placeholder="tag key=value"
            aria-label="Bulk add tag"
          />
          <Button
            type="primary"
            disabled={!bulkGroup && !bulkLocation && !bulkTag.trim()}
            loading={bulkApply.isPending}
            onClick={() => bulkApply.mutate()}
          >
            Apply to selected
          </Button>
          <Button type="link" size="small" onClick={() => setSelected(new Set())}>
            Clear selection
          </Button>
        </div>
      )}

      <DataTable<Device>
        rowKey="id"
        columns={columns}
        dataSource={devices}
        loading={devicesQuery.isLoading}
        rowSelection={
          canManage
            ? {
                selectedRowKeys: Array.from(selected),
                onChange: (keys) => setSelected(new Set(keys as string[])),
                getCheckboxProps: (device) => ({
                  "aria-label": `Select ${device.name}`,
                }),
              }
            : undefined
        }
        emptyTitle="No devices found"
        emptyDescription="Players register using the enrollment key and appear here for approval."
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: false,
          showTotal: (t) => `${t} devices`,
          onChange: setPage,
        }}
      />
    </div>
  );

  return (
    <PageContainer
        title="Devices"
        description="Enroll, organize and operate your display fleet."
        actions={
          canManage &&
          tab === "devices" && (
            <Button icon={<KeyOutlined />} onClick={() => setKeyVisible((v) => !v)}>
              {keyVisible ? "Hide enrollment key" : "Show enrollment key"}
            </Button>
          )
        }
      >

      {keyVisible && keyQuery.data?.data && (
        <Typography.Paragraph className="-mt-3 mb-4">
          <Typography.Text type="secondary">Enrollment key: </Typography.Text>
          <Typography.Text code copyable>
            {keyQuery.data.data.enrollment_key}
          </Typography.Text>
        </Typography.Paragraph>
      )}

      <Tabs
        activeKey={tab}
        onChange={(key) => setTab(key as typeof tab)}
        items={[
          { key: "devices", label: "Devices", children: devicesTab },
          { key: "groups", label: "Groups", children: <GroupsTab /> },
          { key: "walls", label: "Video Walls", children: <WallsTab /> },
          { key: "bundles", label: "Edge Bundles", children: <BundlesTab /> },
        ]}
      />

      {detailId && (
        <DeviceDetailModal
          deviceId={detailId}
          onClose={() => setDetailId(null)}
          onChanged={invalidate}
        />
      )}
    </PageContainer>
  );
}
