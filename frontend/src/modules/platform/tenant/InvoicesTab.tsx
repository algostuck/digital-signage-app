import { DownloadOutlined } from "@ant-design/icons";

import { Button, Space, Typography, type TableProps } from "antd";
import { ToneTag } from "@/design-system";
import { useState } from "react";

import { DataTable } from "@/design-system";

import { StatusBadge } from "@/design-system";
import { api } from "../../../lib/api";
import { formatDate, formatMoney, isOverdue, useTenantInvoices } from "../api";

import { RecordPaymentModal } from "../RecordPaymentModal";
import { type InvoiceRow, type TenantDetail } from "../types";

export function InvoicesTab({ tenant }: { tenant: TenantDetail }) {
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
            <ToneTag tone="error">
              Overdue
            </ToneTag>
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
