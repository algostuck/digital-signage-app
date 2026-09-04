import { DownOutlined, DownloadOutlined } from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Descriptions,
  Dropdown,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Tabs,
  Tag,
  Typography,
  type TableProps,
} from "antd";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { DataTable } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { ErrorState, LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api } from "../../lib/api";
import {
  formatDate,
  formatMoney,
  isOverdue,
  timezoneOptions,
  usePlans,
  usePlatformFeedback,
  useTenant,
  useTenantInvoices,
  useTenantQuotas,
  useTenantSubscription,
} from "./api";
import { PlatformGuard, PLATFORM_CRUMB } from "./PlatformGuard";
import { RecordPaymentModal } from "./RecordPaymentModal";
import {
  BILLING_CYCLES,
  PROVIDERS,
  SUB_STATUSES,
  type InvoiceRow,
  type TenantDetail,
  type UsageMetric,
} from "./types";

/** The tenant workspace: subscription, usage, invoices and profile, each
 * on its own tab with its own save — no page-wide form. */
export function TenantDetailPage() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const tenant = useTenant(tenantId);

  return (
    <PlatformGuard>
      {tenant.isLoading ? (
        <LoadingState rows={10} />
      ) : tenant.error || !tenant.data?.data ? (
        <ErrorState
          title="Tenant unavailable"
          description="It may have been removed, or the service did not respond."
          onRetry={() => void tenant.refetch()}
        />
      ) : (
        <TenantWorkspace tenant={tenant.data.data} />
      )}
    </PlatformGuard>
  );
}

const DANGER_SUB_STATUSES = ["suspended", "cancelled", "expired"];

function TenantWorkspace({ tenant }: { tenant: TenantDetail }) {
  const feedback = usePlatformFeedback();
  const { modal } = App.useApp();

  const setStatus = useMutation({
    mutationFn: (status: string) => api.patch(`/platform/tenants/${tenant.id}/status`, { status }),
    onSuccess: (_d, status) => feedback.done(`${tenant.name} is now ${status}.`),
    onError: feedback.onError,
  });

  const lifecycle: Record<string, { label: string; title: string; body: string; danger?: boolean }> = {
    active: {
      label: "Reactivate tenant",
      title: `Reactivate ${tenant.name}?`,
      body: "Users can sign in again and the API accepts their requests.",
    },
    suspended: {
      label: "Suspend tenant",
      title: `Suspend ${tenant.name}?`,
      body: "Every user is locked out and the API refuses their tokens. Screens keep playing cached content — a suspension never blanks a display.",
      danger: true,
    },
    archived: {
      label: "Archive tenant",
      title: `Archive ${tenant.name}?`,
      body: "The tenant is retired from the platform. Data is retained; nobody can sign in.",
      danger: true,
    },
  };

  const lifecycleMenu = Object.entries(lifecycle)
    .filter(([status]) => status !== tenant.status)
    .map(([status, action]) => ({
      key: status,
      label: action.label,
      danger: action.danger,
      onClick: () =>
        modal.confirm({
          title: action.title,
          content: action.body,
          okText: action.label,
          okButtonProps: { danger: action.danger },
          onOk: () => setStatus.mutateAsync(status),
        }),
    }));

  return (
    <>
      <PageHeader
        title={tenant.name}
        breadcrumbs={[PLATFORM_CRUMB, { label: "Tenants", to: "/platform/tenants" }, { label: tenant.name }]}
        description={`${tenant.code} · created ${formatDate(tenant.created_at)}`}
        actions={
          <>
            <StatusBadge status={tenant.status} />
            <Dropdown menu={{ items: lifecycleMenu }} trigger={["click"]}>
              <Button loading={setStatus.isPending}>
                Lifecycle <DownOutlined />
              </Button>
            </Dropdown>
          </>
        }
      />

      <Tabs
        defaultActiveKey="subscription"
        items={[
          { key: "subscription", label: "Subscription", children: <SubscriptionTab tenant={tenant} /> },
          { key: "usage", label: "Usage & quotas", children: <QuotasTab tenant={tenant} /> },
          { key: "invoices", label: "Invoices", children: <InvoicesTab tenant={tenant} /> },
          { key: "profile", label: "Profile", children: <ProfileTab tenant={tenant} /> },
        ]}
      />
    </>
  );
}

// ---------------------------------------------------------------------------

interface ProfileValues {
  name: string;
  timezone: string;
  region: string;
}

