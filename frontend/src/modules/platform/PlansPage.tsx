import { EditOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Segmented, Space, Tag, Typography, type TableProps } from "antd";
import { useState } from "react";
import { DataTable } from "../../components/ui/DataTable";
import { FilterBar } from "../../components/ui/FilterBar";
import { PageHeader } from "../../components/ui/PageHeader";
import { formatMoney, usePlans, useTenants } from "./api";
import { PlanDrawer } from "./PlanDrawer";
import { PlatformGuard, PLATFORM_CRUMB } from "./PlatformGuard";
import { entitlementLabel, type PlanRow } from "./types";

function limit(plan: PlanRow, key: string): string {
  const row = plan.entitlements.find((e) => e.key === key);
  return row?.int_value == null ? "∞" : row.int_value.toLocaleString();
}

/** The plan catalogue. Each row is what a tenant can subscribe to; the
 * drawer edits every entitlement the engine knows about. */
export function PlansPage() {
  const plans = usePlans();
  const tenants = useTenants();
  const [view, setView] = useState<"active" | "all">("active");
  const [drawer, setDrawer] = useState<{ open: boolean; plan: PlanRow | null }>({
    open: false,
    plan: null,
  });

  const tenantsOnPlan = (code: string) =>
    (tenants.data?.data ?? []).filter((t) => t.plan_code === code).length;

  const rows = (plans.data?.data ?? [])
    .filter((p) => view === "all" || p.is_active)
    .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name));

  const columns: TableProps<PlanRow>["columns"] = [
    {
      title: "Plan",
      dataIndex: "name",
      render: (name: string, p) => (
        <div>
          <Space size={6}>
            <Typography.Text strong>{name}</Typography.Text>
            {!p.is_active && <Tag variant="filled">Inactive</Tag>}
          </Space>
          <div>
            <Typography.Text type="secondary" className="text-xs">
              {p.code}
              {p.description ? ` · ${p.description}` : ""}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      title: "Monthly",
      align: "right",
      render: (_, p) =>
        p.prices.monthly ? formatMoney(p.prices.monthly.amount, p.prices.monthly.currency) : "Custom",
    },
    {
      title: "Yearly",
      align: "right",
      responsive: ["md"],
      render: (_, p) =>
        p.prices.yearly ? formatMoney(p.prices.yearly.amount, p.prices.yearly.currency) : "—",
    },
    { title: entitlementLabel("max_devices"), align: "right", render: (_, p) => limit(p, "max_devices") },
    {
      title: entitlementLabel("max_users"),
      align: "right",
      responsive: ["lg"],
      render: (_, p) => limit(p, "max_users"),
    },
    {
      title: entitlementLabel("max_storage_mb"),
      align: "right",
      responsive: ["lg"],
      render: (_, p) => limit(p, "max_storage_mb"),
    },
    {
      title: "Features",
      align: "right",
      responsive: ["xl"],
      render: (_, p) => p.entitlements.filter((e) => e.bool_value === true).length,
    },
    {
      title: "Tenants",
      align: "right",
      render: (_, p) => tenantsOnPlan(p.code),
    },
    {
      title: "",
      key: "edit",
      align: "right",
      render: (_, p) => (
        <Button size="small" icon={<EditOutlined />} onClick={() => setDrawer({ open: true, plan: p })}>
          Edit
        </Button>
      ),
    },
  ];

  return (
    <PlatformGuard>
      <PageHeader
        title="Plans"
        breadcrumbs={[PLATFORM_CRUMB, { label: "Plans" }]}
        description="What tenants can subscribe to: pricing, limits and feature entitlements."
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setDrawer({ open: true, plan: null })}>
            New plan
          </Button>
        }
      />

      <FilterBar>
        <Segmented
          value={view}
          onChange={(v) => setView(v as "active" | "all")}
          options={[
            { value: "active", label: "Open for subscription" },
            { value: "all", label: "All plans" },
          ]}
        />
      </FilterBar>

      <DataTable<PlanRow>
        rowKey="code"
        columns={columns}
        dataSource={rows}
        loading={plans.isLoading}
        error={plans.error}
        onRetry={() => void plans.refetch()}
        emptyTitle="No plans yet"
        emptyDescription="Create a plan before onboarding tenants."
        pagination={false}
      />

      <PlanDrawer
        open={drawer.open}
        plan={drawer.plan}
        onClose={() => setDrawer({ open: false, plan: null })}
      />
    </PlatformGuard>
  );
}
