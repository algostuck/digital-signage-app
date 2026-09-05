import { CheckOutlined, CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Flex,
  Select,
  Space,
  Table,
  Typography,
  type TableProps,
} from "antd";
import { ToneTag } from "../../components/ui/ToneTag";
import { toneOf } from "../../components/ui/tone";
import { useState } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface PlanBrief {
  code: string;
  name: string;
}

interface SubscriptionInfo {
  id: string;
  plan: PlanBrief;
  status: string;
  billing_cycle: string;
  current_period_end: string | null;
  trial_end_at: string | null;
  cancel_at: string | null;
}

interface BillingData {
  subscription: SubscriptionInfo | null;
  entitlements: Record<string, number | boolean | null>;
  plan_code: string | null;
  plan_name: string | null;
  status: string | null;
  usage: {
    devices: { used: number; limit: number | null };
    users: { used: number; limit: number | null };
    storage_mb: { used: number; limit: number | null };
  };
  pending_plan_request: {
    id: string;
    to_plan: string;
    to_plan_name: string;
    created_at: string | null;
  } | null;
}

interface InvoiceRow {
  id: string;
  number: string;
  amount: string;
  currency: string;
  status: string;
  issued_at: string | null;
  due_at: string | null;
}

interface PlanRow {
  code: string;
  name: string;
  description: string | null;
  prices: Record<string, { amount: number; currency: string }>;
}

const STATUS_COLOR: Record<string, string> = {
  active: "success",
  trialing: "processing",
  past_due: "warning",
  grace_period: "orange",
  suspended: "error",
  cancelled: "default",
  expired: "default",
};

const FEATURE_LABELS: Record<string, string> = {
  proof_of_play: "Proof of play",
  advanced_analytics: "Advanced analytics",
  api_access: "API access",
  sso: "SSO",
  white_label: "White label",
  video_wall: "Video walls",
  ai_features: "AI features",
  dynamic_data: "Dynamic data",
};

function fmtDate(value: string | null): string {
  return value ? new Date(value).toLocaleDateString() : "—";
}

/** Settings › Plan & Billing (SaaS core): current plan, entitlements vs
 * usage, invoices, cancel/reactivate and plan changes. */
