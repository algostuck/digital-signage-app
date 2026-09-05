import { DownOutlined } from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import { Alert, App, Button, Card, Col, Descriptions, Dropdown, Form, Input, InputNumber, Modal, Row, Select, Space, Typography } from "antd";

import { useEffect, useState } from "react";

import { LoadingState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api } from "../../../lib/api";
import { formatDate, usePlans, usePlatformFeedback, useTenantSubscription } from "../api";

import { BILLING_CYCLES, PROVIDERS, SUB_STATUSES, type TenantDetail } from "../types";

interface AssignValues {
  plan_code: string;
  billing_cycle: string;
  trial_days: number;
}

interface ProviderValues {
  provider: string;
  provider_customer_id?: string;
  provider_subscription_id?: string;
}

const DANGER_SUB_STATUSES = ["suspended", "cancelled", "expired"];

export function SubscriptionTab({ tenant }: { tenant: TenantDetail }) {
  const feedback = usePlatformFeedback();
  const { modal } = App.useApp();
  const sub = useTenantSubscription(tenant.id);
  const plans = usePlans();
  const [changePlanOpen, setChangePlanOpen] = useState(false);
  const [assignForm] = Form.useForm<AssignValues>();
  const [planForm] = Form.useForm<{ plan_code: string }>();
  const [providerForm] = Form.useForm<ProviderValues>();
  const [providerDirty, setProviderDirty] = useState(false);

  const subscription = sub.data?.data?.subscription ?? null;
  const activePlans = (plans.data?.data ?? []).filter((p) => p.is_active);

  useEffect(() => {
    if (subscription) {
      providerForm.setFieldsValue({
        provider: subscription.provider,
        provider_customer_id: "",
        provider_subscription_id: "",
      });
      setProviderDirty(false);
    }
  }, [subscription, providerForm]);

  const assign = useMutation({
    mutationFn: (values: AssignValues) => api.post(`/platform/tenants/${tenant.id}/subscription`, values),
    onSuccess: () => feedback.done("Subscription assigned — the first invoice has been issued."),
    onError: feedback.onError,
  });
  const changePlan = useMutation({
    mutationFn: (plan_code: string) =>
      api.patch(`/platform/tenants/${tenant.id}/subscription/plan`, { plan_code }),
    onSuccess: () => {
      feedback.done("Plan changed.");
      setChangePlanOpen(false);
      planForm.resetFields();
    },
    onError: feedback.onError,
  });
  const transition = useMutation({
    mutationFn: (to_status: string) =>
      api.post(`/platform/tenants/${tenant.id}/subscription/transition`, {
        to_status,
        event: "admin_transition",
      }),
    onSuccess: (_d, to) => feedback.done(`Subscription is now ${to.replace(/_/g, " ")}.`),
    onError: feedback.onError,
  });
  const saveProvider = useMutation({
    mutationFn: (values: ProviderValues) =>
      api.patch(`/platform/tenants/${tenant.id}/subscription/provider`, {
        provider: values.provider,
        provider_customer_id: values.provider_customer_id?.trim() || null,
        provider_subscription_id: values.provider_subscription_id?.trim() || null,
      }),
    onSuccess: () => {
      feedback.done("Payment provider saved.");
      setProviderDirty(false);
    },
    onError: feedback.onError,
  });

  if (sub.isLoading) return <LoadingState rows={6} />;

  if (!subscription) {
    return (
      <Card size="small" title="Assign a plan">
        <Alert
          type="info"
          showIcon
          className="mb-4"
          message="This tenant has no subscription and runs in legacy mode — no limits, no entitlement gates."
        />
        <Form
          form={assignForm}
          layout="inline"
          initialValues={{ billing_cycle: "monthly", trial_days: 0 }}
          onFinish={(values) => assign.mutate(values)}
        >
          <Form.Item name="plan_code" label="Plan" rules={[{ required: true, message: "Choose a plan." }]}>
            <Select
              className="w-52"
              placeholder="Choose a plan"
              loading={plans.isLoading}
              options={activePlans.map((p) => ({ value: p.code, label: p.name }))}
            />
          </Form.Item>
          <Form.Item name="billing_cycle" label="Cycle">
            <Select className="w-32" options={BILLING_CYCLES.map((c) => ({ value: c, label: c }))} />
          </Form.Item>
          <Form.Item name="trial_days" label="Trial days">
            <InputNumber min={0} max={365} className="w-24" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={assign.isPending}>
            Assign plan
          </Button>
        </Form>
      </Card>
    );
  }

  const transitionItems = SUB_STATUSES.filter((s) => s !== subscription.status).map((s) => {
    const danger = DANGER_SUB_STATUSES.includes(s);
    return {
      key: s,
      label: s.replace(/_/g, " "),
      danger,
      onClick: () =>
        modal.confirm({
          title: `Set subscription to "${s.replace(/_/g, " ")}"?`,
          content:
            s === "active"
              ? "Growth actions (new devices, users, uploads) are allowed again."
              : danger
                ? "Growth actions are blocked. Existing screens keep playing cached content."
                : "Recorded on the subscription's event trail.",
          okText: "Apply",
          okButtonProps: { danger },
          onOk: () => transition.mutateAsync(s),
        }),
    };
  });

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={14}>
        <Card
          size="small"
          title="Current subscription"
          extra={
            <Space>
              <Button onClick={() => setChangePlanOpen(true)}>Change plan</Button>
              <Dropdown menu={{ items: transitionItems }} trigger={["click"]}>
                <Button loading={transition.isPending}>
                  Set status <DownOutlined />
                </Button>
              </Dropdown>
            </Space>
          }
        >
          <Descriptions
            column={{ xs: 1, sm: 2 }}
            size="small"
            items={[
              {
                key: "plan",
                label: "Plan",
                children: <Typography.Text strong>{subscription.plan.name}</Typography.Text>,
              },
              { key: "status", label: "Status", children: <StatusBadge status={subscription.status} /> },
              { key: "cycle", label: "Billing cycle", children: subscription.billing_cycle },
              { key: "provider", label: "Provider", children: subscription.provider },
              { key: "start", label: "Started", children: formatDate(subscription.start_at) },
              {
                key: "period",
                label: "Current period",
                children: `${formatDate(subscription.current_period_start)} – ${formatDate(subscription.current_period_end)}`,
              },
              ...(subscription.trial_end_at
                ? [{ key: "trial", label: "Trial ends", children: formatDate(subscription.trial_end_at) }]
                : []),
              ...(subscription.cancelled_at
                ? [{ key: "cancelled", label: "Cancelled", children: formatDate(subscription.cancelled_at) }]
                : []),
            ]}
          />
        </Card>
      </Col>

      <Col xs={24} xl={10}>
        <Card size="small" title="Payment provider">
          <Typography.Paragraph type="secondary" className="text-xs" style={{ marginBottom: 12 }}>
            Manual is the enterprise invoice flow — record payments on the Invoices tab. Gateway
            credentials are server configuration and are never entered here; only references.
          </Typography.Paragraph>
          <Form
            form={providerForm}
            layout="vertical"
            onValuesChange={() => setProviderDirty(true)}
            onFinish={(values) => saveProvider.mutate(values)}
          >
            <Form.Item name="provider" label="Provider" rules={[{ required: true }]}>
              <Select options={PROVIDERS.map((p) => ({ value: p, label: p }))} />
            </Form.Item>
            <Form.Item name="provider_customer_id" label="Customer reference">
              <Input placeholder="e.g. cus_…" maxLength={200} />
            </Form.Item>
            <Form.Item name="provider_subscription_id" label="Subscription reference">
              <Input placeholder="e.g. sub_…" maxLength={200} />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={saveProvider.isPending} disabled={!providerDirty}>
              Save provider
            </Button>
          </Form>
        </Card>
      </Col>

      <Modal
        title="Change plan"
        open={changePlanOpen}
        onCancel={() => setChangePlanOpen(false)}
        okText="Change plan"
        confirmLoading={changePlan.isPending}
        onOk={() => planForm.submit()}
        destroyOnHidden
      >
        <Alert
          type="warning"
          showIcon
          className="mb-4"
          message="Applies immediately, up or down."
          description="Limits and features change for every user in the tenant. Quota overrides on the Usage tab still cap below the new plan."
        />
        <Form form={planForm} layout="vertical" onFinish={(v) => changePlan.mutate(v.plan_code)}>
          <Form.Item name="plan_code" label="New plan" rules={[{ required: true, message: "Choose a plan." }]}>
            <Select
              options={(plans.data?.data ?? [])
                .filter((p) => p.code !== subscription.plan.code)
                .map((p) => ({ value: p.code, label: p.is_active ? p.name : `${p.name} (inactive)` }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Row>
  );
}
