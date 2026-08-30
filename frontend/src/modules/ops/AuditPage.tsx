import { useQuery } from "@tanstack/react-query";
import { Input, Select, Table, Typography, type TableProps } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";
import { FilterBar } from "../../components/ui/FilterBar";
import { PageHeader } from "../../components/ui/PageHeader";
import { EmptyState } from "../../components/ui/states";
import { api } from "../../lib/api";
import { timeAgo } from "../devices/types";
import { ExportButtons } from "./AnalyticsTabs";

/** P2-AUD-002 evidence links: entity type -> module route. */
const EVIDENCE_ROUTES: Record<string, string> = {
  device: "/devices",
  device_group: "/devices",
  campaign: "/campaigns",
  deployment: "/deployments",
  asset: "/content",
  layout: "/design",
  template: "/design",
  playlist: "/playlists",
  location: "/locations",
  user: "/users",
  player_release: "/releases",
  webhook_subscription: "/settings",
  api_key: "/settings",
  notification_rule: "/notifications",
  approval_policy: "/settings",
  organization: "/settings",
  incident: "/monitoring",
};

interface AuditRow {
  id: string;
  user_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

const ENTITY_TYPES = ["", "user", "device", "campaign", "deployment", "asset", "layout",
  "playlist", "location"];

/** SCR-25 Audit trail (FR-AUD-004: filter by actor, entity, action, date). */
export function AuditPage() {
  const [entityType, setEntityType] = useState("");
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 30;

  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (entityType) params.set("entity_type", entityType);
  if (action) params.set("action", action);

  const auditQuery = useQuery({
    queryKey: ["audit-logs", params.toString()],
    queryFn: () => api.get<AuditRow[]>(`/audit-logs?${params.toString()}`),
  });

  const rows = auditQuery.data?.data ?? [];
  const total = auditQuery.data?.meta.total ?? 0;

  const columns: TableProps<AuditRow>["columns"] = [
    {
      title: "When",
      width: 110,
      render: (_, row) => (
        <Typography.Text type="secondary">{timeAgo(row.created_at)}</Typography.Text>
      ),
    },
    { title: "Actor", render: (_, row) => row.user_name ?? "system" },
    {
      title: "Action",
      render: (_, row) => (
        <Typography.Text code className="text-xs">
          {row.action}
        </Typography.Text>
      ),
    },
    {
      title: "Entity",
      render: (_, row) => (
        <>
          {EVIDENCE_ROUTES[row.entity_type] ? (
            <Link to={EVIDENCE_ROUTES[row.entity_type]} title={`Open ${row.entity_type} module`}>
              {row.entity_type}
            </Link>
          ) : (
            row.entity_type
          )}
          {row.entity_id && (
            <Typography.Text type="secondary" className="ml-1 text-xs">
              {row.entity_id.slice(0, 8)}
            </Typography.Text>
          )}
        </>
      ),
    },
    {
      title: "Details",
      responsive: ["lg"],
      render: (_, row) => (
        <Typography.Text type="secondary" className="block max-w-72 truncate text-xs" code>
          {row.after ? JSON.stringify(row.after) : "—"}
        </Typography.Text>
      ),
    },
    {
      title: "IP",
      responsive: ["xl"],
      render: (_, row) => (
        <Typography.Text type="secondary" className="text-xs">
          {row.ip_address ?? "—"}
        </Typography.Text>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Audit Logs"
        description="Every consequential action, who did it, and what changed."
      />
      <FilterBar
        onReset={
          entityType || action
            ? () => {
                setEntityType("");
                setAction("");
                setPage(1);
              }
            : undefined
        }
      >
        <Select
          className="w-44"
          value={entityType}
          aria-label="Filter by entity type"
          onChange={(value) => {
            setEntityType(value);
            setPage(1);
          }}
          options={ENTITY_TYPES.map((t) => ({
            value: t,
            label: t ? t.charAt(0).toUpperCase() + t.slice(1) : "All entities",
          }))}
        />
        <Input
          allowClear
          className="w-80 font-mono"
          value={action}
          onChange={(e) => {
            setAction(e.target.value.toUpperCase());
            setPage(1);
          }}
          placeholder="Filter by action, e.g. CAMPAIGN_PUBLISHED"
          aria-label="Filter by action"
        />
        <ExportButtons
          report="audit"
          filters={{ action: action || null, entity_type: entityType || null }}
        />
      </FilterBar>

      <Table<AuditRow>
        size="middle"
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={auditQuery.isLoading}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: <EmptyState title="No audit entries match" /> }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: false,
          showTotal: (t) => `${t} entries`,
          onChange: setPage,
        }}
      />
    </div>
  );
}
