import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Form, Input, InputNumber, Row, Select, Space, Typography, type TableProps } from "antd";
import { useState } from "react";

import { DataTable } from "@/design-system";
import { SectionCard } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface DataSourceRow {
  id: string;
  name: string;
  type: string;
  endpoint: string;
  auth_header: string | null;
  auth_token_ref: string | null;
  cache_ttl_seconds: number;
  refresh_seconds: number;
  state: string;
  last_ok_at: string | null;
  last_error: string | null;
  schema: { required: string[] } | null;
}

interface TestResult {
  ok: boolean;
  error: string | null;
  sample: unknown;
}

interface CreateFormValues {
  name: string;
  type: string;
  endpoint: string;
  auth_header?: string;
  auth_token_ref?: string;
  cache_ttl_seconds: number;
  refresh_seconds: number;
  required_paths?: string;
}

/** P3-03 Data Source Manager: guarded external feeds for dynamic widgets.
 * Credentials never leave the server — sources reference an env-var NAME. */
export function DataSourcesSection() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("settings.manage");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [testResult, setTestResult] = useState<{ id: string; result: TestResult } | null>(null);
  const [form] = Form.useForm<CreateFormValues>();

  const sourcesQuery = useQuery({
    queryKey: ["data-sources"],
    queryFn: () => api.get<DataSourceRow[]>("/data-sources"),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["data-sources"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const create = useMutation({
    mutationFn: (values: CreateFormValues) => {
      const required = (values.required_paths ?? "")
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);
      return api.post("/data-sources", {
        name: values.name,
        type: values.type,
        endpoint: values.endpoint,
        auth_header: values.auth_header || null,
        auth_token_ref: values.auth_token_ref || null,
        cache_ttl_seconds: Number(values.cache_ttl_seconds),
        refresh_seconds: Number(values.refresh_seconds),
        schema_spec: required.length ? { required } : null,
      });
    },
    onSuccess: () => {
      refresh();
      setError(null);
      setCreateOpen(false);
      form.resetFields();
    },
    onError,
  });
  const test = useMutation({
    mutationFn: (id: string) => api.post<TestResult>(`/data-sources/${id}/test`, {}),
    onSuccess: (envelope, id) => setTestResult({ id, result: envelope.data! }),
    onError,
  });
  const refreshNow = useMutation({
    mutationFn: (id: string) => api.post(`/data-sources/${id}/refresh`, {}),
    onSuccess: () => refresh(),
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/data-sources/${id}`),
    onSuccess: () => refresh(),
    onError,
  });

  const sources = sourcesQuery.data?.data ?? [];

  const columns: TableProps<DataSourceRow>["columns"] = [
    {
      title: "Name",
      dataIndex: "name",
      render: (value: string) => <Typography.Text strong>{value}</Typography.Text>,
    },
    { title: "Type", dataIndex: "type" },
    {
      title: "Endpoint",
      dataIndex: "endpoint",
      ellipsis: true,
      render: (value: string) => (
        <Typography.Text code className="text-xs">
          {value}
        </Typography.Text>
      ),
    },
    {
      title: "Health",
      dataIndex: "state",
      render: (_, s) => (
        <>
          <StatusBadge status={s.state} />
          {s.last_error && (
            <Typography.Paragraph
              type="danger"
              ellipsis
              className="mt-1 max-w-xs text-xs" style={{ marginBottom: 0 }}
            >
              {s.last_error}
            </Typography.Paragraph>
          )}
        </>
      ),
    },
    ...(canManage
      ? [
          {
            title: "Actions",
            key: "actions",
            render: (_: unknown, s: DataSourceRow) => (
              <Space size="small">
                <Button size="small" onClick={() => test.mutate(s.id)}>
                  Test
                </Button>
                <Button size="small" onClick={() => refreshNow.mutate(s.id)}>
                  Refresh
                </Button>
                <Button size="small" danger onClick={() => remove.mutate(s.id)}>
                  Delete
                </Button>
              </Space>
            ),
          },
        ]
      : []),
  ];

  return (
    <SectionCard
      title="Data sources"
      actions={
        canManage && (
          <Button type="primary" onClick={() => setCreateOpen((v) => !v)}>
            {createOpen ? "Close" : "Add source"}
          </Button>
        )
      }
    >
      <Space orientation="vertical" size="medium" className="w-full">
        <Typography.Text type="secondary">
          Live REST/JSON and RSS feeds for dynamic widgets. Fetched
          server-side with SSRF guards; devices only receive validated
          snapshots — a downed feed degrades to last-known-good, then to
          the widget fallback.
        </Typography.Text>

        {createOpen && (
          <Card size="small" type="inner">
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                type: "rest_json",
                cache_ttl_seconds: 300,
                refresh_seconds: 900,
              }}
              onFinish={(values) => {
                setError(null);
                create.mutate(values);
              }}
            >
              <Row gutter={12}>
                <Col xs={24} sm={8}>
                  <Form.Item
                    name="name"
                    label="Name"
                    rules={[{ required: true, message: "Name is required" }]}
                  >
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item
                    name="endpoint"
                    label="Endpoint URL (https)"
                    rules={[{ required: true, message: "Endpoint is required" }]}
                  >
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="type" label="Type">
                    <Select
                      options={[
                        { value: "rest_json", label: "REST / JSON" },
                        { value: "rss", label: "RSS / Atom" },
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="auth_header" label="Auth header (optional)">
                    <Input placeholder="Authorization" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="auth_token_ref" label="Token env-var NAME (optional)">
                    <Input placeholder="DS_FEED_TOKEN" />
                  </Form.Item>
                </Col>
                <Col xs={12} sm={4}>
                  <Form.Item name="cache_ttl_seconds" label="Cache TTL (s)">
                    <InputNumber className="w-full" />
                  </Form.Item>
                </Col>
                <Col xs={12} sm={4}>
                  <Form.Item name="refresh_seconds" label="Refresh every (s)">
                    <InputNumber className="w-full" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={16}>
                  <Form.Item
                    name="required_paths"
                    label="Required paths (schema, comma-separated — e.g. city, items)"
                  >
                    <Input />
                  </Form.Item>
                </Col>
              </Row>
              <Button type="primary" htmlType="submit" loading={create.isPending}>
                Create source
              </Button>
            </Form>
          </Card>
        )}

        <DataTable<DataSourceRow>
          rowKey="id"
          columns={columns}
          dataSource={sources}
          pagination={false}
          loading={sourcesQuery.isLoading}
          emptyTitle="No data sources yet"
        />

        {testResult && (
          <Alert
            type={testResult.result.ok ? "success" : "error"}
            showIcon
            message={
              <>
                Test {testResult.result.ok ? "passed" : "failed"}
                {testResult.result.error && ` — ${testResult.result.error}`}
              </>
            }
            description={
              testResult.result.sample != null && (
                <pre className="max-h-40 overflow-auto font-mono text-xs">
                  {JSON.stringify(testResult.result.sample, null, 2)}
                </pre>
              )
            }
          />
        )}

        {error && <Alert type="error" message={error} showIcon role="alert" />}
      </Space>
    </SectionCard>
  );
}
