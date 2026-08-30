import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Spinner } from "../../components/ui/Spinner";
import { api } from "../../lib/api";
import { timeAgo } from "../devices/types";
import { NotificationRulesTab } from "./NotificationRulesTab";

interface NotificationRow {
  id: string;
  type: string;
  severity: string;
  title: string;
  message: string | null;
  read_at: string | null;
  created_at: string;
}

const SEVERITY_STYLES: Record<string, string> = {
  info: "bg-sky-100 text-sky-700",
  warning: "bg-amber-100 text-amber-700",
  critical: "bg-red-100 text-red-700",
};

/** SCR-25 Notifications inbox + P2-18 rules. */
export function NotificationsPage() {
  const [tab, setTab] = useState<"inbox" | "rules">("inbox");

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Notifications</h1>
      <div className="mt-4 border-b border-slate-200" role="tablist">
        {(["inbox", "rules"] as const).map((key) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize ${
              tab === key
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {key === "inbox" ? "Inbox" : "Rules"}
          </button>
        ))}
      </div>
      <div className="mt-4">{tab === "inbox" ? <InboxTab /> : <NotificationRulesTab />}</div>
    </div>
  );
}

function InboxTab() {
  const queryClient = useQueryClient();
  const inboxQuery = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<NotificationRow[]>("/notifications?page_size=100"),
    refetchInterval: 30_000,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
    queryClient.invalidateQueries({ queryKey: ["monitoring-summary"] });
  };
  const markRead = useMutation({
    mutationFn: (id: string) => api.post(`/notifications/${id}/read`),
    onSuccess: refresh,
  });
  const markAll = useMutation({
    mutationFn: () => api.post("/notifications/read-all"),
    onSuccess: refresh,
  });

  const rows = inboxQuery.data?.data ?? [];
  const unread = rows.filter((r) => !r.read_at).length;

  return (
    <div>
      <div className="flex items-center justify-end">
        {unread > 0 && (
          <button
            type="button"
            onClick={() => markAll.mutate()}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
          >
            Mark all read ({unread})
          </button>
        )}
      </div>

      {inboxQuery.isLoading ? (
        <Spinner label="Loading notifications…" />
      ) : rows.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No notifications. Device registrations, approval requests and deployment
          failures appear here.
        </p>
      ) : (
        <ul className="mt-4 space-y-2">
          {rows.map((row) => (
            <li
              key={row.id}
              className={`flex flex-wrap items-center gap-3 rounded-lg border bg-white px-4 py-3 ${
                row.read_at ? "border-slate-200 opacity-60" : "border-slate-300"
              }`}
            >
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  SEVERITY_STYLES[row.severity] ?? "bg-slate-100 text-slate-600"
                }`}
              >
                {row.severity}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-800">{row.title}</p>
                {row.message && <p className="text-sm text-slate-500">{row.message}</p>}
              </div>
              <span className="text-xs text-slate-400">{timeAgo(row.created_at)}</span>
              {!row.read_at && (
                <button
                  type="button"
                  onClick={() => markRead.mutate(row.id)}
                  className="text-sm font-medium text-slate-600 hover:underline"
                >
                  Mark read
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
