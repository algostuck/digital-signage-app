import { AppstoreOutlined, PlusOutlined } from "@ant-design/icons";
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
  Row,
  Select,
  Tabs,
  Typography,
} from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FilterBar, PageContainer, SearchBar, statusLabel } from "@/design-system";
import { EmptyState, LoadingState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { AiStudioTab } from "./AiStudioTab";
import { TemplatesTab } from "./TemplatesTab";
import { WidgetsTab } from "./WidgetsTab";
import type { LayoutDetail, LayoutSummary, Template } from "./types";

/** Design studio: SCR-15 layouts + P2-06 templates + P2-08 widgets. */
export function LayoutsPage() {
  const [tab, setTab] = useState<string>("layouts");

  return (
    <PageContainer
        title="Design"
        description="Screen compositions, reusable templates, live widgets and AI-assisted content."
      >
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          { key: "layouts", label: "Layouts", children: <LayoutsTab /> },
          { key: "templates", label: "Templates", children: <TemplatesTab /> },
          { key: "widgets", label: "Widgets", children: <WidgetsTab /> },
          { key: "ai", label: "AI Studio", children: <AiStudioTab /> },
        ]}
      />
    </PageContainer>
  );
}

function LayoutsTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("layouts.manage");
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const layoutsQuery = useQuery({
    queryKey: ["layouts", search, statusFilter],
    queryFn: () =>
      api.get<LayoutSummary[]>(
        `/layouts?page_size=100${search ? `&q=${encodeURIComponent(search)}` : ""}${
          statusFilter ? `&status=${statusFilter}` : ""
        }`,
      ),
  });

  const layouts = layoutsQuery.data?.data ?? [];

  return (
    <Flex vertical gap={16}>
      <FilterBar
        search={<SearchBar value={search} onChange={setSearch} placeholder="Search layouts" label="Search layouts" />}
        activeCount={(search ? 1 : 0) + (statusFilter ? 1 : 0)}
        onReset={() => {
          setSearch("");
          setStatusFilter("");
        }}
        extra={
          canManage && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              New layout
            </Button>
          )
        }
      >
        <Select
          style={{ width: 160 }}
          value={statusFilter}
          aria-label="Filter by status"
          onChange={setStatusFilter}
          options={[
            { value: "", label: "All statuses" },
            { value: "draft", label: statusLabel("draft", "content") },
            { value: "published", label: statusLabel("published", "content") },
          ]}
        />
      </FilterBar>

      {layoutsQuery.isLoading ? (
        <LoadingState rows={4} />
      ) : layouts.length === 0 ? (
        <Card>
          <EmptyState
            title="No layouts yet"
            description="Create one from scratch or from a template."
            action={
              canManage && (
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
                  New layout
                </Button>
              )
            }
          />
        </Card>
      ) : (
        <Row gutter={[12, 12]}>
          {layouts.map((layout) => (
            <Col key={layout.id} xs={24} sm={12} lg={8}>
              <Card
                size="small"
                hoverable
                onClick={() => navigate(`/design/${layout.id}`)}
                tabIndex={0}
                role="button"
                aria-label={`Open layout ${layout.name}`}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") navigate(`/design/${layout.id}`);
                }}
              >
                <Flex justify="space-between" align="flex-start" gap="small">
                  <Typography.Text strong ellipsis>
                    <AppstoreOutlined className="mr-2 text-slate-600 dark:text-slate-400" />
                    {layout.name}
                  </Typography.Text>
                  <StatusBadge status={layout.status} />
                </Flex>
                <Typography.Paragraph type="secondary" className="!mb-0 !mt-1">
                  {layout.zone_count} zone{layout.zone_count === 1 ? "" : "s"}
                  {layout.current_version_no
                    ? ` · v${layout.current_version_no} published`
                    : " · never published"}
                </Typography.Paragraph>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {createOpen && (
        <CreateLayoutModal
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => navigate(`/design/${id}`)}
        />
      )}
    </Flex>
  );
}

function CreateLayoutModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<{ name: string; template_id?: string }>();
  const [error, setError] = useState<string | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["templates"],
    queryFn: () => api.get<Template[]>("/templates"),
  });

  const create = useMutation({
    mutationFn: (values: { name: string; template_id?: string }) =>
      values.template_id
        ? api.post<LayoutDetail>(`/templates/${values.template_id}/clone`, { name: values.name })
        : api.post<LayoutDetail>("/layouts", { name: values.name }),
    onSuccess: (envelope) => {
      queryClient.invalidateQueries({ queryKey: ["layouts"] });
      onCreated(envelope.data!.id);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create layout"),
  });

  return (
    <Modal
      title="New layout"
      open
      onCancel={onClose}
      okText="Create & open designer"
      confirmLoading={create.isPending}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      {error && <Alert type="error" message={error} showIcon className="mb-4" role="alert" />}
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
          rules={[{ required: true, message: "Give the layout a name." }]}
        >
          <Input autoFocus />
        </Form.Item>
        <Form.Item name="template_id" label="Start from">
          <Select
            allowClear
            placeholder="Blank 1920×1080"
            options={(templatesQuery.data?.data ?? []).map((t) => ({
              value: t.id,
              label: `Template: ${t.name}`,
            }))}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
