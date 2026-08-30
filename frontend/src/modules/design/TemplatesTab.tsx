import { PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Flex,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Typography,
} from "antd";
import { useState } from "react";
import { EmptyState, LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo } from "../devices/types";
import type { Template } from "./types";
import { useNavigate } from "react-router-dom";

/** P2-06 Template Library: versions, approval status, reuse. */
export function TemplatesTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("layouts.manage");
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);
  const [cloneSource, setCloneSource] = useState<Template | null>(null);
  const [error, setError] = useState<string | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["templates"],
    queryFn: () => api.get<Template[]>("/templates"),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["templates"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const submit = useMutation({
    mutationFn: (id: string) => api.post(`/templates/${id}/submit`, {}),
    onSuccess: () => {
      refresh();
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      setError(null);
    },
    onError,
  });
  const archive = useMutation({
    mutationFn: (id: string) => api.delete(`/templates/${id}`),
    onSuccess: refresh,
    onError,
  });
  const clone = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      api.post<{ id: string }>(`/templates/${id}/clone`, { name }),
    onSuccess: (envelope) => navigate(`/design/${envelope.data!.id}`),
    onError,
  });

  const templates = (templatesQuery.data?.data ?? []).filter(
    (t) => t.status !== "archived",
  );

  return (
    <div>
      <Flex justify="space-between" align="center" gap="middle" wrap>
        <Typography.Text type="secondary">
          Governed, versioned design assets. Submissions go through the approval inbox.
        </Typography.Text>
        {canManage && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            New template
          </Button>
        )}
      </Flex>

      {error && <Alert type="error" message={error} showIcon role="alert" className="mt-3" />}

      {templatesQuery.isLoading ? (
        <LoadingState rows={5} />
      ) : templates.length === 0 ? (
        <Card className="mt-4">
          <EmptyState
            title="No templates yet"
            description="Create one from scratch, or save a layout as a template from the designer."
          />
        </Card>
      ) : (
        <Row gutter={[12, 12]} className="mt-4">
          {templates.map((template) => (
            <Col key={template.id} xs={24} sm={12} lg={8}>
              <Card size="small">
                <Flex justify="space-between" align="flex-start" gap="small">
                  <Typography.Text strong ellipsis>
                    {template.name}
                  </Typography.Text>
                  <StatusBadge status={template.status} />
                </Flex>
                <Typography.Paragraph type="secondary" className="!mb-0 !mt-1">
                  {template.canvas_json.zones.length} zone
                  {template.canvas_json.zones.length === 1 ? "" : "s"}
                  {template.current_version_no
                    ? ` · v${template.current_version_no} approved`
                    : " · no approved version"}
                  {" · "}updated {timeAgo(template.updated_at)}
                </Typography.Paragraph>
                {template.description && (
                  <Typography.Paragraph type="secondary" className="!mb-0 !mt-1 text-xs">
                    {template.description}
                  </Typography.Paragraph>
                )}
                {canManage && (
                  <Flex gap="small" wrap className="mt-3">
                    {(template.status === "draft" || template.status === "rejected") && (
                      <Button
                        size="small"
                        type="primary"
                        onClick={() => submit.mutate(template.id)}
                      >
                        Submit for approval
                      </Button>
                    )}
                    <Button size="small" onClick={() => setCloneSource(template)}>
                      Use in layout
                    </Button>
                    {template.status !== "pending_approval" && (
                      <Popconfirm
                        title={`Archive template "${template.name}"?`}
                        onConfirm={() => archive.mutate(template.id)}
                        okButtonProps={{ danger: true }}
                      >
                        <Button size="small" danger>
                          Archive
                        </Button>
                      </Popconfirm>
                    )}
                  </Flex>
                )}
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {createOpen && (
        <CreateTemplateModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            refresh();
            setCreateOpen(false);
          }}
        />
      )}

      {cloneSource && (
        <CloneTemplateModal
          template={cloneSource}
          pending={clone.isPending}
          onClose={() => setCloneSource(null)}
          onClone={(name) => clone.mutate({ id: cloneSource.id, name })}
        />
      )}
    </div>
  );
}

/** Replaces the old window.prompt with a controlled modal. */
function CloneTemplateModal({
  template,
  pending,
  onClose,
  onClone,
}: {
  template: Template;
  pending: boolean;
  onClose: () => void;
  onClone: (name: string) => void;
}) {
  const [form] = Form.useForm<{ name: string }>();

  return (
    <Modal
      title="Use template in a layout"
      open
      onCancel={onClose}
      okText="Create layout"
      confirmLoading={pending}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ name: `${template.name} copy` }}
        onFinish={(values) => onClone(values.name)}
      >
        <Form.Item
          name="name"
          label="Name for the new layout cloned from this template"
          rules={[{ required: true, message: "Give the new layout a name." }]}
        >
          <Input autoFocus />
        </Form.Item>
      </Form>
    </Modal>
  );
}

function CreateTemplateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form] = Form.useForm<{ name: string; description?: string }>();
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (values: { name: string; description?: string }) =>
      api.post("/templates", { name: values.name, description: values.description || null }),
    onSuccess: onCreated,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create template"),
  });

  return (
    <Modal
      title="New template"
      open
      onCancel={onClose}
      okText="Create template"
      confirmLoading={create.isPending}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      {error && <Alert type="error" message={error} showIcon role="alert" className="mb-4" />}
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) => {
          setError(null);
          create.mutate(values);
        }}
      >
        <Form.Item
          name="name"
          label="Name"
          rules={[{ required: true, message: "Give the template a name." }]}
        >
          <Input autoFocus />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input />
        </Form.Item>
      </Form>
      <Typography.Text type="secondary" className="text-xs">
        Starts as a blank 1920×1080 draft. You can also save an existing layout as
        a template from the designer.
      </Typography.Text>
    </Modal>
  );
}