function ProfileTab({ tenant }: { tenant: TenantDetail }) {
  const feedback = usePlatformFeedback();
  const [form] = Form.useForm<ProfileValues>();
  const [dirty, setDirty] = useState(false);

  const reset = () => {
    form.setFieldsValue({ name: tenant.name, timezone: tenant.timezone, region: tenant.region });
    setDirty(false);
  };
  useEffect(reset, [tenant, form]);

  const save = useMutation({
    mutationFn: (values: ProfileValues) =>
      api.patch(`/platform/tenants/${tenant.id}`, {
        name: values.name.trim(),
        timezone: values.timezone,
        region: values.region.trim(),
      }),
    onSuccess: () => {
      feedback.done("Tenant profile saved.");
      setDirty(false);
    },
    onError: feedback.onError,
  });

  return (
    <Card size="small">
      <Form
        form={form}
        layout="vertical"
        requiredMark="optional"
        className="max-w-xl"
        onValuesChange={() => setDirty(true)}
        onFinish={(values) => save.mutate(values)}
      >
        <Form.Item name="name" label="Organization name" rules={[{ required: true, message: "Enter a name." }]}>
          <Input maxLength={200} />
        </Form.Item>
        <Form.Item label="Code" extra="Permanent; used in URLs and the API.">
          <Input value={tenant.code} disabled />
        </Form.Item>
        <Form.Item name="timezone" label="Timezone" rules={[{ required: true }]}>
          <Select showSearch optionFilterProp="label" options={timezoneOptions()} />
        </Form.Item>
        <Form.Item
          name="region"
          label="Data region"
          extra="Residency label shown to the tenant and used for reporting. Moving data is a deployment operation, not this field."
          rules={[{ required: true, message: "Enter a region." }]}
        >
          <Input maxLength={50} />
        </Form.Item>
        <Space>
          <Button type="primary" htmlType="submit" loading={save.isPending} disabled={!dirty}>
            Save changes
          </Button>
          {dirty && <Button onClick={reset}>Discard</Button>}
        </Space>
      </Form>
    </Card>
  );
}

// ---------------------------------------------------------------------------

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

function SubscriptionTab({ tenant }: { tenant: TenantDetail }) {
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
          <Typography.Paragraph type="secondary" className="!mb-3 text-xs">
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

// ---------------------------------------------------------------------------

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

function QuotasTab({ tenant }: { tenant: TenantDetail }) {
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
          <Space orientation="vertical" size="middle" className="w-full">
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

// ---------------------------------------------------------------------------

function InvoicesTab({ tenant }: { tenant: TenantDetail }) {
  const invoices = useTenantInvoices(tenant.id);
  const [paying, setPaying] = useState<InvoiceRow | null>(null);

  const columns: TableProps<InvoiceRow>["columns"] = [
    { title: "Invoice", dataIndex: "number", render: (n: string) => <Typography.Text code>{n}</Typography.Text> },
    {
      title: "Period",
      responsive: ["lg"],
      render: (_, inv) => `${formatDate(inv.period_start)} – ${formatDate(inv.period_end)}`,
    },
    {
      title: "Amount",
      align: "right",
      render: (_, inv) => <Typography.Text strong>{formatMoney(inv.amount, inv.currency)}</Typography.Text>,
    },
    {
      title: "Status",
      render: (_, inv) => (
        <Space size={4}>
          <StatusBadge status={inv.status} />
          {isOverdue(inv) && (
            <Tag color="error" variant="filled">
              Overdue
            </Tag>
          )}
        </Space>
      ),
    },
    { title: "Issued", dataIndex: "issued_at", responsive: ["md"], render: (d: string | null) => formatDate(d) },
    {
      title: "Due",
      dataIndex: "due_at",
      responsive: ["md"],
      render: (d: string | null, inv) => (
        <Typography.Text type={isOverdue(inv) ? "danger" : undefined}>{formatDate(d)}</Typography.Text>
      ),
    },
    { title: "Paid", dataIndex: "paid_at", responsive: ["xl"], render: (d: string | null) => formatDate(d) },
    {
      title: "",
      key: "actions",
      align: "right",
      render: (_, inv) => (
        <Space size="small">
          <Button
            size="small"
            icon={<DownloadOutlined />}
            aria-label={`Download ${inv.number}`}
            onClick={() => void api.download(`/platform/tenants/${tenant.id}/invoices/${inv.id}/download`)}
          />
          {inv.status === "issued" && (
            <Button size="small" type="primary" onClick={() => setPaying(inv)}>
              Record payment
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <DataTable<InvoiceRow>
        rowKey="id"
        columns={columns}
        dataSource={invoices.data?.data ?? []}
        loading={invoices.isLoading}
        error={invoices.error}
        onRetry={() => void invoices.refetch()}
        emptyTitle="No invoices"
        emptyDescription="Invoices are issued when a subscription is assigned or renews."
        pagination={false}
      />
      <RecordPaymentModal
        tenantId={tenant.id}
        tenantName={tenant.name}
        invoice={paying}
        onClose={() => setPaying(null)}
      />
    </>
  );
}
