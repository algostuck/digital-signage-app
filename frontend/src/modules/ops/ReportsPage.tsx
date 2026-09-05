import { useQuery } from "@tanstack/react-query";
import { Card, Space, Table, Tabs, Typography, type TableProps } from "antd";
import { useState } from "react";
import { PageHeader } from "../../components/ui/PageHeader";
import { EmptyState, LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api } from "../../lib/api";
import { EntitlementGuard } from "../../components/ui/EntitlementGuard";
import { CampaignAnalyticsTab, ProofOfPlayTab, UptimeTab } from "./AnalyticsTabs";
import { AdsReportTab, ExportsTab } from "./ExportsAdsTabs";

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

/** SCR-24 Reports + P2-15/16/17 analytics & exports. */
export function ReportsPage() {
  const [tab, setTab] = useState<string>("overview");

  return (
    <div>
      <PageHeader
        title="Reports"
        description="Deployment, proof-of-play, uptime and ad performance reporting."
      />
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          { key: "overview", label: "Overview", children: <OverviewTab /> },
          {
            key: "pop",
            label: "Proof of play",
            children: (
              <EntitlementGuard feature="proof_of_play" featureName="Proof of play">
                <ProofOfPlayTab />
              </EntitlementGuard>
            ),
          },
          {
            key: "analytics",
            label: "Campaign analytics",
            children: (
              <EntitlementGuard feature="advanced_analytics" featureName="Campaign analytics">
                <CampaignAnalyticsTab />
              </EntitlementGuard>
            ),
          },
          { key: "uptime", label: "Uptime", children: <UptimeTab /> },
          { key: "ads", label: "Ads", children: <AdsReportTab /> },
          {
            key: "exports",
            label: "Exports",
            children: (
              <EntitlementGuard feature="advanced_analytics" featureName="Data exports">
                <ExportsTab />
              </EntitlementGuard>
            ),
          },
        ]}
      />
    </div>
  );
}

const deploymentColumns: TableProps<DeploymentRow>["columns"] = [
  {
    title: "Campaign",
    dataIndex: "campaign_name",
    render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
  },
  {
    title: "Status",
    dataIndex: "status",
    render: (status: string) => <StatusBadge status={status} />,
  },
  { title: "Deployments", dataIndex: "deployments", align: "right" },
  {
    title: "Latest",
    dataIndex: "latest_version",
    align: "right",
    responsive: ["lg"],
    render: (version: number | null) => `v${version}`,
  },
  {
    title: "Acked",
    dataIndex: "acknowledged",
    align: "right",
    render: (value: number) => <Typography.Text type="success">{value}</Typography.Text>,
  },
  {
    title: "Failed",
    dataIndex: "failed",
    align: "right",
    render: (value: number) => <Typography.Text type="danger">{value}</Typography.Text>,
  },
  { title: "Pending", dataIndex: "pending", align: "right" },
];

const playbackColumns: TableProps<PlaybackRow>["columns"] = [
  {
    title: "Content",
    dataIndex: "asset_name",
    render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
  },
  { title: "Plays", dataIndex: "plays", align: "right" },
  { title: "Devices reached", dataIndex: "devices_reached", align: "right" },
];

const locationColumns: TableProps<LocationRow>["columns"] = [
  {
    title: "Location",
    dataIndex: "location_name",
    render: (_, row) => (
      <Typography.Text strong style={{ paddingLeft: row.depth * 12 }}>
        {row.location_name}
      </Typography.Text>
    ),
  },
  { title: "Devices", dataIndex: "devices", align: "right" },
  {
    title: "Online",
    dataIndex: "online",
    align: "right",
    render: (value: number) => <Typography.Text type="success">{value}</Typography.Text>,
  },
  {
    title: "Warning",
    dataIndex: "warning",
    align: "right",
    render: (value: number) => <Typography.Text type="warning">{value}</Typography.Text>,
  },
  {
    title: "Offline",
    dataIndex: "offline",
    align: "right",
    render: (value: number) => <Typography.Text type="danger">{value}</Typography.Text>,
  },
];

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
    return <LoadingState rows={8} />;
  }

  const deployments = deploymentsQuery.data?.data ?? [];
  const playback = playbackQuery.data?.data ?? [];
  const locations = locationsQuery.data?.data ?? [];

  return (
    <Space orientation="vertical" size="large" className="w-full">
      <Card size="small" title="Campaign deployments">
        <Table<DeploymentRow>
          size="middle"
          rowKey="campaign_id"
          columns={deploymentColumns}
          dataSource={deployments}
          pagination={false}
          scroll={{ x: "max-content" }}
          locale={{ emptyText: <EmptyState title="No data yet" /> }}
        />
      </Card>

      <Card size="small" title="Playback (proof-of-play foundation)">
        <Table<PlaybackRow>
          size="middle"
          rowKey="asset_id"
          columns={playbackColumns}
          dataSource={playback}
          pagination={false}
          scroll={{ x: "max-content" }}
          locale={{ emptyText: <EmptyState title="No data yet" /> }}
        />
      </Card>

      <Card size="small" title="Device health by location">
        <Table<LocationRow>
          size="middle"
          rowKey="location_id"
          columns={locationColumns}
          dataSource={locations}
          pagination={false}
          scroll={{ x: "max-content" }}
          locale={{ emptyText: <EmptyState title="No data yet" /> }}
        />
      </Card>
    </Space>
  );
}
