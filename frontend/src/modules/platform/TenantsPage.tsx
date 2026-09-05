import { PlusOutlined } from "@ant-design/icons";
import { Button, Select, Typography, type TableProps } from "antd";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { DataTable } from "@/design-system";
import { SearchBar } from "@/design-system";
import { FilterBar } from "@/design-system";
import { PageHeader } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { formatDate, usePlans, useTenants } from "./api";
import { PlatformGuard, PLATFORM_CRUMB } from "./PlatformGuard";
import { TenantCreateDrawer } from "./TenantCreateDrawer";
import { ORG_STATUSES, SUB_STATUSES, type TenantRow } from "./types";

const NONE = "__none__";

/** Every organization on the platform. Rows open the tenant workspace;
 * nothing is edited inline here. */
export function TenantsPage() {
  const tenants = useTenants();
  const plans = usePlans();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [subscription, setSubscription] = useState<string | null>(null);
  const [plan, setPlan] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (tenants.data?.data ?? []).filter((t) => {
      if (q && !t.name.toLowerCase().includes(q) && !t.code.toLowerCase().includes(q)) return false;
      if (status && t.status !== status) return false;
      if (subscription === NONE && t.subscription_status != null) return false;
      if (subscription && subscription !== NONE && t.subscription_status !== subscription) return false;
      if (plan && t.plan_code !== plan) return false;
      return true;
    });
  }, [tenants.data, search, status, subscription, plan]);

  const columns: TableProps<TenantRow>["columns"] = [
    {
      title: "Tenant",
      dataIndex: "name",
      sorter: (a, b) => a.name.localeCompare(b.name),
      render: (name: string, t) => (
        <div className="min-w-0">
          <Link to={`/platform/tenants/${t.id}`} className="font-medium">
            {name}
          </Link>
          <div>
            <Typography.Text type="secondary" className="text-xs">
              {t.code}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      title: "Status",
      dataIndex: "status",
      render: (s: string) => <StatusBadge status={s} />,
    },
    {
      title: "Plan",
      dataIndex: "plan_name",
      responsive: ["md"],
      render: (p: string | null) => p ?? <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: "Subscription",
      dataIndex: "subscription_status",
      render: (s: string | null) =>
        s ? (
          <StatusBadge status={s} />
        ) : (
          <Typography.Text type="secondary" className="text-xs">
            None (legacy)
          </Typography.Text>
        ),
    },
    {
      title: "Devices",
      dataIndex: "devices",
      align: "right",
      responsive: ["lg"],
      sorter: (a, b) => a.devices - b.devices,
    },
    {
      title: "Users",
      dataIndex: "users",
      align: "right",
      responsive: ["lg"],
      sorter: (a, b) => a.users - b.users,
    },
    {
      title: "Created",
      dataIndex: "created_at",
      responsive: ["xl"],
      sorter: (a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""),
      render: (d: string | null) => formatDate(d),
    },
    {
      title: "",
      key: "open",
      align: "right",
      render: (_, t) => (
        <Link to={`/platform/tenants/${t.id}`}>
          <Button size="small">Open</Button>
        </Link>
      ),
    },
  ];

  return (
    <PlatformGuard>
      <PageHeader
        title="Tenants"
        breadcrumbs={[PLATFORM_CRUMB, { label: "Tenants" }]}
        description="Every organization on the platform, with its plan and subscription health."
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            New tenant
          </Button>
        }
      />

      <FilterBar
        search={<SearchBar value={search} onChange={(value) => setSearch(value)} placeholder="Search name or code" label="Search tenants" width={256} />}
        onReset={() => {
          setSearch("");
          setStatus(null);
          setSubscription(null);
          setPlan(null);
        }}
      >
        <Select
          allowClear
          placeholder="Status"
          value={status}
          onChange={(v) => setStatus(v ?? null)}
          className="w-36"
          options={ORG_STATUSES.map((s) => ({ value: s, label: s }))}
          aria-label="Filter by tenant status"
        />
        <Select
          allowClear
          placeholder="Subscription"
          value={subscription}
          onChange={(v) => setSubscription(v ?? null)}
          className="w-44"
          options={[
            { value: NONE, label: "None (legacy)" },
            ...SUB_STATUSES.map((s) => ({ value: s, label: s.replace(/_/g, " ") })),
          ]}
          aria-label="Filter by subscription status"
        />
        <Select
          allowClear
          placeholder="Plan"
          value={plan}
          onChange={(v) => setPlan(v ?? null)}
          className="w-44"
          loading={plans.isLoading}
          options={(plans.data?.data ?? []).map((p) => ({ value: p.code, label: p.name }))}
          aria-label="Filter by plan"
        />
      </FilterBar>

      <DataTable<TenantRow>
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={tenants.isLoading}
        error={tenants.error}
        onRetry={() => void tenants.refetch()}
        emptyTitle={search || status || subscription || plan ? "No tenants match" : "No tenants yet"}
        emptyDescription={
          search || status || subscription || plan
            ? "Try clearing a filter."
            : "Create the first tenant to onboard a customer."
        }
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (n) => `${n} tenants` }}
      />

      <TenantCreateDrawer open={createOpen} onClose={() => setCreateOpen(false)} />
    </PlatformGuard>
  );
}
