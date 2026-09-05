import {
  AppstoreOutlined,
  AuditOutlined,
  DollarOutlined,
  RightOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { Button, Card, Col, Empty, Flex, Row, Space, Typography } from "antd";
import { Link } from "react-router-dom";
import { PageHeader } from "@/design-system";
import { StatCard } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { formatDate, formatMoney, isOverdue, usePlanRequests, usePlans, usePlatformInvoices, useTenants } from "./api";
import { PlatformGuard } from "./PlatformGuard";

/** Landing page for the console: the numbers that need attention today
 * and one-click routes to the section that resolves each of them. */
export function PlatformOverviewPage() {
  const tenants = useTenants();
  const plans = usePlans();
  const requests = usePlanRequests("pending");
  const invoices = usePlatformInvoices("issued", null);

  const tenantRows = tenants.data?.data ?? [];
  const activeTenants = tenantRows.filter((t) => t.status === "active").length;
  const subscribed = tenantRows.filter((t) =>
    ["active", "trialing"].includes(t.subscription_status ?? ""),
  ).length;
  const atRisk = tenantRows.filter((t) =>
    ["past_due", "grace_period", "suspended"].includes(t.subscription_status ?? ""),
  );
  const pending = requests.data?.data ?? [];
  const open = invoices.data?.data ?? [];
  const overdue = open.filter(isOverdue);
  const outstanding = open.reduce<Record<string, number>>((acc, inv) => {
    acc[inv.currency] = (acc[inv.currency] ?? 0) + Number(inv.amount);
    return acc;
  }, {});
  const outstandingLabel =
    Object.entries(outstanding)
      .map(([cur, amt]) => formatMoney(amt, cur))
      .join(" · ") || "—";

  return (
    <PlatformGuard>
      <PageHeader
        title="Platform Console"
        description="Tenants, plans, subscriptions and receivables across the whole platform."
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <StatCard
            label="Tenants"
            icon={<TeamOutlined />}
            value={tenantRows.length}
            context={`${activeTenants} active · ${subscribed} on a live subscription`}
            loading={tenants.isLoading}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <StatCard
            label="Plans"
            icon={<AppstoreOutlined />}
            value={(plans.data?.data ?? []).filter((p) => p.is_active).length}
            context={`${(plans.data?.data ?? []).length} in catalogue`}
            loading={plans.isLoading}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <StatCard
            label="Plan requests"
            icon={<AuditOutlined />}
            value={pending.length}
            context="awaiting your decision"
            valueColor={pending.length ? "#B45309" : undefined}
            loading={requests.isLoading}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <StatCard
            label="Outstanding"
            icon={<DollarOutlined />}
            value={outstandingLabel}
            context={`${open.length} open invoices · ${overdue.length} overdue`}
            valueColor={overdue.length ? "#B91C1C" : undefined}
            loading={invoices.isLoading}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]} className="mt-4">
        <Col xs={24} lg={12}>
          <Card
            size="small"
            title="Plan change requests"
            extra={
              <Link to="/platform/plan-requests">
                Open inbox <RightOutlined />
              </Link>
            }
          >
            <Rows
              loading={requests.isLoading}
              empty="Nothing waiting for approval."
              items={pending.slice(0, 5).map((req) => (
                <Space key={req.id} orientation="vertical" size={0}>
                  <Typography.Text strong>{req.organization_name}</Typography.Text>
                  <Typography.Text type="secondary" className="text-xs">
                    {req.from_plan} → {req.to_plan_name} · {formatDate(req.created_at)}
                  </Typography.Text>
                </Space>
              ))}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            size="small"
            title="Subscriptions needing attention"
            extra={
              <Link to="/platform/tenants">
                All tenants <RightOutlined />
              </Link>
            }
          >
            <Rows
              loading={tenants.isLoading}
              empty="Every subscription is in good standing."
              items={atRisk.slice(0, 5).map((t) => (
                <Flex key={t.id} align="center" justify="space-between" gap="small">
                  <Space>
                    <Typography.Text strong>{t.name}</Typography.Text>
                    <StatusBadge status={t.subscription_status ?? "none"} />
                  </Space>
                  <Link to={`/platform/tenants/${t.id}`}>
                    <Button size="small">Open</Button>
                  </Link>
                </Flex>
              ))}
            />
          </Card>
        </Col>
      </Row>
    </PlatformGuard>
  );
}

/** Short attention lists. antd's List is deprecated in 6.6 and its
 * replacement is a virtualised component built for long feeds, so five
 * rows are simply stacked and separated. */
function Rows({
  loading,
  empty,
  items,
}: {
  loading: boolean;
  empty: string;
  items: React.ReactNode[];
}) {
  if (loading) return <Card size="small" loading variant="borderless" />;
  if (items.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty} style={{ marginBlock: 16 }} />;
  }
  return (
    <Flex vertical gap={0} className="dsc-divided">
      {items.map((node, index) => (
        <div key={index} className="py-2">
          {node}
        </div>
      ))}
    </Flex>
  );
}
