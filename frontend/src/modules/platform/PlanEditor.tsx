import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";

interface EntitlementRow {
  key: string;
  int_value: number | null;
  bool_value: boolean | null;
}

export interface PlanRow {
  code: string;
  name: string;
  description: string | null;
  prices: Record<string, { amount: number; currency: string }>;
  is_active: boolean;
  sort_order: number;
  entitlements: EntitlementRow[];
}

/** Super Admin plan editor: create a plan or edit an existing one. The
 * entitlement catalogue (key -> int|bool) comes from the backend so the
 * form always matches the engine. */
export function PlanEditor({ plans }: { plans: PlanRow[] }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [editing, setEditing] = useState<string>(""); // plan code or "" = new
  const [form, setForm] = useState({
    code: "",
    name: "",
    description: "",
    monthly: "",
    yearly: "",
    currency: "INR",
    is_active: true,
    sort_order: "0",
  });
  const [ints, setInts] = useState<Record<string, string>>({});
  const [bools, setBools] = useState<Record<string, boolean>>({});

  const catalogueQuery = useQuery({
    queryKey: ["platform-entitlement-catalogue"],
    queryFn: () => api.get<Record<string, "int" | "bool">>("/platform/entitlements"),
  });
  const catalogue = catalogueQuery.data?.data ?? {};
  const intKeys = Object.keys(catalogue).filter((k) => catalogue[k] === "int");
  const boolKeys = Object.keys(catalogue).filter((k) => catalogue[k] === "bool");

  function loadPlan(code: string) {
    setEditing(code);
    setMessage(null);
    if (!code) {
      setForm({
        code: "",
        name: "",
        description: "",
        monthly: "",
        yearly: "",
        currency: "INR",
        is_active: true,
        sort_order: "0",
      });
      setInts({});
      setBools({});
      return;
    }
    const plan = plans.find((p) => p.code === code);
    if (!plan) return;
    setForm({
      code: plan.code,
      name: plan.name,
      description: plan.description ?? "",
      monthly: plan.prices.monthly?.amount?.toString() ?? "",
      yearly: plan.prices.yearly?.amount?.toString() ?? "",
      currency: plan.prices.monthly?.currency ?? plan.prices.yearly?.currency ?? "INR",
      is_active: plan.is_active,
      sort_order: String(plan.sort_order),
    });
    setInts(
      Object.fromEntries(
        plan.entitlements
          .filter((e) => e.int_value !== null)
          .map((e) => [e.key, String(e.int_value)]),
      ),
    );
    setBools(
      Object.fromEntries(
        plan.entitlements
          .filter((e) => e.bool_value !== null)
          .map((e) => [e.key, e.bool_value === true]),
      ),
    );
  }

  const save = useMutation({
    mutationFn: () => {
      const prices: Record<string, { amount: number; currency: string }> = {};
      if (form.monthly) prices.monthly = { amount: Number(form.monthly), currency: form.currency };
      if (form.yearly) prices.yearly = { amount: Number(form.yearly), currency: form.currency };
      const entitlements = [
        ...intKeys
          .filter((k) => ints[k] !== undefined && ints[k] !== "")
          .map((k) => ({ key: k, int_value: Number(ints[k]) })),
        ...boolKeys.map((k) => ({ key: k, bool_value: bools[k] ?? false })),
      ];
      return api.post("/platform/plans", {
        code: form.code,
        name: form.name,
        description: form.description || null,
        prices,
        entitlements,
        is_active: form.is_active,
        sort_order: Number(form.sort_order) || 0,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platform-plans"] });
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      setMessage({ kind: "ok", text: `Plan '${form.code}' saved.` });
    },
    onError: (err) =>
      setMessage({
        kind: "error",
        text: err instanceof ApiError ? err.message : "Failed to save plan",
      }),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setMessage(null);
    save.mutate();
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Plan editor
        </h2>
        <select
          aria-label="Plan to edit"
          value={editing}
          onChange={(e) => loadPlan(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">+ New plan</option>
          {plans.map((p) => (
            <option key={p.code} value={p.code}>
              Edit: {p.name}
            </option>
          ))}
        </select>
      </div>

      <form className="mt-3 space-y-4" onSubmit={onSubmit}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Code</span>
            <input
              required
              disabled={editing !== ""}
              value={form.code}
              onChange={(e) => setForm((p) => ({ ...p, code: e.target.value }))}
              className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5 disabled:bg-slate-50"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Name</span>
            <input
              required
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Monthly price (blank = custom)</span>
            <input
              type="number"
              min={0}
              value={form.monthly}
              onChange={(e) => setForm((p) => ({ ...p, monthly: e.target.value }))}
              className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Yearly price</span>
            <input
              type="number"
              min={0}
              value={form.yearly}
              onChange={(e) => setForm((p) => ({ ...p, yearly: e.target.value }))}
              className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Currency</span>
            <input
              maxLength={3}
              value={form.currency}
              onChange={(e) => setForm((p) => ({ ...p, currency: e.target.value.toUpperCase() }))}
              className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Sort order</span>
            <input
              type="number"
              value={form.sort_order}
              onChange={(e) => setForm((p) => ({ ...p, sort_order: e.target.value }))}
              className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="block text-xs text-slate-500">Description</span>
            <input
              value={form.description}
              onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
              className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
        </div>

        <div>
          <h3 className="text-xs font-semibold uppercase text-slate-400">
            Limits (blank = unlimited)
          </h3>
          <div className="mt-1.5 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {intKeys.map((key) => (
              <label key={key} className="block text-sm">
                <span className="block text-xs text-slate-500">{key.replace(/_/g, " ")}</span>
                <input
                  type="number"
                  min={0}
                  value={ints[key] ?? ""}
                  onChange={(e) => setInts((p) => ({ ...p, [key]: e.target.value }))}
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
                />
              </label>
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-xs font-semibold uppercase text-slate-400">Features</h3>
          <div className="mt-1.5 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
            {boolKeys.map((key) => (
              <label key={key} className="flex items-center gap-1.5 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={bools[key] ?? false}
                  onChange={(e) => setBools((p) => ({ ...p, [key]: e.target.checked }))}
                />
                {key.replace(/_/g, " ")}
              </label>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
            />
            Open for subscription
          </label>
          <button
            type="submit"
            disabled={save.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {editing ? "Save plan" : "Create plan"}
          </button>
        </div>

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
      </form>
    </section>
  );
}
