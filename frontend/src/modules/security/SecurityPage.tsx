import { SyncOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Form, InputNumber, Popconfirm, Row, Space, Typography, type TableProps } from "antd";
import { ToneTag } from "@/design-system";
import { DataTable } from "@/design-system";
import { toneOf } from "@/design-system";
import { useState } from "react";
import { PageHeader } from "@/design-system";
import { StatCard } from "@/design-system";

import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface IdentityRow {
  device_id: string;
  device_name: string;
  identity_type: string;
  has_credential: boolean;
  fingerprint: string | null;
  issued_at: string | null;
  age_days: number | null;
  credential_history: number;
}

interface ViolationRow {
  id: string;
  entity_type: string;
  entity_id: string;
  severity: string;
  state: string;
  detail: string | null;
  detected_at: string | null;
}

interface Summary {
  open_violations: Record<string, number>;
  device_identities: number;
  credentials_missing: number;
  oldest_credential_days: number;
}

interface PolicyRow {
  id: string;
  scope_type: string;
  conditions: { max_age_days: number };
  severity: string;
  active: boolean;
}

/** P3-21 Security Center: identities + credential lifecycle, age policies,
 * violations. Rotation forces standard re-registration — no side channel. */
export function SecurityPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("settings.manage");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [ageDays, setAgeDays] = useState("180");

  const summaryQuery = useQuery({
    queryKey: ["security-summary"],
    queryFn: () => api.get<Summary>("/security/summary"),
    enabled: canManage,
    retry: false,
  });
  const identitiesQuery = useQuery({
    queryKey: ["security-identities"],
    queryFn: () => api.get<IdentityRow[]>("/security/devices/identities"),
  });
  const violationsQuery = useQuery({
    queryKey: ["security-violations"],
    queryFn: () => api.get<ViolationRow[]>("/security/policy-violations?page_size=50"),
    enabled: canManage,
  });
  const policiesQuery = useQuery({
    queryKey: ["security-policies"],
    queryFn: () => api.get<PolicyRow[]>("/security/policies"),
    enabled: canManage,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["security-summary"] });
    queryClient.invalidateQueries({ queryKey: ["security-identities"] });
    queryClient.invalidateQueries({ queryKey: ["security-violations"] });
    queryClient.invalidateQueries({ queryKey: ["security-policies"] });
  };
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const rotate = useMutation({
    mutationFn: (deviceId: string) => api.post(`/security/devices/${deviceId}/rotate`, {}),
    onSuccess: () => refresh(),
    onError,
  });
  const savePolicy = useMutation({
    mutationFn: (scope: string) =>
      api.post("/security/policies", {
        scope_type: scope,
        conditions: { max_age_days: Number(ageDays) },
      }),
    onSuccess: () => refresh(),
    onError,
  });
  const resolve = useMutation({
    mutationFn: (id: string) => api.post(`/security/policy-violations/${id}/resolve`, {}),
    onSuccess: () => refresh(),
    onError,
  });

  const summary = summaryQuery.data?.data ?? null;
  const identities = identitiesQuery.data?.data ?? [];
  const violations = violationsQuery.data?.data ?? [];
  const policies = policiesQuery.data?.data ?? [];

  const violationColumns: TableProps<ViolationRow>["columns"] = [
    { title: "Entity", dataIndex: "entity_type" },
    {
      title: "Detail",
      dataIndex: "detail",
      responsive: ["lg"],
      render: (detail: string | null) => (
        <Typography.Text type="secondary">{detail}</Typography.Text>
      ),
    },
    {
      title: "Status",
      render: (_, v) => (
        <ToneTag tone={toneOf(
            v.state === "open"
              ? v.severity === "critical"
                ? "error"
                : "warning"
              : "success"
          )}
        >
          {v.state} · {v.severity}
        </ToneTag>
      ),
    },
    {
      title: "Actions",
      render: (_, v) =>
        v.state === "open" && (
          <Button size="small" onClick={() => resolve.mutate(v.id)}>
            Resolve
          </Button>
        ),
    },
  ];

  const identityColumns: NonNullable<TableProps<IdentityRow>["columns"]> = [
    {
      title: "Device",
      dataIndex: "device_name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    {
      title: "Fingerprint",
      render: (_, row) =>
        row.fingerprint ? (
          <Typography.Text code className="text-xs">
            {row.fingerprint}
          </Typography.Text>
        ) : (
          <Typography.Text type="secondary" className="text-xs">
            — pending re-enrollment
          </Typography.Text>
        ),
    },
    {
      title: "Age",
      align: "right",
      render: (_, row) => (row.age_days != null ? `${row.age_days}d` : "—"),
    },
    {
      title: "History",
      dataIndex: "credential_history",
      align: "right",
      responsive: ["lg"],
    },
  ];
  if (canManage)
    identityColumns.push({
      title: "Actions",
      render: (_, row) =>
        row.has_credential && (
          <Popconfirm
            title={`Rotate credential for ${row.device_name}?`}
            description="The token is revoked and the player re-enrolls through the standard pipeline."
            okButtonProps={{ danger: true }}
            onConfirm={() => rotate.mutate(row.device_id)}
          >
            <Button size="small" icon={<SyncOutlined />}>
              Rotate
            </Button>
          </Popconfirm>
        ),
    });

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="Security Center"
        description="Device credential lifecycle, age policies and violations. Rotation revokes the token — the player re-enrolls through the standard pipeline."
      />
      <Space orientation="vertical" size="large" className="w-full">
        {summary && (
          <Row gutter={[12, 12]}>
            <Col xs={12} sm={6}>
              <StatCard label="Identities" value={summary.device_identities} />
            </Col>
            <Col xs={12} sm={6}>
              <StatCard
                label="Open violations"
                value={Object.values(summary.open_violations).reduce((a, b) => a + b, 0)}
                tone={
                  Object.values(summary.open_violations).reduce((a, b) => a + b, 0)
                    ? "error"
                    : undefined
                }
              />
            </Col>
            <Col xs={12} sm={6}>
              <StatCard
                label="Missing credentials"
                value={summary.credentials_missing}
                tone={summary.credentials_missing ? "warning" : undefined}
              />
            </Col>
            <Col xs={12} sm={6}>
              <StatCard
                label="Oldest credential"
                value={`${summary.oldest_credential_days}d`}
              />
            </Col>
          </Row>
        )}

        {canManage && (
          <Card size="small" title="Age policies">
            <Form layout="inline">
              <Form.Item label="Max age (days)">
                <InputNumber
                  min={1}
                  className="w-24"
                  value={ageDays === "" ? null : Number(ageDays)}
                  onChange={(v) => setAgeDays(v == null ? "" : String(v))}
                />
              </Form.Item>
              <Form.Item className="max-w-full">
                <Space wrap>
                  <Button
                    type="primary"
                    loading={savePolicy.isPending}
                    onClick={() => savePolicy.mutate("device_credentials")}
                  >
                    Apply to device tokens
                  </Button>
                  <Button
                    loading={savePolicy.isPending}
                    onClick={() => savePolicy.mutate("api_keys")}
                  >
                    Apply to API keys
                  </Button>
                  {policies.map((p) => (
                    <ToneTag tone="default" key={p.id}>
                      {p.scope_type}: {p.conditions.max_age_days}d ({p.severity})
                    </ToneTag>
                  ))}
                </Space>
              </Form.Item>
            </Form>
            <Typography.Paragraph type="secondary" className="mt-2 text-xs" style={{ marginBottom: 0 }}>
              The daily sweep opens violations for over-age credentials and
              auto-resolves them once rotated. Violations are surfaced, never
              auto-enforced.
            </Typography.Paragraph>
          </Card>
        )}

        {canManage && violations.length > 0 && (
          <Card size="small" title="Policy violations">
            <DataTable<ViolationRow>
              rowKey="id"
              columns={violationColumns}
              dataSource={violations}
              loading={violationsQuery.isLoading}
              pagination={false}
            />
          </Card>
        )}

        <Card size="small" title="Device identities">
          <DataTable<IdentityRow>
            rowKey="device_id"
            columns={identityColumns}
            dataSource={identities}
            loading={identitiesQuery.isLoading}
            emptyTitle="No device identities yet"
          />
        </Card>

        {error && <Alert type="error" showIcon role="alert" message={error} />}
      </Space>
    </div>
  );
}
