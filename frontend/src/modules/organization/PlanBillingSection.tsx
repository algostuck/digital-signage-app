import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface PlanBrief {
  code: string;
  name: string;
}

interface SubscriptionInfo {
  id: string;
  plan: PlanBrief;
  status: string;
  billing_cycle: string;
  current_period_end: string | null;
  trial_end_at: string | null;
  cancel_at: string | null;
}

interface BillingData {
  subscription: SubscriptionInfo | null;
  entitlements: Record<string, number | boolean | null>;
  plan_code: string | null;
  plan_name: string | null;
  status: string | null;
  usage: {
    devices: { used: number; limit: number | null };
    users: { used: number; limit: number | null };
    storage_mb: { used: number; limit: number | null };
  };
  pending_plan_request: {
    id: string;
    to_plan: string;
    to_plan_name: string;
    created_at: string | null;
  } | null;
}

interface InvoiceRow {
  id: string;
  number: string;
  amount: string;
  currency: string;
  status: string;
  issued_at: string | null;
  due_at: string | null;
}

interface PlanRow {
  code: string;
  name: string;
  description: string | null;
  prices: Record<string, { amount: number; currency: string }>;
}

const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  trialing: "bg-sky-100 text-sky-700",
  past_due: "bg-amber-100 text-amber-700",
  grace_period: "bg-orange-100 text-orange-700",
  suspended: "bg-red-100 text-red-700",
  cancelled: "bg-slate-200 text-slate-600",
  expired: "bg-slate-200 text-slate-600",
};

const FEATURE_LABELS: Record<string, string> = {
  proof_of_play: "Proof of play",
  advanced_analytics: "Advanced analytics",
  api_access: "API access",
  sso: "SSO",
  white_label: "White label",
  video_wall: "Video walls",
  ai_features: "AI features",
  dynamic_data: "Dynamic data",
};

function fmtDate(value: string | null): string {
  return value ? new Date(value).toLocaleDateString() : "—";
}

/** Settings › Plan & Billing (SaaS core): current plan, entitlements vs
 * usage, invoices, cancel/reactivate and plan changes. */
