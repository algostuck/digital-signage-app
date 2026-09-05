import { DownloadOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  DatePicker,
  Flex,
  Progress,
  Select,
  Space,
  Table,
  Typography,
  type TableProps,
} from "antd";
import dayjs from "dayjs";
import { useState } from "react";
import { FilterBar } from "@/design-system";
import { EmptyState } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface PopRow {
  group_by: string;
  key_id: string | null;
  name: string;
  plays: number;
  completed: number;
  completion_rate: number;
  devices_reached: number;
  first_play: string | null;
  last_play: string | null;
}

interface PerformanceRow {
  campaign_id: string;
  campaign_name: string;
  status: string;
  acknowledged: number;
  pending: number;
  failed: number;
  plays: number;
  completed_plays: number;
  completion_rate: number;
  devices_played: number;
}

interface UptimeRow {
  device_id: string;
  device_name: string;
  heartbeats: number;
  covered_seconds: number;
  window_seconds: number;
  uptime_pct: number;
}

function isoDaysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

/** Shared export buttons (P2-RPT-004) — hidden without reports.export. */
export function ExportButtons({
  report,
  filters,
}: {
  report: string;
  filters: Record<string, unknown>;
}) {
  const { hasPermission } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  if (!hasPermission("reports.export")) return null;

  async function run(format: "csv" | "xlsx") {
    setBusy(format);
    setError(null);
    try {
      await api.download("/reports/export", { report, format, filters });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Export failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Space wrap>
      {(["csv", "xlsx"] as const).map((format) => (
        <Button
          key={format}
          icon={<DownloadOutlined />}
          disabled={busy !== null}
          loading={busy === format}
          onClick={() => run(format)}
        >
          Export {format.toUpperCase()}
        </Button>
      ))}
      {error && (
        <Typography.Text type="danger" className="text-xs" role="alert">
          {error}
        </Typography.Text>
      )}
    </Space>
  );
}

const DIMENSIONS = ["campaign", "asset", "device", "location"] as const;

/** P2-15 Proof-of-Play + P2-17 builder-lite (dimension + filters + export). */
export function ProofOfPlayTab() {
  const [groupBy, setGroupBy] = useState<string>("campaign");
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(7));
  const [dateTo, setDateTo] = useState(isoDaysAgo(0));

  const query = useQuery({
    queryKey: ["report-pop", groupBy, dateFrom, dateTo],
    queryFn: () =>
      api.get<PopRow[]>(
        `/reports/proof-of-play?group_by=${groupBy}&date_from=${dateFrom}&date_to=${dateTo}`,
      ),
  });
  const rows = query.data?.data ?? [];
  const filters = { group_by: groupBy, date_from: dateFrom, date_to: dateTo };

  const columns: TableProps<PopRow>["columns"] = [
    {
      title: groupBy.charAt(0).toUpperCase() + groupBy.slice(1),
      dataIndex: "name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    { title: "Plays", dataIndex: "plays", align: "right" },
    {
      title: "Completed",
      dataIndex: "completed",
      align: "right",
      render: (value: number) => <Typography.Text type="success">{value}</Typography.Text>,
    },
    {
      title: "Completion",
      dataIndex: "completion_rate",
      align: "right",
      render: (rate: number) => `${Math.round(rate * 100)}%`,
    },
    { title: "Devices", dataIndex: "devices_reached", align: "right" },
    {
      title: "Last play",
      dataIndex: "last_play",
      responsive: ["lg"],
      render: (value: string | null) => (
        <Typography.Text type="secondary">
          {value ? new Date(value).toLocaleString() : "—"}
        </Typography.Text>
      ),
    },
  ];

  return (
    <div>
      <FilterBar>
        <Select
          className="w-44"
          value={groupBy}
          aria-label="Dimension"
          onChange={setGroupBy}
          options={DIMENSIONS.map((d) => ({
            value: d,
            label: d.charAt(0).toUpperCase() + d.slice(1),
          }))}
        />
        <DatePicker
          allowClear={false}
          value={dayjs(dateFrom)}
          aria-label="From date"
          onChange={(date) => date && setDateFrom(date.format("YYYY-MM-DD"))}
        />
        <DatePicker
          allowClear={false}
          value={dayjs(dateTo)}
          aria-label="To date"
          onChange={(date) => date && setDateTo(date.format("YYYY-MM-DD"))}
        />
        <ExportButtons report="proof-of-play" filters={filters} />
      </FilterBar>

      <Table<PopRow>
        size="middle"
        rowKey={(row) => row.key_id ?? "none"}
        columns={columns}
        dataSource={rows}
        loading={query.isLoading}
        pagination={false}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: <EmptyState title="No playback events in this range" /> }}
      />
    </div>
  );
}

