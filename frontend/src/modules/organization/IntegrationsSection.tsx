import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Modal } from "../../components/ui/Modal";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo } from "../devices/types";

interface Webhook {
  id: string;
  url: string;
  description: string | null;
  event_types_json: string[];
  active: boolean;
  secret?: string;
}

interface WebhookDeliveryRow {
  id: string;
  event_type: string;
  state: string;
  attempt_no: number;
  response_code: number | null;
  last_error: string | null;
  created_at: string;
}

interface ApiKeyRow {
  id: string;
  name: string;
  prefix: string;
  scopes_json: string[];
  expires_at: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
  key?: string;
}

interface EventType {
  event_type: string;
  label: string;
}

/** P2-19 Webhook Integrations + P2-20 API Key Management. */
export function IntegrationsSection() {
  const { hasPermission } = useAuth();
  const canWebhooks = hasPermission("webhooks.manage");
  const canKeys = hasPermission("api_keys.manage");
  if (!canWebhooks && !canKeys) return null;
  return (
    <div className="mt-8 space-y-8">
      {canWebhooks && <WebhooksPanel />}
      {canKeys && <ApiKeysPanel />}
    </div>
  );
}

function SecretReveal({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm">
      <p className="font-medium text-amber-800">{label} — shown only once, copy it now:</p>
      <code className="mt-1 block break-all font-mono text-xs text-slate-800">{value}</code>
    </div>
  );
}

