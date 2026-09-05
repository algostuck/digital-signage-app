import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Form, Input, Modal, Segmented, Space, Typography, type TableProps } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";
import { DataTable } from "@/design-system";
import { FilterBar } from "@/design-system";
import { PageHeader } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api } from "../../lib/api";
import { formatDate, usePlanRequests, usePlatformFeedback } from "./api";
import { PlatformGuard, PLATFORM_CRUMB } from "./PlatformGuard";
import type { PlanRequestRow } from "./types";

type Decision = { request: PlanRequestRow; approve: boolean };

/** The plan-change inbox. Tenants can only request a change; approval
 * here is what actually activates the new plan. */
export function PlanRequestsPage() {
  const [status, setStatus] = useState("pending");
  const requests = usePlanRequests(status);
  const feedback = usePlatformFeedback();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [form] = Form.useForm<{ decision_note?: string }>();

  const decide = useMutation({
    mutationFn: ({ request, approve, note }: Decision & { note?: string }) =>
      api.post(`/platform/plan-requests/${request.id}/${approve ? "approve" : "reject"}`, {
        decision_note: note?.trim() || null,
      }),
    onSuccess: (_d, vars) => {
      feedback.done(
        vars.approve
          ? `${vars.request.organization_name} moved to ${vars.request.to_plan_name}.`
          : `Request from ${vars.request.organization_name} rejected.`,
      );
      form.resetFields();
      setDecision(null);
    },
    onError: feedback.onError,
  });

  const columns: TableProps<PlanRequestRow>["columns"] = [
    {
      title: "Tenant",
      dataIndex: "organization_name",
      render: (name: string, r) => (
        <div>
          <Link to={`/platform/tenants/${r.organization_id}`} className="font-medium">
            {name}
          </Link>
          <div>
            <Typography.Text type="secondary" className="text-xs">
              {r.organization_code}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      title: "Requested change",
      render: (_, r) => (
        <span>
          {r.from_plan} → <Typography.Text strong>{r.to_plan_name}</Typography.Text>
        </span>
      ),
    },
    {
      title: "Tenant's note",
      dataIndex: "note",
      responsive: ["lg"],
      render: (n: string | null) => n || <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: "Requested",
      dataIndex: "created_at",
      responsive: ["md"],
      render: (d: string | null) => formatDate(d),
    },
    { title: "Status", dataIndex: "status", render: (s: string) => <StatusBadge status={s} /> },
    ...(status !== "pending"
      ? [
          {
            title: "Decision note",
            dataIndex: "decision_note",
            responsive: ["lg" as const],
            render: (n: string | null) => n || <Typography.Text type="secondary">—</Typography.Text>,
          },
        ]
      : []),
    {
      title: "",
      key: "actions",
      align: "right",
      render: (_, r) =>
        r.status === "pending" ? (
          <Space size="small">
            <Button type="primary" size="small" onClick={() => setDecision({ request: r, approve: true })}>
              Approve
            </Button>
            <Button danger size="small" onClick={() => setDecision({ request: r, approve: false })}>
              Reject
            </Button>
          </Space>
        ) : null,
    },
  ];

  return (
    <PlatformGuard>
      <PageHeader
        title="Plan requests"
        breadcrumbs={[PLATFORM_CRUMB, { label: "Plan requests" }]}
        description="Plan changes tenants have asked for. Approval activates the new plan immediately."
      />

      <FilterBar>
        <Segmented
          value={status}
          onChange={(v) => setStatus(String(v))}
          options={[
            { value: "pending", label: "Pending" },
            { value: "approved", label: "Approved" },
            { value: "rejected", label: "Rejected" },
            { value: "all", label: "All" },
          ]}
        />
      </FilterBar>

      <DataTable<PlanRequestRow>
        rowKey="id"
        columns={columns}
        dataSource={requests.data?.data ?? []}
        loading={requests.isLoading}
        error={requests.error}
        onRetry={() => void requests.refetch()}
        emptyTitle={status === "pending" ? "Inbox is clear" : "No requests"}
        emptyDescription={status === "pending" ? "No plan changes are waiting on you." : undefined}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title={decision?.approve ? "Approve plan change" : "Reject plan change"}
        open={decision != null}
        onCancel={() => setDecision(null)}
        okText={decision?.approve ? "Approve and activate" : "Reject request"}
        okButtonProps={{ danger: !decision?.approve }}
        confirmLoading={decide.isPending}
        onOk={() => form.submit()}
        destroyOnHidden
      >
        {decision && (
          <>
            <Typography.Paragraph>
              <Typography.Text strong>{decision.request.organization_name}</Typography.Text>: {decision.request.from_plan} →{" "}
              <Typography.Text strong>{decision.request.to_plan_name}</Typography.Text>
            </Typography.Paragraph>
            {decision.approve ? (
              <Alert
                type="warning"
                showIcon
                className="mb-4"
                message="Confirm the payment for the new plan has been received first."
                description="The plan switches the moment you approve; limits and features change for every user in the tenant."
              />
            ) : (
              <Alert
                type="info"
                showIcon
                className="mb-4"
                message="The tenant keeps its current plan and is notified with your note."
              />
            )}
            <Form
              form={form}
              layout="vertical"
              onFinish={(values) => decide.mutate({ ...decision, note: values.decision_note })}
            >
              <Form.Item
                name="decision_note"
                label="Note to the tenant"
                rules={decision.approve ? [] : [{ required: true, message: "Tell the tenant why." }]}
              >
                <Input.TextArea rows={3} maxLength={500} showCount />
              </Form.Item>
            </Form>
          </>
        )}
      </Modal>
    </PlatformGuard>
  );
}
