import { PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Flex,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Popconfirm,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import { useState } from "react";
import { EmptyState, LoadingState } from "../../components/ui/states";
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
      <Flex wrap align="center" justify="space-between" gap="small">
        <Typography.Text type="secondary">
          Route operational events to in-app, email and webhook channels, with
          escalation for unacknowledged alerts.
        </Typography.Text>
        {canManage && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            New rule
          </Button>
        )}
      </Flex>

      {error && <Alert type="error" message={error} showIcon className="mt-3" role="alert" />}

      {rulesQuery.isLoading ? (
        <LoadingState rows={4} />
      ) : rules.length === 0 ? (
        <Card className="mt-4">
          <EmptyState
            title="No alert rules yet"
            description="Events still land in the in-app inbox; rules add email/webhook delivery and escalation."
          />
        </Card>
      ) : (
        <Space orientation="vertical" size="small" className="mt-4 w-full">
          {rules.map((rule) => (
            <Card key={rule.id} size="small">
              <Flex wrap align="center" gap="small">
                <Typography.Text strong>{rule.name}</Typography.Text>
                <Tag variant="filled" className="font-mono text-xs">
                  {rule.event_type}
                </Tag>
                {rule.condition_json?.severity && (
                  <Typography.Text type="secondary" className="text-xs">
                    severity: {rule.condition_json.severity.join(", ")}
                  </Typography.Text>
                )}
                <Typography.Text type="secondary" className="text-xs">
                  →{" "}
                  {rule.channels_json
                    .map((c) => (c.recipient ? `${c.channel}: ${c.recipient}` : c.channel))
                    .join(" · ")}
                </Typography.Text>
                {rule.escalation_minutes && (
                  <Tag color="error" variant="filled">
                    escalate after {rule.escalation_minutes}m
                  </Tag>
                )}
                {!rule.active && <Tag variant="filled">inactive</Tag>}
                <Space className="ms-auto">
                  <Button
                    type="link"
                    size="small"
                    onClick={() => setExpandedRule((v) => (v === rule.id ? null : rule.id))}
                  >
                    Deliveries
                  </Button>
                  {canManage && (
                    <>
                      <Button
                        type="link"
                        size="small"
                        onClick={() => toggle.mutate({ id: rule.id, active: !rule.active })}
                      >
                        {rule.active ? "Disable" : "Enable"}
                      </Button>
                      <Popconfirm
                        title={`Delete rule "${rule.name}"?`}
                        okButtonProps={{ danger: true }}
                        onConfirm={() => remove.mutate(rule.id)}
                      >
                        <Button type="link" size="small" danger>
                          Delete
                        </Button>
                      </Popconfirm>
                    </>
                  )}
                </Space>
              </Flex>
              {expandedRule === rule.id && <DeliveryList ruleId={rule.id} />}
            </Card>
          ))}
        </Space>
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
  if (deliveriesQuery.isLoading) return <LoadingState rows={2} />;
  return (
    <List
      size="small"
      className="mt-2"
      dataSource={rows}
      locale={{
        emptyText: (
          <Typography.Text type="secondary" className="text-xs">
            No deliveries yet for this rule.
          </Typography.Text>
        ),
      }}
      renderItem={(row) => (
        <List.Item className="!px-0">
          <Flex wrap align="center" gap="small">
            <StatusBadge status={row.state} />
            <Typography.Text code className="text-xs">
              {row.channel}
            </Typography.Text>
            <Typography.Text className="text-xs">→ {row.recipient}</Typography.Text>
            <Typography.Text type="secondary" className="text-xs">
              {row.notification_type} · “{row.notification_title}” · {timeAgo(row.created_at)}
              {row.attempts > 1 && ` · ${row.attempts} attempts`}
            </Typography.Text>
            {row.last_error && (
              <Typography.Text type="danger" className="text-xs">
                {row.last_error}
              </Typography.Text>
            )}
          </Flex>
        </List.Item>
      )}
    />
  );
}

interface RuleFormValues {
  name: string;
  event_type: string;
  in_app: boolean;
  email?: string;
  webhook?: string;
  escalation?: number | null;
}

function CreateRuleModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form] = Form.useForm<RuleFormValues>();
  const [severities, setSeverities] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const eventsQuery = useQuery({
    queryKey: ["notification-events"],
    queryFn: () => api.get<EventType[]>("/notification-events"),
  });

  const create = useMutation({
    mutationFn: (values: RuleFormValues) => {
      const channels: RuleChannel[] = [];
      if (values.in_app) channels.push({ channel: "in_app" });
      if (values.email?.trim())
        channels.push({ channel: "email", recipient: values.email.trim() });
      if (values.webhook?.trim())
        channels.push({ channel: "webhook", recipient: values.webhook.trim() });
      return api.post("/notification-rules", {
        name: values.name,
        event_type: values.event_type,
        condition_json: severities.length ? { severity: severities } : null,
        channels_json: channels,
        escalation_minutes: values.escalation ? Number(values.escalation) : null,
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

  return (
    <Modal
      title="New notification rule"
      open
      onCancel={onClose}
      okText="Create rule"
      confirmLoading={create.isPending}
      onOk={() => form.submit()}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ name: "", event_type: "*", in_app: true, email: "", webhook: "" }}
        onFinish={(values) => {
          setError(null);
          create.mutate(values);
        }}
      >
        <Flex gap="small">
          <Form.Item
            name="name"
            label="Name"
            className="flex-1"
            rules={[{ required: true, message: "Name is required" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="event_type" label="Event" className="flex-1">
            <Select
              options={(eventsQuery.data?.data ?? []).map((event) => ({
                value: event.event_type,
                label: `${event.label} (${event.event_type})`,
              }))}
              loading={eventsQuery.isLoading}
            />
          </Form.Item>
        </Flex>

        <Form.Item label="Only for severities (empty = any)">
          <Space>
            {["info", "warning", "critical"].map((severity) => (
              <Tag.CheckableTag
                key={severity}
                checked={severities.includes(severity)}
                onChange={() => toggleSeverity(severity)}
                aria-pressed={severities.includes(severity)}
              >
                {severity}
              </Tag.CheckableTag>
            ))}
          </Space>
        </Form.Item>

        <Form.Item label="Channels" className="mb-0">
          <Form.Item name="in_app" valuePropName="checked" className="mb-2">
            <Checkbox>In-app inbox</Checkbox>
          </Form.Item>
          <Form.Item name="email" label="Email" className="mb-2">
            <Input placeholder="noc@company.com (empty = off)" aria-label="Email recipient" />
          </Form.Item>
          <Form.Item name="webhook" label="Webhook">
            <Input
              placeholder="https://hooks.company.com/… (empty = off)"
              aria-label="Webhook URL"
            />
          </Form.Item>
        </Form.Item>

        <Form.Item
          name="escalation"
          label="Escalate after (minutes, empty = never)"
          extra="Unread matching alerts re-fire as critical ESCALATION notifications."
        >
          <InputNumber min={1} max={1440} className="w-40" />
        </Form.Item>

        {error && (
          <Alert type="error" message={error} showIcon className="mb-2" role="alert" />
        )}
      </Form>
    </Modal>
  );
}
