import { DownloadOutlined } from "@ant-design/icons";
import { Button, Col, Row, Select, Space, Typography, type TableProps } from "antd";
import { ToneTag } from "@/design-system";
import { SearchBar } from "@/design-system";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { DataTable } from "@/design-system";
import { FilterBar } from "@/design-system";
import { PageHeader } from "@/design-system";
import { StatCard } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api } from "../../lib/api";
import { formatDate, formatMoney, isOverdue, usePlatformInvoices, useTenants } from "./api";
import { PlatformGuard, PLATFORM_CRUMB } from "./PlatformGuard";
import { RecordPaymentModal } from "./RecordPaymentModal";
import { INVOICE_STATUSES, type PlatformInvoiceRow } from "./types";

/** The receivables ledger across every tenant. */
export function InvoicesPage() {
  const [status, setStatus] = useState<string | null>("issued");
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [paying, setPaying] = useState<PlatformInvoiceRow | null>(null);
  const invoices = usePlatformInvoices(status, tenantId);
  const tenants = useTenants();

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (invoices.data?.data ?? []).filter((inv) => !q || inv.number.toLowerCase().includes(q));
  }, [invoices.data, search]);

  const open = rows.filter((r) => r.status === "issued");
  const overdue = open.filter(isOverdue);
  const totals = open.reduce<Record<string, number>>((acc, inv) => {
    acc[inv.currency] = (acc[inv.currency] ?? 0) + Number(inv.amount);
    return acc;
  }, {});

  const columns: TableProps<PlatformInvoiceRow>["columns"] = [
    {
      title: "Invoice",
      dataIndex: "number",
      sorter: (a, b) => a.number.localeCompare(b.number),
      render: (n: string) => <Typography.Text code>{n}</Typography.Text>,
    },
    {
      title: "Tenant",
      dataIndex: "organization_name",
      sorter: (a, b) => a.organization_name.localeCompare(b.organization_name),
      render: (name: string, inv) => (
        <div>
          <Link to={`/platform/tenants/${inv.organization_id}`} className="font-medium">
            {name}
          </Link>
          <div>
            <Typography.Text type="secondary" className="text-xs">
              {inv.plan_name}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      title: "Period",
      responsive: ["lg"],
      render: (_, inv) => `${formatDate(inv.period_start)} – ${formatDate(inv.period_end)}`,
    },
    {
      title: "Amount",
      align: "right",
      sorter: (a, b) => Number(a.amount) - Number(b.amount),
      render: (_, inv) => <Typography.Text strong>{formatMoney(inv.amount, inv.currency)}</Typography.Text>,
    },
    {
      title: "Status",
      dataIndex: "status",
      render: (s: string, inv) => (
        <Space size={4}>
          <StatusBadge status={s} />
          {isOverdue(inv) && (
            <ToneTag tone="error">
              Overdue
            </ToneTag>
          )}
        </Space>
      ),
    },
    {
      title: "Issued",
      dataIndex: "issued_at",
      responsive: ["md"],
      sorter: (a, b) => (a.issued_at ?? "").localeCompare(b.issued_at ?? ""),
      defaultSortOrder: "descend",
      render: (d: string | null) => formatDate(d),
    },
    {
      title: "Due",
      dataIndex: "due_at",
      responsive: ["md"],
      render: (d: string | null, inv) => (
        <Typography.Text type={isOverdue(inv) ? "danger" : undefined}>{formatDate(d)}</Typography.Text>
      ),
    },
    {
      title: "Paid",
      dataIndex: "paid_at",
      responsive: ["xl"],
      render: (d: string | null) => formatDate(d),
    },
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
            onClick={() =>
              void api.download(`/platform/tenants/${inv.organization_id}/invoices/${inv.id}/download`)
            }
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
    <PlatformGuard>
      <PageHeader
        title="Invoices"
        breadcrumbs={[PLATFORM_CRUMB, { label: "Invoices" }]}
        description="Every tenant's invoices. Record manual payments here or from the tenant page."
      />

      <Row gutter={[16, 16]} className="mb-4">
        <Col xs={24} sm={8}>
          <StatCard
            label="Outstanding"
            value={
              Object.entries(totals)
                .map(([cur, amt]) => formatMoney(amt, cur))
                .join(" · ") || "—"
            }
            context={`${open.length} open in this view`}
            loading={invoices.isLoading}
          />
        </Col>
        <Col xs={24} sm={8}>
          <StatCard
            label="Overdue"
            value={overdue.length}
            valueColor={overdue.length ? "#B91C1C" : undefined}
            context="past due date, still unpaid"
            loading={invoices.isLoading}
          />
        </Col>
      </Row>

      <FilterBar
        onReset={() => {
          setStatus("issued");
          setTenantId(null);
          setSearch("");
        }}
      >
        <SearchBar
          value={search}
          onChange={(value) => setSearch(value)}
          placeholder="Invoice number"
          label="Search invoice number"
          width={208}
        />
        <Select
          allowClear
          placeholder="All statuses"
          value={status}
          onChange={(v) => setStatus(v ?? null)}
          className="w-36"
          options={INVOICE_STATUSES.map((s) => ({ value: s, label: s }))}
          aria-label="Filter by invoice status"
        />
        <Select
          allowClear
          showSearch
          optionFilterProp="label"
          placeholder="All tenants"
          value={tenantId}
          onChange={(v) => setTenantId(v ?? null)}
          className="w-56"
          loading={tenants.isLoading}
          options={(tenants.data?.data ?? []).map((t) => ({ value: t.id, label: t.name }))}
          aria-label="Filter by tenant"
        />
      </FilterBar>

      <DataTable<PlatformInvoiceRow>
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={invoices.isLoading}
        error={invoices.error}
        onRetry={() => void invoices.refetch()}
        emptyTitle="No invoices in this view"
        emptyDescription="Invoices are issued when a subscription is assigned or renews."
        pagination={{ pageSize: 25, showSizeChanger: true, showTotal: (n) => `${n} invoices` }}
      />

      <RecordPaymentModal
        tenantId={paying?.organization_id ?? ""}
        tenantName={paying?.organization_name}
        invoice={paying}
        onClose={() => setPaying(null)}
      />
    </PlatformGuard>
  );
}
