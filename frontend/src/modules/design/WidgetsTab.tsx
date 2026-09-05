import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Flex,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { useState } from "react";
import { EmptyState, LoadingState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Widget, WidgetSchemaField } from "./types";

const FIELD_TYPES = ["string", "number", "boolean", "select", "url", "color"] as const;

/** P2-08 Widget Library: schema-driven catalogue with versions + fallback. */
export function WidgetsTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("widgets.manage");
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const widgetsQuery = useQuery({
    queryKey: ["widgets"],
    queryFn: () => api.get<Widget[]>("/widgets"),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["widgets"] });

  const archive = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/widgets/${id}`, { status }),
    onSuccess: refresh,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Action failed"),
  });

  const widgets = widgetsQuery.data?.data ?? [];

  return (
    <div>
      <Flex justify="space-between" align="center" gap="middle" wrap>
        <Typography.Text type="secondary">
          Schema-driven widgets with fallback content. Zones bind them via the
          designer's widget panel.
        </Typography.Text>
        {canManage && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            New widget
          </Button>
        )}
      </Flex>

      {error && <Alert type="error" message={error} showIcon role="alert" className="mt-3" />}

      {widgetsQuery.isLoading ? (
        <LoadingState rows={5} />
      ) : widgets.length === 0 ? (
        <Card className="mt-4">
          <EmptyState
            title="No widgets yet"
            description="Create one to make it configurable inside layout zones."
          />
        </Card>
      ) : (
        <Row gutter={[12, 12]} className="mt-4">
          {widgets.map((widget) => {
            const current = widget.versions[widget.versions.length - 1];
            return (
              <Col key={widget.id} xs={24} sm={12} lg={8}>
                <Card size="small">
                  <Flex justify="space-between" align="flex-start" gap="small">
                    <Typography.Text strong ellipsis>
                      {widget.name}
                    </Typography.Text>
                    <StatusBadge status={widget.status} />
                  </Flex>
                  <Typography.Paragraph type="secondary" className="!mb-0 !mt-1">
                    {widget.type} · schema v{current?.version_no ?? "?"}
                    {widget.fallback_json ? " · fallback set" : ""}
                  </Typography.Paragraph>
                  <Flex gap={4} wrap className="mt-2">
                    {(current?.config_schema_json.fields ?? []).map((field) => (
                      <Tooltip
                        key={field.key}
                        title={`${field.type}${field.required ? " · required" : ""}`}
                      >
                        <Tag className="!mr-0">{field.key}</Tag>
                      </Tooltip>
                    ))}
                  </Flex>
                  {canManage && (
                    <div className="mt-3">
                      <Button
                        size="small"
                        onClick={() =>
                          archive.mutate({
                            id: widget.id,
                            status: widget.status === "active" ? "archived" : "active",
                          })
                        }
                      >
                        {widget.status === "active" ? "Archive" : "Restore"}
                      </Button>
                    </div>
                  )}
                </Card>
              </Col>
            );
          })}
        </Row>
      )}

      {createOpen && (
        <CreateWidgetModal
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

interface FieldDraft {
  key: string;
  label: string;
  type: (typeof FIELD_TYPES)[number];
  required: boolean;
  options: string;
}

function CreateWidgetModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form] = Form.useForm<{ name: string; type: string; fallbackText?: string }>();
  const [fields, setFields] = useState<FieldDraft[]>([
    { key: "text", label: "Text", type: "string", required: false, options: "" },
  ]);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (values: { name: string; type: string; fallbackText?: string }) => {
      const schemaFields: WidgetSchemaField[] = fields.map((f) => ({
        key: f.key.trim(),
        label: f.label.trim() || f.key.trim(),
        type: f.type,
        required: f.required,
        ...(f.type === "select"
          ? { options: f.options.split(",").map((o) => o.trim()).filter(Boolean) }
          : {}),
      }));
      return api.post("/widgets", {
        type: values.type,
        name: values.name,
        config_schema_json: { fields: schemaFields },
        fallback_json: values.fallbackText ? { text: values.fallbackText } : null,
      });
    },
    onSuccess: onCreated,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create widget"),
  });

  function setField(index: number, patch: Partial<FieldDraft>) {
    setFields((prev) => prev.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  }

  return (
    <Modal
      title="New widget"
      open
      onCancel={onClose}
      okText="Create widget"
      confirmLoading={create.isPending}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      {error && <Alert type="error" message={error} showIcon role="alert" className="mb-4" />}
      <Form
        form={form}
        layout="vertical"
        initialValues={{ type: "clock" }}
        onFinish={(values) => {
          setError(null);
          create.mutate(values);
        }}
      >
        <Row gutter={12}>
          <Col span={12}>
            <Form.Item
              name="name"
              label="Name"
              rules={[{ required: true, message: "Give the widget a name." }]}
            >
              <Input autoFocus />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="type" label="Type">
              <Input placeholder="clock, weather, ticker…" />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item label="Configuration fields">
          <Space orientation="vertical" size="small" className="w-full">
            {fields.map((field, index) => (
              <Flex key={index} align="center" gap="small" wrap>
                <Input
                  value={field.key}
                  onChange={(e) => setField(index, { key: e.target.value })}
                  placeholder="key"
                  aria-label={`Field ${index + 1} key`}
                  className="w-28 font-mono"
                />
                <Select
                  value={field.type}
                  onChange={(value) => setField(index, { type: value })}
                  aria-label={`Field ${index + 1} type`}
                  options={FIELD_TYPES.map((t) => ({ value: t, label: t }))}
                  className="w-28"
                />
                {field.type === "select" && (
                  <Input
                    value={field.options}
                    onChange={(e) => setField(index, { options: e.target.value })}
                    placeholder="options, comma-separated"
                    aria-label={`Field ${index + 1} options`}
                    className="w-44"
                  />
                )}
                <Checkbox
                  checked={field.required}
                  onChange={(e) => setField(index, { required: e.target.checked })}
                >
                  required
                </Checkbox>
                {fields.length > 1 && (
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    aria-label={`Remove field ${index + 1}`}
                    onClick={() => setFields((prev) => prev.filter((_, i) => i !== index))}
                  />
                )}
              </Flex>
            ))}
            <Button
              type="dashed"
              size="small"
              icon={<PlusOutlined />}
              onClick={() =>
                setFields((prev) => [
                  ...prev,
                  { key: "", label: "", type: "string", required: false, options: "" },
                ])
              }
            >
              Add field
            </Button>
          </Space>
        </Form.Item>

        <Form.Item
          name="fallbackText"
          label="Fallback text (shown when data is unavailable)"
        >
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  );
}
