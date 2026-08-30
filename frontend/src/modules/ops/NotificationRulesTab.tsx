import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo } from "../devices/types";

interface RuleChannel {
  channel: "in_app" | "email" | "webhook";
  recipient?: string | null;
}

interface Rule {
  id: string;
  name: string;
  event_type: string;
  condition_json: { severity?: string[] } | null;
  channels_json: RuleChannel[];
  escalation_minutes: number | null;
  active: boolean;
}

interface Delivery {
  id: string;
  channel: string;
  recipient: string;
  state: string;
  attempts: number;
  last_error: string | null;
  created_at: string;
  notification_title: string;
  notification_type: string;
}

interface EventType {
  event_type: string;
  label: string;
}

/** P2-18 Notification Rules: event → condition → channels → escalation. */
export function NotificationRulesTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("settings.manage");
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [expandedRule, setExpandedRule] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rulesQuery = useQuery({
    queryKey: ["notification-rules"],
    queryFn: () => api.get<Rule[]>("/notification-rules"),
  });
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["notification-rules"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.patch(`/notification-rules/${id}`, { active }),
    onSuccess: refresh,
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/notification-rules/${id}`),
    onSuccess: refresh,
    onError,
  });

  const rules = rulesQuery.data?.data ?? [];

  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          Route operational events to in-app, email and webhook channels, with
          escalation for unacknowledged alerts.
        </p>
        {canManage && (
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
          >
            New rule
          </button>
        )}
      </div>

      {error && (
        <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}

      {rulesQuery.isLoading ? (
        <Spinner label="Loading rules…" />
      ) : rules.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No alert rules yet. Events still land in the in-app inbox; rules add
          email/webhook delivery and escalation.
        </p>
      ) : (
        <ul className="mt-4 space-y-2">
          {rules.map((rule) => (
            <li key={rule.id} className="rounded-lg border border-slate-200 bg-white px-4 py-3">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <span className="font-medium text-slate-800">{rule.name}</span>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
                  {rule.event_type}
                </span>
                {rule.condition_json?.severity && (
                  <span className="text-xs text-slate-500">
                    severity: {rule.condition_json.severity.join(", ")}
                  </span>
                )}
                <span className="text-xs text-slate-500">
                  →{" "}
                  {rule.channels_json
                    .map((c) => (c.recipient ? `${c.channel}: ${c.recipient}` : c.channel))
                    .join(" · ")}
                </span>
                {rule.escalation_minutes && (
                  <span className="rounded bg-red-50 px-1.5 py-0.5 text-xs text-red-700">
                    escalate after {rule.escalation_minutes}m
                  </span>
                )}
                {!rule.active && (
                  <span className="rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-500">
                    inactive
                  </span>
                )}
                <span className="ml-auto space-x-3 text-xs">
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedRule((v) => (v === rule.id ? null : rule.id))
                    }
                    className="font-medium text-slate-600 underline"
                  >
                    Deliveries
                  </button>
                  {canManage && (
                    <>
                      <button
                        type="button"
                        onClick={() => toggle.mutate({ id: rule.id, active: !rule.active })}
                        className="font-medium text-slate-600 underline"
                      >
                        {rule.active ? "Disable" : "Enable"}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (window.confirm(`Delete rule "${rule.name}"?`)) {
                            remove.mutate(rule.id);
                          }
                        }}
                        className="font-medium text-red-600 underline"
                      >
                        Delete
                      </button>
                    </>
                  )}
                </span>
              </div>
              {expandedRule === rule.id && <DeliveryList ruleId={rule.id} />}
            </li>
          ))}
        </ul>
      )}

      {createOpen && (
        <CreateRuleModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            refresh();
            setCreateOpen(false);
          }}
        />
      )}
    </div>
  );
}

function DeliveryList({ ruleId }: { ruleId: string }) {
  const deliveriesQuery = useQuery({
    queryKey: ["notification-deliveries", ruleId],
    queryFn: () =>
      api.get<Delivery[]>(`/notification-deliveries?rule_id=${ruleId}&page_size=20`),
  });
  const rows = deliveriesQuery.data?.data ?? [];
  if (deliveriesQuery.isLoading) return <Spinner label="Loading deliveries…" />;
  return rows.length === 0 ? (
    <p className="mt-2 border-t border-slate-100 pt-2 text-xs text-slate-400">
      No deliveries yet for this rule.
    </p>
  ) : (
    <ul className="mt-2 space-y-1 border-t border-slate-100 pt-2 text-xs text-slate-600">
      {rows.map((row) => (
        <li key={row.id} className="flex flex-wrap items-center gap-2">
          <StatusBadge status={row.state} />
          <span className="font-mono">{row.channel}</span>
          <span>→ {row.recipient}</span>
          <span className="text-slate-400">
            {row.notification_type} · “{row.notification_title}” ·{" "}
            {timeAgo(row.created_at)}
            {row.attempts > 1 && ` · ${row.attempts} attempts`}
          </span>
          {row.last_error && <span className="text-red-600">{row.last_error}</span>}
        </li>
      ))}
    </ul>
  );
}

function CreateRuleModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [eventType, setEventType] = useState("*");
  const [severities, setSeverities] = useState<string[]>([]);
  const [inApp, setInApp] = useState(true);
  const [email, setEmail] = useState("");
  const [webhook, setWebhook] = useState("");
  const [escalation, setEscalation] = useState("");
  const [error, setError] = useState<string | null>(null);

  const eventsQuery = useQuery({
    queryKey: ["notification-events"],
    queryFn: () => api.get<EventType[]>("/notification-events"),
  });

  const create = useMutation({
    mutationFn: () => {
      const channels: RuleChannel[] = [];
      if (inApp) channels.push({ channel: "in_app" });
      if (email.trim()) channels.push({ channel: "email", recipient: email.trim() });
      if (webhook.trim()) channels.push({ channel: "webhook", recipient: webhook.trim() });
      return api.post("/notification-rules", {
        name,
        event_type: eventType,
        condition_json: severities.length ? { severity: severities } : null,
        channels_json: channels,
        escalation_minutes: escalation ? Number(escalation) : null,
      });
    },
    onSuccess: onCreated,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create rule"),
  });

  function toggleSeverity(value: string) {
    setSeverities((prev) =>
      prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value],
    );
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <Modal title="New notification rule" open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="rule-name" className="block text-sm font-medium text-slate-700">
              Name
            </label>
            <input
              id="rule-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="rule-event" className="block text-sm font-medium text-slate-700">
              Event
            </label>
            <select
              id="rule-event"
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {(eventsQuery.data?.data ?? []).map((event) => (
                <option key={event.event_type} value={event.event_type}>
                  {event.label} ({event.event_type})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <span className="block text-sm font-medium text-slate-700">
            Only for severities (empty = any)
          </span>
          <div className="mt-1 flex gap-2">
            {["info", "warning", "critical"].map((severity) => (
              <button
                key={severity}
                type="button"
                onClick={() => toggleSeverity(severity)}
                aria-pressed={severities.includes(severity)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                  severities.includes(severity)
                    ? "bg-slate-900 text-white"
                    : "border border-slate-300 text-slate-600"
                }`}
              >
                {severity}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <span className="block text-sm font-medium text-slate-700">Channels</span>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={inApp}
              onChange={(e) => setInApp(e.target.checked)}
            />
            In-app inbox
          </label>
          <div className="flex items-center gap-2 text-sm">
            <span className="w-16 text-slate-600">Email</span>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="noc@company.com (empty = off)"
              aria-label="Email recipient"
              className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="w-16 text-slate-600">Webhook</span>
            <input
              value={webhook}
              onChange={(e) => setWebhook(e.target.value)}
              placeholder="https://hooks.company.com/… (empty = off)"
              aria-label="Webhook URL"
              className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
        </div>

        <div>
          <label htmlFor="rule-escalation" className="block text-sm font-medium text-slate-700">
            Escalate after (minutes, empty = never)
          </label>
          <input
            id="rule-escalation"
            type="number"
            min={1}
            max={1440}
            value={escalation}
            onChange={(e) => setEscalation(e.target.value)}
            className="mt-1 w-40 rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <p className="mt-1 text-xs text-slate-400">
            Unread matching alerts re-fire as critical ESCALATION notifications.
          </p>
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
            type="submit"
            disabled={create.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create rule"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