export function PlanBillingSection() {
  const { hasPermission } = useAuth();
  const canView = hasPermission("billing.view");
  const canManage = hasPermission("billing.manage");
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const billingQuery = useQuery({
    queryKey: ["billing-subscription"],
    queryFn: () => api.get<BillingData>("/billing/subscription"),
    enabled: canView,
  });
  const invoicesQuery = useQuery({
    queryKey: ["billing-invoices"],
    queryFn: () => api.get<InvoiceRow[]>("/billing/invoices"),
    enabled: canView,
  });
  const plansQuery = useQuery({
    queryKey: ["plans"],
    queryFn: () => api.get<PlanRow[]>("/plans"),
    enabled: canManage,
  });

  const onDone = (text: string) => {
    queryClient.invalidateQueries({ queryKey: ["billing-subscription"] });
    queryClient.invalidateQueries({ queryKey: ["billing-invoices"] });
    queryClient.invalidateQueries({ queryKey: ["org-usage"] });
    setMessage({ kind: "ok", text });
  };
  const onError = (err: unknown) =>
    setMessage({
      kind: "error",
      text: err instanceof ApiError ? err.message : "Billing action failed",
    });

  const changePlan = useMutation({
    mutationFn: (plan_code: string) => api.post("/billing/change-plan", { plan_code }),
    onSuccess: () =>
      onDone(
        "Request submitted. The plan activates once the platform administrator " +
          "confirms your payment and approves.",
      ),
    onError,
  });
  const cancel = useMutation({
    mutationFn: () => api.post("/billing/cancel", { at_period_end: true }),
    onSuccess: () => onDone("Subscription will end at the current period."),
    onError,
  });
  const reactivate = useMutation({
    mutationFn: () => api.post("/billing/reactivate", {}),
    onSuccess: () => onDone("Subscription reactivated."),
    onError,
  });

  if (!canView) return null;
  const billing = billingQuery.data?.data ?? null;
  if (!billing) return null;
  const invoices = invoicesQuery.data?.data ?? [];
  const plans = plansQuery.data?.data ?? [];
  const sub = billing.subscription;

  const invoiceColumns: TableProps<InvoiceRow>["columns"] = [
    {
      title: "Number",
      dataIndex: "number",
      render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
    },
    {
      title: "Amount",
      dataIndex: "amount",
      align: "right",
      render: (_, inv) => `${inv.amount} ${inv.currency}`,
    },
    { title: "Issued", dataIndex: "issued_at", render: fmtDate },
    { title: "Due", dataIndex: "due_at", render: fmtDate },
    {
      title: "Status",
      dataIndex: "status",
      render: (status: string) => (
        <ToneTag tone={toneOf(status === "paid" ? "success" : "warning")}>
          {status}
        </ToneTag>
      ),
    },
    {
      title: "",
      key: "actions",
      render: (_, inv) => (
        <Button
          size="small"
          icon={<DownloadOutlined />}
          onClick={() => void api.download(`/billing/invoices/${inv.id}/download`)}
        >
          Download
        </Button>
      ),
    },
  ];

  return (
    <Space orientation="vertical" size="middle" className="w-full">
      <Card size="small" title="Plan & billing">
        {sub == null ? (
          <Typography.Text type="secondary">
            No subscription — this organization runs without plan limits.
          </Typography.Text>
        ) : (
          <Flex wrap align="center" gap="small">
            <Typography.Text strong className="text-lg">
              {sub.plan.name}
            </Typography.Text>
            <ToneTag tone={toneOf(STATUS_COLOR[sub.status] ?? "default")}>
              {sub.status.replace(/_/g, " ")}
            </ToneTag>
            <Typography.Text type="secondary">
              {sub.billing_cycle} · renews {fmtDate(sub.current_period_end)}
            </Typography.Text>
            {sub.cancel_at && (
              <Typography.Text type="warning">ends {fmtDate(sub.cancel_at)}</Typography.Text>
            )}
            {canManage && (
              <Space className="ms-auto" wrap>
                {plans.length > 0 && !billing.pending_plan_request && (
                  <Select
                    aria-label="Request plan change"
                    placeholder="Request plan change…"
                    value={null}
                    disabled={changePlan.isPending}
                    onChange={(value) => {
                      if (value) changePlan.mutate(value);
                    }}
                    className="w-44"
                    options={plans
                      .filter((p) => p.code !== sub.plan.code)
                      .map((p) => ({ value: p.code, label: p.name }))}
                  />
                )}
                {sub.cancel_at || ["suspended", "cancelled"].includes(sub.status) ? (
                  <Button
                    type="primary"
                    onClick={() => reactivate.mutate()}
                    loading={reactivate.isPending}
                  >
                    Reactivate
                  </Button>
                ) : (
                  <Button
                    danger
                    onClick={() => cancel.mutate()}
                    loading={cancel.isPending}
                  >
                    Cancel at period end
                  </Button>
                )}
              </Space>
            )}
          </Flex>
        )}
        {billing.pending_plan_request && (
          <Alert
            type="info"
            showIcon
            className="mt-3"
            message={
              <>
                Change to <strong>{billing.pending_plan_request.to_plan_name}</strong>{" "}
                requested — it activates once the platform administrator confirms
                your payment and approves the request.
              </>
            }
          />
        )}
        {["past_due", "grace_period", "suspended"].includes(billing.status ?? "") && (
          <Alert
            type="warning"
            showIcon
            className="mt-3"
            message={
              "Payment is overdue. Existing displays continue cached playback; new " +
              "registrations, uploads and publishing are restricted until payment " +
              "is received."
            }
          />
        )}

        <Flex wrap gap="small" className="mt-4">
          {Object.entries(FEATURE_LABELS).map(([key, label]) => {
            const enabled = billing.entitlements[key] !== false;
            return (
              <ToneTag
                key={key} tone={toneOf(enabled ? "success" : "default")}
                icon={enabled ? <CheckOutlined /> : <CloseOutlined />}
              >
                {label}
              </ToneTag>
            );
          })}
        </Flex>
      </Card>

      {invoices.length > 0 && (
        <Card size="small" title="Invoices">
          <Table<InvoiceRow>
            size="middle"
            rowKey="id"
            columns={invoiceColumns}
            dataSource={invoices}
            pagination={false}
            scroll={{ x: "max-content" }}
            loading={invoicesQuery.isLoading}
          />
        </Card>
      )}

      {message && (
        <Alert
          type={message.kind === "ok" ? "success" : "error"}
          message={message.text}
          showIcon
          role={message.kind === "error" ? "alert" : undefined}
        />
      )}
    </Space>
  );
}
