
import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Form, InputNumber, Progress, Row, Space, Typography } from "antd";

import { useEffect, useState } from "react";

import { LoadingState } from "@/design-system";

import { api } from "../../../lib/api";
import { usePlatformFeedback, useTenantQuotas } from "../api";

import { type TenantDetail, type UsageMetric } from "../types";

function UsageBar({ label, metric, unit }: { label: string; metric: UsageMetric; unit?: string }) {
  const percent = metric.limit ? Math.min(100, Math.round((metric.used / metric.limit) * 100)) : 0;
  const status = percent >= 100 ? "exception" : percent >= 85 ? "active" : "normal";
  return (
    <div>
      <div className="mb-1 flex justify-between">
        <Typography.Text>{label}</Typography.Text>
        <Typography.Text type="secondary">
          {metric.used.toLocaleString()}
          {unit ? ` ${unit}` : ""} / {metric.limit == null ? "unlimited" : metric.limit.toLocaleString()}
        </Typography.Text>
      </div>
      <Progress
        percent={metric.limit ? percent : 0}
        status={status}
        showInfo={false}
        size="small"
        aria-label={`${label} usage`}
      />
    </div>
  );
}

const QUOTA_FIELDS = [
  ["max_devices", "Devices"],
  ["max_users", "Users"],
  ["max_storage_mb", "Storage (MB)"],
] as const;

export function QuotasTab({ tenant }: { tenant: TenantDetail }) {
  const feedback = usePlatformFeedback();
  const quotas = useTenantQuotas(tenant.id);
  const [form] = Form.useForm<Record<string, number | null>>();
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    const q = quotas.data?.data?.quotas;
    if (q) {
      form.setFieldsValue({
        max_devices: q.max_devices ?? null,
        max_users: q.max_users ?? null,
        max_storage_mb: q.max_storage_mb ?? null,
      });
      setDirty(false);
    }
  }, [quotas.data, form]);

  const save = useMutation({
    mutationFn: (values: Record<string, number | null>) =>
      api.patch(`/platform/tenants/${tenant.id}/quotas`, {
        max_devices: values.max_devices ?? null,
        max_users: values.max_users ?? null,
        max_storage_mb: values.max_storage_mb ?? null,
      }),
    onSuccess: () => {
      feedback.done("Quota overrides saved.");
      setDirty(false);
    },
    onError: feedback.onError,
  });

  if (quotas.isLoading || !quotas.data?.data) return <LoadingState rows={5} />;
  const usage = quotas.data.data.usage;

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={12}>
        <Card size="small" title="Usage against effective limits">
          <Space orientation="vertical" size="medium" className="w-full">
            <UsageBar label="Devices" metric={usage.devices} />
            <UsageBar label="Users" metric={usage.users} />
            <UsageBar label="Storage" metric={usage.storage_mb} unit="MB" />
          </Space>
          <Typography.Paragraph type="secondary" className="!mb-0 mt-3 text-xs">
            Effective limit = plan entitlement, capped by any override on the right.
          </Typography.Paragraph>
        </Card>
      </Col>
      <Col xs={24} xl={12}>
        <Card size="small" title="Quota overrides">
          <Alert
            type="info"
            showIcon
            className="mb-4"
            message="Overrides only tighten. A value above the plan's limit has no effect; blank removes the override."
          />
          <Form
            form={form}
            layout="vertical"
            onValuesChange={() => setDirty(true)}
            onFinish={(values) => save.mutate(values)}
          >
            <Row gutter={12}>
              {QUOTA_FIELDS.map(([key, label]) => (
                <Col key={key} xs={8}>
                  <Form.Item name={key} label={label}>
                    <InputNumber min={1} className="w-full" placeholder="Plan limit" />
                  </Form.Item>
                </Col>
              ))}
            </Row>
            <Button type="primary" htmlType="submit" loading={save.isPending} disabled={!dirty}>
              Save overrides
            </Button>
          </Form>
        </Card>
      </Col>
    </Row>
  );
}
