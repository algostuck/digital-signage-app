import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface EventRow {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id: string | null;
  payload: Record<string, unknown> | null;
  occurred_at: string | null;
}

interface SubscriptionRow {
  id: string;
  name: string;
  url: string;
  event_types: string[];
  active: boolean;
  secret?: string;
}

interface DeliveryRow {
  id: string;
  event_type: string;
  state: string;
  attempt_no: number;
  response_code: number | null;
  last_error: string | null;
  created_at: string | null;
}

const STATE_STYLE: Record<string, string> = {
  delivered: "bg-emerald-100 text-emerald-700",
  pending: "bg-sky-100 text-sky-700",
  failed: "bg-amber-100 text-amber-700",
  dead: "bg-red-100 text-red-700",
};

/** P3-20 Event Bus (slice 3A-1): normalized domain event stream +
 * consumer subscriptions with signed deliveries. */
export function EventBusSection() {
  const { hasPermission } = useAuth();
  if (!hasPermission("webhooks.manage")) return null;
  return (
    <div className="mt-8 space-y-6">
      <SubscriptionsPanel />
      <EventStreamPanel />
    </div>
  );
}

function SubscriptionsPanel() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ name: "", url: "" });
  const [selectedTypes, setSelectedTypes] = useState<string[]>(["*"]);

  const catalogueQuery = useQuery({
    queryKey: ["event-catalogue"],
    queryFn: () => api.get<Record<string, string>>("/events/catalogue"),
  });
  const subscriptionsQuery = useQuery({
    queryKey: ["event-subscriptions"],
    queryFn: () => api.get<SubscriptionRow[]>("/subscriptions"),
  });
  const deliveriesQuery = useQuery({
    queryKey: ["event-deliveries", expanded],
    queryFn: () => api.get<DeliveryRow[]>(`/subscriptions/${expanded}/deliveries`),
    enabled: expanded != null,
  });

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["event-subscriptions"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const create = useMutation({
    mutationFn: () =>
      api.post<SubscriptionRow>("/subscriptions", {
        name: form.name,
        url: form.url,
        event_types: selectedTypes,
      }),
    onSuccess: (envelope) => {
      refresh();
      setError(null);
      setCreateOpen(false);
      setForm({ name: "", url: "" });
      setSelectedTypes(["*"]);
      setRevealed(envelope.data?.secret ?? null);
    },
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/subscriptions/${id}`),
    onSuccess: () => {
      refresh();
      setExpanded(null);
    },
    onError,
  });
  const replay = useMutation({
    mutationFn: (deliveryId: string) =>
      api.post(`/subscriptions/deliveries/${deliveryId}/replay`, {}),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["event-deliveries", expanded] }),
    onError,
  });

  const catalogue = catalogueQuery.data?.data ?? {};
  const subscriptions = subscriptionsQuery.data?.data ?? [];
  const deliveries = deliveriesQuery.data?.data ?? [];

  function toggleType(type: string) {
    setSelectedTypes((prev) => {
      if (type === "*") return ["*"];
      const without = prev.filter((t) => t !== "*" && t !== type);
      return prev.includes(type) ? (without.length ? without : ["*"]) : [...without, type];
    });
  }

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Event bus — consumers
          </h2>
          <p className="mt-0.5 text-xs text-slate-400">
            Normalized domain events pushed as signed HTTPS deliveries
            (HMAC-SHA256, retries, replayable dead-letter).
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen((v) => !v)}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
        >
          {createOpen ? "Close" : "Add consumer"}
        </button>
      </div>

      {revealed && (
        <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm">
          <p className="font-medium text-amber-800">
            Signing secret — shown only once, copy it now:
          </p>
          <code className="mt-1 block break-all font-mono text-xs text-slate-800">
            {revealed}
          </code>
        </div>
      )}

      {createOpen && (
        <form className="mt-3 space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3" onSubmit={onCreate}>
          <div className="flex flex-wrap gap-3">
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">Name</span>
              <input
                required
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                className="mt-0.5 w-52 rounded-md border border-slate-300 px-2 py-1.5"
              />
            </label>
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">Destination URL</span>
              <input
                required
                type="url"
                value={form.url}
                onChange={(e) => setForm((p) => ({ ...p, url: e.target.value }))}
                placeholder="https://…"
                className="mt-0.5 w-80 rounded-md border border-slate-300 px-2 py-1.5"
              />
            </label>
          </div>
          <div>
            <span className="block text-xs text-slate-500">Event types</span>
            <div className="mt-1 flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => toggleType("*")}
                className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                  selectedTypes.includes("*")
                    ? "bg-slate-900 text-white"
                    : "bg-white text-slate-600 ring-1 ring-slate-300"
                }`}
              >
                * all events
              </button>
              {Object.keys(catalogue).map((type) => (
                <button
                  key={type}
                  type="button"
                  title={catalogue[type]}
                  onClick={() => toggleType(type)}
                  className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                    selectedTypes.includes(type)
                      ? "bg-slate-900 text-white"
                      : "bg-white text-slate-600 ring-1 ring-slate-300"
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Create consumer
          </button>
        </form>
      )}

      <table className="mt-3 w-full text-left text-sm">
        <thead>
          <tr className="text-xs uppercase text-slate-400">
            <th className="py-1.5 pr-4">Name</th>
            <th className="py-1.5 pr-4">URL</th>
            <th className="py-1.5 pr-4">Events</th>
            <th className="py-1.5 pr-4">Status</th>
            <th className="py-1.5">Actions</th>
          </tr>
        </thead>
        <tbody>
          {subscriptions.length === 0 && (
            <tr>
              <td colSpan={5} className="py-3 text-sm text-slate-400">
                No consumers yet.
              </td>
            </tr>
          )}
          {subscriptions.map((s) => (
            <tr key={s.id} className="border-t border-slate-100 align-top">
              <td className="py-2 pr-4 font-medium text-slate-800">{s.name}</td>
              <td className="max-w-xs truncate py-2 pr-4 font-mono text-xs">{s.url}</td>
              <td className="py-2 pr-4 text-xs">{s.event_types.join(", ")}</td>
              <td className="py-2 pr-4">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    s.active ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {s.active ? "active" : "inactive"}
                </span>
              </td>
              <td className="py-2">
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                    className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                  >
                    {expanded === s.id ? "Hide log" : "Deliveries"}
                  </button>
                  <button
                    type="button"
                    onClick={() => remove.mutate(s.id)}
                    className="rounded-md border border-red-300 px-2 py-1 text-xs font-medium text-red-600"
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {expanded && (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
          <h3 className="text-xs font-semibold uppercase text-slate-400">Delivery log</h3>
          {deliveries.length === 0 ? (
            <p className="mt-1 text-sm text-slate-500">No deliveries yet.</p>
          ) : (
            <table className="mt-1 w-full text-left text-sm">
              <tbody>
                {deliveries.map((d) => (
                  <tr key={d.id} className="border-t border-slate-200">
                    <td className="py-1.5 pr-4 font-mono text-xs">{d.event_type}</td>
                    <td className="py-1.5 pr-4">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          STATE_STYLE[d.state] ?? "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {d.state}
                      </span>
                    </td>
                    <td className="py-1.5 pr-4 text-xs text-slate-500">
                      attempt {d.attempt_no}
                      {d.response_code != null && ` · HTTP ${d.response_code}`}
                      {d.last_error && ` · ${d.last_error}`}
                    </td>
                    <td className="py-1.5">
                      {d.state === "dead" && (
                        <button
                          type="button"
                          onClick={() => replay.mutate(d.id)}
                          className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                        >
                          Replay
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </section>
  );
}

function EventStreamPanel() {
  const [typeFilter, setTypeFilter] = useState("");
  const catalogueQuery = useQuery({
    queryKey: ["event-catalogue"],
    queryFn: () => api.get<Record<string, string>>("/events/catalogue"),
  });
  const eventsQuery = useQuery({
    queryKey: ["domain-events", typeFilter],
    queryFn: () =>
      api.get<EventRow[]>(
        `/events?page_size=25${typeFilter ? `&event_type=${typeFilter}` : ""}`,
      ),
  });
  const events = eventsQuery.data?.data ?? [];
  const catalogue = catalogueQuery.data?.data ?? {};

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Recent domain events
        </h2>
        <select
          aria-label="Filter by event type"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">All types</option>
          {Object.keys(catalogue).map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </div>
      <table className="mt-2 w-full text-left text-sm">
        <thead>
          <tr className="text-xs uppercase text-slate-400">
            <th className="py-1.5 pr-4">Event</th>
            <th className="py-1.5 pr-4">Entity</th>
            <th className="py-1.5 pr-4">Payload</th>
            <th className="py-1.5">When</th>
          </tr>
        </thead>
        <tbody>
          {events.length === 0 && (
            <tr>
              <td colSpan={4} className="py-3 text-sm text-slate-400">
                No events recorded yet.
              </td>
            </tr>
          )}
          {events.map((e) => (
            <tr key={e.id} className="border-t border-slate-100 align-top">
              <td className="py-1.5 pr-4 font-mono text-xs">{e.event_type}</td>
              <td className="py-1.5 pr-4 text-xs">{e.entity_type}</td>
              <td className="max-w-md truncate py-1.5 pr-4 font-mono text-xs text-slate-500">
                {e.payload ? JSON.stringify(e.payload) : "—"}
              </td>
              <td className="py-1.5 text-xs text-slate-500">
                {e.occurred_at ? new Date(e.occurred_at).toLocaleString() : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
