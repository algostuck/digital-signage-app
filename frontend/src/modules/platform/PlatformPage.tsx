import { DownloadOutlined, PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Result,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  type TableProps,
} from "antd";
import { useEffect, useState } from "react";
import { PageHeader } from "../../components/ui/PageHeader";
import { EmptyState, LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { PlanEditor, type PlanRow } from "./PlanEditor";

interface TenantRow {
  id: string;
  name: string;
  code: string;
  status: string;
  plan_code: string | null;
  plan_name: string | null;
  subscription_status: string | null;
  devices: number;
  users: number;
}

interface InvoiceRow {
  id: string;
  number: string;
  amount: string;
  currency: string;
  status: string;
  due_at: string | null;
}

interface TenantQuotas {
  usage: {
    devices: { used: number; limit: number | null };
    users: { used: number; limit: number | null };
    storage_mb: { used: number; limit: number | null };
  };
  quotas: Record<string, number>;
}

interface PlanRequestRow {
  id: string;
  organization_name: string;
  organization_code: string;
  from_plan: string;
  to_plan: string;
  to_plan_name: string;
  status: string;
  note: string | null;
  created_at: string | null;
}

interface CreateTenantValues {
  name: string;
  code: string;
  owner_email: string;
  owner_full_name: string;
  owner_password?: string;
}

const PROVIDERS = ["manual", "stripe", "razorpay"];

const SUB_STATUSES = [
  "trialing",
  "active",
  "past_due",
  "grace_period",
  "suspended",
  "cancelled",
  "expired",
];

/** SCR-PLAT: Super Admin console — tenants, plans, subscriptions, payments. */
export function PlatformPage() {
  const { user } = useAuth();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<TenantRow | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm<CreateTenantValues>();

  const tenantsQuery = useQuery({
    queryKey: ["platform-tenants"],
    queryFn: () => api.get<TenantRow[]>("/platform/tenants"),
    enabled: !!user?.is_superuser,
  });
  const plansQuery = useQuery({
    queryKey: ["platform-plans"],
    queryFn: () => api.get<PlanRow[]>("/platform/plans"),
    enabled: !!user?.is_superuser,
  });
  const invoicesQuery = useQuery({
    queryKey: ["platform-invoices", selected?.id],
    queryFn: () => api.get<InvoiceRow[]>(`/platform/tenants/${selected!.id}/invoices`),
    enabled: selected != null,
  });
  const quotasQuery = useQuery({
    queryKey: ["platform-quotas", selected?.id],
    queryFn: () => api.get<TenantQuotas>(`/platform/tenants/${selected!.id}/quotas`),
    enabled: selected != null,
  });

  const requestsQuery = useQuery({
    queryKey: ["platform-plan-requests"],
    queryFn: () => api.get<PlanRequestRow[]>("/platform/plan-requests"),
    enabled: !!user?.is_superuser,
  });

  const [quotaForm, setQuotaForm] = useState<Record<string, string>>({});
  const [providerForm, setProviderForm] = useState({ provider: "manual", customer: "", ref: "" });
  const [tenantForm, setTenantForm] = useState({ name: "", timezone: "" });
  useEffect(() => {
    if (selected) setTenantForm({ name: selected.name, timezone: "" });
  }, [selected]);
  useEffect(() => {
    const quotas = quotasQuery.data?.data?.quotas;
    if (quotas) {
      setQuotaForm({
        max_devices: quotas.max_devices?.toString() ?? "",
        max_users: quotas.max_users?.toString() ?? "",
        max_storage_mb: quotas.max_storage_mb?.toString() ?? "",
      });
    }
  }, [quotasQuery.data]);

  const done = (text: string) => {
    queryClient.invalidateQueries({ queryKey: ["platform-tenants"] });
    if (selected) queryClient.invalidateQueries({ queryKey: ["platform-invoices", selected.id] });
    message.success(text);
  };
  const onError = (err: unknown) =>
    message.error(err instanceof ApiError ? err.message : "Action failed");

  const createTenant = useMutation({
    mutationFn: (values: CreateTenantValues) =>
      api.post("/platform/tenants", {
        ...values,
        owner_password: values.owner_password || null,
      }),
    onSuccess: () => {
      done("Tenant created.");
      createForm.resetFields();
      setCreateOpen(false);
    },
    onError,
  });

  const assignPlan = useMutation({
    mutationFn: ({ tenantId, plan_code }: { tenantId: string; plan_code: string }) =>
      api.post(`/platform/tenants/${tenantId}/subscription`, {
        plan_code,
        billing_cycle: "monthly",
      }),
    onSuccess: () => done("Subscription assigned."),
    onError,
  });
  const transition = useMutation({
    mutationFn: ({ tenantId, to_status }: { tenantId: string; to_status: string }) =>
      api.post(`/platform/tenants/${tenantId}/subscription/transition`, {
        to_status,
        event: "admin_transition",
      }),
    onSuccess: () => done("Subscription status updated."),
    onError,
  });
  const recordPayment = useMutation({
    mutationFn: ({ tenantId, invoiceId }: { tenantId: string; invoiceId: string }) =>
      api.post(`/platform/tenants/${tenantId}/payments`, { invoice_id: invoiceId }),
    onSuccess: () => done("Payment recorded — subscription reactivated."),
    onError,
  });
  const saveQuotas = useMutation({
    mutationFn: () =>
      api.patch(`/platform/tenants/${selected!.id}/quotas`, {
        max_devices: quotaForm.max_devices ? Number(quotaForm.max_devices) : null,
        max_users: quotaForm.max_users ? Number(quotaForm.max_users) : null,
        max_storage_mb: quotaForm.max_storage_mb ? Number(quotaForm.max_storage_mb) : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platform-quotas", selected?.id] });
      done("Quota overrides saved.");
    },
    onError,
  });
  const saveProvider = useMutation({
    mutationFn: () =>
      api.patch(`/platform/tenants/${selected!.id}/subscription/provider`, {
        provider: providerForm.provider,
        provider_customer_id: providerForm.customer || null,
        provider_subscription_id: providerForm.ref || null,
      }),
    onSuccess: () => done("Payment provider updated."),
    onError,
  });
  const saveTenant = useMutation({
    mutationFn: () =>
      api.patch(`/platform/tenants/${selected!.id}`, {
        name: tenantForm.name || null,
        timezone: tenantForm.timezone || null,
      }),
    onSuccess: () => done("Tenant updated."),
    onError,
  });
  const changeTenantPlan = useMutation({
    mutationFn: ({ tenantId, plan_code }: { tenantId: string; plan_code: string }) =>
      api.patch(`/platform/tenants/${tenantId}/subscription/plan`, { plan_code }),
    onSuccess: () => done("Plan changed."),
    onError,
  });
  const decideRequest = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) =>
      api.post(`/platform/plan-requests/${id}/${approve ? "approve" : "reject"}`, {}),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ["platform-plan-requests"] });
      done(vars.approve ? "Request approved — plan activated." : "Request rejected.");
    },
    onError,
  });

  if (!user?.is_superuser)
    return (
      <Result
        status="403"
        title="Platform Administration unavailable"
        subTitle="Platform administrator access required."
      />
    );
  if (tenantsQuery.isLoading) return <LoadingState rows={8} />;

  const tenants = tenantsQuery.data?.data ?? [];
  const plans = plansQuery.data?.data ?? [];
  const invoices = invoicesQuery.data?.data ?? [];
  const planRequests = requestsQuery.data?.data ?? [];

  const requestColumns: TableProps<PlanRequestRow>["columns"] = [
    {
      title: "Organization",
      dataIndex: "organization_name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    {
      title: "Change",
      render: (_, req) => (
        <>
          {req.from_plan} → <Typography.Text strong>{req.to_plan_name}</Typography.Text>
        </>
      ),
    },
    {
      title: "Note",
      dataIndex: "note",
      responsive: ["lg"],
      render: (note: string | null) => (
        <Typography.Text type="secondary">{note ?? ""}</Typography.Text>
      ),
    },
    {
      title: "Actions",
      render: (_, req) => (
        <Space size="small">
          <Popconfirm
            title={`Approve ${req.organization_name}'s change to ${req.to_plan_name}?`}
            description="The plan activates immediately on approval."
            onConfirm={() => decideRequest.mutate({ id: req.id, approve: true })}
          >
            <Button type="primary" size="small" disabled={decideRequest.isPending}>
              Approve
            </Button>
          </Popconfirm>
          <Popconfirm
            title={`Reject ${req.organization_name}'s plan change request?`}
            okButtonProps={{ danger: true }}
            onConfirm={() => decideRequest.mutate({ id: req.id, approve: false })}
          >
            <Button size="small" danger disabled={decideRequest.isPending}>
              Reject
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const tenantColumns: TableProps<TenantRow>["columns"] = [
    {
      title: "Name",
      dataIndex: "name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    {
      title: "Code",
      dataIndex: "code",
      responsive: ["lg"],
      render: (code: string) => (
        <Typography.Text code className="text-xs">
          {code}
        </Typography.Text>
      ),
    },
    { title: "Plan", render: (_, t) => t.plan_name ?? "—" },
    {
      title: "Subscription",
      render: (_, t) =>
        t.subscription_status ? (
          <StatusBadge status={t.subscription_status} />
        ) : (
          <Typography.Text type="secondary" className="text-xs">
            none (legacy)
          </Typography.Text>
        ),
    },
    { title: "Devices", dataIndex: "devices", align: "right", responsive: ["lg"] },
    { title: "Users", dataIndex: "users", align: "right", responsive: ["lg"] },
    {
      title: "Actions",
      render: (_, t) => (
        <Space size="small" wrap>
          {t.subscription_status == null ? (
            <Select
              aria-label={`Assign plan to ${t.name}`}
              size="small"
              className="w-36"
              placeholder="Assign plan…"
              value={null}
              onChange={(value: string | null) => {
                if (value) assignPlan.mutate({ tenantId: t.id, plan_code: value });
              }}
              options={plans
                .filter((p) => p.is_active)
                .map((p) => ({ value: p.code, label: p.name }))}
            />
          ) : (
            <Select
              aria-label={`Set subscription status for ${t.name}`}
              size="small"
              className="w-36"
              value={t.subscription_status}
              onChange={(value: string) =>
                transition.mutate({ tenantId: t.id, to_status: value })
              }
              options={SUB_STATUSES.map((s) => ({
                value: s,
                label: s.replace(/_/g, " "),
              }))}
            />
          )}
          <Button size="small" onClick={() => setSelected(t)}>
            Manage
          </Button>
        </Space>
      ),
    },
  ];

  const invoiceColumns: TableProps<InvoiceRow>["columns"] = [
    {
      title: "Number",
      dataIndex: "number",
      render: (n: string) => (
        <Typography.Text code className="text-xs">
          {n}
        </Typography.Text>
      ),
    },
    {
      title: "Amount",
      align: "right",
      render: (_, inv) => `${inv.amount} ${inv.currency}`,
    },
    { title: "Status", render: (_, inv) => <StatusBadge status={inv.status} /> },
    {
      title: "Actions",
      render: (_, inv) =>
        selected && (
          <Space size="small">
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={() =>
                void api.download(
                  `/platform/tenants/${selected.id}/invoices/${inv.id}/download`,
                )
              }
            >
              Download
            </Button>
            {inv.status === "issued" && (
              <Popconfirm
                title={`Record payment for ${inv.number}?`}
                description="The subscription reactivates immediately."
                onConfirm={() =>
                  recordPayment.mutate({ tenantId: selected.id, invoiceId: inv.id })
                }
              >
                <Button size="small" type="primary">
                  Record payment
                </Button>
              </Popconfirm>
            )}
          </Space>
        ),
    },
  ];

  return (
    <div className="max-w-5xl">
      <PageHeader
        title="Platform Administration"
        description="Tenants, plans and subscriptions across the whole platform."
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            New tenant
          </Button>
        }
      />

      <Space orientation="vertical" size="large" className="w-full">
        {planRequests.length > 0 && (
          <Card size="small" title="Plan change requests awaiting approval">
            <Alert
              type="warning"
              showIcon
              className="mb-3"
              message="Verify the manual payment first, then approve — the plan activates immediately on approval."
            />
            <Table<PlanRequestRow>
              size="middle"
              rowKey="id"
              columns={requestColumns}
              dataSource={planRequests}
              scroll={{ x: "max-content" }}
              pagination={false}
            />
          </Card>
        )}

        <Card size="small" title="Tenants">
          <Table<TenantRow>
            size="middle"
            rowKey="id"
            columns={tenantColumns}
            dataSource={tenants}
            loading={tenantsQuery.isLoading}
            scroll={{ x: "max-content" }}
            locale={{ emptyText: <EmptyState title="No tenants yet" /> }}
          />
        </Card>

        <Card size="small" title="Plans">
          <Row gutter={[12, 12]}>
            {plans.map((plan) => {
              const ints = plan.entitlements.filter((e) => e.int_value !== null);
              const bools = plan.entitlements.filter((e) => e.bool_value === true);
              return (
                <Col key={plan.code} xs={24} sm={12} lg={6}>
                  <Card type="inner" size="small" className="h-full">
                    <Typography.Text strong>{plan.name}</Typography.Text>
                    {!plan.is_active && (
                      <Tag variant="filled" className="ms-2">
                        inactive
                      </Tag>
                    )}
                    <ul className="mb-0 mt-1 list-none space-y-0.5 p-0">
                      {ints.slice(0, 4).map((e) => (
                        <li key={e.key}>
                          <Typography.Text type="secondary" className="text-xs">
                            {e.key.replace(/^max_|_month$/g, "").replace(/_/g, " ")}:{" "}
                            {e.int_value}
                          </Typography.Text>
                        </li>
                      ))}
                      <li>
                        <Typography.Text type="secondary" className="text-xs">
                          {bools.length} features enabled
                        </Typography.Text>
                      </li>
                    </ul>
                  </Card>
                </Col>
              );
            })}
          </Row>
        </Card>

        <PlanEditor plans={plans} />
      </Space>

      <Drawer
        size={640}
        open={selected != null}
        onClose={() => setSelected(null)}
        title={selected ? `Tenant settings — ${selected.name}` : undefined}
      >
        {selected && (
          <Space orientation="vertical" size="large" className="w-full">
            <div>
              <Typography.Title level={5}>Tenant</Typography.Title>
              <Form layout="vertical">
                <Row gutter={12}>
                  <Col xs={24} sm={12}>
                    <Form.Item label="Organization name">
                      <Input
                        value={tenantForm.name}
                        onChange={(e) =>
                          setTenantForm((p) => ({ ...p, name: e.target.value }))
                        }
                      />
                    </Form.Item>
                  </Col>
                  <Col xs={24} sm={12}>
                    <Form.Item label="Timezone (IANA, optional)">
                      <Input
                        value={tenantForm.timezone}
                        placeholder="unchanged"
                        onChange={(e) =>
                          setTenantForm((p) => ({ ...p, timezone: e.target.value }))
                        }
                      />
                    </Form.Item>
                  </Col>
                </Row>
                <Space wrap align="end">
                  <Button
                    type="primary"
                    loading={saveTenant.isPending}
                    onClick={() => saveTenant.mutate()}
                  >
                    Save tenant
                  </Button>
                  {selected.subscription_status != null && (
                    <Select
                      aria-label="Change plan (direct — upgrade or downgrade)"
                      className="w-56"
                      placeholder="Change plan (direct)…"
                      value={null}
                      disabled={changeTenantPlan.isPending}
                      onChange={(value: string | null) => {
                        if (value)
                          changeTenantPlan.mutate({
                            tenantId: selected.id,
                            plan_code: value,
                          });
                      }}
                      options={plans
                        .filter((p) => p.code !== selected.plan_code)
                        .map((p) => ({ value: p.code, label: p.name }))}
                    />
                  )}
                </Space>
              </Form>
            </div>

            <div>
              <Typography.Title level={5}>Quota overrides</Typography.Title>
              <Typography.Paragraph type="secondary" className="!mb-2 text-xs">
                Tightens numeric limits below the plan (blank = plan limit
                applies). Tenants cannot edit these.
              </Typography.Paragraph>
              <Form layout="vertical">
                <Space wrap align="end">
                  {(
                    [
                      ["max_devices", "Devices"],
                      ["max_users", "Users"],
                      ["max_storage_mb", "Storage (MB)"],
                    ] as const
                  ).map(([key, label]) => (
                    <Form.Item key={key} label={label} className="!mb-0">
                      <InputNumber
                        min={1}
                        className="w-28"
                        placeholder="plan limit"
                        value={quotaForm[key] ? Number(quotaForm[key]) : null}
                        onChange={(v) =>
                          setQuotaForm((prev) => ({
                            ...prev,
                            [key]: v == null ? "" : String(v),
                          }))
                        }
                      />
                    </Form.Item>
                  ))}
                  <Button
                    type="primary"
                    loading={saveQuotas.isPending}
                    onClick={() => saveQuotas.mutate()}
                  >
                    Save overrides
                  </Button>
                </Space>
              </Form>
            </div>

            {selected.subscription_status != null && (
              <div>
                <Typography.Title level={5}>Payment provider</Typography.Title>
                <Typography.Paragraph type="secondary" className="!mb-2 text-xs">
                  `manual` = enterprise invoice flow (record payments here).
                  Gateway API keys are server environment configuration — never
                  entered or stored here; only provider references.
                </Typography.Paragraph>
                <Form layout="vertical">
                  <Space wrap align="end">
                    <Form.Item label="Provider" className="!mb-0">
                      <Select
                        className="w-32"
                        value={providerForm.provider}
                        onChange={(value: string) =>
                          setProviderForm((p) => ({ ...p, provider: value }))
                        }
                        options={PROVIDERS.map((p) => ({ value: p, label: p }))}
                      />
                    </Form.Item>
                    <Form.Item label="Customer reference" className="!mb-0">
                      <Input
                        className="w-40"
                        placeholder="e.g. cus_..."
                        value={providerForm.customer}
                        onChange={(e) =>
                          setProviderForm((p) => ({ ...p, customer: e.target.value }))
                        }
                      />
                    </Form.Item>
                    <Form.Item label="Subscription reference" className="!mb-0">
                      <Input
                        className="w-40"
                        placeholder="e.g. sub_..."
                        value={providerForm.ref}
                        onChange={(e) =>
                          setProviderForm((p) => ({ ...p, ref: e.target.value }))
                        }
                      />
                    </Form.Item>
                    <Button
                      type="primary"
                      loading={saveProvider.isPending}
                      onClick={() => saveProvider.mutate()}
                    >
                      Save provider
                    </Button>
                  </Space>
                </Form>
              </div>
            )}

            <div>
              <Typography.Title level={5}>Invoices</Typography.Title>
              <Table<InvoiceRow>
                size="middle"
                rowKey="id"
                columns={invoiceColumns}
                dataSource={invoices}
                loading={invoicesQuery.isLoading}
                scroll={{ x: "max-content" }}
                pagination={false}
                locale={{ emptyText: <EmptyState title="No invoices" /> }}
              />
            </div>
          </Space>
        )}
      </Drawer>

      <Modal
        title="Create tenant"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        okText="Create tenant"
        confirmLoading={createTenant.isPending}
        onOk={() => createForm.submit()}
        destroyOnHidden
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={(values) => createTenant.mutate(values)}
        >
          <Form.Item
            name="name"
            label="Organization name"
            rules={[{ required: true, message: "Organization name is required." }]}
          >
            <Input autoFocus />
          </Form.Item>
          <Form.Item
            name="code"
            label="Code (lowercase)"
            rules={[{ required: true, message: "Code is required." }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="owner_email"
            label="Owner email"
            rules={[
              { required: true, message: "Owner email is required." },
              { type: "email", message: "Enter a valid email address." },
            ]}
          >
            <Input type="email" />
          </Form.Item>
          <Form.Item
            name="owner_full_name"
            label="Owner full name"
            rules={[{ required: true, message: "Owner full name is required." }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="owner_password" label="Owner password (blank = invite)">
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
