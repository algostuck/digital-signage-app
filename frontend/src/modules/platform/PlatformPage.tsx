import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Spinner } from "../../components/ui/Spinner";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { PlanEditor, type PlanRow } from "./PlanEditor";

interface TenantRow {
  id: string;
  name: string;
  code: string;
  status: string;
  plan_code: string | null;
  plan_name: string | null;
  subscription_status: string | null;
  devices: number;
  users: number;
}

interface InvoiceRow {
  id: string;
  number: string;
  amount: string;
  currency: string;
  status: string;
  due_at: string | null;
}

interface TenantQuotas {
  usage: {
    devices: { used: number; limit: number | null };
    users: { used: number; limit: number | null };
    storage_mb: { used: number; limit: number | null };
  };
  quotas: Record<string, number>;
}

interface PlanRequestRow {
  id: string;
  organization_name: string;
  organization_code: string;
  from_plan: string;
  to_plan: string;
  to_plan_name: string;
  status: string;
  note: string | null;
  created_at: string | null;
}

const PROVIDERS = ["manual", "stripe", "razorpay"];

const SUB_STATUSES = [
  "trialing",
  "active",
  "past_due",
  "grace_period",
  "suspended",
  "cancelled",
  "expired",
];

/** SCR-PLAT: Super Admin console — tenants, plans, subscriptions, payments. */
export function PlatformPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [selected, setSelected] = useState<TenantRow | null>(null);

  const tenantsQuery = useQuery({
    queryKey: ["platform-tenants"],
    queryFn: () => api.get<TenantRow[]>("/platform/tenants"),
    enabled: !!user?.is_superuser,
  });
  const plansQuery = useQuery({
    queryKey: ["platform-plans"],
    queryFn: () => api.get<PlanRow[]>("/platform/plans"),
    enabled: !!user?.is_superuser,
  });
  const invoicesQuery = useQuery({
    queryKey: ["platform-invoices", selected?.id],
    queryFn: () => api.get<InvoiceRow[]>(`/platform/tenants/${selected!.id}/invoices`),
    enabled: selected != null,
  });
  const quotasQuery = useQuery({
    queryKey: ["platform-quotas", selected?.id],
    queryFn: () => api.get<TenantQuotas>(`/platform/tenants/${selected!.id}/quotas`),
    enabled: selected != null,
  });

  const requestsQuery = useQuery({
    queryKey: ["platform-plan-requests"],
    queryFn: () => api.get<PlanRequestRow[]>("/platform/plan-requests"),
    enabled: !!user?.is_superuser,
  });

  const [quotaForm, setQuotaForm] = useState<Record<string, string>>({});
  const [providerForm, setProviderForm] = useState({ provider: "manual", customer: "", ref: "" });
  const [tenantForm, setTenantForm] = useState({ name: "", timezone: "" });
  useEffect(() => {
    if (selected) setTenantForm({ name: selected.name, timezone: "" });
  }, [selected]);
  useEffect(() => {
    const quotas = quotasQuery.data?.data?.quotas;
    if (quotas) {
      setQuotaForm({
        max_devices: quotas.max_devices?.toString() ?? "",
        max_users: quotas.max_users?.toString() ?? "",
        max_storage_mb: quotas.max_storage_mb?.toString() ?? "",
      });
    }
  }, [quotasQuery.data]);

  const done = (text: string) => {
    queryClient.invalidateQueries({ queryKey: ["platform-tenants"] });
    if (selected) queryClient.invalidateQueries({ queryKey: ["platform-invoices", selected.id] });
    setMessage({ kind: "ok", text });
  };
  const onError = (err: unknown) =>
    setMessage({
      kind: "error",
      text: err instanceof ApiError ? err.message : "Action failed",
    });

  // -- create tenant form state
  const [form, setForm] = useState({
    name: "",
    code: "",
    owner_email: "",
    owner_full_name: "",
    owner_password: "",
  });
  const createTenant = useMutation({
    mutationFn: () =>
      api.post("/platform/tenants", {
        ...form,
        owner_password: form.owner_password || null,
      }),
    onSuccess: () => {
      done("Tenant created.");
      setForm({ name: "", code: "", owner_email: "", owner_full_name: "", owner_password: "" });
    },
    onError,
  });

  const assignPlan = useMutation({
    mutationFn: ({ tenantId, plan_code }: { tenantId: string; plan_code: string }) =>
      api.post(`/platform/tenants/${tenantId}/subscription`, {
        plan_code,
        billing_cycle: "monthly",
      }),
    onSuccess: () => done("Subscription assigned."),
    onError,
  });
  const transition = useMutation({
    mutationFn: ({ tenantId, to_status }: { tenantId: string; to_status: string }) =>
      api.post(`/platform/tenants/${tenantId}/subscription/transition`, {
        to_status,
        event: "admin_transition",
      }),
    onSuccess: () => done("Subscription status updated."),
    onError,
  });
  const recordPayment = useMutation({
    mutationFn: ({ tenantId, invoiceId }: { tenantId: string; invoiceId: string }) =>
      api.post(`/platform/tenants/${tenantId}/payments`, { invoice_id: invoiceId }),
    onSuccess: () => done("Payment recorded — subscription reactivated."),
    onError,
  });
  const saveQuotas = useMutation({
    mutationFn: () =>
      api.patch(`/platform/tenants/${selected!.id}/quotas`, {
        max_devices: quotaForm.max_devices ? Number(quotaForm.max_devices) : null,
        max_users: quotaForm.max_users ? Number(quotaForm.max_users) : null,
        max_storage_mb: quotaForm.max_storage_mb ? Number(quotaForm.max_storage_mb) : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platform-quotas", selected?.id] });
      done("Quota overrides saved.");
    },
    onError,
  });
  const saveProvider = useMutation({
    mutationFn: () =>
      api.patch(`/platform/tenants/${selected!.id}/subscription/provider`, {
        provider: providerForm.provider,
        provider_customer_id: providerForm.customer || null,
        provider_subscription_id: providerForm.ref || null,
      }),
    onSuccess: () => done("Payment provider updated."),
    onError,
  });
  const saveTenant = useMutation({
    mutationFn: () =>
      api.patch(`/platform/tenants/${selected!.id}`, {
        name: tenantForm.name || null,
        timezone: tenantForm.timezone || null,
      }),
    onSuccess: () => done("Tenant updated."),
    onError,
  });
  const changeTenantPlan = useMutation({
    mutationFn: ({ tenantId, plan_code }: { tenantId: string; plan_code: string }) =>
      api.patch(`/platform/tenants/${tenantId}/subscription/plan`, { plan_code }),
    onSuccess: () => done("Plan changed."),
    onError,
  });
  const decideRequest = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) =>
      api.post(`/platform/plan-requests/${id}/${approve ? "approve" : "reject"}`, {}),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ["platform-plan-requests"] });
      done(vars.approve ? "Request approved — plan activated." : "Request rejected.");
    },
    onError,
  });

  if (!user?.is_superuser)
    return (
      <p className="text-sm text-red-600" role="alert">
        Platform administrator access required.
      </p>
    );
  if (tenantsQuery.isLoading) return <Spinner label="Loading tenants…" />;

  const tenants = tenantsQuery.data?.data ?? [];
  const plans = plansQuery.data?.data ?? [];
  const invoices = invoicesQuery.data?.data ?? [];
  const planRequests = requestsQuery.data?.data ?? [];

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setMessage(null);
    createTenant.mutate();
  }

  return (
    <div className="max-w-5xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Platform Administration</h1>
        <p className="mt-1 text-sm text-slate-500">
          Tenants, plans and subscriptions across the whole platform.
        </p>
      </div>

      {planRequests.length > 0 && (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-600">
            Plan change requests awaiting approval
          </h2>
          <p className="mt-0.5 text-xs text-amber-700">
            Verify the manual payment first, then approve — the plan activates
            immediately on approval.
          </p>
          <table className="mt-2 w-full text-left text-sm">
            <tbody>
              {planRequests.map((req) => (
                <tr key={req.id} className="border-t border-amber-200/60">
                  <td className="py-1.5 pr-4 font-medium text-slate-800">
                    {req.organization_name}
                  </td>
                  <td className="py-1.5 pr-4">
                    {req.from_plan} → <strong>{req.to_plan_name}</strong>
                  </td>
                  <td className="py-1.5 pr-4 text-xs text-slate-500">
                    {req.note ?? ""}
                  </td>
                  <td className="py-1.5">
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        disabled={decideRequest.isPending}
                        onClick={() => decideRequest.mutate({ id: req.id, approve: true })}
                        className="rounded-md bg-emerald-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        disabled={decideRequest.isPending}
                        onClick={() => decideRequest.mutate({ id: req.id, approve: false })}
                        className="rounded-md border border-red-300 px-2 py-1 text-xs font-medium text-red-600 disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Tenants</h2>
        <table className="mt-2 w-full text-left text-sm">
          <thead>
            <tr className="text-xs uppercase text-slate-400">
              <th className="py-1.5 pr-4">Name</th>
              <th className="py-1.5 pr-4">Code</th>
              <th className="py-1.5 pr-4">Plan</th>
              <th className="py-1.5 pr-4">Subscription</th>
              <th className="py-1.5 pr-4">Devices</th>
              <th className="py-1.5 pr-4">Users</th>
              <th className="py-1.5">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.id} className="border-t border-slate-100 align-top">
                <td className="py-2 pr-4 font-medium text-slate-800">{t.name}</td>
                <td className="py-2 pr-4 font-mono text-xs">{t.code}</td>
                <td className="py-2 pr-4">{t.plan_name ?? "—"}</td>
                <td className="py-2 pr-4">
                  {t.subscription_status ? (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">
                      {t.subscription_status.replace(/_/g, " ")}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">none (legacy)</span>
                  )}
                </td>
                <td className="py-2 pr-4">{t.devices}</td>
                <td className="py-2 pr-4">{t.users}</td>
                <td className="py-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {t.subscription_status == null ? (
                      <select
                        aria-label={`Assign plan to ${t.name}`}
                        defaultValue=""
                        onChange={(e) => {
                          if (e.target.value)
                            assignPlan.mutate({ tenantId: t.id, plan_code: e.target.value });
                          e.target.value = "";
                        }}
                        className="rounded-md border border-slate-300 px-1.5 py-1 text-xs"
                      >
                        <option value="">Assign plan…</option>
                        {plans
                          .filter((p) => p.is_active)
                          .map((p) => (
                            <option key={p.code} value={p.code}>
                              {p.name}
                            </option>
                          ))}
                      </select>
                    ) : (
                      <select
                        aria-label={`Set subscription status for ${t.name}`}
                        value={t.subscription_status}
                        onChange={(e) =>
                          transition.mutate({ tenantId: t.id, to_status: e.target.value })
                        }
                        className="rounded-md border border-slate-300 px-1.5 py-1 text-xs"
                      >
                        {SUB_STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {s.replace(/_/g, " ")}
                          </option>
                        ))}
                      </select>
                    )}
                    <button
                      type="button"
                      onClick={() => setSelected(selected?.id === t.id ? null : t)}
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                    >
                      {selected?.id === t.id ? "Close" : "Manage"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {selected && (
          <div className="mt-4 space-y-4 rounded-md border border-slate-200 bg-slate-50 p-3">
            <div>
              <h3 className="text-xs font-semibold uppercase text-slate-400">
                Tenant settings — {selected.name}
              </h3>
              <div className="mt-2 flex flex-wrap items-end gap-3">
                <label className="block text-sm">
                  <span className="block text-xs text-slate-500">Organization name</span>
                  <input
                    value={tenantForm.name}
                    onChange={(e) =>
                      setTenantForm((p) => ({ ...p, name: e.target.value }))
                    }
                    className="mt-0.5 w-56 rounded-md border border-slate-300 px-2 py-1.5"
                  />
                </label>
                <label className="block text-sm">
                  <span className="block text-xs text-slate-500">Timezone (IANA, optional)</span>
                  <input
                    value={tenantForm.timezone}
                    onChange={(e) =>
                      setTenantForm((p) => ({ ...p, timezone: e.target.value }))
                    }
                    placeholder="unchanged"
                    className="mt-0.5 w-44 rounded-md border border-slate-300 px-2 py-1.5"
                  />
                </label>
                <button
                  type="button"
                  disabled={saveTenant.isPending}
                  onClick={() => saveTenant.mutate()}
                  className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                >
                  Save tenant
                </button>
                {selected.subscription_status != null && (
                  <label className="block text-sm">
                    <span className="block text-xs text-slate-500">
                      Change plan (direct — upgrade or downgrade)
                    </span>
                    <select
                      defaultValue=""
                      disabled={changeTenantPlan.isPending}
                      onChange={(e) => {
                        if (e.target.value)
                          changeTenantPlan.mutate({
                            tenantId: selected.id,
                            plan_code: e.target.value,
                          });
                        e.target.value = "";
                      }}
                      className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
                    >
                      <option value="">Select plan…</option>
                      {plans
                        .filter((p) => p.code !== selected.plan_code)
                        .map((p) => (
                          <option key={p.code} value={p.code}>
                            {p.name}
                          </option>
                        ))}
                    </select>
                  </label>
                )}
              </div>
            </div>

            <div>
              <h3 className="text-xs font-semibold uppercase text-slate-400">
                Quota overrides
              </h3>
              <p className="mt-0.5 text-xs text-slate-400">
                Tightens numeric limits below the plan (blank = plan limit
                applies). Tenants cannot edit these.
              </p>
              <div className="mt-2 flex flex-wrap items-end gap-3">
                {(
                  [
                    ["max_devices", "Devices"],
                    ["max_users", "Users"],
                    ["max_storage_mb", "Storage (MB)"],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="block text-sm">
                    <span className="block text-xs text-slate-500">{label}</span>
                    <input
                      type="number"
                      min={1}
                      value={quotaForm[key] ?? ""}
                      onChange={(e) =>
                        setQuotaForm((prev) => ({ ...prev, [key]: e.target.value }))
                      }
                      placeholder="plan limit"
                      className="mt-0.5 w-28 rounded-md border border-slate-300 px-2 py-1.5"
                    />
                  </label>
                ))}
                <button
                  type="button"
                  disabled={saveQuotas.isPending}
                  onClick={() => saveQuotas.mutate()}
                  className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                >
                  Save overrides
                </button>
              </div>
            </div>

            {selected.subscription_status != null && (
              <div>
                <h3 className="text-xs font-semibold uppercase text-slate-400">
                  Payment provider
                </h3>
                <p className="mt-0.5 text-xs text-slate-400">
                  `manual` = enterprise invoice flow (record payments here).
                  Gateway API keys are server environment configuration —
                  never entered or stored here; only provider references.
                </p>
                <div className="mt-2 flex flex-wrap items-end gap-3">
                  <label className="block text-sm">
                    <span className="block text-xs text-slate-500">Provider</span>
                    <select
                      value={providerForm.provider}
                      onChange={(e) =>
                        setProviderForm((p) => ({ ...p, provider: e.target.value }))
                      }
                      className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
                    >
                      {PROVIDERS.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block text-sm">
                    <span className="block text-xs text-slate-500">Customer reference</span>
                    <input
                      value={providerForm.customer}
                      onChange={(e) =>
                        setProviderForm((p) => ({ ...p, customer: e.target.value }))
                      }
                      placeholder="e.g. cus_..."
                      className="mt-0.5 w-40 rounded-md border border-slate-300 px-2 py-1.5"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="block text-xs text-slate-500">Subscription reference</span>
                    <input
                      value={providerForm.ref}
                      onChange={(e) => setProviderForm((p) => ({ ...p, ref: e.target.value }))}
                      placeholder="e.g. sub_..."
                      className="mt-0.5 w-40 rounded-md border border-slate-300 px-2 py-1.5"
                    />
                  </label>
                  <button
                    type="button"
                    disabled={saveProvider.isPending}
                    onClick={() => saveProvider.mutate()}
                    className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                  >
                    Save provider
                  </button>
                </div>
              </div>
            )}

            <div>
              <h3 className="text-xs font-semibold uppercase text-slate-400">Invoices</h3>
              {invoices.length === 0 ? (
                <p className="mt-1 text-sm text-slate-500">No invoices.</p>
              ) : (
                <table className="mt-1 w-full text-left text-sm">
                  <tbody>
                    {invoices.map((inv) => (
                      <tr key={inv.id} className="border-t border-slate-200">
                        <td className="py-1.5 pr-4 font-mono text-xs">{inv.number}</td>
                        <td className="py-1.5 pr-4">
                          {inv.amount} {inv.currency}
                        </td>
                        <td className="py-1.5 pr-4">{inv.status}</td>
                        <td className="py-1.5">
                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() =>
                                void api.download(
                                  `/platform/tenants/${selected.id}/invoices/${inv.id}/download`,
                                )
                              }
                              className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                            >
                              Download
                            </button>
                            {inv.status === "issued" && (
                              <button
                                type="button"
                                onClick={() =>
                                  recordPayment.mutate({
                                    tenantId: selected.id,
                                    invoiceId: inv.id,
                                  })
                                }
                                className="rounded-md bg-emerald-600 px-2 py-1 text-xs font-medium text-white"
                              >
                                Record payment
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Create tenant
        </h2>
        <form className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2" onSubmit={onCreate}>
          {(
            [
              ["name", "Organization name", "text"],
              ["code", "Code (lowercase)", "text"],
              ["owner_email", "Owner email", "email"],
              ["owner_full_name", "Owner full name", "text"],
              ["owner_password", "Owner password (blank = invite)", "password"],
            ] as const
          ).map(([key, label, type]) => (
            <label key={key} className="block text-sm">
              <span className="block text-xs text-slate-500">{label}</span>
              <input
                type={type}
                required={key !== "owner_password"}
                value={form[key]}
                onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))}
                className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
              />
            </label>
          ))}
          <div className="flex items-end">
            <button
              type="submit"
              disabled={createTenant.isPending}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Create tenant
            </button>
          </div>
        </form>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Plans</h2>
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {plans.map((plan) => {
            const ints = plan.entitlements.filter((e) => e.int_value !== null);
            const bools = plan.entitlements.filter((e) => e.bool_value === true);
            return (
              <div key={plan.code} className="rounded-md border border-slate-200 p-3">
                <p className="font-semibold text-slate-800">
                  {plan.name}
                  {!plan.is_active && (
                    <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-normal text-slate-500">
                      inactive
                    </span>
                  )}
                </p>
                <ul className="mt-1 space-y-0.5 text-xs text-slate-500">
                  {ints.slice(0, 4).map((e) => (
                    <li key={e.key}>
                      {e.key.replace(/^max_|_month$/g, "").replace(/_/g, " ")}: {e.int_value}
                    </li>
                  ))}
                  <li>{bools.length} features enabled</li>
                </ul>
              </div>
            );
          })}
        </div>
      </section>

      <PlanEditor plans={plans} />

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
