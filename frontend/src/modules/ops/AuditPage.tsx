import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Spinner } from "../../components/ui/Spinner";
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
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Audit Logs</h1>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <select
          value={entityType}
          onChange={(e) => {
            setEntityType(e.target.value);
            setPage(1);
          }}
          aria-label="Filter by entity type"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm capitalize"
        >
          {ENTITY_TYPES.map((t) => (
            <option key={t} value={t}>
              {t || "All entities"}
            </option>
          ))}
        </select>
        <input
          type="search"
          value={action}
          onChange={(e) => {
            setAction(e.target.value.toUpperCase());
            setPage(1);
          }}
          placeholder="Filter by action, e.g. CAMPAIGN_PUBLISHED"
          aria-label="Filter by action"
          className="w-80 rounded-md border border-slate-300 px-3 py-2 font-mono text-xs"
        />
        <ExportButtons
          report="audit"
          filters={{ action: action || null, entity_type: entityType || null }}
        />
      </div>

      {auditQuery.isLoading ? (
        <Spinner label="Loading audit trail…" />
      ) : rows.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No audit entries match.
        </p>
      ) : (
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">When</th>
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Entity</th>
                <th className="px-4 py-3">Details</th>
                <th className="px-4 py-3">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-slate-50">
                  <td className="whitespace-nowrap px-4 py-2 text-slate-500">
                    {timeAgo(row.created_at)}
                  </td>
                  <td className="px-4 py-2 text-slate-700">{row.user_name ?? "system"}</td>
                  <td className="px-4 py-2">
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
                      {row.action}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {EVIDENCE_ROUTES[row.entity_type] ? (
                      <Link
                        to={EVIDENCE_ROUTES[row.entity_type]}
                        className="text-slate-700 underline decoration-slate-300 hover:decoration-slate-700"
                        title={`Open ${row.entity_type} module`}
                      >
                        {row.entity_type}
                      </Link>
                    ) : (
                      row.entity_type
                    )}
                    {row.entity_id && (
                      <span className="ml-1 font-mono text-xs text-slate-400">
                        {row.entity_id.slice(0, 8)}
                      </span>
                    )}
                  </td>
                  <td className="max-w-72 truncate px-4 py-2 font-mono text-xs text-slate-500">
                    {row.after ? JSON.stringify(row.after) : "—"}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-400">
                    {row.ip_address ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>
            Page {page} of {totalPages} · {total} entries
          </span>
          <div className="space-x-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
