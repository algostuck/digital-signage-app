import { CheckOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Flex,
  Form,
  Input,
  InputNumber,
  Row,
  Segmented,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  type TableProps,
} from "antd";
import { useState } from "react";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatCard } from "../../components/ui/StatCard";
import { EmptyState, LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo } from "../devices/types";
import { IntelligenceTab } from "./IntelligenceTab";

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

/** P2-13 Fleet Monitoring + P2-14 Incident Center. */
export function MonitoringPage() {
  const [tab, setTab] = useState<string>("health");

  return (
    <div>
      <PageHeader
        title="Monitoring"
        description="Fleet health rollups, incident lifecycle, and deterministic anomaly intelligence."
      />
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          { key: "health", label: "Fleet health", children: <FleetHealthTab /> },
          { key: "incidents", label: "Incidents", children: <IncidentsTab /> },
          { key: "intelligence", label: "Intelligence", children: <IntelligenceTab /> },
        ]}
      />
    </div>
  );
}

type HealthRow = Rollup & { key: string; label: string; indent: number };

const healthColumns: TableProps<HealthRow>["columns"] = [
  {
    title: "Name",
    render: (_, row) => <span style={{ paddingLeft: row.indent * 12 }}>{row.label}</span>,
  },
  { title: "Total", dataIndex: "total", align: "right", width: 70 },
  { title: "Online", dataIndex: "online", align: "right", width: 70 },
  { title: "Warning", dataIndex: "warning", align: "right", width: 80 },
  { title: "Offline", dataIndex: "offline", align: "right", width: 70 },
];

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

  if (healthQuery.isLoading || !health) return <LoadingState rows={6} />;
  const org = health.organization;

  return (
    <Space orientation="vertical" size="large" className="w-full">
      <Row gutter={[12, 12]}>
        <Col xs={12} sm={8} xl={4}>
          <StatCard label="Devices" value={org.total} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <StatCard label="Online" value={org.online} valueColor="#059669" />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <StatCard label="Warning" value={org.warning} valueColor={org.warning ? "#D97706" : undefined} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <StatCard label="Offline" value={org.offline} valueColor={org.offline ? "#DC2626" : undefined} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <StatCard
            label="Open incidents"
            value={org.open_incidents}
            valueColor={org.open_incidents ? "#DC2626" : undefined}
          />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <StatCard
            label="Outdated players"
            value={org.outdated_players}
            valueColor={org.outdated_players ? "#D97706" : undefined}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card size="small" title="By location (subtree rollup)">
            <Table<HealthRow>
              size="small"
              scroll={{ x: "max-content" }}
              columns={healthColumns}
              dataSource={health.locations.map((row) => ({
                key: row.id,
                label: row.name,
                indent: row.depth,
                ...row,
              }))}
              pagination={false}
              locale={{ emptyText: <EmptyState title="No devices assigned yet" /> }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="By group">
            <Table<HealthRow>
              size="small"
              scroll={{ x: "max-content" }}
              columns={healthColumns}
              dataSource={health.groups.map((row) => ({
                key: row.id,
                label: row.name,
                indent: 0,
                ...row,
                ...(row.group_type === "dynamic"
                  ? { label: `${row.name} (dynamic)` }
                  : {}),
              }))}
              pagination={false}
              locale={{ emptyText: <EmptyState title="No devices assigned yet" /> }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        size="small"
        title="Tenant thresholds"
        extra={
          canEdit && (
            <Button type="link" size="small" onClick={() => setEditOpen((v) => !v)}>
              {editOpen ? "Close" : "Edit"}
            </Button>
          )
        }
      >
        <Typography.Text type="secondary">
          warning after {health.thresholds.warning_after_seconds}s · offline after{" "}
          {health.thresholds.offline_after_seconds}s · storage alert at{" "}
          {health.thresholds.storage_alert_percent}% · min player version{" "}
          {health.thresholds.min_player_version ?? "—"}
        </Typography.Text>
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
        {error && <Alert type="error" message={error} showIcon className="mt-2" role="alert" />}
      </Card>
    </Space>
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
  const [form] = Form.useForm<{
    warning: number;
    offline: number;
    storage: number;
    min_version?: string;
  }>();

  const save = useMutation({
    mutationFn: (values: { warning: number; offline: number; storage: number; min_version?: string }) =>
      api.put("/monitoring/thresholds", {
        warning_after_seconds: values.warning,
        offline_after_seconds: values.offline,
        storage_alert_percent: values.storage,
        min_player_version: values.min_version?.trim() || null,
      }),
    onSuccess: onSaved,
    onError: (err) =>
      onError(err instanceof ApiError ? err.message : "Failed to save thresholds"),
  });

  return (
    <Form
      form={form}
      layout="inline"
      className="mt-3"
      initialValues={{
        warning: current.warning_after_seconds,
        offline: current.offline_after_seconds,
        storage: current.storage_alert_percent,
        min_version: current.min_player_version ?? "",
      }}
      onFinish={(values) => save.mutate(values)}
    >
      <Form.Item name="warning" label="Warning after (s)">
        <InputNumber min={1} className="w-28" />
      </Form.Item>
      <Form.Item name="offline" label="Offline after (s)">
        <InputNumber min={1} className="w-28" />
      </Form.Item>
      <Form.Item name="storage" label="Storage alert (%)">
        <InputNumber min={50} max={100} className="w-28" />
      </Form.Item>
      <Form.Item name="min_version" label="Min player version">
        <Input placeholder="e.g. 2.5.0" className="w-28" />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={save.isPending}>
          Save thresholds
        </Button>
      </Form.Item>
    </Form>
  );
}

const INCIDENT_STATES = [
  { value: "open", label: "Open" },
  { value: "acknowledged", label: "Acknowledged" },
  { value: "resolved", label: "Resolved" },
  { value: "", label: "All" },
];

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
    onError: (err) => setError(err instanceof ApiError ? err.message : "Action failed"),
  });

  const incidents = incidentsQuery.data?.data ?? [];

  return (
    <div>
      <Segmented
        value={state}
        onChange={(v) => setState(v as string)}
        options={INCIDENT_STATES}
        className="mb-3"
      />
      {error && <Alert type="error" message={error} showIcon className="mb-3" role="alert" />}
      {incidentsQuery.isLoading ? (
        <LoadingState rows={4} />
      ) : incidents.length === 0 ? (
        <Card>
          <EmptyState
            title="No incidents here"
            description="Offline and storage alerts appear automatically."
          />
        </Card>
      ) : (
        <Space orientation="vertical" size="small" className="w-full">
          {incidents.map((incident) => (
            <Card key={incident.id} size="small">
              <Flex wrap align="center" gap="small">
                <StatusBadge status={incident.state} />
                <Tag
                  color={incident.severity === "critical" ? "error" : "warning"}
                  icon={incident.severity === "critical" ? undefined : <ThunderboltOutlined />}
                  variant="filled"
                >
                  {incident.type}
                </Tag>
                <Typography.Text strong>{incident.title}</Typography.Text>
                <Typography.Text type="secondary" className="text-xs">
                  opened {timeAgo(incident.opened_at)}
                  {incident.resolved_at && ` · resolved ${timeAgo(incident.resolved_at)}`}
                  {incident.resolution && ` — ${incident.resolution}`}
                </Typography.Text>
                {canManage && incident.state === "open" && (
                  <Space className="ms-auto">
                    <Button
                      size="small"
                      onClick={() => transition.mutate({ id: incident.id, action: "acknowledge" })}
                    >
                      Acknowledge
                    </Button>
                    <Button
                      size="small"
                      type="primary"
                      icon={<CheckOutlined />}
                      onClick={() => transition.mutate({ id: incident.id, action: "resolve" })}
                    >
                      Resolve
                    </Button>
                  </Space>
                )}
                {canManage && incident.state === "acknowledged" && (
                  <Button
                    size="small"
                    type="primary"
                    icon={<CheckOutlined />}
                    className="ms-auto"
                    onClick={() => transition.mutate({ id: incident.id, action: "resolve" })}
                  >
                    Resolve
                  </Button>
                )}
              </Flex>
            </Card>
          ))}
        </Space>
      )}
    </div>
  );
}
