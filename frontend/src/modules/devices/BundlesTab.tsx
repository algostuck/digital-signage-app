import { BuildOutlined, SendOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Table,
  Typography,
  type TableProps,
} from "antd";
import { useState } from "react";
import { StatCard } from "@/design-system";
import { EmptyState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface BundleRow {
  id: string;
  name: string;
  version: number;
  group_id: string | null;
  state: string;
  expires_at: string | null;
  assets: number;
  devices: number;
  synced: number;
}

interface EdgeMetrics {
  bundles_by_state: Record<string, number>;
  published_coverage: { synced: number; pending: number };
  bandwidth_policy: { windows: { start: string; end: string }[]; concurrency: number };
}

interface BundleFormValues {
  name: string;
  group_id: string;
  ttl_days: number;
}

/** P3-12/13 Offline Bundle Manager + edge delivery metrics: signed
 * prefetch packs with rollout coverage; downloads resume via Range. */
export function BundlesTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("devices.manage");
  const queryClient = useQueryClient();
  const [form] = Form.useForm<BundleFormValues>();
  const [error, setError] = useState<string | null>(null);

  const bundlesQuery = useQuery({
    queryKey: ["edge-bundles"],
    queryFn: () => api.get<BundleRow[]>("/edge/bundles"),
    retry: false,
  });
  const metricsQuery = useQuery({
    queryKey: ["edge-metrics"],
    queryFn: () => api.get<EdgeMetrics>("/edge/metrics"),
    retry: false,
  });
  const groupsQuery = useQuery({
    queryKey: ["device-groups"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/device-groups"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["edge-bundles"] });
    queryClient.invalidateQueries({ queryKey: ["edge-metrics"] });
  };
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const create = useMutation({
    mutationFn: (values: BundleFormValues) =>
      api.post("/edge/bundles", {
        name: values.name,
        group_id: values.group_id || null,
        ttl_days: Number(values.ttl_days),
      }),
    onSuccess: () => {
      refresh();
      setError(null);
      form.resetFields();
    },
    onError,
  });
  const publish = useMutation({
    mutationFn: (id: string) => api.post(`/edge/bundles/${id}/publish`, {}),
    onSuccess: () => refresh(),
    onError,
  });

  if (bundlesQuery.isError)
    return (
      <Alert
        type="warning"
        showIcon
        role="alert"
        message={
          bundlesQuery.error instanceof ApiError
            ? bundlesQuery.error.message
            : "Edge bundles unavailable."
        }
      />
    );

  const bundles = bundlesQuery.data?.data ?? [];
  const metrics = metricsQuery.data?.data ?? null;
  const groups = groupsQuery.data?.data ?? [];

  const columns: TableProps<BundleRow>["columns"] = [
    {
      title: "Name",
      dataIndex: "name",
      render: (_, b) => (
        <Space size="small">
          <Typography.Text strong>{b.name}</Typography.Text>
          <Typography.Text code className="text-xs">
            v{b.version}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: "Contents",
      responsive: ["lg"],
      render: (_, b) =>
        `${b.assets} asset${b.assets === 1 ? "" : "s"} · ${b.synced}/${b.devices} synced` +
        (b.expires_at ? ` · expires ${new Date(b.expires_at).toLocaleDateString()}` : ""),
    },
    {
      title: "State",
      dataIndex: "state",
      render: (state: string) => <StatusBadge status={state} />,
    },
    {
      title: "Actions",
      align: "right",
      render: (_, b) =>
        canManage && b.state === "draft" ? (
          <Button
            size="small"
            type="primary"
            icon={<SendOutlined />}
            loading={publish.isPending}
            onClick={() => publish.mutate(b.id)}
          >
            Publish
          </Button>
        ) : null,
    },
  ];

  return (
    <Space orientation="vertical" size="middle" className="w-full">
      {metrics && (
        <Row gutter={[12, 12]}>
          <Col xs={12} sm={6}>
            <StatCard
              label="Published bundles"
              value={metrics.bundles_by_state.published ?? 0}
              loading={metricsQuery.isLoading}
            />
          </Col>
          <Col xs={12} sm={6}>
            <StatCard
              label="Devices synced"
              value={metrics.published_coverage.synced}
              valueColor="#059669"
              loading={metricsQuery.isLoading}
            />
          </Col>
          <Col xs={12} sm={6}>
            <StatCard
              label="Downloads queued"
              value={metrics.published_coverage.pending}
              valueColor="#d97706"
              loading={metricsQuery.isLoading}
            />
          </Col>
          <Col xs={12} sm={6}>
            <StatCard
              label="Bandwidth window"
              value={
                metrics.bandwidth_policy.windows.map((w) => `${w.start}–${w.end}`).join(", ") +
                ` · ×${metrics.bandwidth_policy.concurrency}`
              }
              loading={metricsQuery.isLoading}
            />
          </Col>
        </Row>
      )}

      {canManage && (
        <Card size="small">
          <Form
            form={form}
            layout="inline"
            initialValues={{ group_id: "", ttl_days: 7 }}
            onFinish={(values) => {
              setError(null);
              create.mutate(values);
            }}
            className="gap-y-2"
          >
            <Form.Item
              name="name"
              label="Bundle name"
              rules={[{ required: true, message: "Bundle name is required." }]}
            >
              <Input className="w-52" />
            </Form.Item>
            <Form.Item name="group_id" label="Scope">
              <Select
                className="w-44"
                options={[
                  { value: "", label: "All active devices" },
                  ...groups.map((g) => ({ value: g.id, label: g.name })),
                ]}
              />
            </Form.Item>
            <Form.Item name="ttl_days" label="Valid for (days)">
              <InputNumber min={1} max={90} className="w-24" />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                icon={<BuildOutlined />}
                loading={create.isPending}
              >
                Build bundle
              </Button>
            </Form.Item>
          </Form>
        </Card>
      )}

      <Card size="small" title="Offline bundles">
        <Typography.Paragraph type="secondary" className="!mb-2 text-xs">
          A bundle is a signed prefetch manifest built from the targets' live manifests —
          binaries stay in storage and downloads resume via HTTP Range. Publishing supersedes
          the previous bundle of the same scope.
        </Typography.Paragraph>
        <Table<BundleRow>
          size="middle"
          rowKey="id"
          columns={columns}
          dataSource={bundles}
          loading={bundlesQuery.isLoading}
          scroll={{ x: "max-content" }}
          pagination={false}
          locale={{
            emptyText: (
              <EmptyState
                title="No bundles yet"
                description="Build a bundle to prefetch content to devices ahead of playback."
              />
            ),
          }}
        />
      </Card>

      {error && <Alert type="error" message={error} showIcon role="alert" />}
    </Space>
  );
}