export function PlanBillingSection() {
  const { hasPermission } = useAuth();
  const canView = hasPermission("billing.view");
  const canManage = hasPermission("billing.manage");
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const billingQuery = useQuery({
    queryKey: ["billing-subscription"],
    queryFn: () => api.get<BillingData>("/billing/subscription"),
    enabled: canView,
  });
  const invoicesQuery = useQuery({
    queryKey: ["billing-invoices"],
    queryFn: () => api.get<InvoiceRow[]>("/billing/invoices"),
    enabled: canView,
  });
  const plansQuery = useQuery({
    queryKey: ["plans"],
    queryFn: () => api.get<PlanRow[]>("/plans"),
    enabled: canManage,
  });

  const onDone = (text: string) => {
    queryClient.invalidateQueries({ queryKey: ["billing-subscription"] });
    queryClient.invalidateQueries({ queryKey: ["billing-invoices"] });
    queryClient.invalidateQueries({ queryKey: ["org-usage"] });
    setMessage({ kind: "ok", text });
  };
  const onError = (err: unknown) =>
    setMessage({
      kind: "error",
      text: err instanceof ApiError ? err.message : "Billing action failed",
    });

  const changePlan = useMutation({
    mutationFn: (plan_code: string) => api.post("/billing/change-plan", { plan_code }),
    onSuccess: () =>
      onDone(
        "Request submitted. The plan activates once the platform administrator " +
          "confirms your payment and approves.",
      ),
    onError,
  });
  const cancel = useMutation({
    mutationFn: () => api.post("/billing/cancel", { at_period_end: true }),
    onSuccess: () => onDone("Subscription will end at the current period."),
    onError,
  });
  const reactivate = useMutation({
    mutationFn: () => api.post("/billing/reactivate", {}),
    onSuccess: () => onDone("Subscription reactivated."),
    onError,
  });

  if (!canView) return null;
  const billing = billingQuery.data?.data ?? null;
  if (!billing) return null;
  const invoices = invoicesQuery.data?.data ?? [];
  const plans = plansQuery.data?.data ?? [];
  const sub = billing.subscription;

  return (
    <div className="mt-8 space-y-6">
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Plan &amp; billing
        </h2>
        {sub == null ? (
          <p className="mt-2 text-sm text-slate-600">
            No subscription — this organization runs without plan limits.
          </p>
        ) : (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <span className="text-lg font-semibold text-slate-800">{sub.plan.name}</span>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                STATUS_STYLE[sub.status] ?? "bg-slate-100 text-slate-600"
              }`}
            >
              {sub.status.replace(/_/g, " ")}
            </span>
            <span className="text-sm text-slate-500">
              {sub.billing_cycle} · renews {fmtDate(sub.current_period_end)}
            </span>
            {sub.cancel_at && (
              <span className="text-sm text-amber-600">
                ends {fmtDate(sub.cancel_at)}
              </span>
            )}
            {canManage && (
              <span className="ml-auto flex items-center gap-2">
                {plans.length > 0 && !billing.pending_plan_request && (
                  <select
                    aria-label="Request plan change"
                    defaultValue=""
                    disabled={changePlan.isPending}
                    onChange={(e) => {
                      if (e.target.value) changePlan.mutate(e.target.value);
                      e.target.value = "";
                    }}
                    className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  >
                    <option value="">Request plan change…</option>
                    {plans
                      .filter((p) => p.code !== sub.plan.code)
                      .map((p) => (
                        <option key={p.code} value={p.code}>
                          {p.name}
                        </option>
                      ))}
                  </select>
                )}
                {sub.cancel_at || ["suspended", "cancelled"].includes(sub.status) ? (
                  <button
                    type="button"
                    onClick={() => reactivate.mutate()}
                    disabled={reactivate.isPending}
                    className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                  >
                    Reactivate
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => cancel.mutate()}
                    disabled={cancel.isPending}
                    className="rounded-md border border-red-300 px-3 py-1.5 text-sm font-medium text-red-600 disabled:opacity-50"
                  >
                    Cancel at period end
                  </button>
                )}
              </span>
            )}
          </div>
        )}
        {billing.pending_plan_request && (
          <p className="mt-3 rounded-md bg-sky-50 px-3 py-2 text-sm text-sky-800">
            Change to <strong>{billing.pending_plan_request.to_plan_name}</strong>{" "}
            requested — it activates once the platform administrator confirms
            your payment and approves the request.
          </p>
        )}
        {["past_due", "grace_period", "suspended"].includes(billing.status ?? "") && (
          <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Payment is overdue. Existing displays continue cached playback; new
            registrations, uploads and publishing are restricted until payment
            is received.
          </p>
        )}

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {Object.entries(FEATURE_LABELS).map(([key, label]) => {
            const enabled = billing.entitlements[key] !== false;
            return (
              <span
                key={key}
                className={`rounded-md px-2 py-1 text-xs font-medium ${
                  enabled ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-400"
                }`}
              >
                {enabled ? "✓" : "✕"} {label}
              </span>
            );
          })}
        </div>
      </section>

      {invoices.length > 0 && (
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Invoices
          </h2>
          <table className="mt-2 w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase text-slate-400">
                <th className="py-1.5 pr-4">Number</th>
                <th className="py-1.5 pr-4">Amount</th>
                <th className="py-1.5 pr-4">Issued</th>
                <th className="py-1.5 pr-4">Due</th>
                <th className="py-1.5 pr-4">Status</th>
                <th className="py-1.5" />
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-t border-slate-100">
                  <td className="py-1.5 pr-4 font-mono text-xs">{inv.number}</td>
                  <td className="py-1.5 pr-4">
                    {inv.amount} {inv.currency}
                  </td>
                  <td className="py-1.5 pr-4">{fmtDate(inv.issued_at)}</td>
                  <td className="py-1.5 pr-4">{fmtDate(inv.due_at)}</td>
                  <td className="py-1.5 pr-4">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        inv.status === "paid"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {inv.status}
                    </span>
                  </td>
                  <td className="py-1.5">
                    <button
                      type="button"
                      onClick={() =>
                        void api.download(`/billing/invoices/${inv.id}/download`)
                      }
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                    >
                      Download
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {message && (
        <p
          role={message.kind === "error" ? "alert" : undefined}
          className={`rounded-md px-3 py-2 text-sm ${
            message.kind === "ok"
              ? "bg-emerald-50 text-emerald-700"
              : "bg-red-50 text-red-700"
          }`}
        >
          {message.text}
        </p>
      )}
    </div>
  );
}
