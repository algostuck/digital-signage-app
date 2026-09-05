import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Flex, Form, Input, Row, Select, Space, Tag, Tooltip, Typography, type TableProps } from "antd";
import { useState } from "react";

import { DataTable } from "@/design-system";
import { SectionCard } from "@/design-system";
import { StatusBadge } from "@/design-system";
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

/** P3-20 Event Bus (slice 3A-1): normalized domain event stream +
 * consumer subscriptions with signed deliveries. */
export function EventBusSection() {
  const { hasPermission } = useAuth();
  if (!hasPermission("webhooks.manage")) return null;
  return (
    <Space orientation="vertical" size="medium" className="w-full">
      <SubscriptionsPanel />
      <EventStreamPanel />
    </Space>
  );
}

function SubscriptionsPanel() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm<{ name: string; url: string }>();
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
    mutationFn: (values: { name: string; url: string }) =>
      api.post<SubscriptionRow>("/subscriptions", {
        name: values.name,
        url: values.url,
        event_types: selectedTypes,
      }),
    onSuccess: (envelope) => {
      refresh();
      setError(null);
      setCreateOpen(false);
      form.resetFields();
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

  const subscriptionColumns: TableProps<SubscriptionRow>["columns"] = [
    {
      title: "Name",
      dataIndex: "name",
      render: (value: string) => <Typography.Text strong>{value}</Typography.Text>,
    },
    {
      title: "URL",
      dataIndex: "url",
      ellipsis: true,
      render: (value: string) => (
        <Typography.Text code className="text-xs">
          {value}
        </Typography.Text>
      ),
    },
    {
      title: "Events",
      dataIndex: "event_types",
      render: (types: string[]) => types.join(", "),
    },
    {
      title: "Status",
      dataIndex: "active",
      render: (active: boolean) => <StatusBadge status={active ? "active" : "inactive"} />,
    },
    {
      title: "Actions",
      key: "actions",
      render: (_, s) => (
        <Space size="small">
          <Button size="small" onClick={() => setExpanded(expanded === s.id ? null : s.id)}>
            {expanded === s.id ? "Hide log" : "Deliveries"}
          </Button>
          <Button size="small" danger onClick={() => remove.mutate(s.id)}>
            Delete
          </Button>
        </Space>
      ),
    },
  ];

  const deliveryColumns: TableProps<DeliveryRow>["columns"] = [
    {
      title: "Event",
      dataIndex: "event_type",
      render: (value: string) => (
        <Typography.Text code className="text-xs">
          {value}
        </Typography.Text>
      ),
    },
    {
      title: "State",
      dataIndex: "state",
      render: (state: string) => <StatusBadge status={state} />,
    },
    {
      title: "Details",
      key: "details",
      render: (_, d) => (
        <Typography.Text type="secondary" className="text-xs">
          attempt {d.attempt_no}
          {d.response_code != null && ` · HTTP ${d.response_code}`}
          {d.last_error && ` · ${d.last_error}`}
        </Typography.Text>
      ),
    },
    {
      title: "",
      key: "actions",
      render: (_, d) =>
        d.state === "dead" && (
          <Button size="small" onClick={() => replay.mutate(d.id)}>
            Replay
          </Button>
        ),
    },
  ];

  return (
    <SectionCard
      title="Event bus — consumers"
      actions={
        <Button type="primary" onClick={() => setCreateOpen((v) => !v)}>
          {createOpen ? "Close" : "Add consumer"}
        </Button>
      }
    >
      <Space orientation="vertical" size="medium" className="w-full">
        <Typography.Text type="secondary">
          Normalized domain events pushed as signed HTTPS deliveries
          (HMAC-SHA256, retries, replayable dead-letter).
        </Typography.Text>

        {revealed && (
          <Alert
            type="warning"
            showIcon
            message="Signing secret — shown only once, copy it now:"
            description={
              <Typography.Text code copyable className="break-all">
                {revealed}
              </Typography.Text>
            }
          />
        )}

        {createOpen && (
          <Card size="small" type="inner">
            <Form
              form={form}
              layout="vertical"
              onFinish={(values) => {
                setError(null);
                create.mutate(values);
              }}
            >
              <Row gutter={12}>
                <Col xs={24} sm={8}>
                  <Form.Item
                    name="name"
                    label="Name"
                    rules={[{ required: true, message: "Name is required" }]}
                  >
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={16}>
                  <Form.Item
                    name="url"
                    label="Destination URL"
                    rules={[
                      { required: true, message: "Destination URL is required" },
                      { type: "url", message: "Must be a valid URL" },
                    ]}
                  >
                    <Input placeholder="https://…" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="Event types">
                <Flex wrap gap={4}>
                  <Tag.CheckableTag
                    checked={selectedTypes.includes("*")}
                    onChange={() => toggleType("*")}
                  >
                    * all events
                  </Tag.CheckableTag>
                  {Object.keys(catalogue).map((type) => (
                    <Tooltip key={type} title={catalogue[type]}>
                      <Tag.CheckableTag
                        checked={selectedTypes.includes(type)}
                        onChange={() => toggleType(type)}
                      >
                        {type}
                      </Tag.CheckableTag>
                    </Tooltip>
                  ))}
                </Flex>
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={create.isPending}>
                Create consumer
              </Button>
            </Form>
          </Card>
        )}

        <DataTable<SubscriptionRow>
          rowKey="id"
          columns={subscriptionColumns}
          dataSource={subscriptions}
          pagination={false}
          loading={subscriptionsQuery.isLoading}
          emptyTitle="No consumers yet"
        />

        {expanded && (
          <Card size="small" type="inner" title="Delivery log">
            <DataTable<DeliveryRow>
              rowKey="id"
              columns={deliveryColumns}
              dataSource={deliveries}
              pagination={false}
              loading={deliveriesQuery.isLoading}
              emptyTitle="No deliveries yet"
            />
          </Card>
        )}

        {error && <Alert type="error" message={error} showIcon role="alert" />}
      </Space>
    </SectionCard>
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

  const columns: TableProps<EventRow>["columns"] = [
    {
      title: "Event",
      dataIndex: "event_type",
      render: (value: string) => (
        <Typography.Text code className="text-xs">
          {value}
        </Typography.Text>
      ),
    },
    { title: "Entity", dataIndex: "entity_type" },
    {
      title: "Payload",
      dataIndex: "payload",
      ellipsis: true,
      render: (payload: EventRow["payload"]) => (
        <Typography.Text type="secondary" className="font-mono text-xs">
          {payload ? JSON.stringify(payload) : "—"}
        </Typography.Text>
      ),
    },
    {
      title: "When",
      dataIndex: "occurred_at",
      render: (value: string | null) => (value ? new Date(value).toLocaleString() : "—"),
    },
  ];

  return (
    <SectionCard
      title="Recent domain events"
      actions={
        <Select
          aria-label="Filter by event type"
          value={typeFilter}
          onChange={setTypeFilter}
          className="w-44"
          options={[
            { value: "", label: "All types" },
            ...Object.keys(catalogue).map((type) => ({ value: type, label: type })),
          ]}
        />
      }
    >
      <DataTable<EventRow>
        rowKey="id"
        columns={columns}
        dataSource={events}
        pagination={false}
        loading={eventsQuery.isLoading}
        emptyTitle="No events recorded yet"
      />
    </SectionCard>
  );
}