function WebhooksPanel() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const webhooksQuery = useQuery({
    queryKey: ["webhooks"],
    queryFn: () => api.get<Webhook[]>("/webhooks"),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["webhooks"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const rotate = useMutation({
    mutationFn: (id: string) => api.post<Webhook>(`/webhooks/${id}/rotate-secret`),
    onSuccess: (envelope) => {
      setRevealed(envelope.data!.secret ?? null);
      refresh();
    },
    onError,
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.patch(`/webhooks/${id}`, { active }),
    onSuccess: refresh,
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/webhooks/${id}`),
    onSuccess: refresh,
    onError,
  });

  const webhooks = webhooksQuery.data?.data ?? [];

  return (
    <section>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Webhook integrations
        </h2>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
        >
          New webhook
        </button>
      </div>
      {error && (
        <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
      {revealed && <div className="mt-2"><SecretReveal label="Signing secret" value={revealed} /></div>}
      {webhooks.length === 0 ? (
        <p className="mt-2 rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
          No webhook subscriptions. Deliveries are signed with HMAC-SHA256 and
          retried with backoff into a replayable dead-letter state.
        </p>
      ) : (
        <ul className="mt-2 space-y-2">
          {webhooks.map((webhook) => (
            <li key={webhook.id} className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-3">
                <code className="font-mono text-xs text-slate-700">{webhook.url}</code>
                <span className="text-xs text-slate-500">
                  {webhook.event_types_json.join(", ")}
                </span>
                {!webhook.active && (
                  <span className="rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-500">
                    inactive
                  </span>
                )}
                <span className="ml-auto space-x-3 text-xs">
                  <button
                    type="button"
                    onClick={() => setExpanded((v) => (v === webhook.id ? null : webhook.id))}
                    className="font-medium text-slate-600 underline"
                  >
                    Deliveries
                  </button>
                  <button
                    type="button"
                    onClick={() => rotate.mutate(webhook.id)}
                    className="font-medium text-slate-600 underline"
                  >
                    Rotate secret
                  </button>
                  <button
                    type="button"
                    onClick={() => toggle.mutate({ id: webhook.id, active: !webhook.active })}
                    className="font-medium text-slate-600 underline"
                  >
                    {webhook.active ? "Disable" : "Enable"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm("Delete this webhook subscription?")) {
                        remove.mutate(webhook.id);
                      }
                    }}
                    className="font-medium text-red-600 underline"
                  >
                    Delete
                  </button>
                </span>
              </div>
              {expanded === webhook.id && <WebhookDeliveries webhookId={webhook.id} />}
            </li>
          ))}
        </ul>
      )}
      {createOpen && (
        <CreateWebhookModal
          onClose={() => setCreateOpen(false)}
          onCreated={(secret) => {
            setRevealed(secret);
            refresh();
            setCreateOpen(false);
          }}
        />
      )}
    </section>
  );
}

function WebhookDeliveries({ webhookId }: { webhookId: string }) {
  const queryClient = useQueryClient();
  const deliveriesQuery = useQuery({
    queryKey: ["webhook-deliveries", webhookId],
    queryFn: () =>
      api.get<WebhookDeliveryRow[]>(`/webhooks/${webhookId}/deliveries?page_size=20`),
  });
  const replay = useMutation({
    mutationFn: (id: string) => api.post(`/webhooks/deliveries/${id}/replay`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["webhook-deliveries", webhookId] }),
  });
  const rows = deliveriesQuery.data?.data ?? [];
  return rows.length === 0 ? (
    <p className="mt-2 border-t border-slate-100 pt-2 text-xs text-slate-400">
      No deliveries yet.
    </p>
  ) : (
    <ul className="mt-2 space-y-1 border-t border-slate-100 pt-2 text-xs text-slate-600">
      {rows.map((row) => (
        <li key={row.id} className="flex flex-wrap items-center gap-2">
          <StatusBadge status={row.state} />
          <span className="font-mono">{row.event_type}</span>
          <span className="text-slate-400">
            attempt {row.attempt_no}
            {row.response_code != null && ` · HTTP ${row.response_code}`} ·{" "}
            {timeAgo(row.created_at)}
          </span>
          {row.last_error && <span className="text-red-600">{row.last_error}</span>}
          {(row.state === "dead" || row.state === "failed") && (
            <button
              type="button"
              onClick={() => replay.mutate(row.id)}
              className="font-medium text-slate-600 underline"
            >
              Replay
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

function CreateWebhookModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (secret: string | null) => void;
}) {
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [events, setEvents] = useState<string[]>(["*"]);
  const [error, setError] = useState<string | null>(null);

  const eventsQuery = useQuery({
    queryKey: ["notification-events"],
    queryFn: () => api.get<EventType[]>("/notification-events"),
  });

  const create = useMutation({
    mutationFn: () =>
      api.post<Webhook>("/webhooks", {
        url,
        description: description || null,
        event_types_json: events,
      }),
    onSuccess: (envelope) => onCreated(envelope.data!.secret ?? null),
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create webhook"),
  });

  function toggleEvent(eventType: string) {
    setEvents((prev) =>
      prev.includes(eventType)
        ? prev.filter((e) => e !== eventType)
        : [...prev.filter((e) => e !== "*" || eventType === "*"), eventType],
    );
  }

  return (
    <Modal title="New webhook subscription" open onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label htmlFor="wh-url" className="block text-sm font-medium text-slate-700">
            Endpoint URL
          </label>
          <input
            id="wh-url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://hooks.company.com/signage"
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label htmlFor="wh-desc" className="block text-sm font-medium text-slate-700">
            Description
          </label>
          <input
            id="wh-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <span className="block text-sm font-medium text-slate-700">Events</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {(eventsQuery.data?.data ?? []).map((event) => (
              <button
                key={event.event_type}
                type="button"
                onClick={() => toggleEvent(event.event_type)}
                aria-pressed={events.includes(event.event_type)}
                className={`rounded-md px-2 py-1 text-xs font-medium ${
                  events.includes(event.event_type)
                    ? "bg-slate-900 text-white"
                    : "border border-slate-300 text-slate-600"
                }`}
              >
                {event.event_type}
              </button>
            ))}
          </div>
        </div>
        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={create.isPending || !url || events.length === 0}
            onClick={() => create.mutate()}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create webhook"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

const SCOPE_OPTIONS = [
  "devices.view",
  "devices.manage",
  "devices.control",
  "monitoring.view",
  "content.view",
  "campaigns.view",
  "deployments.view",
  "reports.view",
];

function ApiKeysPanel() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const keysQuery = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api.get<ApiKeyRow[]>("/api-keys"),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["api-keys"] });

  const revoke = useMutation({
    mutationFn: (id: string) => api.delete(`/api-keys/${id}`),
    onSuccess: refresh,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Revoke failed"),
  });

  const keys = keysQuery.data?.data ?? [];

  return (
    <section>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          API keys
        </h2>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
        >
          New API key
        </button>
      </div>
      {error && (
        <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
      {revealed && <div className="mt-2"><SecretReveal label="API key" value={revealed} /></div>}
      {keys.length === 0 ? (
        <p className="mt-2 rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
          No API keys. Keys are scoped, expirable, revocable — and shown only once.
        </p>
      ) : (
        <ul className="mt-2 space-y-2">
          {keys.map((key) => (
            <li
              key={key.id}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm"
            >
              <span className="font-medium text-slate-800">{key.name}</span>
              <code className="font-mono text-xs text-slate-500">{key.prefix}…</code>
              <span className="text-xs text-slate-500">{key.scopes_json.join(", ")}</span>
              {key.revoked_at ? (
                <span className="rounded bg-red-50 px-1.5 py-0.5 text-xs text-red-700">
                  revoked
                </span>
              ) : key.expires_at ? (
                <span className="text-xs text-slate-400">
                  expires {new Date(key.expires_at).toLocaleDateString()}
                </span>
              ) : null}
              <span className="text-xs text-slate-400">
                {key.last_used_at ? `used ${timeAgo(key.last_used_at)}` : "never used"}
              </span>
              {!key.revoked_at && (
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`Revoke API key "${key.name}"?`)) {
                      revoke.mutate(key.id);
                    }
                  }}
                  className="ml-auto text-xs font-medium text-red-600 underline"
                >
                  Revoke
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {createOpen && (
        <CreateApiKeyModal
          onClose={() => setCreateOpen(false)}
          onCreated={(raw) => {
            setRevealed(raw);
            refresh();
            setCreateOpen(false);
          }}
        />
      )}
    </section>
  );
}

function CreateApiKeyModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (raw: string | null) => void;
}) {
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["devices.view"]);
  const [expiresDays, setExpiresDays] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api.post<ApiKeyRow>("/api-keys", {
        name,
        scopes,
        expires_at: expiresDays
          ? new Date(Date.now() + Number(expiresDays) * 86400_000).toISOString()
          : null,
      }),
    onSuccess: (envelope) => onCreated(envelope.data!.key ?? null),
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create key"),
  });

  function toggleScope(scope: string) {
    setScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope],
    );
  }

  return (
    <Modal title="New API key" open onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label htmlFor="key-name" className="block text-sm font-medium text-slate-700">
            Name
          </label>
          <input
            id="key-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Reporting bot"
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <span className="block text-sm font-medium text-slate-700">Scopes</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {SCOPE_OPTIONS.map((scope) => (
              <button
                key={scope}
                type="button"
                onClick={() => toggleScope(scope)}
                aria-pressed={scopes.includes(scope)}
                className={`rounded-md px-2 py-1 text-xs font-medium ${
                  scopes.includes(scope)
                    ? "bg-slate-900 text-white"
                    : "border border-slate-300 text-slate-600"
                }`}
              >
                {scope}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label htmlFor="key-expiry" className="block text-sm font-medium text-slate-700">
            Expires after (days, empty = never)
          </label>
          <input
            id="key-expiry"
            type="number"
            min={1}
            value={expiresDays}
            onChange={(e) => setExpiresDays(e.target.value)}
            className="mt-1 w-40 rounded-md border border-slate-300 px-3 py-2 text-sm"
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
            onClick={onClose}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={create.isPending || !name || scopes.length === 0}
            onClick={() => create.mutate()}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create key"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
