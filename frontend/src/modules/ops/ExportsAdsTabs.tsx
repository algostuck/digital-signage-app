import { CaretRightOutlined, DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  type TableProps,
} from "antd";
import { useState } from "react";
import { EmptyState } from "../../components/ui/states";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { ExportButtons } from "./AnalyticsTabs";

interface ExportRow {
  id: string;
  name: string;
  dataset: string;
  state: string;
  last_run_at: string | null;
  last_error: string | null;
  last_object_key: string | null;
}

interface AdPerfRow {
  booking_id: string;
  advertiser: string;
  inventory: string | null;
  campaign: string | null;
  status: string;
  booked_units: number;
  delivered_billable: number;
  delivered_total: number;
  fill_rate_pct: number;
}

const DATASETS = ["playback_events", "analytics_aggregates", "ad_performance"];

/** P3-22 Analytics Data Export: scheduled dataset dumps to storage. */
export function ExportsTab() {
  const { hasPermission } = useAuth();
  const canExport = hasPermission("reports.export");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [form] = Form.useForm<{ name: string; dataset: string }>();

  const exportsQuery = useQuery({
    queryKey: ["data-exports"],
    queryFn: () => api.get<ExportRow[]>("/data-exports"),
    enabled: canExport,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["data-exports"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const create = useMutation({
    mutationFn: (values: { name: string; dataset: string }) =>
      api.post("/data-exports", { name: values.name, dataset: values.dataset }),
    onSuccess: () => {
      refresh();
      setError(null);
      form.resetFields();
    },
    onError,
  });
  const run = useMutation({
    mutationFn: (id: string) => api.post(`/data-exports/${id}/run`, {}),
    onSuccess: () => refresh(),
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/data-exports/${id}`),
    onSuccess: () => refresh(),
    onError,
  });

  if (!canExport)
    return (
      <Typography.Text type="secondary">
        Requires the reports.export permission.
      </Typography.Text>
    );

  const rows = exportsQuery.data?.data ?? [];

  const columns: TableProps<ExportRow>["columns"] = [
    {
      title: "Name",
      dataIndex: "name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    {
      title: "Dataset",
      dataIndex: "dataset",
      render: (dataset: string) => (
        <Typography.Text code className="text-xs">
          {dataset}
        </Typography.Text>
      ),
    },
    {
      title: "State",
      dataIndex: "state",
      render: (_, row) => (
        <Space orientation="vertical" size={0}>
          <Tag
            variant="filled"
            color={row.state === "idle" ? "success" : row.state === "error" ? "error" : "processing"}
          >
            {row.state}
          </Tag>
          {row.last_error && (
            <Typography.Text type="danger" className="text-xs" ellipsis={{ tooltip: row.last_error }}>
              {row.last_error}
            </Typography.Text>
          )}
        </Space>
      ),
    },
    {
      title: "Last run",
      dataIndex: "last_run_at",
      responsive: ["lg"],
      render: (_, row) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text type="secondary" className="text-xs">
            {row.last_run_at ? `last ${new Date(row.last_run_at).toLocaleString()}` : "never run"}
          </Typography.Text>
          {row.last_object_key && (
            <Typography.Text
              code
              className="text-xs"
              ellipsis={{ tooltip: row.last_object_key }}
            >
              {row.last_object_key}
            </Typography.Text>
          )}
        </Space>
      ),
    },
    {
      title: "Actions",
      align: "right",
      render: (_, row) => (
        <Space>
          <Button
            size="small"
            icon={<CaretRightOutlined />}
            loading={run.isPending && run.variables === row.id}
            onClick={() => run.mutate(row.id)}
          >
            Run now
          </Button>
          <Popconfirm
            title={`Delete export "${row.name}"?`}
            okButtonProps={{ danger: true }}
            onConfirm={() => remove.mutate(row.id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Space orientation="vertical" size="middle" className="w-full">
      <Typography.Text type="secondary" className="text-xs">
        Scheduled exports run nightly for the previous day and land as CSV in
        the platform object storage — the hand-off point to your own
        warehouse. "Run now" exports yesterday's window immediately.
      </Typography.Text>

      <Card size="small">
        <Form
          form={form}
          layout="inline"
          initialValues={{ name: "", dataset: "playback_events" }}
          onFinish={(values) => {
            setError(null);
            create.mutate(values);
          }}
        >
          <Form.Item
            name="name"
            label="Name"
            rules={[{ required: true, message: "Name is required" }]}
          >
            <Input className="w-56" />
          </Form.Item>
          <Form.Item name="dataset" label="Dataset">
            <Select
              className="w-52"
              options={DATASETS.map((d) => ({ value: d, label: d }))}
            />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              icon={<PlusOutlined />}
              loading={create.isPending}
            >
              Create export
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Table<ExportRow>
        size="middle"
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={exportsQuery.isLoading}
        pagination={false}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: <EmptyState title="No scheduled exports yet" /> }}
      />

      {error && <Alert type="error" message={error} showIcon role="alert" />}
    </Space>
  );
}

const adColumns: TableProps<AdPerfRow>["columns"] = [
  {
    title: "Advertiser",
    dataIndex: "advertiser",
    render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
  },
  {
    title: "Slot / campaign",
    responsive: ["lg"],
    render: (_, row) => (
      <Typography.Text type="secondary" className="text-xs">
        {row.inventory} · {row.campaign}
      </Typography.Text>
    ),
  },
  { title: "Status", dataIndex: "status" },
  { title: "Booked", dataIndex: "booked_units", align: "right" },
  { title: "Delivered (billable)", dataIndex: "delivered_billable", align: "right" },
  {
    title: "Fill rate",
    dataIndex: "fill_rate_pct",
    align: "right",
    render: (pct: number) => (
      <Typography.Text strong type={pct >= 100 ? "success" : "warning"}>
        {pct}%
      </Typography.Text>
    ),
  },
];

/** P3-11 Ad Performance: booked vs delivered vs fill rate (billing-ready). */
export function AdsReportTab() {
  const reportQuery = useQuery({
    queryKey: ["ad-performance"],
    queryFn: () => api.get<AdPerfRow[]>("/reports/ad-performance"),
    retry: false,
  });

  if (reportQuery.isError)
    return <Alert type="warning" message="Ad performance unavailable." showIcon role="alert" />;

  const rows = reportQuery.data?.data ?? [];
  return (
    <Space orientation="vertical" size="middle" className="w-full">
      <ExportButtons report="ad-performance" filters={{}} />
      <Table<AdPerfRow>
        size="middle"
        rowKey="booking_id"
        columns={adColumns}
        dataSource={rows}
        loading={reportQuery.isLoading}
        pagination={false}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: <EmptyState title="No ad bookings yet" /> }}
      />
    </Space>
  );
}
