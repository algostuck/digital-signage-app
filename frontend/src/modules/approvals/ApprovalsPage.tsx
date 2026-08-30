import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo } from "../devices/types";

interface ApprovalAction {
  action: string;
  comments: string | null;
  actor_name: string | null;
  created_at: string;
}

interface ApprovalRequest {
  id: string;
  entity_type: string;
  entity_id: string;
  state: string;
  entity_name: string | null;
  requester_name: string | null;
  submitted_at: string;
  decided_at: string | null;
  comments: string | null;
  actions: ApprovalAction[];
}

const TABS = [
  { key: "pending", label: "Pending" },
  { key: "rejected", label: "Returned" },
  { key: "approved", label: "Approved" },
  { key: "", label: "All" },
] as const;

/** P2-09 Content Approval Inbox. */
export function ApprovalsPage() {
  const { hasPermission } = useAuth();
  const canDecide = hasPermission("campaigns.approve");
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<string>("pending");
  const [decision, setDecision] = useState<{
    request: ApprovalRequest;
    approve: boolean;
  } | null>(null);
  const [comments, setComments] = useState("");
  const [error, setError] = useState<string | null>(null);

  const inboxQuery = useQuery({
    queryKey: ["approvals", tab],
    queryFn: () =>
      api.get<ApprovalRequest[]>(
        `/approvals/inbox?page_size=100${tab ? `&state=${tab}` : ""}`,
      ),
    refetchInterval: 30_000,
  });

  const decide = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) =>
      api.post(`/approvals/${id}/${approve ? "approve" : "reject"}`, {
        comments: comments || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      setDecision(null);
      setComments("");
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Decision failed"),
  });

  const rows = inboxQuery.data?.data ?? [];

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Approvals</h1>
      <p className="mt-1 text-sm text-slate-500">
        Maker-checker governance for campaigns and templates. Configure policies under
        Settings.
      </p>

      <div className="mt-4 border-b border-slate-200" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t.key
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {inboxQuery.isLoading ? (
        <Spinner label="Loading approvals…" />
      ) : inboxQuery.isError ? (
        <p className="mt-6 text-sm text-red-600" role="alert">
          Failed to load the approval inbox (you may lack approval permissions).
        </p>
      ) : rows.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          Nothing here. Submitted items appear in this queue.
        </p>
      ) : (
        <ul className="mt-4 space-y-2">
          {rows.map((request) => (
            <li
              key={request.id}
              className="rounded-lg border border-slate-200 bg-white px-4 py-3"
            >
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium capitalize text-slate-600">
                  {request.entity_type}
                </span>
                <span className="font-medium text-slate-800">
                  {request.entity_name ?? request.entity_id.slice(0, 8)}
                </span>
                <StatusBadge status={request.state} />
                <span className="text-sm text-slate-500">
                  by {request.requester_name ?? "unknown"} · {timeAgo(request.submitted_at)}
                </span>
                {request.state === "pending" && canDecide && (
                  <span className="ml-auto space-x-2">
                    <button
                      type="button"
                      onClick={() => setDecision({ request, approve: true })}
                      className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => setDecision({ request, approve: false })}
                      className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600"
                    >
                      Reject
                    </button>
                  </span>
                )}
              </div>
              {request.actions.length > 1 && (
                <ul className="mt-2 space-y-0.5 border-t border-slate-100 pt-2 text-xs text-slate-500">
                  {request.actions.map((action, index) => (
                    <li key={index}>
                      <span className="font-medium capitalize">{action.action}</span> by{" "}
                      {action.actor_name ?? "system"} · {timeAgo(action.created_at)}
                      {action.comments && <span> — “{action.comments}”</span>}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}

      {decision && (
        <Modal
          title={`${decision.approve ? "Approve" : "Reject"}: ${
            decision.request.entity_name ?? decision.request.entity_type
          }`}
          open
          onClose={() => setDecision(null)}
        >
          <div className="space-y-4">
            <div>
              <label htmlFor="decision-comments" className="block text-sm font-medium text-slate-700">
                Comments {decision.approve ? "(optional)" : "(tell the requester what to fix)"}
              </label>
              <textarea
                id="decision-comments"
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                rows={3}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            {error && (
              <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
                {error}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDecision(null)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={decide.isPending}
                onClick={() =>
                  decide.mutate({ id: decision.request.id, approve: decision.approve })
                }
                className={`rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50 ${
                  decision.approve ? "bg-emerald-600" : "bg-red-600"
                }`}
              >
                {decide.isPending
                  ? "Saving…"
                  : decision.approve
                    ? "Approve"
                    : "Reject"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
