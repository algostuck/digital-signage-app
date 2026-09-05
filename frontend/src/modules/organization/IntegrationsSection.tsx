import { PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Flex,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Tag,
  Typography,
} from "antd";
import { ToneTag } from "@/design-system";
import { EntityList } from "@/design-system";
import { useState } from "react";
import { EmptyState } from "@/design-system";
import { StatusBadge } from "@/design-system";
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
    <Space orientation="vertical" size="medium" className="w-full">
      {canWebhooks && <WebhooksPanel />}
      {canKeys && <ApiKeysPanel />}
    </Space>
  );
}

function SecretReveal({ label, value }: { label: string; value: string }) {
  return (
    <Alert
      type="warning"
      showIcon
      message={`${label} — shown only once, copy it now:`}
      description={
        <Typography.Text code copyable className="break-all">
          {value}
        </Typography.Text>
      }
    />
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
    <Card
      size="small"
      title="Webhook integrations"
      loading={webhooksQuery.isLoading}
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          New webhook
        </Button>
      }
    >
      <Space orientation="vertical" size="small" className="w-full">
        {error && <Alert type="error" message={error} showIcon role="alert" />}
        {revealed && <SecretReveal label="Signing secret" value={revealed} />}
        {webhooks.length === 0 ? (
          <EmptyState
            title="No webhook subscriptions"
            description="Deliveries are signed with HMAC-SHA256 and retried with backoff into a replayable dead-letter state."
          />
        ) : (
          <EntityList
            dense
            items={webhooks}
            rowKey="id"
            aria-label="Webhook subscriptions"
            renderItem={(webhook) => (
              <div>
                <Flex wrap align="center" gap="small">
                  <Typography.Text code>{webhook.url}</Typography.Text>
                  <Typography.Text type="secondary" className="text-xs">
                    {webhook.event_types_json.join(", ")}
                  </Typography.Text>
                  {!webhook.active && <ToneTag tone="default">inactive</ToneTag>}
                  <Space size="small" className="ms-auto">
                    <Button
                      size="small"
                      type="link"
                      onClick={() => setExpanded((v) => (v === webhook.id ? null : webhook.id))}
                    >
                      Deliveries
                    </Button>
                    <Button size="small" type="link" onClick={() => rotate.mutate(webhook.id)}>
                      Rotate secret
                    </Button>
                    <Button
                      size="small"
                      type="link"
                      onClick={() => toggle.mutate({ id: webhook.id, active: !webhook.active })}
                    >
                      {webhook.active ? "Disable" : "Enable"}
                    </Button>
                    <Popconfirm
                      title="Delete this webhook subscription?"
                      okText="Delete"
                      okButtonProps={{ danger: true }}
                      onConfirm={() => remove.mutate(webhook.id)}
                    >
                      <Button size="small" type="link" danger>
                        Delete
                      </Button>
                    </Popconfirm>
                  </Space>
                </Flex>
                {expanded === webhook.id && <WebhookDeliveries webhookId={webhook.id} />}
              </div>
            )}
          />
        )}
      </Space>
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
    </Card>
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
    <Typography.Paragraph type="secondary" className="!mb-0 mt-2 text-xs">
      No deliveries yet.
    </Typography.Paragraph>
  ) : (
    <EntityList
      dense
      style={{ marginTop: 8 }}
      items={rows}
      rowKey="id"
      renderItem={(row) => (
          <Flex wrap align="center" gap="small">
            <StatusBadge status={row.state} />
            <Typography.Text code className="text-xs">
              {row.event_type}
            </Typography.Text>
            <Typography.Text type="secondary" className="text-xs">
              attempt {row.attempt_no}
              {row.response_code != null && ` · HTTP ${row.response_code}`} ·{" "}
              {timeAgo(row.created_at)}
            </Typography.Text>
            {row.last_error && (
              <Typography.Text type="danger" className="text-xs">
                {row.last_error}
              </Typography.Text>
            )}
            {(row.state === "dead" || row.state === "failed") && (
              <Button size="small" type="link" onClick={() => replay.mutate(row.id)}>
                Replay
              </Button>
            )}
          </Flex>
      )}
    />
  );
}

function CreateWebhookModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (secret: string | null) => void;
}) {
  const [form] = Form.useForm<{ url: string; description?: string }>();
  const [events, setEvents] = useState<string[]>(["*"]);
  const [error, setError] = useState<string | null>(null);

  const eventsQuery = useQuery({
    queryKey: ["notification-events"],
    queryFn: () => api.get<EventType[]>("/notification-events"),
  });

  const create = useMutation({
    mutationFn: (values: { url: string; description?: string }) =>
      api.post<Webhook>("/webhooks", {
        url: values.url,
        description: values.description || null,
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
    <Modal
      title="New webhook subscription"
      open
      onCancel={onClose}
      okText="Create webhook"
      onOk={() => form.submit()}
      confirmLoading={create.isPending}
      okButtonProps={{ disabled: events.length === 0 }}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) => create.mutate(values)}
      >
        <Form.Item
          name="url"
          label="Endpoint URL"
          rules={[{ required: true, message: "Endpoint URL is required" }]}
        >
          <Input placeholder="https://hooks.company.com/signage" />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input />
        </Form.Item>
        <Form.Item label="Events">
          <Flex wrap gap={4}>
            {(eventsQuery.data?.data ?? []).map((event) => (
              <Tag.CheckableTag
                key={event.event_type}
                checked={events.includes(event.event_type)}
                onChange={() => toggleEvent(event.event_type)}
              >
                {event.event_type}
              </Tag.CheckableTag>
            ))}
          </Flex>
        </Form.Item>
        {error && <Alert type="error" message={error} showIcon role="alert" />}
      </Form>
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
    <Card
      size="small"
      title="API keys"
      loading={keysQuery.isLoading}
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          New API key
        </Button>
      }
    >
      <Space orientation="vertical" size="small" className="w-full">
        {error && <Alert type="error" message={error} showIcon role="alert" />}
        {revealed && <SecretReveal label="API key" value={revealed} />}
        {keys.length === 0 ? (
          <EmptyState
            title="No API keys"
            description="Keys are scoped, expirable, revocable — and shown only once."
          />
        ) : (
          <EntityList
            dense
            items={keys}
            rowKey="id"
            aria-label="API keys"
            renderItem={(key) => (
                <Flex wrap align="center" gap="small" className="w-full">
                  <Typography.Text strong>{key.name}</Typography.Text>
                  <Typography.Text code className="text-xs">
                    {key.prefix}…
                  </Typography.Text>
                  <Typography.Text type="secondary" className="text-xs">
                    {key.scopes_json.join(", ")}
                  </Typography.Text>
                  {key.revoked_at ? (
                    <ToneTag tone="error">
                      revoked
                    </ToneTag>
                  ) : key.expires_at ? (
                    <Typography.Text type="secondary" className="text-xs">
                      expires {new Date(key.expires_at).toLocaleDateString()}
                    </Typography.Text>
                  ) : null}
                  <Typography.Text type="secondary" className="text-xs">
                    {key.last_used_at ? `used ${timeAgo(key.last_used_at)}` : "never used"}
                  </Typography.Text>
                  {!key.revoked_at && (
                    <Popconfirm
                      title={`Revoke API key "${key.name}"?`}
                      okText="Revoke"
                      okButtonProps={{ danger: true }}
                      onConfirm={() => revoke.mutate(key.id)}
                    >
                      <Button size="small" type="link" danger className="ms-auto">
                        Revoke
                      </Button>
                    </Popconfirm>
                  )}
                </Flex>
            )}
          />
        )}
      </Space>
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
    </Card>
  );
}

function CreateApiKeyModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (raw: string | null) => void;
}) {
  const [form] = Form.useForm<{ name: string; expires_days?: number | null }>();
  const [scopes, setScopes] = useState<string[]>(["devices.view"]);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (values: { name: string; expires_days?: number | null }) =>
      api.post<ApiKeyRow>("/api-keys", {
        name: values.name,
        scopes,
        expires_at: values.expires_days
          ? new Date(Date.now() + Number(values.expires_days) * 86400_000).toISOString()
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
    <Modal
      title="New API key"
      open
      onCancel={onClose}
      okText="Create key"
      onOk={() => form.submit()}
      confirmLoading={create.isPending}
      okButtonProps={{ disabled: scopes.length === 0 }}
    >
      <Form form={form} layout="vertical" onFinish={(values) => create.mutate(values)}>
        <Form.Item
          name="name"
          label="Name"
          rules={[{ required: true, message: "Name is required" }]}
        >
          <Input placeholder="Reporting bot" />
        </Form.Item>
        <Form.Item label="Scopes">
          <Flex wrap gap={4}>
            {SCOPE_OPTIONS.map((scope) => (
              <Tag.CheckableTag
                key={scope}
                checked={scopes.includes(scope)}
                onChange={() => toggleScope(scope)}
              >
                {scope}
              </Tag.CheckableTag>
            ))}
          </Flex>
        </Form.Item>
        <Form.Item name="expires_days" label="Expires after (days, empty = never)">
          <InputNumber min={1} className="w-44" />
        </Form.Item>
        {error && <Alert type="error" message={error} showIcon role="alert" />}
      </Form>
    </Modal>
  );
}