const performanceColumns: TableProps<PerformanceRow>["columns"] = [
  {
    title: "Campaign",
    dataIndex: "campaign_name",
    render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
  },
  {
    title: "Delivered",
    dataIndex: "acknowledged",
    align: "right",
    render: (value: number) => <Typography.Text type="success">{value}</Typography.Text>,
  },
  { title: "Pending", dataIndex: "pending", align: "right" },
  {
    title: "Failed",
    dataIndex: "failed",
    align: "right",
    render: (value: number) => <Typography.Text type="danger">{value}</Typography.Text>,
  },
  { title: "Plays", dataIndex: "plays", align: "right" },
  {
    title: "Completion",
    dataIndex: "completion_rate",
    align: "right",
    render: (rate: number) => `${Math.round(rate * 100)}%`,
  },
  { title: "Devices played", dataIndex: "devices_played", align: "right", responsive: ["lg"] },
];

/** P2-16 Campaign Analytics. */
export function CampaignAnalyticsTab() {
  const query = useQuery({
    queryKey: ["report-campaign-performance"],
    queryFn: () => api.get<PerformanceRow[]>("/reports/campaign-performance"),
  });
  const rows = query.data?.data ?? [];

  return (
    <div>
      <Flex justify="flex-end" className="mb-4">
        <ExportButtons report="campaign-performance" filters={{}} />
      </Flex>
      <Table<PerformanceRow>
        size="middle"
        rowKey="campaign_id"
        columns={performanceColumns}
        dataSource={rows}
        loading={query.isLoading}
        pagination={false}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: <EmptyState title="No campaign activity yet" /> }}
      />
    </div>
  );
}

/** P2-RPT-003 Device uptime from heartbeat windows. */
export function UptimeTab() {
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(7));
  const [dateTo, setDateTo] = useState(isoDaysAgo(0));
  const query = useQuery({
    queryKey: ["report-uptime", dateFrom, dateTo],
    queryFn: () =>
      api.get<UptimeRow[]>(
        `/reports/device-uptime?date_from=${dateFrom}&date_to=${dateTo}`,
      ),
  });
  const rows = query.data?.data ?? [];
  const filters = { date_from: dateFrom, date_to: dateTo };

  const columns: TableProps<UptimeRow>["columns"] = [
    {
      title: "Device",
      dataIndex: "device_name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    {
      title: "Uptime",
      dataIndex: "uptime_pct",
      render: (pct: number) => (
        <Space>
          <Typography.Text
            strong
            type={pct >= 99 ? "success" : pct >= 90 ? "warning" : "danger"}
          >
            {pct}%
          </Typography.Text>
          <Progress
            className="w-24"
            percent={Math.min(pct, 100)}
            size="small"
            showInfo={false}
            strokeColor={pct >= 99 ? "#059669" : pct >= 90 ? "#D97706" : "#DC2626"}
            aria-label={`Uptime ${pct}%`}
          />
        </Space>
      ),
    },
    { title: "Heartbeats", dataIndex: "heartbeats", align: "right" },
    {
      title: "Covered",
      align: "right",
      responsive: ["lg"],
      render: (_, row) => (
        <Typography.Text type="secondary">
          {Math.round(row.covered_seconds / 3600)}h / {Math.round(row.window_seconds / 3600)}h
        </Typography.Text>
      ),
    },
  ];

  return (
    <div>
      <FilterBar>
        <DatePicker
          allowClear={false}
          value={dayjs(dateFrom)}
          aria-label="From date"
          onChange={(date) => date && setDateFrom(date.format("YYYY-MM-DD"))}
        />
        <DatePicker
          allowClear={false}
          value={dayjs(dateTo)}
          aria-label="To date"
          onChange={(date) => date && setDateTo(date.format("YYYY-MM-DD"))}
        />
        <ExportButtons report="device-uptime" filters={filters} />
      </FilterBar>
      <Table<UptimeRow>
        size="middle"
        rowKey="device_id"
        columns={columns}
        dataSource={rows}
        loading={query.isLoading}
        pagination={false}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: <EmptyState title="No uptime data in this range" /> }}
      />
    </div>
  );
}
